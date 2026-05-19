# python3 test/neopixel_range_test/neopixel_range.py --port /dev/ttyACM0 --start 3 --end 10
import argparse
import time

import serial
from serial.tools import list_ports


LED_COUNT = 30


def find_arduino_port():
    ports = list(list_ports.comports())

    for port in ports:
        text = f"{port.device} {port.description} {port.manufacturer or ''}".lower()
        if "arduino" in text or "ch340" in text or "usb serial" in text:
            return port.device

    if ports:
        return ports[0].device

    return None


def read_int(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default is not None:
            return default
        try:
            return int(value)
        except ValueError:
            print("숫자로 입력하세요.")


def read_led_or_quit(prompt):
    while True:
        value = input(f"{prompt} (0~{LED_COUNT - 1}, q=종료): ").strip().lower()
        if value in {"q", "quit", "exit"}:
            return None
        try:
            return clamp_led(int(value))
        except ValueError:
            print("숫자 또는 q를 입력하세요.")


def clamp_led(value):
    return max(0, min(LED_COUNT - 1, value))


def send_command(ser, command):
    ser.reset_input_buffer()
    ser.write(f"{command}\n".encode("utf-8"))
    response = ser.readline().decode("utf-8", errors="ignore").strip()
    if response:
        print(f"아두이노 응답: {response}")


def send_range(ser, start, end, red, green, blue):
    print(f"LED {start}번부터 {end}번까지 켭니다.")
    send_command(ser, f"RANGE {start} {end} {red} {green} {blue}")


def main():
    parser = argparse.ArgumentParser(description="NeoPixel 구간 LED 테스트")
    parser.add_argument("--port", help="예: /dev/ttyACM0 또는 /dev/ttyUSB0")
    parser.add_argument("--start", type=int, help="켜기 시작할 LED 번호, 0부터 시작")
    parser.add_argument("--end", type=int, help="켜기 끝 LED 번호, 0부터 시작")
    parser.add_argument("--red", type=int, default=255, help="빨강 밝기 0~255")
    parser.add_argument("--green", type=int, default=255, help="초록 밝기 0~255")
    parser.add_argument("--blue", type=int, default=255, help="파랑 밝기 0~255")
    parser.add_argument("--hold", type=float, help="지정한 초 뒤 자동 OFF")
    parser.add_argument("--no-off", action="store_true", help="종료할 때 LED를 끄지 않음")
    args = parser.parse_args()

    port = args.port or find_arduino_port()
    if port is None:
        print("시리얼 포트를 찾지 못했습니다.")
        print("아두이노 연결 후 `python3 -m serial.tools.list_ports`로 포트를 확인하세요.")
        raise SystemExit(1)

    red = max(0, min(255, args.red))
    green = max(0, min(255, args.green))
    blue = max(0, min(255, args.blue))

    ser = serial.Serial(port, 9600, timeout=1)
    time.sleep(2)

    print(f"연결 완료: {port}")

    try:
        if args.start is not None or args.end is not None:
            start = clamp_led(args.start if args.start is not None else read_int("시작 LED 번호", 0))
            end = clamp_led(args.end if args.end is not None else read_int("끝 LED 번호", LED_COUNT - 1))

            send_range(ser, start, end, red, green, blue)

            if args.hold is not None:
                time.sleep(args.hold)
            else:
                input("끄고 종료하려면 Enter를 누르세요.")

        else:
            print("시작 번호와 끝 번호를 입력하면 해당 범위만 켜집니다.")
            while True:
                start = read_led_or_quit("시작 LED 번호")
                if start is None:
                    break

                end = read_led_or_quit("끝 LED 번호")
                if end is None:
                    break

                send_range(ser, start, end, red, green, blue)

    except KeyboardInterrupt:
        print("종료")

    finally:
        if not args.no_off:
            send_command(ser, "OFF")
        ser.close()


if __name__ == "__main__":
    main()
