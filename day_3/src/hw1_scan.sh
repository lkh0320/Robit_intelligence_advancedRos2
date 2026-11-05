#!/usr/bin/env bash
# 1단계 스캔 스크립트 (최종)
# 시도 1: 데몬 사용 → 도메인마다 데몬이 새로 떠서, 갓 뜬 데몬이 발견을 못 끝낸 채 답함 (79개 생성, 신호 누락)
# 시도 2: --no-daemon 만 → 대기 시간이 너무 짧아 아무 토픽도 못 봄
# 최종  : --no-daemon + --spin-time 4 (SPDP→SEDP 발견을 기다림), 15개씩 병렬로 시간 단축
SPIN=${SPIN:-4}
scan_one() {
  local d=$1 topics
  topics=$(ROS_DOMAIN_ID=$d ros2 topic list --no-daemon --spin-time "$SPIN" 2>/dev/null | grep '^/bb_')
  [ -n "$topics" ] && echo "$topics" | sed "s/^/domain $d  /"
}
for d in $(seq 10 95); do
  scan_one "$d" &
  (( d % 15 == 0 )) && wait
done
wait
