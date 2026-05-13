#!/usr/bin/env python3

# ros2 launch tetra tetra_configuration.launch.py

# ros2 run apriltag_ros apriltag_node --ros-args \
#   -r image_rect:=/camera/camera/color/image_raw \
#   -r camera_info:=/camera/camera/color/camera_info \
#   --params-file $(ros2 pkg prefix apriltag_ros)/share/apriltag_ros/cfg/tags_36h11.yaml

# ros2 launch realsense2_camera rs_launch.py publish_tf:=false

# ros2 run tetra_navigation apriltag_servo --ros-args -p tag_id:=9 -p tag_size:=0.12

import math

import cv2
import numpy as np
import rclpy
from apriltag_msgs.msg import AprilTagDetectionArray
from geometry_msgs.msg import PoseStamped, Twist
from rclpy.duration import Duration
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo
from tf2_ros import Buffer, TransformException, TransformListener


def quaternion_to_matrix(q):
    x = q.x
    y = q.y
    z = q.z
    w = q.w

    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z

    return np.array([
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
        [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
        [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
    ])


def rotation_vector_to_quaternion(rvec):
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    trace = float(np.trace(rotation_matrix))

    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * scale
        x = (rotation_matrix[2, 1] - rotation_matrix[1, 2]) / scale
        y = (rotation_matrix[0, 2] - rotation_matrix[2, 0]) / scale
        z = (rotation_matrix[1, 0] - rotation_matrix[0, 1]) / scale
    else:
        diagonal = np.diag(rotation_matrix)
        index = int(np.argmax(diagonal))
        if index == 0:
            scale = math.sqrt(1.0 + rotation_matrix[0, 0] - rotation_matrix[1, 1] - rotation_matrix[2, 2]) * 2.0
            w = (rotation_matrix[2, 1] - rotation_matrix[1, 2]) / scale
            x = 0.25 * scale
            y = (rotation_matrix[0, 1] + rotation_matrix[1, 0]) / scale
            z = (rotation_matrix[0, 2] + rotation_matrix[2, 0]) / scale
        elif index == 1:
            scale = math.sqrt(1.0 + rotation_matrix[1, 1] - rotation_matrix[0, 0] - rotation_matrix[2, 2]) * 2.0
            w = (rotation_matrix[0, 2] - rotation_matrix[2, 0]) / scale
            x = (rotation_matrix[0, 1] + rotation_matrix[1, 0]) / scale
            y = 0.25 * scale
            z = (rotation_matrix[1, 2] + rotation_matrix[2, 1]) / scale
        else:
            scale = math.sqrt(1.0 + rotation_matrix[2, 2] - rotation_matrix[0, 0] - rotation_matrix[1, 1]) * 2.0
            w = (rotation_matrix[1, 0] - rotation_matrix[0, 1]) / scale
            x = (rotation_matrix[0, 2] + rotation_matrix[2, 0]) / scale
            y = (rotation_matrix[1, 2] + rotation_matrix[2, 1]) / scale
            z = 0.25 * scale

    return x, y, z, w


class AprilTagServo(Node):
    def __init__(self):
        super().__init__('apriltag_servo')

        self.declare_parameter('tag_id', 9)
        self.declare_parameter('tag_size', 0.12)
        self.declare_parameter('target_distance', 0.13)
        self.declare_parameter('distance_tolerance', 0.02)
        self.declare_parameter('lateral_tolerance', 0.015)
        self.declare_parameter('linear_gain', 0.25)
        self.declare_parameter('angular_gain', 0.8)
        self.declare_parameter('max_linear_speed', 0.05)
        self.declare_parameter('max_angular_speed', 0.20)
        self.declare_parameter('angular_sign', -1.0)
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('camera_frame', 'camera_color_optical_frame')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('detections_topic', '/detections')
        self.declare_parameter('camera_info_topic', '/camera/camera/color/camera_info')
        self.declare_parameter('tag_timeout', 0.5)
        self.declare_parameter('stop_after_reached', False)

        self.tag_id = int(self.get_parameter('tag_id').value)
        self.tag_size = float(self.get_parameter('tag_size').value)
        self.target_distance = float(self.get_parameter('target_distance').value)
        self.distance_tolerance = float(self.get_parameter('distance_tolerance').value)
        self.lateral_tolerance = float(self.get_parameter('lateral_tolerance').value)
        self.linear_gain = float(self.get_parameter('linear_gain').value)
        self.angular_gain = float(self.get_parameter('angular_gain').value)
        self.max_linear_speed = float(self.get_parameter('max_linear_speed').value)
        self.max_angular_speed = float(self.get_parameter('max_angular_speed').value)
        self.angular_sign = float(self.get_parameter('angular_sign').value)
        self.base_frame = self.get_parameter('base_frame').value
        self.camera_frame = self.get_parameter('camera_frame').value
        self.tag_timeout = float(self.get_parameter('tag_timeout').value)
        self.stop_after_reached = bool(self.get_parameter('stop_after_reached').value)

        self.camera_matrix = None
        self.dist_coeffs = None
        self.last_detection_time = None
        self.last_cmd_was_stop = True
        self.should_exit = False

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.cmd_pub = self.create_publisher(
            Twist,
            self.get_parameter('cmd_vel_topic').value,
            10
        )
        self.pose_camera_pub = self.create_publisher(PoseStamped, 'apriltag/pose_camera', 10)
        self.pose_base_pub = self.create_publisher(PoseStamped, 'apriltag/pose_base', 10)

        self.create_subscription(
            CameraInfo,
            self.get_parameter('camera_info_topic').value,
            self.camera_info_callback,
            10
        )
        self.create_subscription(
            AprilTagDetectionArray,
            self.get_parameter('detections_topic').value,
            self.detection_callback,
            10
        )

        self.create_timer(0.1, self.timeout_callback)

        self.get_logger().info(
            f'AprilTag servo ready: tag_id={self.tag_id}, tag_size={self.tag_size:.3f} m'
        )

    def camera_info_callback(self, msg):
        self.camera_matrix = np.array(msg.k, dtype=np.float64).reshape((3, 3))
        self.dist_coeffs = np.array(msg.d, dtype=np.float64)

    def detection_callback(self, msg):
        if self.camera_matrix is None or self.dist_coeffs is None:
            self.get_logger().warn('Waiting for camera_info before solving AprilTag pose.', throttle_duration_sec=2.0)
            return

        detection = self.select_detection(msg)
        if detection is None:
            return

        pose_camera = self.solve_tag_pose(detection, msg.header)
        if pose_camera is None:
            return

        self.last_detection_time = self.get_clock().now()
        self.pose_camera_pub.publish(pose_camera)

        pose_base = self.transform_pose_to_base(pose_camera)
        if pose_base is not None:
            self.pose_base_pub.publish(pose_base)

        self.publish_servo_command(pose_camera)

    def select_detection(self, msg):
        for detection in msg.detections:
            if int(detection.id) == self.tag_id:
                return detection

        if msg.detections:
            ids = ', '.join(str(d.id) for d in msg.detections)
            self.get_logger().debug(f'Ignoring tag ids [{ids}], waiting for id {self.tag_id}.')
        return None

    def solve_tag_pose(self, detection, header):
        half = self.tag_size / 2.0
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

        success, rvec, tvec = cv2.solvePnP(
            object_points,
            image_points,
            self.camera_matrix,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        if not success:
            self.get_logger().warn('cv2.solvePnP failed for AprilTag detection.')
            return None

        pose = PoseStamped()
        pose.header.stamp = header.stamp
        pose.header.frame_id = header.frame_id or self.camera_frame
        pose.pose.position.x = float(tvec[0][0])
        pose.pose.position.y = float(tvec[1][0])
        pose.pose.position.z = float(tvec[2][0])

        qx, qy, qz, qw = rotation_vector_to_quaternion(rvec)
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        return pose

    def transform_pose_to_base(self, pose_camera):
        try:
            transform = self.tf_buffer.lookup_transform(
                self.base_frame,
                pose_camera.header.frame_id,
                rclpy.time.Time(),
                timeout=Duration(seconds=0.05)
            )
        except TransformException as exc:
            self.get_logger().warn(f'Cannot transform tag pose to {self.base_frame}: {exc}', throttle_duration_sec=2.0)
            return None

        translation = transform.transform.translation
        rotation = quaternion_to_matrix(transform.transform.rotation)
        point_camera = np.array([
            pose_camera.pose.position.x,
            pose_camera.pose.position.y,
            pose_camera.pose.position.z,
        ])
        point_base = rotation @ point_camera + np.array([translation.x, translation.y, translation.z])

        pose_base = PoseStamped()
        pose_base.header.stamp = pose_camera.header.stamp
        pose_base.header.frame_id = self.base_frame
        pose_base.pose.position.x = float(point_base[0])
        pose_base.pose.position.y = float(point_base[1])
        pose_base.pose.position.z = float(point_base[2])
        pose_base.pose.orientation = pose_camera.pose.orientation
        return pose_base

    def publish_servo_command(self, pose_camera):
        lateral_error = pose_camera.pose.position.x
        distance_error = pose_camera.pose.position.z - self.target_distance

        cmd = Twist()

        if abs(lateral_error) > self.lateral_tolerance:
            angular = self.angular_sign * self.angular_gain * lateral_error
            cmd.angular.z = self.clamp(angular, -self.max_angular_speed, self.max_angular_speed)

        if abs(distance_error) > self.distance_tolerance:
            linear = -self.linear_gain * distance_error
            cmd.linear.x = self.clamp(linear, -self.max_linear_speed, self.max_linear_speed)

        if cmd.linear.x == 0.0 and cmd.angular.z == 0.0:
            self.publish_stop_once()
            self.get_logger().info('AprilTag servo target reached.', throttle_duration_sec=1.0)
            if self.stop_after_reached:
                self.should_exit = True
            return

        self.cmd_pub.publish(cmd)
        self.last_cmd_was_stop = False
        self.get_logger().info(
            'tag camera pose: '
            f'x={pose_camera.pose.position.x:.3f}, '
            f'y={pose_camera.pose.position.y:.3f}, '
            f'z={pose_camera.pose.position.z:.3f}, '
            f'cmd linear.x={cmd.linear.x:.3f}, angular.z={cmd.angular.z:.3f}',
            throttle_duration_sec=0.5
        )

    def timeout_callback(self):
        if self.last_detection_time is None:
            return

        elapsed = self.get_clock().now() - self.last_detection_time
        if elapsed.nanoseconds > self.tag_timeout * 1e9:
            self.publish_stop_once()

    def publish_stop_once(self):
        if self.last_cmd_was_stop:
            return
        self.cmd_pub.publish(Twist())
        self.last_cmd_was_stop = True

    @staticmethod
    def clamp(value, lower, upper):
        return max(lower, min(upper, value))


def main(args=None):
    rclpy.init(args=args)
    node = AprilTagServo()
    try:
        while rclpy.ok() and not node.should_exit:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        if rclpy.ok():
            node.cmd_pub.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
