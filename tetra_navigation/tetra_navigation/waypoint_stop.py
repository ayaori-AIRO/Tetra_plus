import rclpy
import time
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped
import subprocess

def main():
    rclpy.init()
    nav = BasicNavigator()

    # Nav2 서버 활성화 대기
    nav.waitUntilNav2Active()

    # 1. 첫 번째 목표 지점 정의
    gp1 = PoseStamped()
    gp1.header.frame_id = 'map'
    gp1.pose.position.x = 17.651343391534965
    gp1.pose.position.y = 3.061480262290648
    gp1.pose.orientation.z = 0.9999773599247862
    gp1.pose.orientation.w = 0.006729014627305277

    print('Tetra가 미션을 시작합니다...')

    # [1단계] 첫 번째 목표 지점으로 이동
    print('\n[이동] 1번 목표 지점으로 향하는 중...')
    gp1.header.stamp = nav.get_clock().now().to_msg()
    nav.goToPose(gp1)

    while not nav.isTaskComplete():
        pass

    result = nav.getResult()
    if result == TaskResult.SUCCEEDED:
        print('[도착] 1번 지점에 도착했습니다.')
        time.sleep(1.0)

        print('[서보] AprilTag visual servoing 시작...')
        servo_process = subprocess.Popen([
            'ros2', 'run', 'tetra_navigation', 'apriltag_servo',
            '--ros-args',
            '-p', 'tag_id:=9',
            '-p', 'target_distance:=0.15',
            '-p', 'stop_after_reached:=true'
        ])
        servo_result = servo_process.wait()

        if servo_result != 0:
            print(f'[실패] AprilTag visual servoing이 비정상 종료되었습니다. code={servo_result}')
            rclpy.shutdown()
            return

        print('[서보] 완료. 추가 후진 15cm 시작...')
        
        # backup 함수 사용: 
        # backup_dist: 후진 거리 (미터 단위, 양수로 입력하면 뒤로 갑니다)
        # backup_speed: 후진 속도 (m/s)
        # time_allowance: 제한 시간
        nav.backup(backup_dist=0.13, backup_speed=0.03, time_allowance=10)

        while not nav.isTaskComplete():
            pass

        if nav.getResult() == TaskResult.SUCCEEDED:
            print('[성공] 모든 이동 및 후진 미션을 완료했습니다!')
            time.sleep(5.0)
        else:
            print('[실패] 후진 이동 중 문제가 발생했습니다.')

    elif result == TaskResult.CANCELED:
        print('[취소] 작업이 취소되었습니다.')
    elif result == TaskResult.FAILED:
        print('[실패] 1번 지점 이동에 실패했습니다.')

    print('\n프로그램을 종료합니다.')
    rclpy.shutdown()

if __name__ == '__main__':
    main()
