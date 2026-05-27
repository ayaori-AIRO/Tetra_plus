#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'mission_autostart',
            default_value='false',
            description='Start the proto mission sequence automatically.',
        ),
        DeclareLaunchArgument(
            'target_waypoint',
            default_value='1',
            description='Fire extinguisher waypoint number for single-target tests.',
        ),
        DeclareLaunchArgument(
            'inspection_waypoints',
            default_value='[1, 2]',
            description='Ordered fire extinguisher waypoint numbers for proto inspection.',
        ),
        DeclareLaunchArgument(
            'waypoint2_backup_after_arrival',
            default_value='true',
            description='Drive on heading after waypoint 2 navigation arrives.',
        ),
        DeclareLaunchArgument(
            'waypoint2_backup_distance',
            default_value='0.35',
            description='Drive distance in meters after waypoint 2 navigation arrives.',
        ),
        DeclareLaunchArgument(
            'waypoint2_forward_after_inspection_distance',
            default_value='0.5',
            description='Drive distance in meters after waypoint 2 inspection finishes.',
        ),
        DeclareLaunchArgument(
            'waypoint2_forward_after_inspection_speed',
            default_value='0.10',
            description='Drive speed in m/s after waypoint 2 inspection finishes.',
        ),
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
                'target_waypoint': LaunchConfiguration('target_waypoint', default='1'),
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
            launch_arguments={
                'mission_autostart': LaunchConfiguration('mission_autostart', default='false'),
                'target_waypoint': LaunchConfiguration('target_waypoint', default='1'),
                'inspection_waypoints': LaunchConfiguration('inspection_waypoints', default='[1, 2]'),
                'waypoint2_backup_after_arrival': LaunchConfiguration('waypoint2_backup_after_arrival', default='true'),
                'waypoint2_backup_distance': LaunchConfiguration('waypoint2_backup_distance', default='0.35'),
                'waypoint2_forward_after_inspection_distance': LaunchConfiguration('waypoint2_forward_after_inspection_distance', default='0.5'),
                'waypoint2_forward_after_inspection_speed': LaunchConfiguration('waypoint2_forward_after_inspection_speed', default='0.10'),
            }.items(),
        ),
    ])
