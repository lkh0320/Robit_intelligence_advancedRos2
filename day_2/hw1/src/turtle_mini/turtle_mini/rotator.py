"""/{turtle_name}/rotate_absolute 액션 클라이언트."""
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from turtlesim.action import RotateAbsolute


class Rotator(Node):

    def __init__(self):
        super().__init__('rotator')
        self.theta = float(self.declare_parameter('theta', 1.57).value)
        self.turtle_name = self.declare_parameter('turtle_name', 'turtle1').value
        self.client = ActionClient(
            self, RotateAbsolute, f'/{self.turtle_name}/rotate_absolute')

    def send_goal(self):
        self.get_logger().info('액션 서버 대기 중...')
        self.client.wait_for_server()

        goal = RotateAbsolute.Goal()
        goal.theta = self.theta
        self.get_logger().info(f'goal 전송: {self.turtle_name} theta={self.theta:.3f}')
        future = self.client.send_goal_async(goal, feedback_callback=self.on_feedback)
        future.add_done_callback(self.on_goal_response)

    def on_goal_response(self, future):
        handle = future.result()
        if not handle.accepted:
            self.get_logger().error('goal 거부됨')
            rclpy.try_shutdown()
            return
        self.get_logger().info('goal 수락됨')
        handle.get_result_async().add_done_callback(self.on_result)

    def on_feedback(self, feedback_msg):
        self.get_logger().info(f'feedback: remaining={feedback_msg.feedback.remaining:.3f}')

    def on_result(self, future):
        result = future.result().result
        self.get_logger().info(f'result: delta={result.delta:.3f}')
        rclpy.try_shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = Rotator()
    node.send_goal()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
