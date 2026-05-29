#!/usr/bin/env bash
set -eo pipefail

LOG_DIR="/tmp/tetra_autostart_logs"
mkdir -p "${LOG_DIR}"
exec >> "${LOG_DIR}/robot_bringup_proto_autostart.log" 2>&1

echo
echo "========== $(date '+%Y-%m-%d %H:%M:%S %Z') =========="

echo "[tetra-autostart] waiting for NetworkManager online..."
if command -v nm-online >/dev/null 2>&1; then
  nm-online -q --timeout=120 || echo "[tetra-autostart] nm-online timeout; continuing"
fi

if command -v udevadm >/dev/null 2>&1; then
  echo "[tetra-autostart] waiting for udev settle..."
  udevadm settle --timeout=60 || echo "[tetra-autostart] udev settle timeout; continuing"
fi

for device in /dev/tetra/lidar /dev/tetra/motor /dev/tetra/neopixel; do
  echo "[tetra-autostart] waiting for ${device}..."
  for _ in $(seq 1 60); do
    if [ -e "${device}" ]; then
      break
    fi
    sleep 1
  done
  if [ ! -e "${device}" ]; then
    echo "[tetra-autostart] warning: ${device} not found before launch"
  fi
done

echo "[tetra-autostart] allowing USB devices to stabilize..."
sleep 5

echo "[tetra-autostart] sourcing ROS environment"
source /opt/ros/humble/setup.bash
source /home/ayaori/ros2_ws/install/setup.bash

cd /home/ayaori/ros2_ws/src/tetra

echo "[tetra-autostart] launching robot_bringup_proto"
exec ros2 launch tetra_navigation robot_bringup_proto.launch.py mission_autostart:=true rviz:=false
