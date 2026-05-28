import cv2
import numpy as np
import os
import math

# ================================
# 0. 설정 및 로드
# ================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAFE_ANGLE_MIN = 60
SAFE_ANGLE_MAX = 120

gauge_img = cv2.imread(
    "/home/ayaori/ros2_ws/src/tetra/Inspection/capture/Real_Environment/pressure_gauge/camera1_pressure_gauge_20260507_011409_1.jpg"
)
if gauge_img is None:
    print("[gauge_debug] 이미지를 불러올 수 없습니다.")
    exit()

h, w = gauge_img.shape[:2]

# ================================
# 1. Hough Circle로 게이지 중심 검출
# ================================
gray_for_circle = cv2.cvtColor(gauge_img, cv2.COLOR_BGR2GRAY)
gray_for_circle = cv2.medianBlur(gray_for_circle, 5)
circles = cv2.HoughCircles(
    gray_for_circle,
    cv2.HOUGH_GRADIENT,
    dp=1.2,
    minDist=min(w, h) // 2,
    param1=80,
    param2=20,
    minRadius=min(w, h) // 3,
    maxRadius=min(w, h) // 2,
)

detected_radius = min(w, h) // 2 - 5
circle_result = gauge_img.copy()
if circles is not None:
    circles = np.uint16(np.around(circles))
    x, y, r = circles[0][0]
    center = (int(x), int(y))
    detected_radius = int(r)
    print(f"[gauge_debug] Hough Circle 검출: center={center}, radius={detected_radius}")
else:
    center = (w // 2, h // 2)
    print(f"[gauge_debug] Hough Circle 미검출, 이미지 중앙 사용: center={center}")

cv2.circle(circle_result, center, max(1, detected_radius), (255, 255, 0), 1)
cv2.circle(circle_result, center, 2, (255, 255, 0), -1)
processing_radius = max(1, detected_radius - 5)

# ================================
# 2. 전처리 (Masking)
# ================================
circle_mask = np.zeros((h, w), dtype=np.uint8)
cv2.circle(circle_mask, center, processing_radius, 255, -1)
gauge_circle = cv2.bitwise_and(gauge_img, gauge_img, mask=circle_mask)

# HSV 변환 및 빨간색 마스킹 (원래 코드로 복원 - 바늘은 위쪽)
hsv = cv2.cvtColor(gauge_circle, cv2.COLOR_BGR2HSV)
mask1 = cv2.inRange(hsv, np.array([0, 10, 10]), np.array([40, 255, 255]))
mask2 = cv2.inRange(hsv, np.array([140, 10, 10]), np.array([180, 255, 255]))
red_mask = mask1 + mask2

# 노이즈 제거 (모폴로지)
kernel = np.ones((5, 5), np.uint8)
green_kernel = np.ones((3, 3), np.uint8)

# ================================
# 2. 정상 범위 HSV 추출
# ================================
lower_green = np.array([22, 25, 25])
upper_green = np.array([115, 255, 255])
green_mask = cv2.inRange(hsv, lower_green, upper_green)
clean_green = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, green_kernel)

