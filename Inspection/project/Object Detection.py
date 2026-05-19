import cv2
import json
import os
from ultralytics import YOLO

# 🔥 현재 파일 기준 상위 폴더 경로 얻기
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 🔥 모델, 카메라 config 경로
model_config_path = os.path.join(BASE_DIR, "config", "model_config.json")
camera_config_path = os.path.join(BASE_DIR, "config", "camera_config.json")

# 🔥 모델 설정 불러오기
with open(model_config_path, "r") as f:
    model_config = json.load(f)

FireExtinguisher_model_path = model_config["FireExtinguisher_model_path"]
pressure_gauge_model_path = model_config["pressure_gauge_model_path"]
label_model_path = model_config["label_model_path"]
gauge_crop_image_path = model_config["gauge_crop_image_path"]

# 🔥 카메라 설정 불러오기
with open(camera_config_path, "r") as f:
    camera_config = json.load(f)

camera_index_1 = camera_config["camera_index_1"]
camera_index_2 = camera_config["camera_index_2"]
width = camera_config["width"]
height = camera_config["height"]
fps = camera_config["fps"]
confidence = camera_config["confidence"]

# 🔥 모델 로드 (딕셔너리로 관리)
models = {
    "소화기": YOLO(FireExtinguisher_model_path),
    "압력게이지": YOLO(pressure_gauge_model_path),
    "라벨": YOLO(label_model_path)
}

# 🔥 카메라 설정
cap1 = cv2.VideoCapture(camera_index_1, cv2.CAP_V4L2)
cap2 = cv2.VideoCapture(camera_index_2, cv2.CAP_V4L2)

for cap in [cap1, cap2]:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap1.isOpened() or not cap2.isOpened():
    print("❌ 카메라 열기 실패")
    exit()

print("✅ YOLO11 세 모델 탐지 시작")

cv2.namedWindow("Camera 1", cv2.WINDOW_NORMAL)
cv2.namedWindow("Camera 2", cv2.WINDOW_NORMAL)

while True:
    # 🔥 오래된 프레임 버리기
    cap1.grab()
    cap2.grab()

    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()

    if not ret1 or not ret2:
        print("❌ 프레임 읽기 실패")
        break

    frames = [frame1, frame2]
    annotated_frames = []

    for i, frame in enumerate(frames):
        annotated = frame.copy()
        # 🔥 각 모델별 추론
        for name, model in models.items():
            results = model(frame, imgsz=640, conf=confidence, verbose=False, device=0)
            for box in results[0].boxes:
                conf_score = float(box.conf[0])
                cls_id = int(box.cls[0])
                class_name = model.names[cls_id]

                if conf_score >= 0.85:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    print(f"🔥 Camera {i+1} | {name} {class_name} 감지 | 확률: {conf_score:.2f} | 좌표: ({x1},{y1})~({x2},{y2})")
            # 🔥 시각화
            annotated = results[0].plot(img=annotated)

        annotated_frames.append(annotated)

    cv2.imshow("Camera 1", annotated_frames[0])
    cv2.imshow("Camera 2", annotated_frames[1])

    # ESC 종료
    if cv2.waitKey(1) & 0xFF == 27:
        break

# -----------------------------
# 종료
# -----------------------------
cap1.release()
cap2.release()
cv2.destroyAllWindows()
print("🛑 프로그램 종료")
