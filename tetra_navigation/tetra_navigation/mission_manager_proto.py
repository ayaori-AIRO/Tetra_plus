#!/usr/bin/env python3

import json
import os
import subprocess
import time
import urllib.error

import rclpy
from rclpy.executors import MultiThreadedExecutor

from tetra_navigation.mission_manager import MissionManager


class MissionManagerProto(MissionManager):
    def __init__(self):
        super().__init__()
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

        self.stop_object_detection()
        self.run_inspection_pipeline()

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
