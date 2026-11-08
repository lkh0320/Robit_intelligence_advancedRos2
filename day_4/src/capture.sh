#!/usr/bin/env bash
# lo 를 지나는 패킷을 세면서 ping/pong 을 돌린다. netns.sh 안에서 실행한다.
# 사용법: netns.sh 0 ./capture.sh <ping쪽> <pong쪽>
HERE=$(cd "$(dirname "$0")" && pwd)
python3 "$HERE/sniff.py" > /tmp/sniff.$$ &
SN=$!
until grep -q ready /tmp/sniff.$$ 2>/dev/null; do sleep 0.1; done
PING_PAD=200 "$HERE/one_run.sh" "$1" "$2"
sleep 0.5
kill -TERM $SN; wait $SN
grep -v ready /tmp/sniff.$$
rm -f /tmp/sniff.$$
