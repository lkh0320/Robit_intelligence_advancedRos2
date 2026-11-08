"""RTT 측정 노드. /ping 으로 보내고 pong.py 가 되돌린 /pong 을 받아 왕복 시간을 잰다.

수업 ping.py 에서 두 가지만 바꿨다.
- 탐침이 왕복할 때까지 기다린 뒤 측정한다 (발견이 늦어서 생기는 가짜 손실 방지).
- 앞쪽 WARMUP 개는 통계에서 뺀다 (연결 직후 튀는 값 제외).
"""
import os
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

N = int(os.environ.get('PING_N', '100'))
WARMUP = int(os.environ.get('PING_WARMUP', '10'))
PAD = int(os.environ.get('PING_PAD', '0'))
RAW = os.environ.get('PING_RAW')
TOTAL = N + WARMUP
CONNECT_TIMEOUT = 20.0


class Ping(Node):
    def __init__(self):
        super().__init__('ping')
        self.pub = self.create_publisher(String, '/ping', 10)
        self.create_subscription(String, '/pong', self.on_pong, 10)
        self.seq, self.rtts = 0, {}
        self.pad = 'x' * PAD
        self.t_start = time.monotonic()
        self.connected = False
        self.create_timer(0.05, self.send)

    def send(self):
        if not self.connected:
            if time.monotonic() - self.t_start > CONNECT_TIMEOUT:
                print('no peer: 연결 실패', flush=True)
                rclpy.shutdown()
                return
            self.pub.publish(String(data=f'-1,{time.monotonic()},'))  # 탐침
            return
        if self.seq >= TOTAL:
            return
        self.pub.publish(String(data=f'{self.seq},{time.monotonic()},{self.pad}'))
        self.seq += 1
        if self.seq == TOTAL:
            self.create_timer(3.0, self.report)

    def on_pong(self, msg):
        seq, t0, _ = msg.data.split(',')
        if int(seq) < 0:  # 탐침이 돌아왔다 = 왕복 경로가 모두 연결됐다
            if not self.connected:
                self.connected = True
                self.connect_s = time.monotonic() - self.t_start
            return
        self.rtts[int(seq)] = (time.monotonic() - float(t0)) * 1000

    def report(self):
        kept = [self.rtts[s] for s in range(WARMUP, TOTAL) if s in self.rtts]
        v = sorted(kept)
        if v:
            p95 = v[int(0.95 * (len(v) - 1))]
            print(f'recv {len(v)}/{N} loss {100 * (N - len(v)) / N:.1f}% '
                  f'mean {sum(v) / len(v):.2f}ms p50 {v[len(v) // 2]:.2f}ms '
                  f'p95 {p95:.2f}ms max {v[-1]:.2f}ms connect {self.connect_s:.2f}s',
                  flush=True)
            if RAW:
                with open(RAW, 'a') as f:
                    f.write('\n'.join(f'{x:.3f}' for x in kept) + '\n')
        else:
            print('no reply', flush=True)
        rclpy.shutdown()


rclpy.init()
try:
    rclpy.spin(Ping())
except (KeyboardInterrupt, ExternalShutdownException):
    pass
