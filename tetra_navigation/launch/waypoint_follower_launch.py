import rclpy
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped

def main():
    rclpy.init()
    nav = BasicNavigator()

    # 1. 초기 위치 설정 (이미 Rviz에서 설정했다면 생략 가능)
    # 초기 위치가 정확해야 목표 지점으로 잘 이동합니다.

    # 2. 이동할 Waypoints 리스트 정의
    goal_poses = []
    
    # 첫 번째 목표 지점
    goal_pose1 = PoseStamped()
    goal_pose1.header.frame_id = 'map'
    goal_pose1.pose.position.x = 1.5  # x 좌표 (미터 단위)
    goal_pose1.pose.position.y = 0.5  # y 좌표
    goal_pose1.pose.orientation.w = 1.0
    goal_poses.append(goal_pose1)

    # 두 번째 목표 지점
    goal_pose2 = PoseStamped()
    goal_pose2.header.frame_id = 'map'
    goal_pose2.pose.position.x = 2.5
    goal_pose2.pose.position.y = -1.0
    goal_pose2.pose.orientation.w = 1.0
    goal_poses.append(goal_pose2)

    # 3. 순차적 이동 실행
    nav.followWaypoints(goal_poses)

    # 4. 상태 확인 루프
    while not nav.isTaskComplete():
        feedback = nav.getFeedback()
        if feedback:
            print(f'남은 Waypoint 개수: {feedback.current_waypoint}')

    # 5. 결과 출력
    result = nav.getResult()
    if result == TaskResult.SUCCEEDED:
        print('모든 지점에 도착했습니다!')
    elif result == TaskResult.CANCELED:
        print('작업이 취소되었습니다.')
    elif result == TaskResult.FAILED:
        print('이동에 실패했습니다.')

    rclpy.shutdown()

if __name__ == '__main__':
    main()