#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    mission_autostart = LaunchConfiguration('mission_autostart')
    start_docking_after_nav_active = LaunchConfiguration('start_docking_after_nav_active')
    dock_after_waypoint = LaunchConfiguration('dock_after_waypoint')
    object_detection_script = LaunchConfiguration('object_detection_script')
    neopixel_controller_script = LaunchConfiguration('neopixel_controller_script')
    inspection_pipeline_script = LaunchConfiguration('inspection_pipeline_script')
    forward_after_inspection = LaunchConfiguration('forward_after_inspection')
    forward_distance = LaunchConfiguration('forward_distance')
    forward_speed = LaunchConfiguration('forward_speed')
    forward_time_allowance_sec = LaunchConfiguration('forward_time_allowance_sec')
    use_proto_mission_manager = LaunchConfiguration('use_proto_mission_manager')

    return LaunchDescription([
        DeclareLaunchArgument(
            'mission_autostart',
            default_value='false',
            description='Start the front-only proto mission sequence automatically.'
        ),
        DeclareLaunchArgument(
            'start_docking_after_nav_active',
            default_value='false',
            description='Send a dock_to_tag action goal after Nav2 becomes active. For testing only.'
        ),
        DeclareLaunchArgument(
            'dock_after_waypoint',
            default_value='true',
            description='Start dock_to_tag after the fire extinguisher waypoint is reached.'
        ),
        DeclareLaunchArgument(
            'object_detection_script',
            default_value='/home/ayaori/ros2_ws/src/tetra/Inspection/project/Object_Detection_Live.py',
            description='Path to the YOLO live object detection stream server.'
        ),
        DeclareLaunchArgument(
            'neopixel_controller_script',
            default_value='/home/ayaori/ros2_ws/src/tetra/Inspection/project/neopixel_controller.py',
            description='Path to the NeoPixel controller script.'
        ),
        DeclareLaunchArgument(
            'inspection_pipeline_script',
            default_value='/home/ayaori/ros2_ws/src/tetra/Inspection/project/extinguisher_inspection/run_inspection_pipeline.py',
            description='Path to the inspection pipeline script.'
        ),
        DeclareLaunchArgument(
            'forward_after_inspection',
            default_value='true',
            description='Drive forward after front-only inspection finishes.'
        ),
        DeclareLaunchArgument(
            'forward_distance',
            default_value='1.0',
            description='Forward distance in meters after inspection.'
        ),
        DeclareLaunchArgument(
            'forward_speed',
            default_value='0.03',
            description='Forward speed in m/s after inspection.'
        ),
        DeclareLaunchArgument(
            'forward_time_allowance_sec',
            default_value='10.0',
            description='Time allowance in seconds for forward drive.'
        ),
        DeclareLaunchArgument(
            'use_proto_mission_manager',
            default_value='true',
            description='Start the proto mission manager node.'
        ),
        Node(
            package='tetra_navigation',
            executable='mission_manager_proto',
            name='mission_manager_proto',
            output='screen',
            parameters=[{
                'autostart': mission_autostart,
                'start_docking_after_nav_active': start_docking_after_nav_active,
                'dock_after_waypoint': dock_after_waypoint,
                'object_detection_script': object_detection_script,
                'neopixel_controller_script': neopixel_controller_script,
                'inspection_pipeline_script': inspection_pipeline_script,
                'forward_after_inspection': forward_after_inspection,
                'forward_distance': forward_distance,
                'forward_speed': forward_speed,
                'forward_time_allowance_sec': forward_time_allowance_sec,
            }],
            condition=IfCondition(use_proto_mission_manager),
        ),
    ])
