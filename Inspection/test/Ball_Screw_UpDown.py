from pymodbus.client import ModbusSerialClient
import time

client = ModbusSerialClient(
    port="/dev/ttyUSB3",
    baudrate=38400,
    timeout=1
)

client.connect()

print("왕복 2회 시작")

travel = 65500
acc = 0
speed = 150

def move_relative(delta):
    # 🔥 방향 정의 (네 요청 기준)
    if delta >= 0:
        dir = 1   # CCW
    else:
        dir = 0   # CW

    dir_acc = (dir << 8) | acc

    move = abs(delta)

    move_bytes = move.to_bytes(4, byteorder='little', signed=False)
    pos1 = int.from_bytes(move_bytes[2:4], 'little')
    pos2 = int.from_bytes(move_bytes[0:2], 'little')

    client.write_registers(0x00FD, [dir_acc, speed, pos1, pos2], device_id=1)


# 🔥 왕복 2회 (for문 사용)
for i in range(2):
    print(f"{i+1}번째 왕복")

    # CW 이동
    print("CCW 이동")
    move_relative(travel)
    time.sleep(12)

    # CCW 이동
    print("CW 이동")
    move_relative(-travel)
    time.sleep(12)

# 🔥 정지
client.write_registers(0x00F6, [(0 << 8) | acc, 0])

client.close()

print("완료 (정지)")