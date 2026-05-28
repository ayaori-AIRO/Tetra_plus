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
            description='Prepare mission manager automatically. Proto mission departure waits for UI start by default.',
        ),
        DeclareLaunchArgument(
            'wait_for_ui_start',
            default_value='true',
            description='Wait for the web UI inspection start button before starting the proto mission.',
        ),
        DeclareLaunchArgument(
            'rviz',
            default_value='true',
            description='Launch RViz as part of robot bringup.',
        ),
        DeclareLaunchArgument(
            'target_waypoint',
            default_value='1',
            description='Fire extinguisher waypoint number for single-target tests.',
        ),
        DeclareLaunchArgument(
            'inspection_waypoints',
            default_value='[1, 2, 3]',
            description='Ordered fire extinguisher waypoint numbers for proto inspection.',
        ),
        DeclareLaunchArgument(
            'waypoint2_backup_after_arrival',
            default_value='true',
            description='Drive on heading after waypoint 2 navigation arrives.',
        ),
        DeclareLaunchArgument(
            'waypoint2_backup_distance',
            default_value='0.6',
            description='Drive distance in meters after waypoint 2 navigation arrives.',
        ),
        DeclareLaunchArgument(
            'waypoint2_backup_speed',
            default_value='0.06',
            description='Drive speed in m/s after waypoint 2 navigation arrives.',
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
        DeclareLaunchArgument(
            'return_home_after_mission',
            default_value='true',
            description='Navigate back to home after all proto inspections finish.',
        ),
        DeclareLaunchArgument(
            'home_x',
            default_value='0.0',
            description='Home pose x in map frame.',
        ),
        DeclareLaunchArgument(
            'home_y',
            default_value='0.0',
            description='Home pose y in map frame.',
        ),
        DeclareLaunchArgument(
            'home_z',
            default_value='0.0',
            description='Home pose orientation z in map frame.',
        ),
        DeclareLaunchArgument(
            'home_w',
            default_value='1.0',
            description='Home pose orientation w in map frame.',
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
                'use_rviz': LaunchConfiguration('rviz', default='true'),
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
                'inspection_waypoints': LaunchConfiguration('inspection_waypoints', default='[1, 2, 3]'),
                'wait_for_ui_start': LaunchConfiguration('wait_for_ui_start', default='true'),
                'waypoint2_backup_after_arrival': LaunchConfiguration('waypoint2_backup_after_arrival', default='true'),
                'waypoint2_backup_distance': LaunchConfiguration('waypoint2_backup_distance', default='0.6'),
                'waypoint2_backup_speed': LaunchConfiguration('waypoint2_backup_speed', default='0.06'),
                'waypoint2_forward_after_inspection_distance': LaunchConfiguration('waypoint2_forward_after_inspection_distance', default='0.5'),
                'waypoint2_forward_after_inspection_speed': LaunchConfiguration('waypoint2_forward_after_inspection_speed', default='0.10'),
                'return_home_after_mission': LaunchConfiguration('return_home_after_mission', default='true'),
                'home_x': LaunchConfiguration('home_x', default='0.0'),
                'home_y': LaunchConfiguration('home_y', default='0.0'),
                'home_z': LaunchConfiguration('home_z', default='0.0'),
                'home_w': LaunchConfiguration('home_w', default='1.0'),
            }.items(),
        ),
    ])
