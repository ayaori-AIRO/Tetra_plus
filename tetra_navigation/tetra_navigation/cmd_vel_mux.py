#!/usr/bin/env python3

import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Bool
from std_msgs.msg import String


class CmdVelMux(Node):
    def __init__(self):
        super().__init__('cmd_vel_mux')

        self.declare_parameter('default_source', 'nav')
        self.source = self.get_parameter('default_source').value
        self.emergency_stop_active = False
        self.last_nav_cmd = Twist()
        self.last_servo_cmd = Twist()
        self.last_direct_cmd = Twist()

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_out', 10)
        self.create_subscription(Twist, '/cmd_vel', self.nav_callback, 10)
        self.create_subscription(Twist, '/cmd_vel_servo', self.servo_callback, 10)
        self.create_subscription(Twist, '/cmd_vel_direct', self.direct_callback, 10)
        self.create_subscription(String, '/cmd_vel_mux/select', self.select_callback, 10)
        self.create_subscription(Bool, '/cmd_vel_mux/emergency_stop', self.emergency_stop_callback, 10)
        self.create_timer(0.1, self.emergency_stop_timer)

        self.get_logger().info(f'cmd_vel_mux ready. selected source={self.source}')

    def emergency_stop_callback(self, msg):
        active = bool(msg.data)
        if active == self.emergency_stop_active:
            return

        self.emergency_stop_active = active
        if active:
            self.publish_stop(repeats=3, interval=0.02)
            self.get_logger().warn('cmd_vel_mux emergency motor stop active')
        else:
            self.publish_stop(repeats=1, interval=0.0)
            self.get_logger().info(
                f'cmd_vel_mux emergency motor stop released. selected source={self.source}'
            )

    def emergency_stop_timer(self):
        if self.emergency_stop_active:
            self.publish_stop(repeats=1, interval=0.0)

    def select_callback(self, msg):
        requested = msg.data.strip().lower()
        if requested not in ('nav', 'servo', 'direct', 'stop'):
            self.get_logger().warn(f'Ignoring unknown cmd_vel source: {msg.data}')
            return

        self.source = requested
        self.publish_stop(repeats=1, interval=0.0)
        self.get_logger().info(f'cmd_vel_mux selected source={self.source}')

    def nav_callback(self, msg):
        self.last_nav_cmd = msg
        if not self.emergency_stop_active and self.source == 'nav':
            self.cmd_pub.publish(msg)

    def servo_callback(self, msg):
        self.last_servo_cmd = msg
        if not self.emergency_stop_active and self.source == 'servo':
            self.cmd_pub.publish(msg)

    def direct_callback(self, msg):
        self.last_direct_cmd = msg
        if not self.emergency_stop_active and self.source == 'direct':
            self.cmd_pub.publish(msg)

    def publish_stop(self, repeats=3, interval=0.05):
        stop_cmd = Twist()
        for _ in range(repeats):
            self.cmd_pub.publish(stop_cmd)
            if interval > 0.0:
                time.sleep(interval)


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = CmdVelMux()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            try:
                node.publish_stop(repeats=5, interval=0.05)
            except Exception as exc:
                node.get_logger().error(f'Failed to publish stop command during shutdown: {exc}')
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
