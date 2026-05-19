import cv2
import os
import time

# 저장 폴더
save_dir = "/home/ayaori/Capstone/capture"
os.makedirs(save_dir, exist_ok=True)

# 카메라 설정
cap = cv2.VideoCapture(2, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    print("❌ 카메라 열기 실패")
    exit()

cv2.namedWindow("C922 Live", cv2.WINDOW_NORMAL)
frame_count = 0

print("✅ 실시간 모드 시작 (스페이스바 눌러 캡처, ESC 종료)")

while True:
    # 오래된 프레임 폐기
    for _ in range(3):
        cap.grab()

    ret, frame = cap.read()
    if not ret:
        print("프레임 수신 실패")
        break

    # 화면 표시
    cv2.imshow("C922 Live", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == 27:  # ESC → 종료
        break
    elif key == 32:  # 스페이스바 → 캡처
        filename = os.path.join(save_dir, f"capture_{frame_count:04d}.jpg")
        cv2.imwrite(filename, frame)
        print(f"📸 저장: {filename}")
        frame_count += 1

cap.release()
cv2.destroyAllWindows()