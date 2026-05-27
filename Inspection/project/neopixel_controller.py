#!/usr/bin/env python3

import argparse
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import serial


DEFAULT_PORT = "/dev/tetra/neopixel"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "config", "neopixel_state.json")
BAUDRATE = 9600
COMMANDS = {
    "internal": "INTERNAL",
    "camera": "CAMERA",
    "off": "OFF",
}
TARGET_ALIASES = {
    "internal": "internal",
    "camera": "camera",
    "external": "camera",
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

    def set_gray(self, target, value):
        target = normalize_target(target)
        value = clamp_color_value(value)
        save_target_value(target, value)
        command = f"{COMMANDS[target]} {value} {value} {value}"
        return self._send(command)

    def off(self):
        return self._send(COMMANDS["off"])


def clamp_color_value(value):
    return max(0, min(255, int(value)))


def normalize_target(target):
    normalized = TARGET_ALIASES.get(str(target).lower())
    if normalized is None:
        raise ValueError(f"Unknown NeoPixel target: {target}")
    return normalized


def load_state():
    if not os.path.exists(STATE_PATH):
        return {}

    try:
        with open(STATE_PATH, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (OSError, json.JSONDecodeError):
        return {}

    return {
        normalize_target(target): clamp_color_value(value)
        for target, value in state.items()
        if TARGET_ALIASES.get(str(target).lower()) is not None
    }


def save_state(state):
    safe_state = {
        normalize_target(target): clamp_color_value(value)
        for target, value in state.items()
    }
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as state_file:
        json.dump(safe_state, state_file)


def save_target_value(target, value):
    target = normalize_target(target)
    state = load_state()
    state[target] = clamp_color_value(value)
    save_state(state)


def get_target_value(target):
    target = normalize_target(target)
    state = load_state()
    return state.get(target)


def camera_led_on(port=DEFAULT_PORT):
    return NeoPixelController(port=port).camera_on()


def internal_led_on(port=DEFAULT_PORT):
    return NeoPixelController(port=port).internal_on()


def neopixel_off(port=DEFAULT_PORT):
    return NeoPixelController(port=port).off()


def set_neopixel_gray(target, value, port=DEFAULT_PORT):
    return NeoPixelController(port=port).set_gray(target, value)


class NeoPixelApiServer:
    def __init__(self, host="0.0.0.0", port=8002, serial_port=DEFAULT_PORT):
        self.host = host
        self.port = int(port)
        self.serial_port = serial_port
        self.server = ThreadingHTTPServer((self.host, self.port), self.make_handler())

    def make_handler(self):
        serial_port = self.serial_port

        class NeoPixelApiHandler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                self.send_response(204)
                self.send_cors_headers()
                self.end_headers()

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/health":
                    self.send_json(200, {"ok": True})
                    return

                if path == "/neopixel/state":
                    state = load_state()
                    self.send_json(
                        200,
                        {
                            "ok": True,
                            "state": {
                                "internal": state.get("internal", 0),
                                "external": state.get("camera", 0),
                            },
                        },
                    )
                    return

                if path == "/neopixel":
                    query = parse_qs(urlparse(self.path).query)
                    target = query.get("target", [""])[0]
                    value = query.get("value", [""])[0]
                    self.handle_set_neopixel(target, value)
                    return

                self.send_error(404)

            def do_POST(self):
                path = urlparse(self.path).path
                if path != "/neopixel":
                    self.send_error(404)
                    return

                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self.send_json(400, {"ok": False, "error": "invalid json"})
                    return

                self.handle_set_neopixel(payload.get("target"), payload.get("value"))

            def handle_set_neopixel(self, target, value):
                try:
                    target = normalize_target(target)
                    value = clamp_color_value(value)
                    responses = set_neopixel_gray(target, value, port=serial_port)
                except (ValueError, TypeError) as exc:
                    self.send_json(400, {"ok": False, "error": str(exc)})
                    return
                except serial.SerialException as exc:
                    self.send_json(503, {"ok": False, "error": str(exc)})
                    return

                self.send_json(
                    200,
                    {
                        "ok": True,
                        "target": target,
                        "rgb": [value, value, value],
                        "responses": responses,
                    },
                )

            def send_json(self, status, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def send_cors_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Cache-Control", "no-cache")

            def log_message(self, format, *args):
                return

        return NeoPixelApiHandler

    def serve_forever(self):
        print(f"NeoPixel API server: http://{self.host}:{self.port}")
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()
        self.server.server_close()


def main():
    parser = argparse.ArgumentParser(description="NeoPixel controller")
    parser.add_argument(
        "target",
        choices=["camera", "external", "internal", "off", "server"],
        help="camera/external=depth camera LED, internal=inspection internal LED, off=all off, server=HTTP API",
    )
    parser.add_argument("value", nargs="?", type=int, help="0-255 grayscale value")
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--api-port", type=int, default=8002)
    args = parser.parse_args()

    if args.target == "server":
        NeoPixelApiServer(
            host=args.host,
            port=args.api_port,
            serial_port=args.port,
        ).serve_forever()
        return

    controller = NeoPixelController(port=args.port)
    applied_value = None
    if args.value is not None:
        applied_value = clamp_color_value(args.value)
        responses = controller.set_gray(args.target, applied_value)
    elif args.target in ("camera", "external"):
        saved_value = get_target_value(args.target)
        if saved_value is None:
            responses = controller.camera_on()
        else:
            applied_value = saved_value
            responses = controller.set_gray(args.target, saved_value)
    elif args.target == "internal":
        saved_value = get_target_value(args.target)
        if saved_value is None:
            responses = controller.internal_on()
        else:
            applied_value = saved_value
            responses = controller.set_gray(args.target, saved_value)
    else:
        responses = controller.off()

    print(f"port: {args.port}")
    print(f"target: {args.target}")
    if applied_value is not None:
        print(f"rgb: {applied_value},{applied_value},{applied_value}")
    if responses:
        for response in responses:
            print(f"arduino: {response}")
    else:
        print("arduino: no response")


if __name__ == "__main__":
    main()
