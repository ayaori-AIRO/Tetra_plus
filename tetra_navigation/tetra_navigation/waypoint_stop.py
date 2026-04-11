import rclpy
import time
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped

def main():
    rclpy.init()
    nav = BasicNavigator()

    # Nav2 서버 활성화 대기
    nav.waitUntilNav2Active()

    # 1. 첫 번째 목표 지점 정의
    gp1 = PoseStamped()
    gp1.header.frame_id = 'map'
    gp1.pose.position.x = 17.965
    gp1.pose.position.y = 3.610
    gp1.pose.orientation.z = 1.000
    gp1.pose.orientation.w = -0.011

    print('Tetra가 미션을 시작합니다...')

    # [1단계] 첫 번째 목표 지점으로 이동
    print('\n[이동] 1번 목표 지점으로 향하는 중...')
    gp1.header.stamp = nav.get_clock().now().to_msg()
    nav.goToPose(gp1)

    while not nav.isTaskComplete():
        pass

    result = nav.getResult()
    if result == TaskResult.SUCCEEDED:
        print('[도착] 1번 지점에 도착했습니다. 5초간 대기합니다...')
        time.sleep(5.0)

        # [2단계] 뒤로 슬쩍 물러나기 (backUp 활용)
        print('\n[이동] 이제 직선 후진으로 0.968m 이동합니다...')
        
        # backup 함수 사용: 
        # backup_dist: 후진 거리 (미터 단위, 양수로 입력하면 뒤로 갑니다)
        # backup_speed: 후진 속도 (m/s)
        # time_allowance: 제한 시간
        nav.backup(backup_dist=1.1, backup_speed=0.05, time_allowance=20)

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