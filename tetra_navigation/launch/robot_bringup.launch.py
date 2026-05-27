#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    tetra_share = get_package_share_directory('tetra')
    tetra_navigation_share = get_package_share_directory('tetra_navigation')
    realsense_share = get_package_share_directory('realsense2_camera')

    use_react = LaunchConfiguration('use_react')
    react_dir = LaunchConfiguration('react_dir')
    react_port = LaunchConfiguration('react_port')
    use_react_dev_server = LaunchConfiguration('use_react_dev_server')
    react_start_delay = LaunchConfiguration('react_start_delay')
    use_object_detection = LaunchConfiguration('use_object_detection')
    object_detection_script = LaunchConfiguration('object_detection_script')
    neopixel_controller_script = LaunchConfiguration('neopixel_controller_script')
    motor_controller_script = LaunchConfiguration('motor_controller_script')
    inspection_pipeline_script = LaunchConfiguration('inspection_pipeline_script')
    object_detection_start_delay = LaunchConfiguration('object_detection_start_delay')
    use_realsense = LaunchConfiguration('use_realsense')
    use_apriltag = LaunchConfiguration('use_apriltag')
    use_servo = LaunchConfiguration('use_servo')
    use_mission_manager = LaunchConfiguration('use_mission_manager')
    use_cmd_vel_mux = LaunchConfiguration('use_cmd_vel_mux')
    use_rviz = LaunchConfiguration('use_rviz')
    use_sim_time = LaunchConfiguration('use_sim_time')
    mission_autostart = LaunchConfiguration('mission_autostart')
    start_docking_after_nav_active = LaunchConfiguration('start_docking_after_nav_active')
    dock_after_waypoint = LaunchConfiguration('dock_after_waypoint')
    target_waypoint = LaunchConfiguration('target_waypoint')
    servo_enabled = LaunchConfiguration('servo_enabled')

    tags_config = os.path.join(
        tetra_navigation_share,
        'config',
        'tags_36h11_tetra.yaml'
    )

    tetra_configuration = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tetra_share, 'launch', 'tetra_configuration.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
        }.items()
    )

    lidar = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tetra_navigation_share, 'launch', 'view_sllidar_a2m12_launch.py')
        )
    )

    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tetra_navigation_share, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
        }.items()
    )

    rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tetra_navigation_share, 'launch', 'rviz_launch.py')
        ),
        condition=IfCondition(use_rviz)
    )

    realsense = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(realsense_share, 'launch', 'rs_launch.py')
        ),
        launch_arguments={
            'publish_tf': 'false',
        }.items(),
        condition=IfCondition(use_realsense)
    )

    apriltag_node = Node(
        package='apriltag_ros',
        executable='apriltag_node',
        name='apriltag_node',
        output='screen',
        parameters=[tags_config],
        remappings=[
            ('image_rect', '/camera/camera/color/image_raw'),
            ('camera_info', '/camera/camera/color/camera_info'),
        ],
        condition=IfCondition(use_apriltag),
    )

    apriltag_visualizer = Node(
        package='tetra_navigation',
        executable='apriltag_visualizer',
        name='apriltag_visualizer',
        output='screen',
        condition=IfCondition(use_apriltag),
    )

    apriltag_stream_server = Node(
        package='tetra_navigation',
        executable='apriltag_stream_server',
        name='apriltag_stream_server',
        output='screen',
        parameters=[{
            'image_topic': '/apriltag/annotated_image',
            'host': '0.0.0.0',
            'port': 8001,
            'stream_fps': 12.0,
        }],
        condition=IfCondition(use_apriltag),
    )

    apriltag_servo = Node(
        package='tetra_navigation',
        executable='apriltag_servo',
        name='apriltag_servo',
        output='screen',
        parameters=[{
            'tag_id': 10,
            'tag_size': 0.10,
            'target_distance': 0.4,
            'mid_tag_id': 9,
            'mid_tag_size': 0.05,
            'mid_target_distance': 0.2,
            'near_tag_id': 1,
            'near_tag_ids': [1, 2, 3],
            'near_tag_size': 0.01,
            'switch_distance': 0.45,
            'near_switch_distance': 0.25,
            'near_target_distance': 0.03,
            'distance_tolerance': 0.001,
            'min_linear_speed': 0.003,
            'cmd_vel_topic': '/cmd_vel_servo',
            'stop_after_reached': False,
            'enabled': servo_enabled,
        }],
        condition=IfCondition(use_servo),
    )

    cmd_vel_mux = Node(
        package='tetra_navigation',
        executable='cmd_vel_mux',
        name='cmd_vel_mux',
        output='screen',
        parameters=[{
            'default_source': 'nav',
        }],
        condition=IfCondition(use_cmd_vel_mux),
    )

    mission_manager = Node(
        package='tetra_navigation',
        executable='mission_manager',
        name='mission_manager',
        output='screen',
        parameters=[{
            'autostart': mission_autostart,
            'start_docking_after_nav_active': start_docking_after_nav_active,
            'dock_after_waypoint': dock_after_waypoint,
            'target_waypoint': target_waypoint,
            'object_detection_script': object_detection_script,
            'neopixel_controller_script': neopixel_controller_script,
            'motor_controller_script': motor_controller_script,
            'inspection_pipeline_script': inspection_pipeline_script,
        }],
        condition=IfCondition(use_mission_manager),
    )

    react_dev_server = ExecuteProcess(
        condition=IfCondition(use_react_dev_server),
        cmd=['npm', 'start'],
        cwd=react_dir,
        output='screen',
        additional_env={
            'BROWSER': 'none',
            'PORT': react_port,
            'CHOKIDAR_USEPOLLING': 'false',
            'WATCHPACK_POLLING': 'false',
        },
    )

    react_static_server = ExecuteProcess(
        condition=UnlessCondition(use_react_dev_server),
        cmd=[
            'python3',
            '-m',
            'http.server',
            react_port,
            '--bind',
            '0.0.0.0',
            '--directory',
            PathJoinSubstitution([react_dir, 'build']),
        ],
        output='screen',
    )

    react_web = TimerAction(
        condition=IfCondition(use_react),
        period=0.0,
        actions=[
            react_dev_server,
            react_static_server,
        ],
    )

    object_detection_live = TimerAction(
        period=object_detection_start_delay,
        actions=[
            ExecuteProcess(
                condition=IfCondition(use_object_detection),
                cmd=['python3', '-u', object_detection_script],
                output='screen',
                additional_env={
                    'PYTHONUNBUFFERED': '1',
                },
            )
        ],
    )

    robot_nodes = TimerAction(
        period=react_start_delay,
        actions=[
            tetra_configuration,
            lidar,
            nav2_bringup,
            cmd_vel_mux,
            realsense,
            apriltag_node,
            apriltag_visualizer,
            apriltag_stream_server,
            apriltag_servo,
            mission_manager,
            rviz,
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_react',
            default_value='true',
            description='Start the React inspection web app before robot bringup.'
        ),
        DeclareLaunchArgument(
            'react_dir',
            default_value='/home/ayaori/ros2_ws/src/tetra/Inspection/react/inspection-web',
            description='Path to the React inspection web app.'
        ),
        DeclareLaunchArgument(
            'react_port',
            default_value='3000',
            description='Port for the React inspection web app.'
        ),
        DeclareLaunchArgument(
            'use_react_dev_server',
            default_value='false',
            description='Use npm start instead of serving the React build directory.'
        ),
        DeclareLaunchArgument(
            'react_start_delay',
            default_value='5.0',
            description='Seconds to wait after starting React before launching robot nodes.'
        ),
        DeclareLaunchArgument(
            'use_object_detection',
            default_value='false',
            description='Start Object_Detection_Live.py at bringup. Normally false; mission_manager starts it during inspection.'
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
            'motor_controller_script',
            default_value='/home/ayaori/ros2_ws/src/tetra/Inspection/project/motor_controller.py',
            description='Path to the inspection motor controller script.'
        ),
        DeclareLaunchArgument(
            'inspection_pipeline_script',
            default_value='/home/ayaori/ros2_ws/src/tetra/Inspection/project/extinguisher_inspection/run_inspection_pipeline.py',
            description='Path to the inspection pipeline script.'
        ),
        DeclareLaunchArgument(
            'object_detection_start_delay',
            default_value='2.0',
            description='Seconds to wait before starting Object_Detection_Live.py.'
        ),
        DeclareLaunchArgument(
            'use_realsense',
            default_value='true',
            description='Start the RealSense camera launch.'
        ),
        DeclareLaunchArgument(
            'use_apriltag',
            default_value='true',
            description='Start AprilTag detection and visualization nodes.'
        ),
        DeclareLaunchArgument(
            'use_servo',
            default_value='true',
            description='Start the AprilTag visual servo action server.'
        ),
        DeclareLaunchArgument(
            'use_mission_manager',
            default_value='true',
            description='Start the mission manager node.'
        ),
        DeclareLaunchArgument(
            'use_cmd_vel_mux',
            default_value='true',
            description='Start cmd_vel_mux for nav/servo velocity selection.'
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='true',
            description='Launch tetra_navigation rviz_launch.py as part of robot bringup.'
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock for robot and Nav2.'
        ),
        DeclareLaunchArgument(
            'mission_autostart',
            default_value='false',
            description='Start the mission sequence automatically when implemented.'
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
            'target_waypoint',
            default_value='1',
            description='Fire extinguisher waypoint number to navigate to.'
        ),
        DeclareLaunchArgument(
            'servo_enabled',
            default_value='false',
            description='Allow apriltag_servo to publish /cmd_vel immediately.'
        ),
        react_web,
        object_detection_live,
        robot_nodes,
    ])
