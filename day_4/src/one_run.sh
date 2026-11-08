#!/usr/bin/env bash
# ping/pong 1회 측정. 사용법: one_run.sh <ping쪽 fast|cyclone> <pong쪽 fast|cyclone>
HERE=$(cd "$(dirname "$0")" && pwd)
set +u; source /opt/ros/jazzy/setup.bash
rmw() { [ "$1" = fast ] && echo rmw_fastrtps_cpp || echo rmw_cyclonedds_cpp; }
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-44}
RMW_IMPLEMENTATION=$(rmw "$2") python3 "$HERE/pong.py" &
PONG=$!
RMW_IMPLEMENTATION=$(rmw "$1") timeout 60 python3 "$HERE/ping.py"
RC=$?
kill -INT $PONG 2>/dev/null; wait $PONG 2>/dev/null
exit $RC
