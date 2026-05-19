#!/bin/bash
set -e

RULE_FILE="/etc/udev/rules.d/tetra_motor.rules"

rm -f \
  /etc/udev/rules.d/tetra_motor.rules \
  /etc/udev/rules.d/tetra_motor0.rules \
  /etc/udev/rules.d/tetra_motor1.rules \
  /etc/udev/rules.d/tetra_lidar.rules \
  /etc/udev/rules.d/tetra_power.rules

{
  echo '# TETRA USB serial rules.'
  echo '# /dev/tetra/motor, /dev/tetra/motor0: ID_PATH=pci-0000:00:14.0-usb-0:4.3:1.0'
  echo 'SUBSYSTEM=="tty", ENV{ID_PATH}=="pci-0000:00:14.0-usb-0:4.3:1.0", MODE="0666", GROUP="dialout", SYMLINK+="tetra/motor", SYMLINK+="tetra/motor0"'
  echo '# /dev/tetra/motor1: ID_PATH=pci-0000:00:14.0-usb-0:4.4.1:1.0'
  echo 'SUBSYSTEM=="tty", ENV{ID_PATH}=="pci-0000:00:14.0-usb-0:4.4.1:1.0", MODE="0666", GROUP="dialout", SYMLINK+="tetra/motor1"'
  echo '# /dev/tetra/lidar: ID_PATH=pci-0000:00:14.0-usb-0:4.1:1.0'
  echo 'SUBSYSTEM=="tty", ENV{ID_PATH}=="pci-0000:00:14.0-usb-0:4.1:1.0", MODE="0666", GROUP="dialout", SYMLINK+="tetra/lidar"'
} >"${RULE_FILE}"

udevadm control --reload-rules
udevadm trigger --subsystem-match=tty
sleep 1

echo "Generated TETRA USB serial rules:"
cat "${RULE_FILE}"
echo
echo "Current TETRA links:"
ls -l /dev/tetra/motor /dev/tetra/motor0 /dev/tetra/motor1 /dev/tetra/lidar 2>/dev/null || true
