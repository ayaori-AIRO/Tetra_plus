#!/usr/bin/env python3

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String


class CmdVelMux(Node):
    def __init__(self):
        super().__init__('cmd_vel_mux')

        self.declare_parameter('default_source', 'nav')
        self.source = self.get_parameter('default_source').value
        self.last_nav_cmd = Twist()
        self.last_servo_cmd = Twist()

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel_out', 10)
        self.create_subscription(Twist, '/cmd_vel', self.nav_callback, 10)
        self.create_subscription(Twist, '/cmd_vel_servo', self.servo_callback, 10)
        self.create_subscription(String, '/cmd_vel_mux/select', self.select_callback, 10)

        self.get_logger().info(f'cmd_vel_mux ready. selected source={self.source}')

    def select_callback(self, msg):
        requested = msg.data.strip().lower()
        if requested not in ('nav', 'servo', 'stop'):
            self.get_logger().warn(f'Ignoring unknown cmd_vel source: {msg.data}')
            return

        self.source = requested
        self.cmd_pub.publish(Twist())
        self.get_logger().info(f'cmd_vel_mux selected source={self.source}')

    def nav_callback(self, msg):
        self.last_nav_cmd = msg
        if self.source == 'nav':
            self.cmd_pub.publish(msg)

    def servo_callback(self, msg):
        self.last_servo_cmd = msg
        if self.source == 'servo':
            self.cmd_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelMux()
    try:
        rclpy.spin(node)
    finally:
        node.cmd_pub.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
