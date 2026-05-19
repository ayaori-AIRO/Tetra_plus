from pymodbus.client import ModbusSerialClient


PORT = "/dev/ttyUSB0"
BAUDRATE = 38400
DEVICE_ID = 1

TRAVEL = 67000
ACC = 0
SPEED = 150

DIR_CW = 0


def move_relative(client, direction, move, acc, speed):
    dir_acc = (direction << 8) | acc

    move_bytes = move.to_bytes(4, byteorder="little", signed=False)
    pos1 = int.from_bytes(move_bytes[2:4], "little")
    pos2 = int.from_bytes(move_bytes[0:2], "little")

    client.write_registers(0x00FD, [dir_acc, speed, pos1, pos2], device_id=DEVICE_ID)


def stop(client):
    client.write_registers(0x00F6, [(DIR_CW << 8) | ACC, 0], device_id=DEVICE_ID)


client = ModbusSerialClient(
    port=PORT,
    baudrate=BAUDRATE,
    timeout=1,
)

try:
    if not client.connect():
        raise RuntimeError(f"볼스크류 포트 연결 실패: {PORT}")

    print(f"볼스크류 UP 이동 시작 | 방향: CW | 이동량: {TRAVEL}")
    move_relative(client, DIR_CW, TRAVEL, ACC, SPEED)

finally:
    client.close()
