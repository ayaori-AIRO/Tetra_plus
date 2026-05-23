#!/usr/bin/env python3

import argparse
import time

import serial


DEFAULT_PORT = "/dev/tetra/neopixel"
BAUDRATE = 9600
COMMANDS = {
    "internal": "INTERNAL",
    "camera": "CAMERA",
    "off": "OFF",
}


class NeoPixelController:
    def __init__(self, port=DEFAULT_PORT, baudrate=BAUDRATE, timeout=1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

    def _send(self, command):
        with serial.Serial(self.port, self.baudrate, timeout=self.timeout) as ser:
            time.sleep(2.0)
            ser.reset_input_buffer()
            ser.write(f"{command}\n".encode("utf-8"))
            ser.flush()
            return self._read_responses(ser)

    def _read_responses(self, ser, duration=1.0):
        deadline = time.time() + duration
        responses = []

        while time.time() < deadline:
            response = ser.readline().decode("utf-8", errors="ignore").strip()
            if response:
                responses.append(response)

        return responses

    def camera_on(self):
        return self._send(COMMANDS["camera"])

    def internal_on(self):
        return self._send(COMMANDS["internal"])

    def off(self):
        return self._send(COMMANDS["off"])


def camera_led_on(port=DEFAULT_PORT):
    return NeoPixelController(port=port).camera_on()


def internal_led_on(port=DEFAULT_PORT):
    return NeoPixelController(port=port).internal_on()


def neopixel_off(port=DEFAULT_PORT):
    return NeoPixelController(port=port).off()


def main():
    parser = argparse.ArgumentParser(description="NeoPixel controller")
    parser.add_argument(
        "target",
        choices=["camera", "internal", "off"],
        help="camera=depth camera LED, internal=inspection internal LED, off=all off",
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    args = parser.parse_args()

    controller = NeoPixelController(port=args.port)
    if args.target == "camera":
        responses = controller.camera_on()
    elif args.target == "internal":
        responses = controller.internal_on()
    else:
        responses = controller.off()

    print(f"port: {args.port}")
    print(f"target: {args.target}")
    if responses:
        for response in responses:
            print(f"arduino: {response}")
    else:
        print("arduino: no response")


if __name__ == "__main__":
    main()
