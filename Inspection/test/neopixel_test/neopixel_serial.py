# python3 test/neopixel_test/neopixel_serial.py --port /dev/ttyACM0
import argparse
import time

import serial
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


parser = argparse.ArgumentParser(description="NeoPixel Arduino serial controller")
parser.add_argument("--port", help="예: /dev/ttyACM0 또는 /dev/ttyUSB0")
args = parser.parse_args()

port = args.port or find_arduino_port()

if port is None:
    print("시리얼 포트를 찾지 못했습니다.")
    print("아두이노 연결 후 `python -m serial.tools.list_ports`로 포트를 확인하세요.")
    raise SystemExit(1)

ser = serial.Serial(port, 9600, timeout=1)
time.sleep(2)

print(f"연결 완료: {port}")
print("명령어: ON = LED 켜기 / OFF = LED 끄기 / quit = 종료")

try:
    while True:
        cmd = input("명령 입력 >> ").strip().upper()

        if cmd == "ON":
            ser.write(b'ON\n')
            response = ser.readline().decode('utf-8', errors='ignore').strip()
            print(f"아두이노 응답: {response}")

        elif cmd == "OFF":
            ser.write(b'OFF\n')
            response = ser.readline().decode('utf-8', errors='ignore').strip()
            print(f"아두이노 응답: {response}")

        elif cmd == "QUIT":
            ser.write(b'OFF\n')
            print("종료")
            break

        else:
            print("ON 또는 OFF 또는 quit 입력하세요")

except KeyboardInterrupt:
    ser.write(b'OFF\n')
    print("종료")

finally:
    ser.close()
