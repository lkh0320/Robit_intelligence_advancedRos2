"""TF로 leader의 상대 위치를 구해 follower 거북이가 따라가게 하는 노드.

solution 대비 추가한 파라미터
  - max_lin_vel, max_ang_vel : 속도 상한
  - stop_distance            : 이 거리 안이면 멈춤 (겹치지 않게)
  - leader_frame, follower_frame : 따라갈 대상 / 움직일 거북이 (read only)
  - spawn_x, spawn_y, spawn_theta : follower 생성 위치 (read only)
  - control_rate             : 제어 주기 [Hz]
read only 가 아닌 값은 ros2 param set 으로 실행 중에 바로 바뀐다.
"""
import math

from geometry_msgs.msg import Twist
from rcl_interfaces.msg import ParameterDescriptor, SetParametersResult
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from turtlesim.srv import Spawn


def clamp(value, limit):
    return max(-limit, min(limit, value))


class TurtleFollower(Node):

    # 실행 중 바꿀 수 있는 값
    TUNABLE = ('k_ang', 'k_lin', 'max_lin_vel', 'max_ang_vel', 'stop_distance', 'control_rate')

    def __init__(self):
        super().__init__('turtle_follower')
        self.k_ang = self.declare_parameter('k_ang', 1.0).value
        self.k_lin = self.declare_parameter('k_lin', 0.5).value
        self.max_lin_vel = self.declare_parameter('max_lin_vel', 2.0).value
        self.max_ang_vel = self.declare_parameter('max_ang_vel', 3.0).value
        self.stop_distance = self.declare_parameter('stop_distance', 1.0).value
        self.control_rate = self.declare_parameter('control_rate', 10.0).value

        read_only = ParameterDescriptor(read_only=True)
        self.leader = self.declare_parameter('leader_frame', 'turtle1', read_only).value
        self.follower = self.declare_parameter('follower_frame', 'turtle2', read_only).value
        self.spawn_x = self.declare_parameter('spawn_x', 4.0, read_only).value
        self.spawn_y = self.declare_parameter('spawn_y', 2.0, read_only).value
        self.spawn_theta = self.declare_parameter('spawn_theta', 0.0, read_only).value

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.publisher = self.create_publisher(Twist, f'/{self.follower}/cmd_vel', 10)

        # 시작 시 follower가 없으면 /spawn으로 생성
        self.spawner = self.create_client(Spawn, '/spawn')
        self.spawn_future = None
        self.turtle_spawned = False

        self.timer = self.create_timer(1.0 / self.control_rate, self.on_timer)
        self.add_on_set_parameters_callback(self.on_set_parameters)

        self.get_logger().info(
            f'{self.follower} -> {self.leader} 추종 시작 '
            f'(k_ang={self.k_ang}, k_lin={self.k_lin}, stop={self.stop_distance} m, '
            f'{self.control_rate} Hz)')

    def on_set_parameters(self, params):
        """ros2 param set 으로 들어온 값을 검사하고 바로 반영."""
        for p in params:
            if p.name not in self.TUNABLE:
                continue
            # stop_distance 만 0 허용 (끝까지 붙어서 따라감)
            if p.value < 0.0 or (p.value == 0.0 and p.name != 'stop_distance'):
                return SetParametersResult(successful=False, reason=f'{p.name} 값이 잘못됨: {p.value}')

        for p in params:
            if p.name not in self.TUNABLE:
                continue
            setattr(self, p.name, float(p.value))
            if p.name == 'control_rate':
                # 주기가 바뀌면 타이머를 새로 만든다
                self.timer.cancel()
                self.destroy_timer(self.timer)
                self.timer = self.create_timer(1.0 / self.control_rate, self.on_timer)
            self.get_logger().info(f'파라미터 변경: {p.name} = {p.value}')
        return SetParametersResult(successful=True)

    def ensure_follower(self):
        """follower 거북이가 준비됐으면 True. 없으면 /spawn 요청."""
        if self.turtle_spawned:
            return True

        if self.spawn_future is None:
            # 이미 있으면 (예: 다른 노드가 생성) 그대로 사용
            if self.count_publishers(f'/{self.follower}/pose') > 0:
                self.get_logger().info(f'{self.follower}가 이미 존재함')
                self.turtle_spawned = True
                return True
            if not self.spawner.service_is_ready():
                self.get_logger().info('/spawn 서비스 대기 중...', throttle_duration_sec=2.0)
                return False
            req = Spawn.Request()
            req.name = self.follower
            req.x = float(self.spawn_x)
            req.y = float(self.spawn_y)
            req.theta = float(self.spawn_theta)
            self.spawn_future = self.spawner.call_async(req)
            return False

        if self.spawn_future.done():
            try:
                res = self.spawn_future.result()
                self.get_logger().info(
                    f'{res.name} 생성 완료 ({self.spawn_x}, {self.spawn_y})')
            except Exception as e:  # 이미 있는 이름이면 서비스가 에러를 반환
                self.get_logger().warn(f'spawn 실패(이미 존재할 수 있음): {e}')
            self.turtle_spawned = True
            return True
        return False

    def on_timer(self):
        if not self.ensure_follower():
            return

        try:
            # follower 기준으로 leader가 어디 있나
            t = self.tf_buffer.lookup_transform(self.follower, self.leader, Time())
        except TransformException as ex:
            self.get_logger().info(
                f'{self.follower} <- {self.leader} TF 대기 중: {ex}', throttle_duration_sec=2.0)
            return

        x = t.transform.translation.x
        y = t.transform.translation.y
        distance = math.sqrt(x ** 2 + y ** 2)

        msg = Twist()
        if distance > self.stop_distance:
            # 멈춤 거리를 뺀 만큼만 다가가서 leader와 겹치지 않게
            msg.angular.z = clamp(self.k_ang * math.atan2(y, x), self.max_ang_vel)
            msg.linear.x = clamp(self.k_lin * (distance - self.stop_distance), self.max_lin_vel)
        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TurtleFollower()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