green_contours, _ = cv2.findContours(clean_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
safe_min = SAFE_ANGLE_MIN
safe_max = SAFE_ANGLE_MAX
configured_safe_min = safe_min
configured_safe_max = safe_max

if green_contours:
    largest_green = max(green_contours, key=cv2.contourArea)
    if cv2.contourArea(largest_green) > 30:
        pts = largest_green.reshape(-1, 2)
        angles = []
        for pt in pts:
            dx = pt[0] - center[0]
            dy = center[1] - pt[1]
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0:
                angle += 360
            angles.append(angle)

        safe_min, safe_max = min(angles), max(angles)

clean_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

# ================================
# 3. 특징점 검출 및 벡터 계산
# ================================
# 컨투어 기반 바늘 끝 검출 (원래 코드)
contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
img_result = gauge_img.copy()
cv2.circle(img_result, center, max(1, detected_radius), (255, 255, 0), 1)
cv2.circle(img_result, center, 2, (255, 255, 0), -1)

safe_range_result = gauge_img.copy()
cv2.circle(safe_range_result, center, max(1, detected_radius), (255, 255, 0), 1)
cv2.circle(safe_range_result, center, 2, (255, 255, 0), -1)

safe_radius = max(1, detected_radius - 12)
safe_arc = []
for angle in range(round(configured_safe_min), round(configured_safe_max) + 1):
    x = round(center[0] + safe_radius * math.cos(math.radians(angle)))
    y = round(center[1] - safe_radius * math.sin(math.radians(angle)))
    safe_arc.append((x, y))

if len(safe_arc) > 1:
    cv2.polylines(safe_range_result, [np.array(safe_arc, dtype=np.int32)], False, (0, 255, 0), 3)

for angle in (configured_safe_min, configured_safe_max):
    x = round(center[0] + safe_radius * math.cos(math.radians(angle)))
    y = round(center[1] - safe_radius * math.sin(math.radians(angle)))
    cv2.line(safe_range_result, center, (x, y), (255, 0, 0), 4)

cv2.putText(safe_range_result, f"NORMAL {configured_safe_min:.0f}-{configured_safe_max:.0f} deg", (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
cv2.putText(safe_range_result, f"NORMAL {configured_safe_min:.0f}-{configured_safe_max:.0f} deg", (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

tip_point = None
tip_crop = None

if contours:
    largest_contour = max(contours, key=cv2.contourArea)
    pts = largest_contour.reshape(-1, 2)
    distances = np.sqrt((pts[:, 0] - center[0])**2 + (pts[:, 1] - center[1])**2)
    max_dist_idx = np.argmax(distances)
    tip_point = tuple(pts[max_dist_idx])
    print(f"[gauge_debug] 컨투어 기반: center={center}, tip_point={tip_point}")
    print(f"[gauge_debug] 바늘 끝 좌표: ({tip_point[0]}, {tip_point[1]})")
    print(f"[gauge_debug] 중심에서 거리: {distances[max_dist_idx]:.1f}")

    dx = tip_point[0] - center[0]
    dy = center[1] - tip_point[1]

    current_angle = math.degrees(math.atan2(dy, dx))
    if current_angle < 0:
        current_angle += 360

    is_safe_angle = safe_min <= current_angle <= safe_max

    check_points = []
    matched_check_point = None
    is_safe_hsv = False
    for check_dist in  (3, 5, 7, 9,11):
        check_x = round(tip_point[0] + check_dist * math.cos(math.radians(current_angle)))
        check_y = round(tip_point[1] - check_dist * math.sin(math.radians(current_angle)))

        if 0 <= check_x < w and 0 <= check_y < h:
            check_points.append((check_x, check_y))
            y1 = max(0, check_y - 1)
            y2 = min(h, check_y + 2)
            x1 = max(0, check_x - 1)
            x2 = min(w, check_x + 2)
            if cv2.countNonZero(clean_green[y1:y2, x1:x2]) > 0:
                is_safe_hsv = True
                if matched_check_point is None:
                    matched_check_point = (check_x, check_y)

    if is_safe_hsv:
        status_text = f"SAFE HSV ({current_angle:.1f} deg)"
        line_color = (0, 255, 0)
        decision_source = "HSV_MAIN"
    elif is_safe_angle:
        status_text = f"SAFE ANGLE BACKUP ({current_angle:.1f} deg)"
        line_color = (0, 200, 255)
        decision_source = "ANGLE_BACKUP"
    else:
        status_text = f"DANGER ({current_angle:.1f} deg)"
        line_color = (0, 0, 255)
        decision_source = "DANGER"

    print(f"[gauge_debug] 정상 범위 각도: {safe_min:.1f} ~ {safe_max:.1f}")
    print(f"[gauge_debug] 현재 바늘 각도: {current_angle:.1f}")
    print(f"[gauge_debug] HSV 주 판정: {is_safe_hsv}, 각도 보조 판정: {is_safe_angle}")
    print(f"[gauge_debug] 최종 판정 기준: {decision_source}")

    cv2.line(img_result, center, tip_point, line_color, 2)

    # 바늘 끝점을 파란색 1픽셀로만 표시
    cv2.circle(img_result, tip_point, 1, (255, 0, 0), -1)

    crop_size = 20
    tip_x1 = max(0, tip_point[0] - crop_size)
    tip_y1 = max(0, tip_point[1] - crop_size)
    tip_x2 = min(w, tip_point[0] + crop_size + 1)
    tip_y2 = min(h, tip_point[1] + crop_size + 1)
    tip_crop = img_result[tip_y1:tip_y2, tip_x1:tip_x2].copy()
    tip_crop = cv2.resize(tip_crop, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)

    if matched_check_point is None and check_points:
        matched_check_point = check_points[0]

    if matched_check_point is not None:
        cv2.circle(img_result, matched_check_point, 1, (0, 255, 255), -1)

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img_result, status_text, (5, h - 10), font, 0.5, (0, 0, 0), 3)
    cv2.putText(img_result, status_text, (5, h - 10), font, 0.5, line_color, 1)
else:
    print("[gauge_debug] no contours found")

# ================================
# 거리 계산 함수
# ================================
def line_distance_to_point(line, pt):
    x1, y1, x2, y2 = line
    px, py = pt
    vx = x2 - x1
    vy = y2 - y1
    if vx == 0 and vy == 0:
        return np.hypot(px - x1, py - y1)
    return abs(vy * px - vx * py + x2 * y1 - y2 * x1) / np.hypot(vx, vy)


cv2.imshow("1. Original", gauge_img)
cv2.imshow("2. Circle Detection", circle_result)
cv2.imshow("3. Safe Angle Range", safe_range_result)
cv2.imshow("4. HSV Masking", red_mask)     # HSV로 빨간색만 추출한 상태
cv2.imshow("5. Morphology", clean_mask)    # 노이즈 제거된 최종 바늘 형상
cv2.imshow("6. Green Mask", green_mask)
cv2.imshow("7. Clean Green", clean_green)
cv2.imshow("8. Final Result", img_result)  # 중심-바늘 끝 연결 및 각도 표시
if tip_crop is not None:
    cv2.imshow("9. Needle Tip Crop", tip_crop)

cv2.waitKey(0)
cv2.destroyAllWindows()

# 디버그 이미지 저장
# debug_dir = os.path.join(BASE_DIR, "runs", "gauge_debug")
# os.makedirs(debug_dir, exist_ok=True)
# cv2.imwrite(os.path.join(debug_dir, "1_original.jpg"), gauge_img)
# cv2.imwrite(os.path.join(debug_dir, "2_hsv_mask.jpg"), red_mask)
# cv2.imwrite(os.path.join(debug_dir, "3_morphology.jpg"), clean_mask)
# cv2.imwrite(os.path.join(debug_dir, "4_final_result.jpg"), img_result)
# print(f"[gauge_debug] 디버그 이미지 저장됨: {debug_dir}")
