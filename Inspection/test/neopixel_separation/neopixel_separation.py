# python3 test/neopixel_separation/neopixel_separation.py --port /dev/ttyACM0 --target internal
import argparse
import time

import serial
from serial.tools import list_ports


TARGETS = {
    "internal": "INTERNAL",
    "camera": "CAMERA",
    "off": "OFF",
}


def find_arduino_port():
    ports = list(list_ports.comports())

    for port in ports:
        text = f"{port.device} {port.description} {port.manufacturer or ''}".lower()
        if "arduino" in text or "ch340" in text or "usb serial" in text:
            return port.device

    if ports:
        return ports[0].device

    return None


def clamp_color(value):
    return max(0, min(255, value))


def send_command(ser, command):
    ser.reset_input_buffer()
    ser.write(f"{command}\n".encode("utf-8"))
    response = ser.readline().decode("utf-8", errors="ignore").strip()
    if response:
        print(f"아두이노 응답: {response}")


def choose_target():
    print("켜고 싶은 구역을 선택하세요.")
    print("1. 소화기 점검기 내부 LED (0~19)")
    print("2. depth 카메라 주변 LED (20~23)")
    print("3. 전체 끄기")
    print("4. LED 한 개 번호 테스트")

    while True:
        value = input("선택 [1/2/3]: ").strip()
        if value == "1":
            return "internal"
        if value == "2":
            return "camera"
        if value == "3":
            return "off"
        if value == "4":
            return "pixel"
        print("1, 2, 3, 4 중 하나를 입력하세요.")


def main():
    parser = argparse.ArgumentParser(description="NeoPixel 구역 분리 테스트")
    parser.add_argument("--port", help="예: /dev/ttyACM0 또는 /dev/ttyUSB0")
    parser.add_argument(
        "--target",
        choices=[*TARGETS, "pixel", "range"],
        help="internal=소화기 내부, camera=depth 카메라 주변, off=전체 끄기",
    )
    parser.add_argument("--pixel", type=int, help="한 개만 켤 LED 번호, 0부터 시작")
    parser.add_argument("--start", type=int, help="직접 켤 시작 LED 번호, 0부터 시작")
    parser.add_argument("--end", type=int, help="직접 켤 끝 LED 번호, 0부터 시작")
    parser.add_argument("--hold", type=float, help="지정한 초 뒤 자동 OFF")
    parser.add_argument("--no-off", action="store_true", help="종료할 때 LED를 끄지 않음")
    args = parser.parse_args()

    port = args.port or find_arduino_port()
    if port is None:
        print("시리얼 포트를 찾지 못했습니다.")
        print("아두이노 연결 후 `python3 -m serial.tools.list_ports`로 포트를 확인하세요.")
        raise SystemExit(1)

    target = args.target or choose_target()

    if args.pixel is not None:
        target = "pixel"

    if target == "pixel":
        pixel = args.pixel
        if pixel is None:
            pixel = int(input("켜볼 LED 번호 [0~29]: ").strip())
        pixel = max(0, min(29, pixel))
        command = f"PIXEL {pixel}"
    else:
        command = TARGETS[target]

    ser = serial.Serial(port, 9600, timeout=1)
    time.sleep(2)

    print(f"연결 완료: {port}")
    if target == "internal":
        print("소화기 점검기 내부 LED만 켭니다. LED 번호: 0~19")
    elif target == "camera":
        print("depth 카메라 주변 LED만 켭니다. LED 번호: 20~23")
    elif target == "pixel":
        print("LED 한 개만 켭니다.")
    elif target == "range":
        print("지정한 LED 범위만 켭니다.")
    else:
        print("전체 LED를 끕니다.")

    try:
        send_command(ser, command)

        if target != "off":
            if args.hold is not None:
                time.sleep(args.hold)
            elif not args.no_off:
                input("끄고 종료하려면 Enter를 누르세요.")

    except KeyboardInterrupt:
        print("종료")

    finally:
        if target != "off" and not args.no_off:
            send_command(ser, "OFF")
        ser.close()


if __name__ == "__main__":
    main()
