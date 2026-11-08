#!/usr/bin/env bash
# 지연(0, 20ms) × 조합 5가지 × 반복 3회를 측정해 logs 에 남긴다.
HERE=$(cd "$(dirname "$0")" && pwd)
LOG=$HERE/../report/logs
RAW=$LOG/raw; mkdir -p "$RAW"; rm -f "$RAW"/*.txt   # 이전 측정값과 섞이지 않게 비운다
OUT=$LOG/s2_matrix.txt; : > "$OUT"
REPS=${REPS:-3}
for delay in 0 20; do
  for combo in fast:fast cyclone:cyclone fast:cyclone cyclone:fast fast_udp:fast_udp; do
    a=${combo%:*}; b=${combo#*:}
    for r in $(seq 1 "$REPS"); do
      name=${a}_${b}_d${delay}
      env_args=(PING_RAW="$RAW/$name.txt")
      if [ "$a" = fast_udp ]; then
        env_args+=(FASTDDS_BUILTIN_TRANSPORTS=UDPv4); a2=fast; b2=fast
      else a2=$a; b2=$b; fi
      res=$(env "${env_args[@]}" "$HERE/netns.sh" "$delay" "$HERE/one_run.sh" "$a2" "$b2" 2>&1 | tail -1)
      echo "delay=${delay}ms ping=$a pong=$b run=$r $res" | tee -a "$OUT"
    done
  done
done
