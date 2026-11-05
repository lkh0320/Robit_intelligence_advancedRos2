#!/usr/bin/env python3
"""2단계 구독 노드: config(늦게 와도 받기) + stream(흘러가는 값) 두 토픽 구독.

ros2 topic info -v 로 확인한 발행자 QoS
  /bb_3868/config : RELIABLE   + TRANSIENT_LOCAL
  /bb_3868/stream : BEST_EFFORT + VOLATILE
구독자는 발행자가 제공하는 것 이하만 요구해야 매칭된다 (RxO 규칙).
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_msgs.msg import String

# 이미 발행된 마지막 값을 받으려면 TRANSIENT_LOCAL 이 필요하다.
# (기본 VOLATILE 구독은 내가 접속하기 전에 나간 config 를 영영 못 받는다)
CONFIG_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

# 발행자가 BEST_EFFORT 이므로 구독자가 RELIABLE 을 요구하면 매칭되지 않는다.
# (기본값 RELIABLE 구독은 "incompatible QoS" 로 아무것도 못 받는다)
STREAM_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)


class BbSub(Node):
    def __init__(self):
        super().__init__('lkh_bb_sub')
        self.create_subscription(String, '/bb_3868/config', self.on_config, CONFIG_QOS)
        self.create_subscription(String, '/bb_3868/stream', self.on_stream, STREAM_QOS)

    def on_config(self, msg):
        self.get_logger().info(f'[config] {msg.data}')

    def on_stream(self, msg):
        self.get_logger().info(f'[stream] {msg.data}')


def main():
    rclpy.init()
    node = BbSub()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
