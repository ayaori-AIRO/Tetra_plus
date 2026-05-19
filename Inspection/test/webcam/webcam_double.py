import cv2
import os
import time
from datetime import datetime

# 저장 폴더
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
capture_dir = os.path.join(BASE_DIR, "capture")
os.makedirs(capture_dir, exist_ok=True)

# 카메라 열기
cap1 = cv2.VideoCapture("/dev/video2", cv2.CAP_V4L2)
cap2 = cv2.VideoCapture("/dev/video4", cv2.CAP_V4L2)

# 카메라 설정 함수
def setup_camera(cap, name):
    if not cap.isOpened():
        print(f"❌ {name} 열기 실패")
        return False

    # 최대 화질: 1080p 30fps
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, 30)

    # 자동 초점 끄고 고정
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cap.set(cv2.CAP_PROP_FOCUS, 30)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"{name}: {width}x{height} {fps:.0f}fps")

    return True

if not setup_camera(cap1, "Camera1") or not setup_camera(cap2, "Camera2"):
    exit()

# 카메라 초기화 시간
time.sleep(2)

# 첫 프레임 여러 번 읽어서 버퍼 안정화
for _ in range(10):
    cap1.read()
    cap2.read()

print("✅ 카메라 실행됨")
print("📸 'c' 누르면 캡쳐")
print("🛑 ESC 누르면 종료")

cv2.namedWindow("Camera 1", cv2.WINDOW_NORMAL)
cv2.namedWindow("Camera 2", cv2.WINDOW_NORMAL)

while True:
    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()

    if not ret1:
        print("❌ Camera 1 프레임 읽기 실패 (/dev/video2)")
        break

    if not ret2:
        print("❌ Camera 2 프레임 읽기 실패 (/dev/video4)")
        break

    cv2.imshow("Camera 1", frame1)
    cv2.imshow("Camera 2", frame2)

    key = cv2.waitKey(1) & 0xFF

    # ESC 종료
    if key == 27:
        break

    # c 누르면 저장
    elif key == ord('c'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        path1 = os.path.join(capture_dir, f"cam1_{timestamp}.jpg")
        path2 = os.path.join(capture_dir, f"cam2_{timestamp}.jpg")

        ok1 = cv2.imwrite(path1, frame1)
        ok2 = cv2.imwrite(path2, frame2)

        if ok1 and ok2:
            print("📸 저장 완료")
            print(path1)
            print(path2)
        else:
            print("❌ 저장 실패")

cap1.release()
cap2.release()
cv2.destroyAllWindows()

print("🛑 프로그램 종료")