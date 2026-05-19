import cv2
import numpy as np
import math

# ================================
# 1️⃣ 이미지 읽기
# ================================
img_path = "/home/ayaori/Capstone/capture/gauge_crop.jpg"
img = cv2.imread(img_path)
h, w = img.shape[:2]

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
img_circle = cv2.bitwise_and(img, img, mask=circle_mask)

# ================================
# 4️⃣ 사각형 영역 선택 (x=31~50, y=4~22)
# ================================
rect_mask = np.zeros((h, w), dtype=np.uint8)
rect_mask[4:23, 31:51] = 255  # y: 4~22, x: 31~50

# 원형 마스크와 사각형 마스크 AND 처리
final_mask = cv2.bitwise_and(circle_mask, rect_mask)
img_final = cv2.bitwise_and(img, img, mask=final_mask)

# ================================
# 5️⃣ Gray 변환
# ================================
gray = cv2.cvtColor(img_final, cv2.COLOR_BGR2GRAY)

# ================================
# 6️⃣ Edge Detection (Canny)
# ================================
edges = cv2.Canny(gray, 50, 150)

# ================================
# 7️⃣ Hough Line으로 직선 검출
# ================================
lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=10, minLineLength=5, maxLineGap=2)

# ================================
# 8️⃣ 교차점 계산 및 각도 측정
# ================================
def line_to_vector(line):
    x1, y1, x2, y2 = line
    return np.array([x2-x1, y2-y1], dtype=np.float32)

def angle_between(v1, v2):
    cos_theta = np.dot(v1,v2) / (np.linalg.norm(v1)*np.linalg.norm(v2)+1e-8)
    cos_theta = np.clip(cos_theta, -1, 1)
    return np.degrees(np.arccos(cos_theta))

needle_tip = None
min_angle = 180
intersection_point = None

if lines is not None and len(lines) > 1:
    for i in range(len(lines)):
        for j in range(i+1, len(lines)):
            # 각 선분의 벡터
            v1 = line_to_vector(lines[i][0])
            v2 = line_to_vector(lines[j][0])
            # 각도 계산
            ang = angle_between(v1, v2)
            if ang < min_angle:
                min_angle = ang
                # 교차점 근사: 선분 시작점끼리 평균
                x1, y1, x2, y2 = lines[i][0]
                x3, y3, x4, y4 = lines[j][0]
                intersection_point = ((x1+x2+x3+x4)//4, (y1+y2+y3+y4)//4)

# ================================
# 9️⃣ 결과 표시
# ================================
img_result = img.copy()

if intersection_point is not None:
    cv2.circle(img_result, intersection_point, 3, (0,0,255), -1)
    cv2.putText(img_result, f"{min_angle:.1f} deg", (intersection_point[0]+5, intersection_point[1]-5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,255), 1)

# ================================
# 🔴 10️⃣ 빨간색 여부 확인 (끝점 아래쪽으로 4픽셀 이동)
# ================================
is_red = False

if intersection_point is not None:
    x, y = intersection_point

    # 끝점에서 아래쪽으로 4픽셀 이동
    y_check = min(y + 4, h - 1)  # 이미지 범위를 넘지 않도록

    b, g, r = img[y_check, x]

    print("intersection_point:", intersection_point, " -> check at y =", y_check)
    print("BGR at check pixel:", b, g, r)

    if r > 130 and r > g and r > b:
        is_red = True

print("Red needle:", is_red)

# 결과 표시
if intersection_point is not None:
    color = (0,255,0) if is_red else (255,0,0)
    text = "RED NEEDLE" if is_red else "NOT RED"

    cv2.circle(img_result, intersection_point, 5, color, -1)
    cv2.putText(img_result, text, (intersection_point[0]+5, intersection_point[1]+15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

print("Red needle detected:", is_red)
    

cv2.imshow("Original", img)

# 원형 마스크 자체
cv2.imshow("Circle Mask", circle_mask)

# 원형 마스크 적용된 이미지
cv2.imshow("Circle Applied", img_circle)

cv2.imshow("Masked Image", img_final)
cv2.imshow("Edges", edges)
cv2.imshow("Needle Tip Candidate", img_result)

cv2.waitKey(0)
cv2.destroyAllWindows()