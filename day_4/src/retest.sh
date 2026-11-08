#!/usr/bin/env bash
# Cyclone -> Fast 가 2회차부터 느려지는 원인을 가린다. netem 은 걸지 않는다.
#   1. 실행 사이 간격을 늘리면 사라지는가 (앞 실행의 정보가 남아서인가)
#   2. pong 메시지가 멀티캐스트로 오는가 (in_multi 가 0 보다 큰가)
# 먼저 PC B 에서 friend_pong.sh 를 새로 띄운 뒤 실행한다.
# 사용법: retest.sh <인터페이스> <PC B 의 IP>   (약 6분)
HERE=$(cd "$(dirname "$0")" && pwd)
IF=$1; PEER=$2
LOG=${LOG_DIR:-$HERE/../report/logs}
OUT=$LOG/s7_retest.txt; : > "$OUT"
SUDO=${SUDO-sudo -n}
GAPS=${GAPS:-0:4 15:3 60:3}
TMP=$(mktemp -d)
trap 'touch "$TMP/stop"; rm -rf "$TMP"' EXIT
set +u; source /opt/ros/jazzy/setup.bash
[ -z "$SUDO" ] || sudo -v || exit 1

one() {  # one <ping RMW 이름> <도메인> <pong 이름> <라벨>
  local mine=$1 dom=$2 pong=$3 label=$4 rmw=rmw_cyclonedds_cpp res
  [ "$mine" = fast ] && rmw=rmw_fastrtps_cpp
  rm -f "$TMP/stop" "$TMP/sn"
  $SUDO env SNIFF_IFACE="$IF" SNIFF_STOP="$TMP/stop" python3 -I "$HERE/sniff.py" > "$TMP/sn" < /dev/null &
  local sn=$!
  until grep -q ready "$TMP/sn" 2>/dev/null; do sleep 0.1; done
  res=$(ROS_DOMAIN_ID=$dom RMW_IMPLEMENTATION=$rmw PING_PAD=200 timeout 60 python3 "$HERE/ping.py" 2>&1 | tail -1)
  touch "$TMP/stop"; wait "$sn" 2>/dev/null
  echo "$label ping=$mine pong=$pong $res | $(tail -1 "$TMP/sn")" | tee -a "$OUT"
}

echo "# $(date '+%F %T') iface=$IF peer=$PEER" | tee -a "$OUT"
for g in $GAPS; do
  gap=${g%:*}; n=${g#*:}
  for r in $(seq 1 "$n"); do
    sleep "$gap"
    one cyclone 45 fast "gap=${gap}s run=$r"
  done
done
for r in 1 2 3; do one fast 45 fast "control run=$r"; done
for r in 1 2 3; do one cyclone 46 cyclone "control run=$r"; done
for r in 1 2 3; do one fast 46 cyclone "control run=$r"; done
[ -z "$SUDO" ] || sudo -k
echo "끝. 기록: $OUT"
