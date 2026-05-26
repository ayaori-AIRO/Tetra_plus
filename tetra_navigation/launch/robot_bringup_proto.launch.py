#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare('tetra_navigation'),
                    'launch',
                    'robot_bringup.launch.py',
                ])
            ),
            launch_arguments={
                'mission_autostart': LaunchConfiguration('mission_autostart', default='false'),
                'use_mission_manager': 'false',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare('tetra_navigation'),
                    'launch',
                    'robot_bringup_proto_nodes.launch.py',
                ])
            ),
        ),
    ])
