#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from apriltag_msgs.msg import AprilTagDetectionArray

import numpy as np
import cv2


class AprilTagVisualizer(Node):
    def __init__(self):
        super().__init__('apriltag_visualizer')

        self.latest_detections = None

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

        self.image_pub = self.create_publisher(
            Image,
            '/apriltag/annotated_image',
            10
        )

    def detection_callback(self, msg):
        self.latest_detections = msg

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

        out_msg = Image()
        out_msg.header = msg.header
        out_msg.height = frame.shape[0]
        out_msg.width = frame.shape[1]
        out_msg.encoding = 'bgr8'
        out_msg.is_bigendian = 0
        out_msg.step = frame.shape[1] * 3
        out_msg.data = frame.tobytes()

        self.image_pub.publish(out_msg)


def main(args=None):
    rclpy.init(args=args)
    node = AprilTagVisualizer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()