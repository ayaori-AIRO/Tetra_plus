#!/usr/bin/env python3

import json
import math
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool
from std_msgs.msg import Empty
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener


def quaternion_to_yaw(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class RobotPoseServer(Node):
    def __init__(self):
        super().__init__('robot_pose_server')

        self.declare_parameter('host', '0.0.0.0')
        self.declare_parameter('port', 8003)
        self.declare_parameter('map_yaml', '/home/ayaori/ros2_ws/src/tetra/maps/result2.yaml')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('base_frame', 'base_footprint')

        self.host = self.get_parameter('host').value
        self.port = int(self.get_parameter('port').value)
        self.map_yaml = self.get_parameter('map_yaml').value
        self.map_frame = self.get_parameter('map_frame').value
        self.base_frame = self.get_parameter('base_frame').value

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.pose_lock = threading.Lock()
        self.latest_amcl_pose = None
        self.latest_amcl_time = 0.0
        self.map_info = self.load_map_info(self.map_yaml)
        self.map_png = self.load_map_png(self.map_info)
        self.stop_event = threading.Event()
        self.emergency_stop_active = False
        self.emergency_stop_pub = self.create_publisher(
            Bool,
            '/cmd_vel_mux/emergency_stop',
            10,
        )
        self.mission_start_pub = self.create_publisher(Empty, '/mission/start', 10)
        self.mission_start_selected_pub = self.create_publisher(
            String,
            '/mission/start_selected',
            10,
        )
        self.publish_emergency_stop_state()
        self.create_timer(0.1, self.publish_emergency_stop_state)

        self.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self.amcl_pose_callback,
            10,
        )

        self.server = ThreadingHTTPServer(
            (self.host, self.port),
            self.make_handler(),
        )
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()

        self.get_logger().info(
            f'Robot pose server ready: http://{self.host}:{self.port}/pose '
            f'with map {self.map_yaml}'
        )

    def publish_emergency_stop_state(self):
        msg = Bool()
        msg.data = bool(self.emergency_stop_active)
        self.emergency_stop_pub.publish(msg)

    def amcl_pose_callback(self, msg):
        pose = msg.pose.pose
        with self.pose_lock:
            self.latest_amcl_pose = {
                'x': float(pose.position.x),
                'y': float(pose.position.y),
                'yaw': float(quaternion_to_yaw(pose.orientation)),
                'source': '/amcl_pose',
            }
            self.latest_amcl_time = time.time()

    def get_robot_pose(self):
        try:
            transform = self.tf_buffer.lookup_transform(
                self.map_frame,
                self.base_frame,
                rclpy.time.Time(),
                timeout=Duration(seconds=0.05),
            )
            translation = transform.transform.translation
            rotation = transform.transform.rotation
            pose = {
                'x': float(translation.x),
                'y': float(translation.y),
                'yaw': float(quaternion_to_yaw(rotation)),
                'source': f'{self.map_frame}->{self.base_frame}',
            }
            return self.add_map_pixel_position(pose)
        except TransformException:
            pass

        with self.pose_lock:
            if (
                self.latest_amcl_pose is not None
                and time.time() - self.latest_amcl_time < 2.0
            ):
                return self.add_map_pixel_position(dict(self.latest_amcl_pose))

        return {
            'available': False,
            'map': self.public_map_info(),
        }

    def add_map_pixel_position(self, pose):
        image_width = self.map_info['width']
        image_height = self.map_info['height']
        resolution = self.map_info['resolution']
        origin_x = self.map_info['origin'][0]
        origin_y = self.map_info['origin'][1]

        pixel_x = (pose['x'] - origin_x) / resolution
        pixel_y = image_height - ((pose['y'] - origin_y) / resolution)
        percent_x = 100.0 * pixel_x / max(image_width, 1)
        percent_y = 100.0 * pixel_y / max(image_height, 1)

        pose.update({
            'available': True,
            'pixel_x': pixel_x,
            'pixel_y': pixel_y,
            'percent_x': percent_x,
            'percent_y': percent_y,
            'display_percent_x': 100.0 - percent_y,
            'display_percent_y': percent_x,
            'display_yaw': math.pi - (pose.get('yaw') or 0.0),
            'map': self.public_map_info(),
            'stamp': time.time(),
        })
        return pose

    def public_map_info(self):
        return {
            'width': self.map_info['width'],
            'height': self.map_info['height'],
            'resolution': self.map_info['resolution'],
            'origin': self.map_info['origin'],
        }

    def make_handler(self):
        node = self

        class RobotPoseHandler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                self.send_response(204)
                self.send_cors_headers()
                self.end_headers()

            def do_GET(self):
                path = urlparse(self.path).path

                if path == '/':
                    self.send_text(200, 'Robot pose server\n')
                    return

                if path == '/health':
                    pose = node.get_robot_pose()
                    self.send_json({'pose': bool(pose.get('available'))})
                    return

                if path == '/pose':
                    self.send_json(node.get_robot_pose())
                    return

                if path == '/map.png':
                    self.send_bytes('image/png', node.map_png)
                    return

                if path == '/logs/bringup':
                    self.send_json(node.get_bringup_logs())
                    return

                self.send_error(404)

            def do_POST(self):
                path = urlparse(self.path).path
                if path == '/mission/start':
                    length = int(self.headers.get('Content-Length', '0'))
                    body = self.rfile.read(length).decode('utf-8') if length else '{}'
                    try:
                        payload = json.loads(body)
                    except json.JSONDecodeError:
                        self.send_json({'ok': False, 'error': 'invalid json'}, status=400)
                        return

                    waypoint = payload.get('waypoint')
                    if waypoint is None:
                        node.mission_start_pub.publish(Empty())
                        self.send_json({'ok': True, 'mode': 'all'})
                        return

                    try:
                        waypoint = int(waypoint)
                    except (TypeError, ValueError):
                        self.send_json(
                            {'ok': False, 'error': 'waypoint must be 1, 2, or 3'},
                            status=400,
                        )
                        return

                    if waypoint not in (1, 2, 3):
                        self.send_json(
                            {'ok': False, 'error': 'waypoint must be 1, 2, or 3'},
                            status=400,
                        )
                        return

                    msg = String()
                    msg.data = str(waypoint)
                    node.mission_start_selected_pub.publish(msg)
                    self.send_json({'ok': True, 'mode': 'single', 'waypoint': waypoint})
                    return

                if path != '/motor_stop':
                    self.send_error(404)
                    return

                length = int(self.headers.get('Content-Length', '0'))
                body = self.rfile.read(length).decode('utf-8') if length else '{}'
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self.send_json({'ok': False, 'error': 'invalid json'}, status=400)
                    return

                active = bool(payload.get('active'))
                msg = Bool()
                msg.data = active
                node.emergency_stop_active = active
                node.emergency_stop_pub.publish(msg)
                self.send_json({'ok': True, 'active': active})

            def send_json(self, payload, status=200):
                body = json.dumps(payload).encode('utf-8')
                self.send_bytes('application/json; charset=utf-8', body, status=status)

            def send_text(self, status, text):
                body = text.encode('utf-8')
                self.send_response(status)
                self.send_cors_headers()
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(body)

            def send_bytes(self, content_type, body, status=200):
                self.send_response(status)
                self.send_cors_headers()
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(body)

            def send_cors_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')

            def log_message(self, format, *args):
                return

        return RobotPoseHandler

    def get_bringup_logs(self):
        log_dir = '/tmp/tetra_ui_logs'
        groups = self.empty_log_groups()

        if not os.path.isdir(log_dir):
            return {
                'ok': False,
                'log_dir': '',
                'groups': list(groups.values()),
            }

        for group in groups.values():
            file_path = os.path.join(log_dir, group['file'])
            group.pop('file', None)
            if not os.path.isfile(file_path):
                continue

            for line in self.tail_text_lines(file_path):
                clean_line = line.rstrip()
                if not clean_line:
                    continue
                group['lines'].append(clean_line)

        for group in groups.values():
            group['lines'] = group['lines'][-500:]

        return {
            'ok': True,
            'log_dir': log_dir,
            'groups': list(groups.values()),
            'updated_at': time.time(),
        }

    @staticmethod
    def empty_log_groups():
        definitions = [
            ('tetra', 'TETRA / 모터', 'tetra_configuration.log'),
            ('lidar', 'LiDAR', 'lidar.log'),
            ('nav2', 'Nav2 / Localization', 'nav2.log'),
            ('rviz', 'RViz', 'rviz.log'),
            ('realsense', 'RealSense', 'realsense.log'),
            ('apriltag_servo', 'AprilTag Servo', 'apriltag_servo.log'),
        ]
        return {
            group_id: {
                'id': group_id,
                'title': title,
                'file': filename,
                'lines': [],
            }
            for group_id, title, filename in definitions
        }

    @staticmethod
    def tail_text_lines(file_path, max_bytes=350000):
        try:
            file_size = os.path.getsize(file_path)
            with open(file_path, 'rb') as log_file:
                if file_size > max_bytes:
                    log_file.seek(-max_bytes, os.SEEK_END)
                    log_file.readline()
                data = log_file.read()
        except OSError:
            return []

        return data.decode('utf-8', errors='replace').splitlines()

    @staticmethod
    def load_map_info(map_yaml):
        info = {}
        with open(map_yaml, 'r', encoding='utf-8') as map_file:
            for line in map_file:
                if ':' not in line:
                    continue
                key, value = line.split(':', 1)
                info[key.strip()] = value.strip()

        image_path = info['image']
        if not os.path.isabs(image_path):
            image_path = os.path.join(os.path.dirname(map_yaml), image_path)

        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(f'Failed to load map image: {image_path}')

        origin_text = info.get('origin', '[0, 0, 0]').strip('[]')
        origin = [float(part.strip()) for part in origin_text.split(',')]

        return {
            'image_path': image_path,
            'width': int(image.shape[1]),
            'height': int(image.shape[0]),
            'resolution': float(info.get('resolution', '0.05')),
            'origin': origin,
        }

    @staticmethod
    def load_map_png(map_info):
        image = cv2.imread(map_info['image_path'], cv2.IMREAD_GRAYSCALE)
        free_mask = image > 245
        occupied_mask = image < 45

        rendered = np.zeros((image.shape[0], image.shape[1], 3), dtype=np.uint8)
        rendered[:] = (44, 48, 51)
        rendered[occupied_mask] = (10, 15, 19)
        rendered[free_mask] = (230, 248, 242)

        glow = cv2.GaussianBlur(free_mask.astype(np.uint8) * 255, (0, 0), 2.0)
        glow_layer = np.zeros_like(rendered)
        glow_layer[:] = (148, 194, 34)
        alpha = (glow.astype(np.float32) / 255.0 * 0.28)[..., None]
        rendered = (rendered.astype(np.float32) * (1.0 - alpha) + glow_layer.astype(np.float32) * alpha).astype(np.uint8)

        rendered = cv2.rotate(rendered, cv2.ROTATE_90_CLOCKWISE)
        image = rendered
        ok, buffer = cv2.imencode('.png', image)
        if not ok:
            raise RuntimeError('Failed to encode map image as PNG.')
        return buffer.tobytes()

    def destroy_node(self):
        self.stop_event.set()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RobotPoseServer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.remove_node(node)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
