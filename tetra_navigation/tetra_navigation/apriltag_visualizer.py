#!/usr/bin/env python3

# ros2 launch realsense2_camera rs_launch.py

# ros2 run apriltag_ros apriltag_node --ros-args \
# -r image_rect:=/camera/camera/color/image_raw \
# -r camera_info:=/camera/camera/color/camera_info \
# --params-file $(ros2 pkg prefix apriltag_ros)/share/apriltag_ros/cfg/tags_36h11.yaml

# ros2 run tetra_navigation apriltag_visualizer

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import CameraInfo, Image
from apriltag_msgs.msg import AprilTagDetectionArray

import numpy as np
import cv2


class AprilTagVisualizer(Node):
    def __init__(self):
        super().__init__('apriltag_visualizer')

        self.declare_parameter('far_tag_size', 0.10)
        self.declare_parameter('mid_tag_size', 0.05)
        self.declare_parameter('near_tag_size', 0.01)
        self.declare_parameter('camera_info_topic', '/camera/camera/color/camera_info')

        self.latest_detections = None
        self.camera_matrix = None
        self.dist_coeffs = None
        self.far_tag_size = float(self.get_parameter('far_tag_size').value)
        self.mid_tag_size = float(self.get_parameter('mid_tag_size').value)
        self.near_tag_size = float(self.get_parameter('near_tag_size').value)

        self.image_sub = self.create_subscription(
            Image,
            '/camera/camera/color/image_raw',
            self.image_callback,
            10
        )

        self.det_sub = self.create_subscription(
            AprilTagDetectionArray,
            '/detections',
            self.detection_callback,
            10
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            self.get_parameter('camera_info_topic').value,
            self.camera_info_callback,
            10
        )

        self.image_pub = self.create_publisher(
            Image,
            '/apriltag/annotated_image',
            10
        )

    def detection_callback(self, msg):
        self.latest_detections = msg

    def camera_info_callback(self, msg):
        self.camera_matrix = np.array(msg.k, dtype=np.float64).reshape((3, 3))
        self.dist_coeffs = np.array(msg.d, dtype=np.float64)

    def image_callback(self, msg):
        frame = np.frombuffer(msg.data, dtype=np.uint8)

        if msg.encoding == 'rgb8':
            frame = frame.reshape((msg.height, msg.width, 3))
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif msg.encoding == 'bgr8':
            frame = frame.reshape((msg.height, msg.width, 3))
        else:
            self.get_logger().warn(f"Unsupported encoding: {msg.encoding}")
            return

        frame = frame.copy()

        if self.latest_detections is not None:
            for det in self.latest_detections.detections:
                pts = [(int(p.x), int(p.y)) for p in det.corners]

                for i in range(4):
                    cv2.line(frame, pts[i], pts[(i + 1) % 4], (0, 255, 0), 2)

                cx = int(det.centre.x)
                cy = int(det.centre.y)
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

                text = f"ID {det.id}"
                cv2.putText(frame, text, (pts[0][0], pts[0][1] - 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

                coord_text = f"x={cx}, y={cy}"
                cv2.putText(frame, coord_text, (pts[0][0], pts[0][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

                distance = self.estimate_distance(det)
                if distance is not None:
                    distance_text = f"camera-QR: {distance:.3f} m"
                else:
                    distance_text = "camera-QR: n/a"
                cv2.putText(frame, distance_text, (pts[0][0], pts[0][1] + 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        out_msg = Image()
        out_msg.header = msg.header
        out_msg.height = frame.shape[0]
        out_msg.width = frame.shape[1]
        out_msg.encoding = 'bgr8'
        out_msg.is_bigendian = 0
        out_msg.step = frame.shape[1] * 3
        out_msg.data = frame.tobytes()

        self.image_pub.publish(out_msg)

    def estimate_distance(self, detection):
        if self.camera_matrix is None or self.dist_coeffs is None:
            return None

        tag_size = self.tag_size_for_id(int(detection.id))
        half = tag_size / 2.0
        object_points = np.array([
            [-half, half, 0.0],
            [half, half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=np.float64)
        image_points = np.array(
            [[corner.x, corner.y] for corner in detection.corners],
            dtype=np.float64
        )

        success, _, tvec = cv2.solvePnP(
            object_points,
            image_points,
            self.camera_matrix,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        if not success:
            return None

        return float(tvec[2][0])

    def tag_size_for_id(self, tag_id):
        if tag_id == 10:
            return self.far_tag_size
        if tag_id == 9:
            return self.mid_tag_size
        return self.near_tag_size


def main(args=None):
    rclpy.init(args=args)
    node = AprilTagVisualizer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
