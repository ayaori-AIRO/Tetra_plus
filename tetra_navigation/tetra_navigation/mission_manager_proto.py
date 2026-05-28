#!/usr/bin/env python3

import json
import os
import subprocess
import time
import urllib.error

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Twist
from nav2_simple_commander.robot_navigator import TaskResult
from rclpy.executors import MultiThreadedExecutor
from tetra_msgs.action import DockToTag

from tetra_navigation.mission_manager import MissionManager


class MissionManagerProto(MissionManager):
    def __init__(self):
        super().__init__()
        self.declare_parameter('inspection_waypoints', [1, 2, 3])
        self.declare_parameter('forward_after_inspection', True)
        self.declare_parameter('forward_distance', 0.13)
        self.declare_parameter('forward_speed', 0.03)
        self.declare_parameter('forward_time_allowance_sec', 10.0)
        self.declare_parameter('waypoint2_backup_after_arrival', True)
        self.declare_parameter('waypoint2_backup_distance', 0.65)
        self.declare_parameter('waypoint2_backup_speed', 0.06)
        self.declare_parameter('waypoint3_backup_distance', 0.6)
        self.declare_parameter('waypoint3_backup_speed', 0.06)
        self.declare_parameter('waypoint2_forward_after_inspection_distance', 0.5)
        self.declare_parameter('waypoint2_forward_after_inspection_speed', 0.10)
        self.declare_parameter('return_home_after_mission', True)
        self.declare_parameter('home_x', 0.0)
        self.declare_parameter('home_y', 0.0)
        self.declare_parameter('home_z', 0.0)
        self.declare_parameter('home_w', 1.0)

        self.inspection_waypoints = self.parse_waypoint_sequence(
            self.get_parameter('inspection_waypoints').value
        )
        self.forward_after_inspection = bool(
            self.get_parameter('forward_after_inspection').value
        )
        self.forward_distance = float(self.get_parameter('forward_distance').value)
        self.forward_speed = float(self.get_parameter('forward_speed').value)
        self.forward_time_allowance_sec = float(
            self.get_parameter('forward_time_allowance_sec').value
        )
        self.waypoint2_backup_after_arrival = bool(
            self.get_parameter('waypoint2_backup_after_arrival').value
        )
        self.waypoint2_backup_distance = float(
            self.get_parameter('waypoint2_backup_distance').value
        )
        self.waypoint2_backup_speed = float(
            self.get_parameter('waypoint2_backup_speed').value
        )
        self.waypoint3_backup_distance = float(
            self.get_parameter('waypoint3_backup_distance').value
        )
        self.waypoint3_backup_speed = float(
            self.get_parameter('waypoint3_backup_speed').value
        )
        self.waypoint2_forward_after_inspection_distance = float(
            self.get_parameter('waypoint2_forward_after_inspection_distance').value
        )
        self.waypoint2_forward_after_inspection_speed = float(
            self.get_parameter('waypoint2_forward_after_inspection_speed').value
        )
        self.return_home_after_mission = bool(
            self.get_parameter('return_home_after_mission').value
        )
        self.home_waypoint = {
            'x': float(self.get_parameter('home_x').value),
            'y': float(self.get_parameter('home_y').value),
            'z': float(self.get_parameter('home_z').value),
            'w': float(self.get_parameter('home_w').value),
        }
        self.cmd_vel_direct_pub = self.create_publisher(Twist, '/cmd_vel_direct', 10)
        self.get_logger().info(
            'Mission manager proto mode: front-only inspection, no ST3235/ball screw.'
        )
        self.get_logger().info(
            f'Proto inspection waypoint sequence: {self.inspection_waypoints}'
        )

    def run_mission(self):
        self.set_mission_action('Nav2 활성화 대기')
        self.get_logger().info('Waiting for Nav2 to become active...')
        self.navigator.waitUntilNav2Active()
        self.get_logger().info('Nav2 is active. Proto mission sequence can continue.')
        self.set_mission_action('Nav2 준비 완료')
        self.select_cmd_vel_source('nav')
        self.set_inspection_running(True, '검사 시작')

        try:
            if self.start_docking_after_nav_active:
                self.set_mission_action(f'EXT{self.target_waypoint} 비주얼 서보잉 시작')
                if self.dock_to_tag_sync(self.target_waypoint):
                    self.run_inspection_sequence()
                return

            for index, waypoint_id in enumerate(self.inspection_waypoints):
                if not rclpy.ok():
                    return

                self.target_waypoint = waypoint_id
                self.get_logger().info(
                    f'Starting extinguisher {waypoint_id} inspection '
                    f'({index + 1}/{len(self.inspection_waypoints)}).'
                )
                self.set_mission_action(f'EXT{waypoint_id} 이동 시작')

                if not self.navigate_to_fire_extinguisher():
                    self.get_logger().error(
                        f'Aborting proto mission: waypoint {waypoint_id} navigation failed.'
                    )
                    self.set_mission_action(f'EXT{waypoint_id} 이동 실패')
                    return
                self.set_mission_action(f'EXT{waypoint_id} 도착')

                if waypoint_id in (2, 3) and self.waypoint2_backup_after_arrival:
                    backup_distance = self.waypoint2_backup_distance
                    backup_speed = self.waypoint2_backup_speed
                    if waypoint_id == 3:
                        backup_distance = self.waypoint3_backup_distance
                        backup_speed = self.waypoint3_backup_speed

                    self.set_mission_action(f'EXT{waypoint_id} 충돌 방지 전진')
                    if not self.drive_fixed_distance(
                        backup_distance,
                        backup_speed,
                        f'waypoint {waypoint_id} backup after arrival',
                    ):
                        self.get_logger().warn(
                            f'Waypoint {waypoint_id} backup after arrival did not succeed. '
                            'Continuing to visual servoing.'
                        )

                if not self.dock_after_waypoint:
                    self.get_logger().info('Waypoint reached. Docking is disabled.')
                    continue

                time.sleep(1.0)
                self.set_mission_action(f'EXT{waypoint_id} 비주얼 서보잉 시작')
                if not self.dock_to_tag_sync(waypoint_id):
                    self.get_logger().error(
                        f'Aborting proto mission: waypoint {waypoint_id} visual servoing failed.'
                    )
                    self.set_mission_action(f'EXT{waypoint_id} 비주얼 서보잉 실패')
                    return
                self.set_mission_action(f'EXT{waypoint_id} 비주얼 서보잉 완료')

                if not self.run_inspection_sequence():
                    self.get_logger().error(
                        f'Aborting proto mission: extinguisher {waypoint_id} inspection failed.'
                    )
                    self.set_mission_action(f'EXT{waypoint_id} 검사 실패')
                    return

                self.select_cmd_vel_source('nav')

            if self.return_home_after_mission:
                self.return_home()

            self.set_mission_action('작업 완료')
            self.get_logger().info('Proto mission sequence finished.')
        finally:
            self.set_inspection_running(False, '검사 종료')

    def return_home(self):
        self.get_logger().info('All inspections complete. Returning to home pose.')
        self.set_mission_action('홈 위치 복귀 시작')
        self.select_cmd_vel_source('nav')
        if self.navigate_to_pose(self.home_waypoint, 'home'):
            self.get_logger().info('Arrived at home pose. Proto mission complete.')
            self.set_mission_action('홈 위치 복귀 완료')
            return True

        self.get_logger().error('Failed to return to home pose.')
        self.set_mission_action('홈 위치 복귀 실패')
        return False

    def navigate_to_fire_extinguisher(self):
        if self.target_waypoint == 2:
            approach_waypoint = {
                'x': 18.218999280079128,
                'y': 2.9610134627059015,
                'z': -0.7146790841040943,
                'w': 0.6994525049952519,
            }
            if not self.navigate_to_pose(
                approach_waypoint,
                'fire extinguisher waypoint 2 approach',
            ):
                return False

            final_waypoint = {
                'x': 24.339566679100553,
                'y': 0.0513142952244203,
                'z': 0.6965519599773928,
                'w': 0.7175063533179706,
            }
            return self.navigate_to_pose(
                final_waypoint,
                'fire extinguisher waypoint 2 final',
            )

        if self.target_waypoint == 3:
            final_waypoint = {
                'x': 40.68936856521227,
                'y': 0.2179757647171073,
                'z': -0.7100444040265033,
                'w': 0.704156903190367,
            }
            return self.navigate_to_pose(
                final_waypoint,
                'fire extinguisher waypoint 3 final',
            )

        return super().navigate_to_fire_extinguisher()

    def navigate_to_pose(self, waypoint, label):
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = 'map'
        goal_pose.header.stamp = self.navigator.get_clock().now().to_msg()
        goal_pose.pose.position.x = waypoint['x']
        goal_pose.pose.position.y = waypoint['y']
        goal_pose.pose.orientation.z = waypoint['z']
        goal_pose.pose.orientation.w = waypoint['w']

        self.get_logger().info(
            f'Navigating to {label}: x={waypoint["x"]:.3f}, y={waypoint["y"]:.3f}'
        )
        self.navigator.goToPose(goal_pose)

        while not self.navigator.isTaskComplete():
            feedback = self.navigator.getFeedback()
            if feedback is not None:
                self.get_logger().info(
                    f'{label} distance remaining: {feedback.distance_remaining:.2f} m',
                    throttle_duration_sec=1.0,
                )
            time.sleep(0.1)

        result = self.navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            self.get_logger().info(f'Arrived at {label}.')
            return True

        if result == TaskResult.CANCELED:
            self.get_logger().warn(f'{label} navigation goal was canceled.')
        elif result == TaskResult.FAILED:
            self.get_logger().error(f'{label} navigation goal failed.')
        else:
            self.get_logger().error(
                f'{label} navigation ended with unknown result: {result}'
            )

        return False

    def dock_to_tag_sync(self, waypoint_id):
        self.get_logger().info(
            f'Waiting for dock_to_tag action server at waypoint {waypoint_id}...'
        )
        if not self.dock_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('dock_to_tag action server is not available.')
            return False

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
        self.get_logger().info(f'Sending dock_to_tag goal for waypoint {waypoint_id}.')
        send_future = self.dock_client.send_goal_async(
            goal,
            feedback_callback=self.docking_feedback_callback,
        )
        while rclpy.ok() and not send_future.done():
            time.sleep(0.05)

        if not rclpy.ok():
            self.select_cmd_vel_source('stop')
            return False

        goal_handle = send_future.result()
        if not goal_handle.accepted:
            self.select_cmd_vel_source('stop')
            self.get_logger().error('dock_to_tag goal was rejected.')
            return False

        self.get_logger().info('dock_to_tag goal accepted.')
        result_future = goal_handle.get_result_async()
        while rclpy.ok() and not result_future.done():
            time.sleep(0.05)

        self.select_cmd_vel_source('stop')
        if not rclpy.ok():
            return False

        action_result = result_future.result()
        result = action_result.result
        if action_result.status == GoalStatus.STATUS_SUCCEEDED and result.success:
            self.get_logger().info(
                'dock_to_tag succeeded: '
                f'reason={result.reason}, '
                f'final_distance={result.final_distance:.3f} m, '
                f'final_lateral={result.final_lateral_error:.3f} m, '
                f'final_tag_id={result.final_tag_id}'
            )
            self.current_extinguisher_id = self.normalize_extinguisher_id(
                result.final_tag_id
            )
            return True

        self.get_logger().error(
            'dock_to_tag failed: '
            f'status={action_result.status}, '
            f'reason={result.reason}, '
            f'final_distance={result.final_distance:.3f} m, '
            f'final_lateral={result.final_lateral_error:.3f} m, '
            f'final_tag_id={result.final_tag_id}'
        )
        return False

    @staticmethod
    def parse_waypoint_sequence(value):
        if isinstance(value, str):
            cleaned = value.strip().strip('[]')
            if not cleaned:
                return [1]
            return [int(part.strip()) for part in cleaned.split(',') if part.strip()]

        if isinstance(value, (list, tuple)):
            return [int(item) for item in value]

        return [int(value)]

    def run_inspection_sequence(self):
        was_running = bool(self.read_inspection_status().get('running'))
        if not was_running:
            self.set_inspection_running(True, '검사 시작')
        try:
            return self._run_inspection_sequence()
        finally:
            if not was_running:
                self.set_inspection_running(False, '검사 종료')

    def _run_inspection_sequence(self):
        self.set_mission_action(f'EXT{self.target_waypoint} LED 켜는 중')
        self.turn_on_internal_led()

        if not self.start_object_detection():
            self.turn_off_neopixel()
            return False

        self.set_mission_action(f'EXT{self.target_waypoint} 검사 카메라 준비')
        if not self.wait_for_object_detection_ready():
            self.stop_inspection_live()
            return False

        if not self.set_object_detection_extinguisher_id():
            self.stop_inspection_live()
            return False

        if not self.wait_for_react_monitoring_ready():
            self.stop_inspection_live()
            return False

        self.set_mission_action(f'EXT{self.target_waypoint} 촬영 대기')
        if not self.reset_object_detection_capture(1):
            self.stop_inspection_live()
            return False

        self.capture_started_at = time.time()
        self.wait_for_front_capture()
        self.stop_inspection_live()

        self.set_mission_action(f'EXT{self.target_waypoint} 검사 분석 중')
        pipeline_ok = self.run_inspection_pipeline()

        if not pipeline_ok:
            return False

        if self.forward_after_inspection:
            distance = self.forward_distance
            speed = self.forward_speed
            label = 'forward drive after inspection'
            if self.target_waypoint in (2, 3):
                distance = self.waypoint2_forward_after_inspection_distance
                speed = self.waypoint2_forward_after_inspection_speed
                label = f'waypoint {self.target_waypoint} forward drive after inspection'

            self.set_mission_action(f'EXT{self.target_waypoint} 도킹 해제 전진')
            if not self.drive_fixed_distance(
                distance,
                speed,
                label,
            ):
                self.get_logger().warn(
                    'Forward drive after inspection did not succeed. '
                    'Continuing to the next waypoint.'
                )

        return True

    def stop_inspection_live(self):
        self.turn_off_neopixel()
        self.stop_object_detection()

    def turn_off_neopixel(self):
        if not os.path.exists(self.neopixel_controller_script):
            self.get_logger().error(
                f'NeoPixel controller script not found: {self.neopixel_controller_script}'
            )
            return False

        self.get_logger().info('Turning off NeoPixel LED before stopping camera live.')
        completed = subprocess.run(
            ['python3', self.neopixel_controller_script, 'off'],
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
                f'NeoPixel off command failed: returncode={completed.returncode}'
            )
            return False

        return True

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

        self.get_logger().warn(
            'Timed out waiting for front all_targets capture. '
            'Saving full-frame fallback and continuing inspection.'
        )
        self.save_fallback_fire_extinguisher_capture(1)
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
                '--capture-started-at',
                str(self.capture_started_at),
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

    def drive_fixed_distance(self, distance, speed, label):
        if speed == 0.0:
            self.get_logger().error(f'{label} speed must not be zero.')
            return False

        drive_duration_sec = abs(distance) / max(abs(speed), 0.001)
        linear_x = abs(speed) if distance >= 0.0 else -abs(speed)

        self.get_logger().info(
            f'Driving directly for {label}: '
            f'distance={distance:.3f} m, '
            f'linear.x={linear_x:.3f} m/s, '
            f'duration={drive_duration_sec:.1f} s'
        )

        self.select_cmd_vel_source('direct')
        cmd = Twist()
        cmd.linear.x = linear_x
        deadline = time.monotonic() + drive_duration_sec

        while rclpy.ok() and time.monotonic() < deadline:
            self.cmd_vel_direct_pub.publish(cmd)
            time.sleep(0.05)

        self.force_stop_motion()
        self.get_logger().info(f'{label} direct drive finished.')
        return rclpy.ok()

    def force_stop_motion(self):
        self.select_cmd_vel_source('stop')
        stop_cmd = Twist()
        for _ in range(10):
            self.cmd_vel_direct_pub.publish(stop_cmd)
            time.sleep(0.05)


def main(args=None):
    rclpy.init(args=args)
    node = MissionManagerProto()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.stop_inspection_live()
        executor.remove_node(node)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
