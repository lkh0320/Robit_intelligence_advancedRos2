#!/usr/bin/env bash
# PC 한 대에서 조합별로 메시지가 UDP 로 지나가는지 센다. 결과는 logs/s3_packet_count.txt (약 1분)
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/../report/logs/s3_packet_count.txt; : > "$OUT"
cd "$HERE"
run() { echo "\$ $*" | tee -a "$OUT"; env "$@" 2>&1 | grep -E '^(recv|UDP|no )' | tee -a "$OUT"; }
for c in fast:fast fast:cyclone cyclone:fast cyclone:cyclone; do
  run PING_N=100 ./netns.sh 0 ./capture.sh "${c%:*}" "${c#*:}"
done
run FASTDDS_BUILTIN_TRANSPORTS=UDPv4 PING_N=100 ./netns.sh 0 ./capture.sh fast fast
