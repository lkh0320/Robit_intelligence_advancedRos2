#!/usr/bin/env bash
# PC A 에서 실행한다. PC B 에는 friend_pong.sh 가 떠 있어야 한다.
# 사용법: two_pc_run.sh <인터페이스> <PC B 의 IP>
# netem 은 이 PC 의 해당 인터페이스 전체에 걸린다. 끝나거나 Ctrl+C 로 멈추면 자동으로 해제한다.
# PC A 에서 나가는 방향에만 걸리므로 delay 20ms 는 왕복으로 20ms 늘어난다.
HERE=$(cd "$(dirname "$0")" && pwd)
IF=$1; PEER=$2
LOG=${LOG_DIR:-$HERE/../report/logs}
RAW=$LOG/raw_two_pc; mkdir -p "$RAW"
OUT=$LOG/s5_two_pc_matrix.txt; : > "$OUT"
REPS=${REPS:-3}
SUDO=${SUDO-sudo}
set +u; source /opt/ros/jazzy/setup.bash

$SUDO true || exit 1
clear_netem() { $SUDO tc qdisc del dev "$IF" root 2>/dev/null; }
trap 'clear_netem; exit' INT TERM
trap clear_netem EXIT
clear_netem

{ echo "# $(date '+%F %T') iface=$IF peer=$PEER"
  ping -c 20 -q "$PEER" | tail -1; } | tee -a "$OUT"

for cond in none 'delay 20ms' 'loss 5%'; do
  clear_netem
  if [ "$cond" != none ]; then $SUDO tc qdisc add dev "$IF" root netem $cond || exit 1; fi
  for combo in fast:45:fast fast:46:cyclone cyclone:45:fast cyclone:46:cyclone; do
    IFS=: read -r mine dom pong <<< "$combo"
    [ "$mine" = fast ] && rmw=rmw_fastrtps_cpp || rmw=rmw_cyclonedds_cpp
    for r in $(seq 1 "$REPS"); do
      res=$(ROS_DOMAIN_ID=$dom RMW_IMPLEMENTATION=$rmw PING_RAW="$RAW/${mine}_${pong}_${cond// /_}.txt" \
            timeout 60 python3 "$HERE/ping.py" 2>&1 | tail -1)
      echo "netem=${cond// /_} ping=$mine pong=$pong run=$r $res" | tee -a "$OUT"
    done
  done
done
clear_netem
echo "끝. 현재 $IF 설정: $(tc qdisc show dev "$IF" | head -1)"
