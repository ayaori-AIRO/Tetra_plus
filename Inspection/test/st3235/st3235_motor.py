import time
import json
from scservo_sdk import PortHandler, sms_sts
import os

# 🔥 현재 파일 기준 상위 폴더 경로
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(BASE_DIR, "config", "st3235_config.json")

with open(config_path, "r") as f:
    cfg = json.load(f)

# ==============================
# 설정 값 가져오기
# ==============================
SERIAL_PORT = cfg["SERIAL_PORT"]
BAUDRATE = cfg["BAUDRATE"]
SERVO_ID = cfg["SERVO_ID"]

ADDR_TORQUE_ENABLE = cfg["ADDR_TORQUE_ENABLE"]
ADDR_GOAL_POSITION = cfg["ADDR_GOAL_POSITION"]
ADDR_PRESENT_POSITION = cfg["ADDR_PRESENT_POSITION"]
ADDR_PRESENT_VOLTAGE = cfg["ADDR_PRESENT_VOLTAGE"]
ADDR_PRESENT_TEMPERATURE = cfg["ADDR_PRESENT_TEMPERATURE"]

goal_position = cfg["GOAL_POSITION"]
move_speed = cfg["MOVE_SPEED"]
move_acc = cfg["MOVE_ACC"]

# ==============================
# 시리얼 포트 초기화
# ==============================
portHandler = PortHandler(SERIAL_PORT)
servo = sms_sts(portHandler)

if not portHandler.openPort():
    print("포트 열기 실패")
    quit()
print("포트 연결 성공")

if not portHandler.setBaudRate(BAUDRATE):
    print("보드레이트 설정 실패")
    quit()
print("보드레이트 설정 성공")

# ==============================
# 서보 연결 확인 (Ping)
# ==============================
model_number, result, error = servo.ping(SERVO_ID)
if result != 0:
    print("서보 발견 실패")
    quit()
print("서보 발견 | 모델 번호:", model_number)

# ==============================
# 현재 토크 상태 읽기
# ==============================
torque_state, result, error = servo.read1ByteTxRx(SERVO_ID, ADDR_TORQUE_ENABLE)
if result == 0:
    print("현재 토크 상태 :", "ON" if torque_state==1 else "OFF")
else:
    print("토크 상태 읽기 실패")

# ==============================
# 토크 활성화
# ==============================
servo.write1ByteTxRx(SERVO_ID, ADDR_TORQUE_ENABLE, 1)
print("토크 활성화 완료")
time.sleep(1)

# ==============================
# 모터 이동
# ==============================
degree = goal_position * 360 / 4096
print(f"이동 명령 | 목표 위치: {goal_position} | 각도: {degree:.2f} | 속도: {move_speed} | 가속도: {move_acc}")

servo.WritePosEx(SERVO_ID, goal_position, move_speed, move_acc)
time.sleep(3)

# ==============================
# 현재 위치 읽기
# ==============================
current_position, result, error = servo.read2ByteTxRx(SERVO_ID, ADDR_PRESENT_POSITION)
if result == 0:
    current_degree = current_position * 360 / 4096
    print("현재 위치 :", current_position, "| 각도:", round(current_degree, 2))
else:
    print("현재 위치 읽기 실패")

# ==============================
# 전압 / 온도 확인
# ==============================
voltage_raw, result, error = servo.read1ByteTxRx(SERVO_ID, ADDR_PRESENT_VOLTAGE)
if result == 0:
    print("현재 전압:", voltage_raw*0.1, "V")

temp, result, error = servo.read1ByteTxRx(SERVO_ID, ADDR_PRESENT_TEMPERATURE)
if result == 0:
    print("현재 온도:", temp, "도")