"""turtlesim Pose를 구독해 {parent_frame} -> {turtlename} TF를 발행하는 노드."""
import math

from geometry_msgs.msg import TransformStamped
import rclpy
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from turtlesim.msg import Pose


class PoseBroadcaster(Node):

    def __init__(self):
        super().__init__('pose_broadcaster')
        self.turtlename = self.declare_parameter('turtlename', 'turtle1').value
        self.parent_frame = self.declare_parameter('parent_frame', 'world').value
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_subscription(
            Pose, f'/{self.turtlename}/pose', self.handle_pose, 10)
        self.get_logger().info(f'{self.parent_frame} -> {self.turtlename} TF 발행 시작')

    def handle_pose(self, msg: Pose):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = self.parent_frame
        t.child_frame_id = self.turtlename

        # turtlesim은 2D: z = 0
        t.transform.translation.x = msg.x
        t.transform.translation.y = msg.y
        t.transform.translation.z = 0.0

        # yaw만 있는 쿼터니언
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = math.sin(msg.theta / 2.0)
        t.transform.rotation.w = math.cos(msg.theta / 2.0)

        self.tf_broadcaster.sendTransform(t)


def main(args=None):
    rclpy.init(args=args)
    node = PoseBroadcaster()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
