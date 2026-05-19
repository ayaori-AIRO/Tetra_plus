from scservo_sdk import sms_sts, PortHandler

# ==============================
# Configuration
# ==============================
#SERIAL_PORT = "COM5" #연결된 시리얼 포트 (Window)
SERIAL_PORT = "/dev/ttyUSB0"     # 연결된 시리얼 포트 (Ubuntu)
BAUDRATE = 1000000
SERVO_ID = 1

# ==============================
# Register addresses
# ==============================
ADDR_PRESENT_POSITION = 56
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMPERATURE = 63
ADDR_MOVING = 66
ADDR_TORQUE_ENABLE = 40

# ==============================
# Initialize
# ==============================
port_handler = PortHandler(SERIAL_PORT)
servo = sms_sts(port_handler)

# Open port
if port_handler.openPort():
    print("✓ Port opened successfully")
else:
    print("✗ Failed to open port")
    quit()

# Set baudrate
if port_handler.setBaudRate(BAUDRATE):
    print(f"✓ Baud rate set to {BAUDRATE}")
else:
    print("✗ Failed to set baud rate")
    quit()

# Ping servo
model_number, comm_result, error = servo.ping(SERVO_ID)

if comm_result == 0:
    print(f"✓ Servo ID {SERVO_ID} found!")
    print(f"Model number: {model_number}")
else:
    print("✗ Failed to ping servo")
    quit()

# ==============================
# Read data
# ==============================

# Position
position, comm_result, error = servo.read2ByteTxRx(SERVO_ID, ADDR_PRESENT_POSITION)

if comm_result == 0:
    degrees = position * 360 / 4096
    print(f"Current Position: {position} (raw) = {degrees:.1f}°")
else:
    print("Failed to read position")

# Voltage
voltage_raw, comm_result, error = servo.read1ByteTxRx(SERVO_ID, ADDR_PRESENT_VOLTAGE)

if comm_result == 0:
    voltage = voltage_raw * 0.1
    print(f"Voltage: {voltage:.1f}V")
else:
    print("Failed to read voltage")

# Temperature
temp, comm_result, error = servo.read1ByteTxRx(SERVO_ID, ADDR_PRESENT_TEMPERATURE)

if comm_result == 0:
    print(f"Temperature: {temp}°C")
else:
    print("Failed to read temperature")

# Torque status
torque_enabled, comm_result, error = servo.read1ByteTxRx(SERVO_ID, ADDR_TORQUE_ENABLE)

if comm_result == 0:
    print(f"Torque Enabled: {'Yes' if torque_enabled else 'No'}")
else:
    print("Failed to read torque status")

# Moving status
moving, comm_result, error = servo.read1ByteTxRx(SERVO_ID, ADDR_MOVING)

if comm_result == 0:
    print(f"Moving: {'Yes' if moving else 'No'}")
else:
    print("Failed to read moving status")