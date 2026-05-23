#!/usr/bin/env python3

import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import json

from geometry_msgs.msg import PoseStamped
import rclpy
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
from tetra_msgs.action import DockToTag


class MissionManager(Node):
    def __init__(self):
        super().__init__('mission_manager')
        self.declare_parameter('autostart', False)
        self.declare_parameter('start_docking_after_nav_active', False)
        self.declare_parameter('dock_after_waypoint', True)
        self.declare_parameter(
            'object_detection_script',
            '/home/ayaori/ros2_ws/src/tetra/Inspection/project/Object_Detection_Live.py',
        )
        self.declare_parameter(
            'neopixel_controller_script',
            '/home/ayaori/ros2_ws/src/tetra/Inspection/project/neopixel_controller.py',
        )
        self.declare_parameter(
            'motor_controller_script',
            '/home/ayaori/ros2_ws/src/tetra/Inspection/project/motor_controller.py',
        )
        self.declare_parameter('start_object_detection_after_docking', True)
        self.declare_parameter('object_detection_health_url', 'http://127.0.0.1:8000/health')
        self.declare_parameter('object_detection_ready_timeout_sec', 15.0)
        self.declare_parameter('object_detection_viewer_timeout_sec', 30.0)
        self.declare_parameter('inspection_duration_sec', 30.0)
        self.autostart = bool(self.get_parameter('autostart').value)
        self.start_docking_after_nav_active = bool(
            self.get_parameter('start_docking_after_nav_active').value
        )
        self.dock_after_waypoint = bool(self.get_parameter('dock_after_waypoint').value)
        self.object_detection_script = str(
            self.get_parameter('object_detection_script').value
        )
        self.neopixel_controller_script = str(
            self.get_parameter('neopixel_controller_script').value
        )
        self.motor_controller_script = str(
            self.get_parameter('motor_controller_script').value
        )
        self.start_object_detection_after_docking = bool(
            self.get_parameter('start_object_detection_after_docking').value
        )
        self.object_detection_health_url = str(
            self.get_parameter('object_detection_health_url').value
        )
        self.object_detection_ready_timeout_sec = float(
            self.get_parameter('object_detection_ready_timeout_sec').value
        )
        self.object_detection_viewer_timeout_sec = float(
            self.get_parameter('object_detection_viewer_timeout_sec').value
        )
        self.inspection_duration_sec = float(
            self.get_parameter('inspection_duration_sec').value
        )
        self.navigator = BasicNavigator()
        self.dock_client = ActionClient(self, DockToTag, 'dock_to_tag')
        self.cmd_vel_select_pub = self.create_publisher(String, '/cmd_vel_mux/select', 10)
        self.start_timer = None
        self.mission_thread = None
        self.object_detection_process = None

        if self.autostart:
            self.get_logger().info('Mission manager autostart is enabled.')
            self.start_timer = self.create_timer(1.0, self.start_mission)
        else:
            self.get_logger().info('Mission manager ready. Autostart is disabled.')

    def start_mission(self):
        if self.start_timer is not None:
            self.start_timer.cancel()

        if self.mission_thread is not None and self.mission_thread.is_alive():
            self.get_logger().warn('Mission is already running.')
            return

        self.mission_thread = threading.Thread(target=self.run_mission, daemon=True)
        self.mission_thread.start()

    def run_mission(self):
        self.get_logger().info('Waiting for Nav2 to become active...')
        self.navigator.waitUntilNav2Active()
        self.get_logger().info('Nav2 is active. Mission sequence can continue.')
        self.select_cmd_vel_source('nav')

        if self.start_docking_after_nav_active:
            self.start_docking()
            return

        if self.navigate_to_fire_extinguisher():
            if self.dock_after_waypoint:
                time.sleep(1.0)
                self.start_docking()
            else:
                self.get_logger().info('Waypoint reached. Docking is disabled.')

    def navigate_to_fire_extinguisher(self):
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = 'map'
        goal_pose.header.stamp = self.navigator.get_clock().now().to_msg()
        goal_pose.pose.position.x = 17.651343391534965
        goal_pose.pose.position.y = 3.061480262290648
        goal_pose.pose.orientation.z = 0.9999773599247862
        goal_pose.pose.orientation.w = 0.006729014627305277

        self.get_logger().info('Navigating to fire extinguisher waypoint.')
        self.navigator.goToPose(goal_pose)

        while not self.navigator.isTaskComplete():
            feedback = self.navigator.getFeedback()
            if feedback is not None:
                self.get_logger().info(
                    f'Navigation distance remaining: {feedback.distance_remaining:.2f} m',
                    throttle_duration_sec=1.0,
                )
            time.sleep(0.1)

        result = self.navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            self.get_logger().info('Arrived at fire extinguisher waypoint.')
            return True

        if result == TaskResult.CANCELED:
            self.get_logger().warn('Navigation goal was canceled.')
        elif result == TaskResult.FAILED:
            self.get_logger().error('Navigation goal failed.')
        else:
            self.get_logger().error(f'Navigation ended with unknown result: {result}')

        return False

    def start_docking(self):
        self.get_logger().info('Waiting for dock_to_tag action server...')
        if not self.dock_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('dock_to_tag action server is not available.')
            return

        goal = DockToTag.Goal()
        goal.tag_id = 10
        goal.tag_size = 0.10
        goal.target_distance = 0.4
        goal.mid_tag_id = 9
        goal.mid_tag_size = 0.05
        goal.mid_target_distance = 0.2
        goal.near_tag_id = 1
        goal.near_tag_size = 0.01
        goal.near_target_distance = 0.03
        goal.switch_distance = 0.45
        goal.near_switch_distance = 0.25
        goal.timeout_sec = 60.0

        self.select_cmd_vel_source('servo')
        self.get_logger().info('Sending dock_to_tag goal.')
        send_future = self.dock_client.send_goal_async(
            goal,
            feedback_callback=self.docking_feedback_callback,
        )
        send_future.add_done_callback(self.docking_goal_response_callback)

    def docking_goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('dock_to_tag goal was rejected.')
            return

        self.get_logger().info('dock_to_tag goal accepted.')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.docking_result_callback)

    def docking_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(
            'dock_to_tag feedback: '
            f'state={feedback.state}, tag={feedback.active_tag_id}, '
            f'distance={feedback.current_distance:.3f} m, '
            f'lateral={feedback.lateral_error:.3f} m',
            throttle_duration_sec=0.5,
        )

    def docking_result_callback(self, future):
        result = future.result().result
        self.select_cmd_vel_source('stop')
        if result.success:
            self.get_logger().info(
                'dock_to_tag succeeded: '
                f'reason={result.reason}, '
                f'final_distance={result.final_distance:.3f} m, '
                f'final_lateral={result.final_lateral_error:.3f} m'
            )
            if self.start_object_detection_after_docking:
                threading.Thread(target=self.run_inspection_sequence, daemon=True).start()
        else:
            self.get_logger().error(
                'dock_to_tag failed: '
                f'reason={result.reason}, '
                f'final_distance={result.final_distance:.3f} m, '
                f'final_lateral={result.final_lateral_error:.3f} m'
            )

    def select_cmd_vel_source(self, source):
        msg = String()
        msg.data = source
        self.cmd_vel_select_pub.publish(msg)
        self.get_logger().info(f'Selected cmd_vel source: {source}')

    def run_inspection_sequence(self):
        self.turn_on_internal_led()

        if not self.start_object_detection():
            return

        if not self.wait_for_object_detection_ready():
            self.stop_object_detection()
            return

        if not self.wait_for_react_monitoring_ready():
            self.stop_object_detection()
            return

        if not self.move_ballscrew_down():
            self.stop_object_detection()
            return

        self.get_logger().info(
            'Object detection is ready. Inspection placeholder is running.'
        )
        if self.inspection_duration_sec > 0.0:
            time.sleep(self.inspection_duration_sec)
            self.get_logger().info('Inspection placeholder finished.')
            self.stop_object_detection()
        else:
            self.get_logger().info(
                'inspection_duration_sec <= 0. Object detection will stay running.'
            )

    def turn_on_internal_led(self):
        if not os.path.exists(self.neopixel_controller_script):
            self.get_logger().error(
                f'NeoPixel controller script not found: {self.neopixel_controller_script}'
            )
            return False

        self.get_logger().info('Turning on inspection internal NeoPixel LED.')
        completed = subprocess.run(
            ['python3', self.neopixel_controller_script, 'internal'],
            capture_output=True,
            text=True,
            timeout=8.0,
            check=False,
        )

        if completed.stdout:
            for line in completed.stdout.splitlines():
                self.get_logger().info(f'neopixel: {line}')

        if completed.stderr:
            for line in completed.stderr.splitlines():
                self.get_logger().warn(f'neopixel stderr: {line}')

        if completed.returncode != 0:
            self.get_logger().error(
                f'NeoPixel internal LED command failed: returncode={completed.returncode}'
            )
            return False

        return True

    def move_ballscrew_down(self):
        if not os.path.exists(self.motor_controller_script):
            self.get_logger().error(
                f'Motor controller script not found: {self.motor_controller_script}'
            )
            return False

        self.get_logger().info('Moving ball screw down for inspection.')
        completed = subprocess.run(
            ['python3', self.motor_controller_script, 'down'],
            capture_output=True,
            text=True,
            timeout=20.0,
            check=False,
        )

        if completed.stdout:
            for line in completed.stdout.splitlines():
                self.get_logger().info(f'motor: {line}')

        if completed.stderr:
            for line in completed.stderr.splitlines():
                self.get_logger().warn(f'motor stderr: {line}')

        if completed.returncode != 0:
            self.get_logger().error(
                f'Ball screw down command failed: returncode={completed.returncode}'
            )
            return False

        return True

    def start_object_detection(self):
        if self.object_detection_process is not None:
            if self.object_detection_process.poll() is None:
                self.get_logger().warn('Object detection is already running.')
                return True
            self.object_detection_process = None

        if not os.path.exists(self.object_detection_script):
            self.get_logger().error(
                f'Object detection script not found: {self.object_detection_script}'
            )
            return False

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        self.get_logger().info(
            f'Starting object detection: {self.object_detection_script}'
        )
        self.object_detection_process = subprocess.Popen(
            ['python3', '-u', self.object_detection_script],
            env=env,
        )
        return True

    def wait_for_object_detection_ready(self):
        deadline = time.time() + self.object_detection_ready_timeout_sec
        while time.time() < deadline:
            if (
                self.object_detection_process is not None
                and self.object_detection_process.poll() is not None
            ):
                self.get_logger().error(
                    'Object detection exited before becoming ready.'
                )
                return False

            try:
                with urllib.request.urlopen(
                    self.object_detection_health_url,
                    timeout=1.0,
                ) as response:
                    health = json.loads(response.read().decode('utf-8'))
                    if (
                        response.status == 200
                        and health.get('camera1')
                        and health.get('camera2')
                    ):
                        self.get_logger().info('Object detection health check passed.')
                        return True
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                pass

            time.sleep(0.5)

        self.get_logger().error('Timed out waiting for object detection health check.')
        return False

    def wait_for_react_monitoring_ready(self):
        deadline = time.time() + self.object_detection_viewer_timeout_sec
        self.get_logger().info('Waiting for React inspection camera viewers...')

        while time.time() < deadline:
            if (
                self.object_detection_process is not None
                and self.object_detection_process.poll() is not None
            ):
                self.get_logger().error(
                    'Object detection exited before React viewers connected.'
                )
                return False

            try:
                with urllib.request.urlopen(
                    self.object_detection_health_url,
                    timeout=1.0,
                ) as response:
                    health = json.loads(response.read().decode('utf-8'))
                    camera1_ready = bool(health.get('viewer_camera1'))
                    camera2_ready = bool(health.get('viewer_camera2'))
                    if response.status == 200 and camera1_ready and camera2_ready:
                        self.get_logger().info(
                            'React inspection camera viewers are connected.'
                        )
                        return True

                    self.get_logger().info(
                        'Waiting for React viewers: '
                        f'camera1={camera1_ready}, camera2={camera2_ready}',
                        throttle_duration_sec=1.0,
                    )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                pass

            time.sleep(0.5)

        self.get_logger().error('Timed out waiting for React inspection camera viewers.')
        return False

    def stop_object_detection(self):
        if self.object_detection_process is None:
            return

        if self.object_detection_process.poll() is not None:
            self.object_detection_process = None
            return

        self.get_logger().info('Stopping object detection.')
        self.object_detection_process.terminate()
        try:
            self.object_detection_process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self.get_logger().warn('Object detection did not stop. Killing it.')
            self.object_detection_process.kill()
            self.object_detection_process.wait(timeout=2.0)
        finally:
            self.object_detection_process = None


def main(args=None):
    rclpy.init(args=args)
    node = MissionManager()
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
