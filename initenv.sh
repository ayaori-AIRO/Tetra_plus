#!/bin/bash
set -e

RULE_FILE="/etc/udev/rules.d/tetra_motor.rules"

rm -f \
  /etc/udev/rules.d/tetra_motor.rules \
  /etc/udev/rules.d/tetra_motor0.rules \
  /etc/udev/rules.d/tetra_motor1.rules \
  /etc/udev/rules.d/tetra_power.rules

{
  echo '# TETRA motor USB serial rules.'
  echo '# /dev/ttyUSB0: ID_PATH=pci-0000:00:14.0-usb-0:4.3:1.0'
  echo 'SUBSYSTEM=="tty", ENV{ID_PATH}=="pci-0000:00:14.0-usb-0:4.3:1.0", MODE="0666", GROUP="dialout", SYMLINK+="tetra/motor", SYMLINK+="tetra/motor0"'
  echo '# /dev/ttyUSB1: ID_PATH=pci-0000:00:14.0-usb-0:4.4.1:1.0'
  echo 'SUBSYSTEM=="tty", ENV{ID_PATH}=="pci-0000:00:14.0-usb-0:4.4.1:1.0", MODE="0666", GROUP="dialout", SYMLINK+="tetra/motor1"'
} >"${RULE_FILE}"

udevadm control --reload-rules
udevadm trigger --subsystem-match=tty
sleep 1

echo "Generated motor rules:"
cat "${RULE_FILE}"
echo
echo "Current motor links:"
ls -l /dev/tetra/motor /dev/tetra/motor0 /dev/tetra/motor1 2>/dev/null || true
