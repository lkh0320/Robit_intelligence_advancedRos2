"""받은 /ping 을 그대로 /pong 으로 되돌린다."""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String


class Pong(Node):
    def __init__(self):
        super().__init__('pong')
        self.pub = self.create_publisher(String, '/pong', 10)
        self.create_subscription(String, '/ping', self.pub.publish, 10)


rclpy.init()
try:
    rclpy.spin(Pong())
except (KeyboardInterrupt, ExternalShutdownException):
    pass
