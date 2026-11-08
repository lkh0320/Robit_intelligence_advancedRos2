#!/usr/bin/env bash
# PC A 에서 측정 전에 실행한다. 사용법: two_pc_check.sh <PC B 의 IP>
HERE=$(cd "$(dirname "$0")" && pwd)
PEER=$1
set +u; source /opt/ros/jazzy/setup.bash
echo "== 환경"
echo "ROS_LOCALHOST_ONLY=$ROS_LOCALHOST_ONLY ROS_AUTOMATIC_DISCOVERY_RANGE=$ROS_AUTOMATIC_DISCOVERY_RANGE ROS_STATIC_PEERS=$ROS_STATIC_PEERS"
ip -br -4 addr | grep -v '^lo'
echo "peer 로 가는 인터페이스: $(ip -o route get "$PEER" | sed -E 's/.* dev ([^ ]+).*/\1/')"
echo "== ICMP ping"
ping -c 5 -q "$PEER" | tail -2
echo "== ROS (각 20개, 안 되면 20초 뒤 no peer)"
for pong in 45:fast 46:cyclone; do
  for mine in rmw_fastrtps_cpp rmw_cyclonedds_cpp; do
    printf '%-20s -> %-8s ' "$mine" "${pong#*:}"
    ROS_DOMAIN_ID=${pong%:*} RMW_IMPLEMENTATION=$mine PING_N=20 timeout 40 python3 "$HERE/ping.py" 2>&1 | tail -1
  done
done
