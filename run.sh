#!/bin/bash
# ROS 환경 설정
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash

ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 lidar_link laser &
# Launch 파일 실행
ros2 launch tetra_nav2 nav2.launch.py &



wait
