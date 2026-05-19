import cv2
import json
import os
import time

import numpy as np
import serial
from serial.tools import list_ports
from ultralytics import YOLO


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_CONFIG_PATH = os.path.join(BASE_DIR, "config", "model_config.json")
CAMERA_CONFIG_PATH = os.path.join(BASE_DIR, "config", "camera_config.json")
NEOPIXEL_PORT = "/dev/ttyACM0"
CAPTURE_DIR = os.path.join(BASE_DIR, "capture", "Real_Environment")
SAVE_CONFIDENCE = 0.85
CONTROL_WINDOW = "Capture Controls"
BUTTONS = [
    ("full", "Full Capture"),
    ("압력게이지", "Pressure Gauge"),
    ("라벨", "Label"),
    ("소화기", "Fire Extinguisher"),
]
SAVE_FOLDER_NAMES = {
    "full": "full",
    "압력게이지": "pressure_gauge",
    "라벨": "label",
    "소화기": "fire_extinguisher",
}

latest_frame1 = None
latest_frame2 = None
latest_camera1_detections = {}
pending_capture_action = None


def find_arduino_port():
    ports = list(list_ports.comports())

    for port in ports:
        text = f"{port.device} {port.description} {port.manufacturer or ''}".lower()
        if "arduino" in text or "ch340" in text or "usb serial" in text:
            return port.device

    if ports:
        return ports[0].device

    return None


def open_neopixel(port=None):
    port = port or find_arduino_port()

    if port is None:
        raise RuntimeError("시리얼 포트를 찾지 못했습니다.")

    ser = serial.Serial(port, 9600, timeout=1)
    time.sleep(2)
    ser.reset_input_buffer()
    print(f"NeoPixel 연결 완료: {port}")
    return ser


def send_neopixel(ser, command):
    ser.write(f"{command}\n".encode("utf-8"))
    return ser.readline().decode("utf-8", errors="ignore").strip()


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def make_timestamp():
    return time.strftime("%Y%m%d_%H%M%S")


def clamp_box(box, frame_shape):
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(w - 1, int(x1)))
    y1 = max(0, min(h - 1, int(y1)))
    x2 = max(0, min(w, int(x2)))
    y2 = max(0, min(h, int(y2)))
    return x1, y1, x2, y2


def save_full_capture(frame1, frame2):
    save_dir = os.path.join(CAPTURE_DIR, SAVE_FOLDER_NAMES["full"])
    ensure_dir(save_dir)

    if frame1.shape[1] != frame2.shape[1]:
        resized_height = int(frame2.shape[0] * (frame1.shape[1] / frame2.shape[1]))
        frame2 = cv2.resize(frame2, (frame1.shape[1], resized_height))

    merged = cv2.vconcat([frame1, frame2])
    save_path = os.path.join(save_dir, f"full_{make_timestamp()}.jpg")
    cv2.imwrite(save_path, merged)
    print(f"전체 캡쳐 저장 완료: {save_path}")


def save_camera1_crops(frame, detections, target_name):
    target_detections = detections.get(target_name, [])

    if not target_detections:
        print(f"Camera 1에서 저장할 {target_name} 탐지 결과가 없습니다.")
        return

    save_folder_name = SAVE_FOLDER_NAMES.get(target_name, target_name)
    save_dir = os.path.join(CAPTURE_DIR, save_folder_name)
    ensure_dir(save_dir)
    timestamp = make_timestamp()
    saved_count = 0

    for idx, detection in enumerate(target_detections, start=1):
        x1, y1, x2, y2 = clamp_box(detection["box"], frame.shape)

        if x2 <= x1 or y2 <= y1:
            continue

        crop = frame[y1:y2, x1:x2]
        save_path = os.path.join(
            save_dir,
            f"camera1_{save_folder_name}_{timestamp}_{idx}.jpg",
        )
        cv2.imwrite(save_path, crop)
        saved_count += 1
        print(f"{target_name} 크롭 저장 완료: {save_path}")

    if saved_count == 0:
        print(f"Camera 1에서 유효한 {target_name} 크롭 영역이 없습니다.")


