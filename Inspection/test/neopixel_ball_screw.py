import argparse
import time

import serial
from pymodbus.client import ModbusSerialClient
from serial.tools import list_ports


def find_arduino_port():
    ports = list(list_ports.comports())

    for port in ports:
        text = f"{port.device} {port.description} {port.manufacturer or ''}".lower()
        if "arduino" in text or "ch340" in text or "usb serial" in text:
            return port.device

    if ports:
        return ports[0].device

    return None


def send_neopixel_command(ser, command):
    ser.reset_input_buffer()
    ser.write(f"{command}\n".encode("utf-8"))

    deadline = time.time() + 2
    while time.time() < deadline:
        response = ser.readline().decode("utf-8", errors="ignore").strip()
        if response:
            print(f"아두이노 응답: {response}")
            if command in response:
                return


def move_relative(client, delta, acc, speed, device_id):
    if delta >= 0:
        direction = 1
    else:
        direction = 0

    dir_acc = (direction << 8) | acc
    move = abs(delta)

    move_bytes = move.to_bytes(4, byteorder="little", signed=False)
    pos1 = int.from_bytes(move_bytes[2:4], "little")
    pos2 = int.from_bytes(move_bytes[0:2], "little")

    client.write_registers(0x00FD, [dir_acc, speed, pos1, pos2], device_id=device_id)


def stop_ball_screw(client, acc, device_id):
    client.write_registers(0x00F6, [(0 << 8) | acc, 0], device_id=device_id)


def main():
    parser = argparse.ArgumentParser(
        description="NeoPixel을 켠 상태로 볼스크류 왕복 운동을 실행합니다."
    )
    parser.add_argument("--neopixel-port", default="/dev/ttyACM0", help="예: /dev/ttyACM0")
    parser.add_argument("--ballscrew-port", default="/dev/ttyUSB0", help="예: /dev/ttyUSB0")
    parser.add_argument("--cycles", type=int, default=2, help="왕복 횟수")
    parser.add_argument("--travel", type=int, default=15000, help="왕복 이동량")
    parser.add_argument("--acc", type=int, default=100, help="가감속 설정값")
    parser.add_argument("--speed", type=int, default=500, help="속도 설정값")
    parser.add_argument("--delay", type=float, default=3.0, help="각 이동 후 대기 시간")
    parser.add_argument("--device-id", type=int, default=1, help="Modbus device id")
    args = parser.parse_args()

    neopixel_port = args.neopixel_port or find_arduino_port()
    if neopixel_port is None:
        print("NeoPixel Arduino 시리얼 포트를 찾지 못했습니다.")
        print("예: python3 test/neopixel_ball_screw.py --neopixel-port /dev/ttyACM0")
        raise SystemExit(1)

    if neopixel_port == args.ballscrew_port:
        print("NeoPixel 포트와 볼스크류 포트가 같습니다.")
        print(f"NeoPixel: {neopixel_port}")
        print(f"볼스크류: {args.ballscrew_port}")
        print("예: --neopixel-port /dev/ttyACM0 --ballscrew-port /dev/ttyUSB0")
        raise SystemExit(1)

    neo_ser = None
    ball_client = None

    try:
        neo_ser = serial.Serial(neopixel_port, 9600, timeout=1)
        time.sleep(2)
        print(f"NeoPixel 연결 완료: {neopixel_port}")

        ball_client = ModbusSerialClient(
            port=args.ballscrew_port,
            baudrate=38400,
            timeout=1,
        )

        if not ball_client.connect():
            print(f"볼스크류 포트 연결 실패: {args.ballscrew_port}")
            raise SystemExit(1)

        print(f"볼스크류 연결 완료: {args.ballscrew_port}")
        print("NeoPixel ON")
        send_neopixel_command(neo_ser, "ON")

        print(f"왕복 {args.cycles}회 시작")
        for i in range(args.cycles):
            print(f"{i + 1}번째 왕복")

            print("CW 이동")
            move_relative(
                ball_client,
                args.travel,
                args.acc,
                args.speed,
                args.device_id,
            )
            time.sleep(args.delay)

            print("CCW 이동")
            move_relative(
                ball_client,
                -args.travel,
                args.acc,
                args.speed,
                args.device_id,
            )
            time.sleep(args.delay)

        print("완료")

    except KeyboardInterrupt:
        print("사용자 중단")

    finally:
        if ball_client is not None:
            try:
                stop_ball_screw(ball_client, args.acc, args.device_id)
                print("볼스크류 정지")
            finally:
                ball_client.close()

        if neo_ser is not None:
            try:
                print("NeoPixel OFF")
                send_neopixel_command(neo_ser, "OFF")
            finally:
                neo_ser.close()


if __name__ == "__main__":
    main()
