#!/usr/bin/env bash
# 전용 네트워크 네임스페이스 안에서 명령을 실행한다. 지연이 이 네임스페이스의 lo 에만
# 걸려서 PC 의 다른 통신에는 영향이 없다. 명령이 끝나면 네임스페이스가 사라지므로
# netem 도 함께 해제된다.
# Ubuntu 24.04 는 일반 터미널의 비특권 네임스페이스를 막아 두었다. 그때는 sudo 로
# 네임스페이스만 만들고, 측정 프로그램은 다시 내 계정으로 실행한다.
# 사용법: netns.sh <지연ms, 0이면 없음> <명령...>
set -e
DELAY_MS=$1; shift

SETUP='
  ip link set lo up
  ip link set lo multicast on
  ip route add 224.0.0.0/4 dev lo
  if [ "$0" != 0 ]; then tc qdisc add dev lo root netem delay "${0}ms"; fi
'

if unshare -Urn true 2>/dev/null; then
  exec unshare -Urn bash -c "$SETUP"'
  exec "$@"
' "$DELAY_MS" "$@"
fi

KEEP=PING_N,PING_WARMUP,PING_PAD,PING_RAW,ROS_DOMAIN_ID,FASTDDS_BUILTIN_TRANSPORTS
exec sudo --preserve-env="$KEEP" unshare -n env \
  RUN_UID="$(id -u)" RUN_GID="$(id -g)" RUN_HOME="$HOME" \
  bash -c "$SETUP"'
  export HOME=$RUN_HOME
  exec setpriv --reuid="$RUN_UID" --regid="$RUN_GID" --init-groups \
    --inh-caps=+net_raw --ambient-caps=+net_raw "$@"
' "$DELAY_MS" "$@"