def draw_control_panel():
    panel_width = 720
    panel_height = 90
    button_gap = 12
    button_width = (panel_width - button_gap * (len(BUTTONS) + 1)) // len(BUTTONS)
    button_height = 52
    y = 18

    panel = np.full((panel_height, panel_width, 3), 255, dtype=np.uint8)

    for i, (_, label) in enumerate(BUTTONS):
        x = button_gap + i * (button_width + button_gap)
        cv2.rectangle(panel, (x, y), (x + button_width, y + button_height), (45, 90, 170), -1)
        cv2.rectangle(panel, (x, y), (x + button_width, y + button_height), (20, 45, 90), 2)

        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
        text_x = x + (button_width - text_size[0]) // 2
        text_y = y + (button_height + text_size[1]) // 2
        cv2.putText(
            panel,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return panel


def on_control_mouse(event, x, y, flags, param):
    del flags, param
    global pending_capture_action

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    button_gap = 12
    panel_width = 720
    button_width = (panel_width - button_gap * (len(BUTTONS) + 1)) // len(BUTTONS)
    button_height = 52
    button_y = 18

    if y < button_y or y > button_y + button_height:
        return

    for i, (action, _) in enumerate(BUTTONS):
        button_x = button_gap + i * (button_width + button_gap)
        if button_x <= x <= button_x + button_width:
            pending_capture_action = action
            return


with open(MODEL_CONFIG_PATH, "r") as f:
    model_config = json.load(f)

with open(CAMERA_CONFIG_PATH, "r") as f:
    camera_config = json.load(f)

FireExtinguisher_model_path = model_config["FireExtinguisher_model_path"]
pressure_gauge_model_path = model_config["pressure_gauge_model_path"]
label_model_path = model_config["label_model_path"]

camera_index_1 = camera_config["camera_index_1"]
camera_index_2 = camera_config["camera_index_2"]
width = camera_config["width"]
height = camera_config["height"]
fps = camera_config["fps"]
confidence = camera_config["confidence"]

models = {
    "소화기": YOLO(FireExtinguisher_model_path),
    "압력게이지": YOLO(pressure_gauge_model_path),
    "라벨": YOLO(label_model_path),
}

cap1 = cv2.VideoCapture(camera_index_1, cv2.CAP_V4L2)
cap2 = cv2.VideoCapture(camera_index_2, cv2.CAP_V4L2)

for cap in [cap1, cap2]:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap1.isOpened() or not cap2.isOpened():
    print("카메라 열기 실패")
    cap1.release()
    cap2.release()
    raise SystemExit(1)

neopixel = None

try:
    neopixel = open_neopixel(NEOPIXEL_PORT)
    response = send_neopixel(neopixel, "ON")
    print(f"NeoPixel ON: {response}")

    print("YOLO11 세 모델 탐지 시작")
    cv2.namedWindow("Camera 1", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Camera 2", cv2.WINDOW_NORMAL)
    cv2.namedWindow(CONTROL_WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(CONTROL_WINDOW, on_control_mouse)

    while True:
        cap1.grab()
        cap2.grab()

        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if not ret1 or not ret2:
            print("프레임 읽기 실패")
            break

        latest_frame1 = frame1.copy()
        latest_frame2 = frame2.copy()
        camera1_detections = {name: [] for name in models}
        frames = [frame1, frame2]
        annotated_frames = []

        for i, frame in enumerate(frames):
            annotated = frame.copy()

            for name, model in models.items():
                results = model(frame, imgsz=640, conf=confidence, verbose=False, device=0)

                for box in results[0].boxes:
                    conf_score = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = model.names[cls_id]

                    if conf_score >= SAVE_CONFIDENCE:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        if i == 0:
                            camera1_detections[name].append(
                                {
                                    "box": (x1, y1, x2, y2),
                                    "class_name": class_name,
                                    "confidence": conf_score,
                                }
                            )
                        print(
                            f"Camera {i + 1} | {name} {class_name} 감지 | "
                            f"확률: {conf_score:.2f} | 좌표: ({x1},{y1})~({x2},{y2})"
                        )

                annotated = results[0].plot(img=annotated)

            annotated_frames.append(annotated)

        latest_camera1_detections = camera1_detections

        cv2.imshow("Camera 1", annotated_frames[0])
        cv2.imshow("Camera 2", annotated_frames[1])
        cv2.imshow(CONTROL_WINDOW, draw_control_panel())

        if pending_capture_action is not None:
            action = pending_capture_action
            pending_capture_action = None

            if action == "full":
                save_full_capture(latest_frame1, latest_frame2)
            else:
                save_camera1_crops(
                    latest_frame1,
                    latest_camera1_detections,
                    action,
                )

        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    cap1.release()
    cap2.release()
    cv2.destroyAllWindows()

    if neopixel is not None:
        try:
            response = send_neopixel(neopixel, "OFF")
            print(f"NeoPixel OFF: {response}")
        finally:
            neopixel.close()

    print("프로그램 종료")
