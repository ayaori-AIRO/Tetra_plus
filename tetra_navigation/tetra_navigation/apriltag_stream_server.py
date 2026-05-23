#!/usr/bin/env python3

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import cv2
import numpy as np
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import Image


class AprilTagStreamServer(Node):
    def __init__(self):
        super().__init__('apriltag_stream_server')

        self.declare_parameter('image_topic', '/apriltag/annotated_image')
        self.declare_parameter('host', '0.0.0.0')
        self.declare_parameter('port', 8001)
        self.declare_parameter('stream_fps', 12.0)
        self.declare_parameter('jpeg_quality', 80)

        self.image_topic = self.get_parameter('image_topic').value
        self.host = self.get_parameter('host').value
        self.port = int(self.get_parameter('port').value)
        self.stream_fps = float(self.get_parameter('stream_fps').value)
        self.jpeg_quality = int(self.get_parameter('jpeg_quality').value)

        self.frame_lock = threading.Lock()
        self.latest_jpeg = None
        self.latest_frame_time = 0.0
        self.stop_event = threading.Event()
        self.server = ThreadingHTTPServer(
            (self.host, self.port),
            self.make_handler(),
        )
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

        self.create_subscription(Image, self.image_topic, self.image_callback, 10)
        self.server_thread.start()
        self.get_logger().info(
            f'AprilTag stream server ready: '
            f'http://{self.host}:{self.port}/video/apriltag '
            f'from {self.image_topic}'
        )

    def image_callback(self, msg):
        frame = self.image_to_bgr(msg)
        if frame is None:
            return

        ok, buffer = cv2.imencode(
            '.jpg',
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
        )
        if not ok:
            return

        with self.frame_lock:
            self.latest_jpeg = buffer.tobytes()
            self.latest_frame_time = time.time()

    def image_to_bgr(self, msg):
        try:
            if msg.encoding == 'bgr8':
                frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (msg.height, msg.width, 3)
                )
                return frame.copy()

            if msg.encoding == 'rgb8':
                frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (msg.height, msg.width, 3)
                )
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            if msg.encoding in ('mono8', '8UC1'):
                frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (msg.height, msg.width)
                )
                return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        except ValueError as exc:
            self.get_logger().warn(f'Failed to convert image: {exc}')
            return None

        self.get_logger().warn(
            f'Unsupported image encoding for AprilTag stream: {msg.encoding}',
            throttle_duration_sec=2.0,
        )
        return None

    def get_latest_jpeg(self):
        with self.frame_lock:
            return self.latest_jpeg

    def is_stream_healthy(self):
        with self.frame_lock:
            return (
                self.latest_jpeg is not None
                and time.time() - self.latest_frame_time < 2.0
            )

    def make_handler(self):
        node = self

        class AprilTagStreamHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlparse(self.path).path

                if path == '/':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(b'AprilTag stream server\n')
                    return

                if path == '/health':
                    body = json.dumps({
                        'apriltag': node.is_stream_healthy(),
                    }).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if path == '/video/apriltag':
                    self.stream_apriltag()
                    return

                self.send_error(404)

            def stream_apriltag(self):
                self.send_response(200)
                self.send_header('Age', '0')
                self.send_header('Cache-Control', 'no-cache, private')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header(
                    'Content-Type',
                    'multipart/x-mixed-replace; boundary=frame',
                )
                self.end_headers()

                frame_interval = 1.0 / max(node.stream_fps, 0.1)
                try:
                    while not node.stop_event.is_set():
                        jpg = node.get_latest_jpeg()
                        if jpg is None:
                            time.sleep(0.1)
                            continue

                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n')
                        self.wfile.write(
                            f'Content-Length: {len(jpg)}\r\n\r\n'.encode('ascii')
                        )
                        self.wfile.write(jpg)
                        self.wfile.write(b'\r\n')
                        time.sleep(frame_interval)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format, *args):
                return

        return AprilTagStreamHandler

    def destroy_node(self):
        self.stop_event.set()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = AprilTagStreamServer()
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
