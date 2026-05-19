import serial.tools.list_ports

# List all available serial ports
ports = serial.tools.list_ports.comports()

print("Available serial ports:")
for port in ports:
    print(f"  {port.device}")
    print(f"    Description: {port.description}")
    print(f"    Manufacturer: {port.manufacturer}")
    print()