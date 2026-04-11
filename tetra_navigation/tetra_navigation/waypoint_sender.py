import rclpy
import time

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped


def main():
    rclpy.init()

    nav = BasicNavigator()

    # Nav2 서버 활성화 대기
    nav.waitUntilNav2Active()

    # 목표 지점 리스트
    goal_poses = []

    # 목표 1
    gp1 = PoseStamped()
    gp1.header.frame_id = 'map'
    gp1.pose.position.x = 17.965
    gp1.pose.position.y = 3.610
    gp1.pose.position.z = 0.0
    gp1.pose.orientation.x = 0.0
    gp1.pose.orientation.y = 0.0
    gp1.pose.orientation.z = 1.000
    gp1.pose.orientation.w = -0.011
    goal_poses.append(gp1)

    # 목표 2 예시
    # gp2 = PoseStamped()
    # gp2.header.frame_id = 'map'
    # gp2.pose.position.x = 23.141
    # gp2.pose.position.y = -0.327
    # gp2.pose.position.z = 0.0
    # gp2.pose.orientation.x = 0.0
    # gp2.pose.orientation.y = 0.0
    # gp2.pose.orientation.z = 0.700
    # gp2.pose.orientation.w = 0.714
    # goal_poses.append(gp2)

    print('Tetra가 순차적 이동 및 정지 미션을 시작합니다...')

    for i, target_pose in enumerate(goal_poses):
        print(f'\n[이동] {i + 1}번 목표 지점으로 향하는 중...')

        # 현재 시간으로 stamp 갱신
        target_pose.header.stamp = nav.get_clock().now().to_msg()

        # 한 지점씩 이동
        nav.goToPose(target_pose)

        # 도착할 때까지 대기
        while not nav.isTaskComplete():
            feedback = nav.getFeedback()

            if feedback:
                print(
                    f'\r남은 거리: {feedback.distance_remaining:.2f} m',
                    end=''
                )

            time.sleep(0.1)

        print()  # 줄바꿈

        # 결과 확인
        result = nav.getResult()

        if result == TaskResult.SUCCEEDED:
            print(f'[도착] {i + 1}번 지점에 도착했습니다. 5초간 대기합니다...')
            time.sleep(5.0)

        elif result == TaskResult.CANCELED:
            print('[취소] 작업이 취소되었습니다.')
            break

        elif result == TaskResult.FAILED:
            print(f'[실패] {i + 1}번 지점 이동에 실패했습니다.')
            break

    print('\n모든 미션이 완료되었습니다.')

    rclpy.shutdown()


if __name__ == '__main__':
    main()