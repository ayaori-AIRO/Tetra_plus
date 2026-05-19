from ultralytics import YOLO
import cv2
import numpy as np
import math

# ================================
# 1️⃣ 모델 로드
# ================================
model = YOLO("/home/ayaori/Capstone/runs/detect/Capstone/fire_extinguisher/weights/best.pt")

# ================================
# 2️⃣ 이미지 불러오기
# ================================
img_path = "/home/ayaori/Capstone/capture/FireExtinguisher_top_edit.jpg"
img = cv2.imread(img_path)

if img is None:
    raise Exception("이미지를 불러올 수 없습니다.")

cv2.imshow("1_original", cv2.resize(img, None, fx=0.5, fy=0.5))

# ================================
# 3️⃣ YOLO 탐지
# ================================
results = model(img)

# ================================
# 4️⃣ bounding box → crop
# ================================
for r in results:
    boxes = r.boxes.xyxy.cpu().numpy()

    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box)

        crop = img[y1:y2, x1:x2]

        cv2.imshow("2_crop", cv2.resize(crop, None, fx=0.7, fy=0.7))

        # ================================
        # 5️⃣ Grayscale
        # ================================
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        cv2.imshow("3_gray", cv2.resize(gray, None, fx=0.7, fy=0.7))

        # ================================
        # 6️⃣ Blur
        # ================================
        blur = cv2.GaussianBlur(gray, (5,5), 0)

        cv2.imshow("4_blur", cv2.resize(blur, None, fx=0.7, fy=0.7))

        # ================================
        # 7️⃣ Edge
        # ================================
        edges = cv2.Canny(blur, 50, 150)

        cv2.imshow("5_edges", cv2.resize(edges, None, fx=0.7, fy=0.7))

        # ================================
        # 8️⃣ Contour 찾기
        # ================================
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_rect = None
        max_area = 0

        for cnt in contours:

            area = cv2.contourArea(cnt)
            if area < 100:
                continue

            peri = cv2.arcLength(cnt, True)

            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            # 꼭짓점 4개 → 사각형
            if len(approx) == 4 and area > max_area:
                best_rect = approx
                max_area = area

        result_img = crop.copy()

        if best_rect is not None:

            # 사각형 표시
            cv2.drawContours(result_img, [best_rect], -1, (0,255,0), 3)

            # 중심 계산
            M = cv2.moments(best_rect)

            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                cv2.circle(result_img, (cx,cy), 6, (0,0,255), -1)

                print("사각형 중심:", cx, cy)
                print("area:", max_area)

        cv2.imshow("6_best_rectangle", cv2.resize(result_img, None, fx=0.7, fy=0.7))

cv2.waitKey(0)
cv2.destroyAllWindows()