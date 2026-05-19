from ultralytics import YOLO
import cv2
import os

# 입력/저장 경로
img_path = "/home/ayaori/Capstone/capture/FireExtinguisher_up.jpg"
save_dir = "/home/ayaori/Capstone/capture"
os.makedirs(save_dir, exist_ok=True)

# YOLOv11 모델 로드
model_path = "/home/ayaori/Capstone/runs/detect/Capstone/label/weights/best.pt"
model = YOLO(model_path)  # ultralytics YOLOv11

# 이미지 읽기
img = cv2.imread(img_path)
if img is None:
    raise FileNotFoundError(f"{img_path} 파일을 찾을 수 없음")

# 추론
results = model.predict(source=img, verbose=False)  # source에 이미지 전달, verbose=False로 로그 최소화

# 결과 박스 가져오기
boxes = results[0].boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2

if len(boxes) == 0:
    print("⚠️ 압력게이지 감지 실패")
else:
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        cropped = img[y1:y2, x1:x2]
        save_path = os.path.join(save_dir, f"label_crop_{i:02d}.jpg")
        cv2.imwrite(save_path, cropped)
        print(f"📌 잘라낸 이미지 저장: {save_path}")