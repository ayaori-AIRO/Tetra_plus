#!/usr/bin/env python3

import json
import os
import subprocess
import time
import urllib.error

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Point
from nav2_msgs.action import DriveOnHeading
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor

from tetra_navigation.mission_manager import MissionManager


class MissionManagerProto(MissionManager):
    def __init__(self):
        super().__init__()
        self.declare_parameter('forward_after_inspection', True)
        self.declare_parameter('forward_distance', 0.13)
        self.declare_parameter('forward_speed', 0.03)
        self.declare_parameter('forward_time_allowance_sec', 10.0)

        self.forward_after_inspection = bool(
            self.get_parameter('forward_after_inspection').value
        )
        self.forward_distance = float(self.get_parameter('forward_distance').value)
        self.forward_speed = float(self.get_parameter('forward_speed').value)
        self.forward_time_allowance_sec = float(
            self.get_parameter('forward_time_allowance_sec').value
        )
        self.drive_on_heading_client = ActionClient(
            self,
            DriveOnHeading,
            'drive_on_heading',
        )
        self.get_logger().info(
            'Mission manager proto mode: front-only inspection, no ST3235/ball screw.'
        )

    def run_inspection_sequence(self):
        self.turn_on_internal_led()

        if not self.start_object_detection():
            return

        if not self.wait_for_object_detection_ready():
            self.stop_object_detection()
            return

        if not self.set_object_detection_extinguisher_id():
            self.stop_object_detection()
            return

        if not self.wait_for_react_monitoring_ready():
            self.stop_object_detection()
            return

        if not self.reset_object_detection_capture(1):
            self.stop_object_detection()
            return

        if not self.wait_for_front_capture():
            self.stop_object_detection()
            return

        pipeline_ok = self.run_inspection_pipeline()
        self.stop_object_detection()

        if not pipeline_ok:
            return

        if self.forward_after_inspection:
            self.drive_forward_after_inspection()

    def wait_for_front_capture(self):
        deadline = time.time() + self.object_detection_capture_timeout_sec
        self.get_logger().info(
            'Waiting for front capture: fire_extinguisher, label, pressure_gauge.'
        )

        while time.time() < deadline:
            if (
                self.object_detection_process is not None
                and self.object_detection_process.poll() is not None
            ):
                self.get_logger().error(
                    'Object detection exited before front capture completed.'
                )
                return False

            try:
                status, capture = self.read_object_detection_json('/capture/status')
                if status == 200 and capture.get('all_targets'):
                    self.get_logger().info(
                        'Front capture completed: '
                        f'fire_extinguisher={capture.get("fire_extinguisher")}, '
                        f'label={capture.get("label")}, '
                        f'pressure_gauge={capture.get("pressure_gauge")}'
                    )
                    return True

                self.get_logger().info(
                    'Waiting for front targets: '
                    f'fire_extinguisher={capture.get("fire_extinguisher")}, '
                    f'label={capture.get("label")}, '
                    f'pressure_gauge={capture.get("pressure_gauge")}',
                    throttle_duration_sec=1.0,
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                pass

            time.sleep(0.5)

        self.get_logger().error('Timed out waiting for front all_targets capture.')
        return False

    def run_inspection_pipeline(self):
        if not os.path.exists(self.inspection_pipeline_script):
            self.get_logger().error(
                f'Inspection pipeline script not found: {self.inspection_pipeline_script}'
            )
            return False

        extinguisher_id = f'id{self.normalize_extinguisher_id(self.current_extinguisher_id)}'
        self.get_logger().info(
            f'Running front-only inspection pipeline for {extinguisher_id}.'
        )
        completed = subprocess.run(
            [
                'python3',
                self.inspection_pipeline_script,
                '--ids',
                extinguisher_id,
                '--corrosion-side-count',
                '1',
            ],
            capture_output=True,
            text=True,
            timeout=180.0,
            check=False,
        )

        if completed.stdout:
            for line in completed.stdout.splitlines():
                self.get_logger().info(f'inspection_pipeline: {line}')

        if completed.stderr:
            for line in completed.stderr.splitlines():
                self.get_logger().warn(f'inspection_pipeline stderr: {line}')

        if completed.returncode != 0:
            self.get_logger().error(
                f'Inspection pipeline failed: returncode={completed.returncode}'
            )
            return False

        self.get_logger().info('Front-only inspection pipeline finished.')
        return True

    def drive_forward_after_inspection(self):
        self.get_logger().info(
            'Driving forward after inspection: '
            f'distance={self.forward_distance:.3f} m, '
            f'speed={self.forward_speed:.3f} m/s'
        )

        if not self.drive_on_heading_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('drive_on_heading action server is not available.')
            return False

        goal = DriveOnHeading.Goal()
        goal.target = Point(x=self.forward_distance, y=0.0, z=0.0)
        goal.speed = self.forward_speed
        goal.time_allowance = Duration(
            seconds=self.forward_time_allowance_sec
        ).to_msg()

        self.select_cmd_vel_source('nav')
        send_future = self.drive_on_heading_client.send_goal_async(goal)
        while rclpy.ok() and not send_future.done():
            time.sleep(0.05)

        if not rclpy.ok():
            self.select_cmd_vel_source('stop')
            return False

        goal_handle = send_future.result()
        if not goal_handle.accepted:
            self.select_cmd_vel_source('stop')
            self.get_logger().error('drive_on_heading goal was rejected.')
            return False

        result_future = goal_handle.get_result_async()
        while rclpy.ok() and not result_future.done():
            time.sleep(0.05)

        self.select_cmd_vel_source('stop')
        if not rclpy.ok():
            return False

        status = result_future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info('Forward drive after inspection succeeded.')
            return True

        self.get_logger().error(
            f'Forward drive after inspection failed: status={status}'
        )
        return False


def main(args=None):
    rclpy.init(args=args)
    node = MissionManagerProto()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.stop_object_detection()
        executor.remove_node(node)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
