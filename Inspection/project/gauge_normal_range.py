import cv2
import numpy as np
import os
import json

# 🔥 현재 파일 기준 상위 폴더 경로 얻기
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 🔥 model_config.json 경로
model_config_path = os.path.join(BASE_DIR, "config", "model_config.json")

with open(model_config_path, "r") as f:
    model_config = json.load(f)

# ================================
# 1️⃣ 이미지 읽기
# ================================
gauge_crop_image_path = model_config["gauge_crop_image_path"]
gauge_img = cv2.imread(gauge_crop_image_path)
h, w = gauge_img.shape[:2]

# ================================
# 2️⃣ 원형 마스크 생성
# ================================
circle_mask = np.zeros((h, w), dtype=np.uint8)
center = (w // 2, h // 2)
radius = min(w, h) // 2 - 5
cv2.circle(circle_mask, center, radius, 255, -1)

# ================================
# 3️⃣ 원 영역만 남기기
# ================================
gauge_circle_img = cv2.bitwise_and(gauge_img, gauge_img, mask=circle_mask)

# ================================
# 4️⃣ 사각형 영역 선택 (x=31~50, y=4~22)
# ================================
rect_mask = np.zeros((h, w), dtype=np.uint8)
rect_mask[4:23, 31:51] = 255  # y: 4~22, x: 31~50

# 원형 마스크와 사각형 마스크 AND 처리
final_mask = cv2.bitwise_and(circle_mask, rect_mask)
gauge_masked_img = cv2.bitwise_and(gauge_img, gauge_img, mask=final_mask)

# ================================
# 5️⃣ Gray 변환 후 Canny Edge Detection
# ================================
gray = cv2.cvtColor(gauge_masked_img, cv2.COLOR_BGR2GRAY)
edges = cv2.Canny(gray, 50, 150)

# ================================
# 6️⃣ Hough Line으로 직선 검출
# ================================
lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=10, minLineLength=5, maxLineGap=2)

# ================================
# 7️⃣ 교차점 계산 및 각도 측정
# ================================
def line_to_vector(line):
    x1, y1, x2, y2 = line
    return np.array([x2-x1, y2-y1], dtype=np.float32)

def angle_between(v1, v2):
    cos_theta = np.dot(v1, v2) / (np.linalg.norm(v1)*np.linalg.norm(v2) + 1e-8)
    cos_theta = np.clip(cos_theta, -1, 1)
    return np.degrees(np.arccos(cos_theta))

needle_tip = None
min_angle = 180
intersection_point = None

if lines is not None and len(lines) > 1:
    for i in range(len(lines)):
        for j in range(i+1, len(lines)):
            v1 = line_to_vector(lines[i][0])
            v2 = line_to_vector(lines[j][0])
            ang = angle_between(v1, v2)
            if ang < min_angle:
                min_angle = ang
                x1, y1, x2, y2 = lines[i][0]
                x3, y3, x4, y4 = lines[j][0]
                intersection_point = ((x1+x2+x3+x4)//4, (y1+y2+y3+y4)//4)

# ================================
# 8️⃣ 결과 표시용 이미지 복사
# ================================
img_result = gauge_img.copy()
if intersection_point is not None:
    cv2.circle(img_result, intersection_point, 3, (0,0,255), -1)
    cv2.putText(img_result, f"{min_angle:.1f} deg",
                (intersection_point[0]+5, intersection_point[1]-5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,255), 1)

# ================================
# 9️⃣ 빨간 바늘 여부 확인 (끝점 아래 4픽셀 이동)
# ================================
is_red = False
if intersection_point is not None:
    x, y = intersection_point
    y_check = min(y + 4, h - 1)
    b, g, r = gauge_img[y_check, x]
    print("Red check at:", (x, y_check), "BGR:", b, g, r)
    if r > 130 and r > g + 13 and r > b + 13:
        is_red = True
        print("Red needle detected:", is_red)
    else:
        print("Red tick mark ❌")

# ================================
# 🔵 정상 범위 초록색 여부 확인 (intersection_point 기준)
# ================================
is_normal = False
if intersection_point is not None:
    x, y = intersection_point
    b, g, r = gauge_img[y, x]
    print("Normal check at:", (x, y), "BGR:", b, g, r)
    if r <= 100 and g <= 100 and b <= 100 and g > r and g > b:
        is_normal = True
print("Normal range detected:", is_normal)

# ================================
# 10️⃣ 결과 시각화
# ================================
if intersection_point is not None:
    color = (0,255,0) if is_red else (255,0,0)
    text = "RED NEEDLE" if is_red else "NOT RED"
    cv2.circle(img_result, intersection_point, 5, color, -1)
    cv2.putText(img_result, text, (intersection_point[0]+5, intersection_point[1]+15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

# ================================
# 11️⃣ 윈도우 표시
# ================================
cv2.imshow("Original", gauge_img)
cv2.imshow("Circle Mask", circle_mask)
cv2.imshow("Circle Applied", gauge_circle_img)
cv2.imshow("Masked Image", gauge_masked_img)
cv2.imshow("Edges", edges)
cv2.imshow("Needle Tip Candidate", img_result)

cv2.waitKey(0)
cv2.destroyAllWindows()