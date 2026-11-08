#!/usr/bin/env bash
# 두 PC 지연 측정을 도와주는 사람이 실행하는 파일. 이 파일 하나만 있으면 된다.
#   실행: bash friend_pong.sh
#   종료: Ctrl+C
# 받은 메시지를 되돌려 주기만 하고, 설정 파일이나 네트워크 설정은 바꾸지 않는다.
set -u

if [ ! -f /opt/ros/jazzy/setup.bash ]; then
  echo "ROS 2 Jazzy 를 찾지 못했습니다 (/opt/ros/jazzy). 먼저 설치해 주세요."
  exit 1
fi
set +u; source /opt/ros/jazzy/setup.bash; set -u

if ! ros2 pkg prefix rmw_cyclonedds_cpp >/dev/null 2>&1; then
  read -r -p "Cyclone DDS 패키지가 없습니다. 지금 설치할까요? [y/N] " yn
  if [ "$yn" = y ] || [ "$yn" = Y ]; then
    sudo apt install -y ros-jazzy-rmw-cyclonedds-cpp || exit 1
  else
    echo "Cyclone 없이는 측정할 수 없어 종료합니다."; exit 1
  fi
fi

unset ROS_LOCALHOST_ONLY ROS_AUTOMATIC_DISCOVERY_RANGE ROS_STATIC_PEERS CYCLONEDDS_URI FASTRTPS_DEFAULT_PROFILES_FILE

WORK=$(mktemp -d)
cat > "$WORK/pong.py" <<'PY'
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
PY

ROS_DOMAIN_ID=45 RMW_IMPLEMENTATION=rmw_fastrtps_cpp python3 "$WORK/pong.py" &
FAST=$!
ROS_DOMAIN_ID=46 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp python3 "$WORK/pong.py" &
CYC=$!
# 스크립트의 백그라운드 프로세스는 SIGINT 를 무시하므로 TERM 으로 끝낸다
trap 'kill -TERM $FAST $CYC 2>/dev/null; wait 2>/dev/null; rm -rf "$WORK"; echo 종료했습니다.; exit 0' INT TERM
sleep 2

if command -v ufw >/dev/null && LC_ALL=C sudo -n ufw status 2>/dev/null | grep -q 'Status: active'; then
  echo "주의: 방화벽(ufw)이 켜져 있습니다. 연결이 안 되면 sudo ufw disable 후 측정이 끝나면 sudo ufw enable 하세요."
fi

echo
echo "준비 완료. 아래 IP 를 측정하는 사람에게 알려 주세요."
ip -br -4 addr | grep -v '^lo' | awk '$2=="UP" {print "  " $1 "  " $3}'
echo
echo "측정이 끝날 때까지 이 창을 그대로 두세요. 끝나면 Ctrl+C."
wait
