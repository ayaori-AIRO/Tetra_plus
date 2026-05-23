#!/usr/bin/env python3

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


from ament_index_python.packages import get_package_share_directory
from launch.actions import IncludeLaunchDescription

from launch.launch_description_sources import PythonLaunchDescriptionSource
def generate_launch_description():
  ekf_option = LaunchConfiguration("ekf_option")
  ekf_option_arg = DeclareLaunchArgument(
    'ekf_option',
    default_value="False"
  )
  tetra_node = Node(
    package="tetra",
    executable="tetra",
    name="tetra",
    output="screen",
    parameters=[
      {"ekf_option":ekf_option}
    ],
    remappings=[
      ("cmd_vel", "/cmd_vel_out"),
    ]
  )
  start_robot_description_cmd = IncludeLaunchDescription(
      PythonLaunchDescriptionSource(
          os.path.join(
              get_package_share_directory("tetra_description"), "launch", "tetra.launch.py"

          )
      )
  )
  # rplidar_prefix = get_package_share_directory("sllidar_ros2")
  # start_rplidar_cmd = IncludeLaunchDescription(
  #     PythonLaunchDescriptionSource(os.path.join(rplidar_prefix, "launch", "sllidar_a2m12_launch.py"))
  # )
  return LaunchDescription([
    ekf_option_arg,
    tetra_node,
    start_robot_description_cmd,
    # start_rplidar_cmd,
  ])
