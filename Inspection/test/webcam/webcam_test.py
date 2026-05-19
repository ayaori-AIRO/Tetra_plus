import cv2

# V4L2 백엔드 명시
cap = cv2.VideoCapture(8, cv2.CAP_V4L2)

# MJPEG 강제 (핵심)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

# 해상도 / FPS (너무 높으면 지연 생김)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

# 버퍼 최소화
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    print("❌ 카메라 열기 실패")
    exit()

print("✅ C922 저지연 모드 시작")

cv2.namedWindow("C922 Live", cv2.WINDOW_NORMAL)

while True:
    # 🔥 오래된 프레임 강제 폐기 (중요)
    for _ in range(3):
        cap.grab()

    ret, frame = cap.read()
    if not ret:
        print("프레임 수신 실패")
        break

    cv2.imshow("C922 Live", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
