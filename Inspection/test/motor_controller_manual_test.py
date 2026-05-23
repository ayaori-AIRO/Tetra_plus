#!/usr/bin/env python3

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

with open(CONFIG_PATH, "r") as f:
    cfg = json.load(f)

PORT = os.environ.get(
    "TETRA_ST3235_BALLSCREW_PORT",
    cfg.get("SERIAL_PORT", "/dev/tetra/st3235_ballscrew"),
)

ST_BAUDRATE = cfg["BAUDRATE"]
ST_SERVO_ID = cfg["SERVO_ID"]
ST_ADDR_TORQUE_ENABLE = cfg["ADDR_TORQUE_ENABLE"]
ST_MOVE_SPEED = cfg["MOVE_SPEED"]
ST_MOVE_ACC = cfg["MOVE_ACC"]

BALLSCREW_BAUDRATE = 38400
BALLSCREW_DEVICE_ID = 1
BALLSCREW_TRAVEL = 67000
BALLSCREW_ACC = 0
BALLSCREW_SPEED = 150
BALLSCREW_DIR_CW = 0
BALLSCREW_DIR_CCW = 1


def degree_to_position(degree):
    degree = max(0.0, min(360.0, float(degree)))
    return int(degree * 4095 / 360)


def rotate_st3235():
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

        position_360 = degree_to_position(360)
        position_0 = degree_to_position(0)

        print("[ST3235] 360도 위치로 이동")
        servo.WritePosEx(ST_SERVO_ID, position_360, ST_MOVE_SPEED, ST_MOVE_ACC)
        time.sleep(2.0)

        print("[ST3235] 0도 위치로 복귀")
        servo.WritePosEx(ST_SERVO_ID, position_0, ST_MOVE_SPEED, ST_MOVE_ACC)
        time.sleep(2.0)

        print("[ST3235] 완료")

    finally:
        port_handler.closePort()


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
        client.write_registers(
            0x00FD,
            [dir_acc, BALLSCREW_SPEED, pos1, pos2],
            device_id=BALLSCREW_DEVICE_ID,
        )
        print(f"[볼스크류] {label} 명령 전송 완료")

    finally:
        client.close()


def ballscrew_down():
    move_ballscrew_relative(BALLSCREW_DIR_CCW, "DOWN")


def ballscrew_up():
    move_ballscrew_relative(BALLSCREW_DIR_CW, "UP")


def print_menu():
    print()
    print("=== ST3235 + 볼스크류 수동 테스트 ===")
    print(f"PORT: {PORT}")
    print("1: ST3235 360도 회전 후 0도 복귀")
    print("2: 볼스크류 DOWN")
    print("3: 볼스크류 UP")
    print("q: 종료")


def main():
    if not os.path.exists(PORT):
        print(f"[경고] 포트가 아직 보이지 않습니다: {PORT}")

    while True:
        print_menu()
        command = input("명령 입력: ").strip().lower()

        try:
            if command == "1":
                rotate_st3235()
            elif command == "2":
                ballscrew_down()
            elif command == "3":
                ballscrew_up()
            elif command in ("q", "quit", "exit"):
                print("종료합니다.")
                return
            else:
                print("알 수 없는 명령입니다. 1, 2, 3, q 중 하나를 입력하세요.")
        except Exception as exc:
            print(f"[에러] {exc}")


if __name__ == "__main__":
    main()
