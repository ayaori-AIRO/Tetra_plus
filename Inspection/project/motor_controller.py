#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time

from pymodbus.client import ModbusSerialClient


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scservo_sdk import PortHandler, sms_sts


CONFIG_PATH = os.path.join(BASE_DIR, "config", "st3235_config.json")
DEFAULT_PORT = "/dev/tetra/st3235_ballscrew"

with open(CONFIG_PATH, "r") as f:
    cfg = json.load(f)

PORT = os.environ.get(
    "TETRA_ST3235_BALLSCREW_PORT",
    cfg.get("SERIAL_PORT", DEFAULT_PORT),
)

ST_BAUDRATE = cfg["BAUDRATE"]
ST_SERVO_ID = cfg["SERVO_ID"]
ST_ADDR_TORQUE_ENABLE = cfg["ADDR_TORQUE_ENABLE"]
ST_MOVE_SPEED = cfg["MOVE_SPEED"]
ST_MOVE_ACC = cfg["MOVE_ACC"]

ST_90_DEGREE_TICKS = 1024
ST_MIN_POSITION = 0
ST_MAX_POSITION = 4095
ST_MOVE_WAIT_SEC = 1.5

BALLSCREW_BAUDRATE = 38400
BALLSCREW_DEVICE_ID = 1
BALLSCREW_TRAVEL = 67000
BALLSCREW_ACC = 0
BALLSCREW_SPEED = 150
BALLSCREW_DIR_CW = 0
BALLSCREW_DIR_CCW = 1


def clamp_position(position):
    return max(ST_MIN_POSITION, min(ST_MAX_POSITION, int(position)))


def read_st3235_position(servo):
    position, comm_result, error = servo.ReadPos(ST_SERVO_ID)
    if comm_result != 0:
        raise RuntimeError(
            f"ST3235 현재 위치 읽기 실패: comm_result={comm_result}, error={error}"
        )
    return clamp_position(position)


def move_st3235_delta(delta_ticks, label):
    print(f"[ST3235] 포트 연결: {PORT}, baud={ST_BAUDRATE}")
    port_handler = PortHandler(PORT)
    servo = sms_sts(port_handler)

    if not port_handler.openPort():
        raise RuntimeError(f"ST3235 포트 열기 실패: {PORT}")

    try:
        if not port_handler.setBaudRate(ST_BAUDRATE):
            raise RuntimeError(f"ST3235 보드레이트 설정 실패: {ST_BAUDRATE}")

        servo.write1ByteTxRx(ST_SERVO_ID, ST_ADDR_TORQUE_ENABLE, 1)
        time.sleep(0.2)

        current_position = read_st3235_position(servo)
        target_position = clamp_position(current_position + delta_ticks)

        print(
            f"[ST3235] {label} | "
            f"current={current_position}, target={target_position}"
        )
        servo.WritePosEx(ST_SERVO_ID, target_position, ST_MOVE_SPEED, ST_MOVE_ACC)
        time.sleep(ST_MOVE_WAIT_SEC)
        return target_position

    finally:
        port_handler.closePort()


def rotate_st3235_90():
    return move_st3235_delta(ST_90_DEGREE_TICKS, "+90도 회전")


def rotate_st3235_minus_90():
    return move_st3235_delta(-ST_90_DEGREE_TICKS, "-90도 회전")


def move_ballscrew_relative(direction, label):
    print(f"[볼스크류] 포트 연결: {PORT}, baud={BALLSCREW_BAUDRATE}")
    client = ModbusSerialClient(
        port=PORT,
        baudrate=BALLSCREW_BAUDRATE,
        timeout=1,
    )

    try:
        if not client.connect():
            raise RuntimeError(f"볼스크류 포트 연결 실패: {PORT}")

        dir_acc = (direction << 8) | BALLSCREW_ACC
        move_bytes = BALLSCREW_TRAVEL.to_bytes(4, byteorder="little", signed=False)
        pos1 = int.from_bytes(move_bytes[2:4], "little")
        pos2 = int.from_bytes(move_bytes[0:2], "little")

        print(
            f"[볼스크류] {label} 이동 시작 | 이동량={BALLSCREW_TRAVEL}, "
            f"speed={BALLSCREW_SPEED}"
        )
        response = client.write_registers(
            0x00FD,
            [dir_acc, BALLSCREW_SPEED, pos1, pos2],
            device_id=BALLSCREW_DEVICE_ID,
        )

        if response.isError():
            raise RuntimeError(f"볼스크류 {label} 명령 실패: {response}")

        print(f"[볼스크류] {label} 명령 전송 완료")
        return response

    finally:
        client.close()


def ballscrew_up():
    return move_ballscrew_relative(BALLSCREW_DIR_CW, "UP")


def ballscrew_down():
    return move_ballscrew_relative(BALLSCREW_DIR_CCW, "DOWN")


def main():
    parser = argparse.ArgumentParser(description="ST3235 and ball screw controller")
    parser.add_argument(
        "command",
        choices=["st90", "st-90", "up", "down"],
        help="st90=ST3235 +90deg, st-90=ST3235 -90deg, up/down=ball screw",
    )
    args = parser.parse_args()

    if args.command == "st90":
        rotate_st3235_90()
    elif args.command == "st-90":
        rotate_st3235_minus_90()
    elif args.command == "up":
        ballscrew_up()
    elif args.command == "down":
        ballscrew_down()


if __name__ == "__main__":
    main()
