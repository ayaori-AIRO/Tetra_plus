import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import FollowWaypoints
from rclpy.action import ActionClient
import tf_transformations  # quaternion 변환

class WaypointClient(Node):
    def __init__(self):
        super().__init__('waypoint_client')
        self._client = ActionClient(self, FollowWaypoints, 'FollowWaypoints')

    def send_waypoints(self, waypoints):
        self._client.wait_for_server()
        goal_msg = FollowWaypoints.Goal()
        goal_msg.poses = waypoints
        self.get_logger().info('Sending waypoints with orientation...')
        self._client.send_goal_async(goal_msg)

def create_pose(x, y, yaw_deg):
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.pose.position.x = x
    pose.pose.position.y = y
    pose.pose.position.z = 0.0
    yaw_rad = yaw_deg * 3.14159265 / 180.0
    q = tf_transformations.quaternion_from_euler(0, 0, yaw_rad)
    pose.pose.orientation.x = q[0]
    pose.pose.orientation.y = q[1]
    pose.pose.orientation.z = q[2]
    pose.pose.orientation.w = q[3]
    return pose

def main():
    rclpy.init()
    node = WaypointClient()

    waypoints = [
        create_pose(5.642, -0.751, 45),    # 첫번째 목표
        create_pose(12.080, 0.035, -30)    # 두번째 목표
    ]

    node.send_waypoints(waypoints)
    rclpy.spin(node)

if __name__ == '__main__':
    main()