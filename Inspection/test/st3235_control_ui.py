import tkinter as tk
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scservo_sdk import PortHandler, sms_sts

# 🔥 설정 파일 로드
config_path = os.path.join(BASE_DIR, "config", "st3235_config.json")

with open(config_path, "r") as f:
    cfg = json.load(f)

SERIAL_PORT = os.environ.get(
    "TETRA_ST3235_BALLSCREW_PORT",
    cfg.get("SERIAL_PORT", "/dev/tetra/st3235_ballscrew"),
)
BAUDRATE = cfg["BAUDRATE"]
SERVO_ID = cfg["SERVO_ID"]
ADDR_TORQUE_ENABLE = cfg["ADDR_TORQUE_ENABLE"]
ADDR_GOAL_POSITION = cfg["ADDR_GOAL_POSITION"]
ADDR_PRESENT_POSITION = cfg["ADDR_PRESENT_POSITION"]
ADDR_PRESENT_VOLTAGE = cfg["ADDR_PRESENT_VOLTAGE"]
ADDR_PRESENT_TEMPERATURE = cfg["ADDR_PRESENT_TEMPERATURE"]
move_speed = cfg["MOVE_SPEED"]
move_acc = cfg["MOVE_ACC"]

# ==============================
# 서보 초기화
# ==============================
portHandler = PortHandler(SERIAL_PORT)
servo = sms_sts(portHandler)

if not portHandler.openPort():
    raise Exception("포트 열기 실패")
if not portHandler.setBaudRate(BAUDRATE):
    raise Exception("보드레이트 설정 실패")

# 토크 활성화
servo.write1ByteTxRx(SERVO_ID, ADDR_TORQUE_ENABLE, 1)
time.sleep(0.5)

# ==============================
# 모터 상태 변수
# ==============================
current_position = 0  # 0~4095 기준 현재 위치

# ==============================
# 모터 이동 함수
# ==============================
def move_servo(position):
    global current_position
    if position < 0: position = 0
    if position > 4095: position = 4095
    servo.WritePosEx(SERVO_ID, position, move_speed, move_acc)
    current_position = position
    time.sleep(1)
    update_angle_label()

def degree_to_position(degree):
    """0°~360° -> 0~4095 변환"""
    if degree < 0: degree = 0
    if degree > 360: degree = 360
    return int(degree * 4096 / 360)

def get_current_angle():
    """현재 위치를 읽어서 각도로 반환"""
    return round(current_position * 360 / 4096, 1)

# ==============================
# UI 업데이트 함수
# ==============================
def update_angle_label():
    angle = get_current_angle()
    angle_label.config(text=f"현재 각도: {angle}°")

# ==============================
# 버튼 이벤트
# ==============================
def rotate_plus_90():
    move_servo(current_position + 1024)  # +90°

def rotate_minus_90():
    move_servo(current_position - 1024)  # -90°

def rotate_to_0():
    move_servo(0)

def rotate_to_custom():
    try:
        deg = float(entry_degree.get())
        pos = degree_to_position(deg)
        move_servo(pos)
    except ValueError:
        print("숫자를 입력해주세요!")

# ==============================
# Tkinter UI
# ==============================
root = tk.Tk()
root.title("ST3235 모터 테스트")

tk.Label(root, text="ST3235 모터 테스트 UI", font=("Arial", 16)).pack(pady=10)

# 사용자 각도 입력
frame_entry = tk.Frame(root)
frame_entry.pack(pady=10)

tk.Label(frame_entry, text="목표 각도(0~360°):").grid(row=0, column=0, padx=5)
entry_degree = tk.Entry(frame_entry, width=10)
entry_degree.grid(row=0, column=1, padx=5)
tk.Button(frame_entry, text="이동", command=rotate_to_custom).grid(row=0, column=2, padx=5)

# 현재 각도 표시
angle_label = tk.Label(root, text=f"현재 각도: {get_current_angle()}°", font=("Arial", 14))
angle_label.pack(pady=10)

# 고정 버튼
btn_frame = tk.Frame(root)
btn_frame.pack(pady=20)

tk.Button(btn_frame, text="-90°", command=rotate_minus_90, width=12, height=2).grid(row=0, column=0, padx=5)
tk.Button(btn_frame, text="원위치(0°)", command=rotate_to_0, width=12, height=2).grid(row=0, column=1, padx=5)
tk.Button(btn_frame, text="+90°", command=rotate_plus_90, width=12, height=2).grid(row=0, column=2, padx=5)

root.mainloop()
