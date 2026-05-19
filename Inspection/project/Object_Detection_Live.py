# cd Capstone/
# python3 project/Object_Detection_Live.py 

import cv2
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from ultralytics import YOLO


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_CONFIG_PATH = os.path.join(BASE_DIR, "config", "model_config.json")
CAMERA_CONFIG_PATH = os.path.join(BASE_DIR, "config", "camera_config.json")
HOST = "0.0.0.0"
PORT = 8000
STREAM_FPS = 12

latest_frames = {
    "camera1": None,
    "camera2": None,
}
latest_frame_times = {
    "camera1": 0,
    "camera2": 0,
}
frame_lock = threading.Lock()
stop_event = threading.Event()


def load_config():
    with open(MODEL_CONFIG_PATH, "r") as f:
        model_config = json.load(f)

    with open(CAMERA_CONFIG_PATH, "r") as f:
        camera_config = json.load(f)

    return model_config, camera_config


def setup_camera(camera_index, width, height, fps):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def resolve_camera_source(camera_source):
    if isinstance(camera_source, int):
        return camera_source

    if isinstance(camera_source, str) and camera_source.isdigit():
        return int(camera_source)

    if isinstance(camera_source, str) and os.path.exists(camera_source):
        return camera_source

    raise FileNotFoundError(f"카메라 장치를 찾을 수 없습니다: {camera_source}")


def detection_loop():
    model_config, camera_config = load_config()

    models = {
        "소화기": YOLO(model_config["FireExtinguisher_model_path"]),
        "압력게이지": YOLO(model_config["pressure_gauge_model_path"]),
        "라벨": YOLO(model_config["label_model_path"]),
    }

    camera_index_1 = resolve_camera_source(camera_config["camera_index_1"])
    camera_index_2 = resolve_camera_source(camera_config["camera_index_2"])
    width = camera_config["width"]
    height = camera_config["height"]
    fps = camera_config["fps"]
    confidence = camera_config["confidence"]

    print(f"Top Camera: {camera_index_1}")
    print(f"Bottom Camera: {camera_index_2}")

    cap1 = setup_camera(camera_index_1, width, height, fps)
    cap2 = setup_camera(camera_index_2, width, height, fps)

    if not cap1.isOpened() or not cap2.isOpened():
        print("카메라 열기 실패")
        cap1.release()
        cap2.release()
        stop_event.set()
        return

    print("YOLO11 라이브 스트리밍 시작")
    print(f"Camera 1: http://localhost:{PORT}/video/camera1")
    print(f"Camera 2: http://localhost:{PORT}/video/camera2")

    try:
        while not stop_event.is_set():
            cap1.grab()
            cap2.grab()

            ret1, frame1 = cap1.read()
            ret2, frame2 = cap2.read()

            if not ret1 or not ret2:
                print("프레임 읽기 실패")
                time.sleep(0.05)
                continue

            frames = [frame1, frame2]
            annotated_frames = []

            for camera_number, frame in enumerate(frames, start=1):
                annotated = frame.copy()

                for name, model in models.items():
                    results = model(
                        frame,
                        imgsz=640,
                        conf=confidence,
                        verbose=False,
                        device=0,
                    )

                    for box in results[0].boxes:
                        conf_score = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        class_name = model.names[cls_id]

                        if conf_score >= 0.85:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            print(
                                f"Camera {camera_number} | {name} {class_name} 감지 | "
                                f"확률: {conf_score:.2f} | 좌표: ({x1},{y1})~({x2},{y2})"
                            )

                    annotated = results[0].plot(img=annotated)

                annotated_frames.append(annotated)

            with frame_lock:
                latest_frames["camera1"] = annotated_frames[0]
                latest_frames["camera2"] = annotated_frames[1]
                now = time.time()
                latest_frame_times["camera1"] = now
                latest_frame_times["camera2"] = now

    finally:
        cap1.release()
        cap2.release()
        print("YOLO11 라이브 스트리밍 종료")


def get_jpeg_frame(camera_name):
    with frame_lock:
        frame = latest_frames.get(camera_name)
        if frame is None:
            return None
        frame = frame.copy()

    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return None

    return buffer.tobytes()


def get_stream_health():
    now = time.time()

    with frame_lock:
        return {
            camera_name: latest_frames[camera_name] is not None
            and now - latest_frame_times[camera_name] < 2
            for camera_name in latest_frames
        }


class LiveStreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"YOLO live stream server\n")
            return

        if path == "/health":
            body = json.dumps(get_stream_health()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/video/camera1":
            self.stream_camera("camera1")
            return

        if path == "/video/camera2":
            self.stream_camera("camera2")
            return

        self.send_error(404)

    def stream_camera(self, camera_name):
        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        frame_interval = 1 / STREAM_FPS

        try:
            while not stop_event.is_set():
                jpg = get_jpeg_frame(camera_name)
                if jpg is None:
                    time.sleep(0.1)
                    continue

                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpg)
                self.wfile.write(b"\r\n")
                time.sleep(frame_interval)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        return


def main():
    worker = threading.Thread(target=detection_loop, daemon=True)
    worker.start()

    server = ThreadingHTTPServer((HOST, PORT), LiveStreamHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.server_close()
        worker.join(timeout=2)


if __name__ == "__main__":
    main()
