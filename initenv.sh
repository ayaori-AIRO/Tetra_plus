#!/bin/bash
set -e

RULE_FILE="/etc/udev/rules.d/tetra_motor.rules"
ST3235_BALLSCREW_SOURCE="${TETRA_ST3235_BALLSCREW_SOURCE:-/dev/ttyUSB3}"
ST3235_BALLSCREW_LINK="tetra/st3235_ballscrew"
ST3235_BALLSCREW_ID_PATH="${TETRA_ST3235_BALLSCREW_ID_PATH:-pci-0000:00:14.0-usb-0:8.1:1.0}"
NEOPIXEL_SOURCE="${TETRA_NEOPIXEL_SOURCE:-/dev/ttyACM0}"
NEOPIXEL_LINK="tetra/neopixel"
TOP_CAMERA_SERIAL="1B7AD4BF"
BOTTOM_CAMERA_SERIAL="E06DE4BF"

make_tty_rule() {
  local source_device="$1"
  local symlink_name="$2"
  local description="$3"
  local id_path

  id_path="$(udevadm info --query=property --name="${source_device}" 2>/dev/null | sed -n 's/^ID_PATH=//p' | head -n 1)"

  echo "# ${description}"
  if [ -n "${id_path}" ]; then
    echo "# ${source_device}: ID_PATH=${id_path}"
    echo "SUBSYSTEM==\"tty\", ENV{ID_PATH}==\"${id_path}\", MODE=\"0666\", GROUP=\"dialout\", SYMLINK+=\"${symlink_name}\""
  else
    echo "# ${source_device}: ID_PATH not available while generating rules; falling back to kernel name."
    echo "SUBSYSTEM==\"tty\", KERNEL==\"$(basename "${source_device}")\", MODE=\"0666\", GROUP=\"dialout\", SYMLINK+=\"${symlink_name}\""
  fi
}

make_video_rule() {
  local serial_short="$1"
  local symlink_name="$2"
  local description="$3"

  echo "# ${description}"
  echo "# ID_SERIAL_SHORT=${serial_short}"
  echo "SUBSYSTEM==\"video4linux\", ENV{ID_SERIAL_SHORT}==\"${serial_short}\", ENV{ID_V4L_CAPABILITIES}==\":capture:\", MODE=\"0666\", GROUP=\"video\", SYMLINK+=\"${symlink_name}\""
}

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
  echo "# /dev/${ST3235_BALLSCREW_LINK}: ST3235 and ball screw debug board"
  echo "# ${ST3235_BALLSCREW_SOURCE}: ID_PATH=${ST3235_BALLSCREW_ID_PATH}"
  echo "SUBSYSTEM==\"tty\", ENV{ID_PATH}==\"${ST3235_BALLSCREW_ID_PATH}\", MODE=\"0666\", GROUP=\"dialout\", SYMLINK+=\"${ST3235_BALLSCREW_LINK}\""
  make_tty_rule "${NEOPIXEL_SOURCE}" "${NEOPIXEL_LINK}" "/dev/${NEOPIXEL_LINK}: Arduino Leonardo NeoPixel controller"
  make_video_rule "${TOP_CAMERA_SERIAL}" "tetra/top_camera" "/dev/tetra/top_camera: Top Camera"
  make_video_rule "${BOTTOM_CAMERA_SERIAL}" "tetra/bottom_camera" "/dev/tetra/bottom_camera: Bottom Camera"
} >"${RULE_FILE}"

udevadm control --reload-rules
udevadm trigger --subsystem-match=tty
udevadm trigger --subsystem-match=video4linux
sleep 1

echo "Generated TETRA USB serial rules:"
cat "${RULE_FILE}"
echo
echo "Current TETRA links:"
ls -l /dev/tetra/motor /dev/tetra/motor0 /dev/tetra/motor1 /dev/tetra/lidar /dev/tetra/st3235_ballscrew /dev/tetra/neopixel /dev/tetra/top_camera /dev/tetra/bottom_camera 2>/dev/null || true
