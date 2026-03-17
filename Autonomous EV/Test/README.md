# ESP32 - ROS2 UART Communication Test

This project provides simple code to test UART communication between ESP32 and Raspberry Pi 5 running ROS2.

## Hardware Setup

### Wiring Diagram

```
ESP32           Raspberry Pi 5
-------         ---------------
GPIO1 (TX0) --> GPIO15 (RX, Pin 10)
GPIO3 (RX0) <-- GPIO14 (TX, Pin 8)
GND         --- GND (Pin 6)
```

**IMPORTANT**: Common ground is required for UART communication!

### Pin Reference

| ESP32 | GPIO | Function | RPi Pin | Function |
|-------|------|----------|---------|----------|
| TX0   | 1    | Transmit | 10      | RX       |
| RX0   | 1    | Receive  | 8       | TX       |
| GND   | -    | Ground   | 6       | GND      |

## Raspberry Pi 5 Setup

### 1. Enable Serial Port

```bash
sudo raspi-config
```

Navigate to: `Interface Options` -> `Serial Port`

- **Disable** serial console (login shell)
- **Enable** serial port hardware

### 2. Add User to Dialout Group

```bash
sudo usermod -aG dialout $USER
```

Logout and login again for changes to take effect.

### 3. Install ROS2 Dependencies

```bash
# Install pyserial for Python serial communication
pip3 install pyserial

# Or if using system packages
sudo apt install python3-serial
```

### 4. Create ROS2 Package

```bash
# Navigate to your ROS2 workspace
cd ~/ros2_ws/src

# Create package
ros2 pkg create --build-type ament_python esp32_uart_comm

# Copy the node file
cp ros2_uart_node.py ~/ros2_ws/src/esp32_uart_comm/esp32_uart_comm/

# Build
cd ~/ros2_ws
colcon build

# Source
source install/setup.bash
```

## ESP32 Setup

### 1. Upload Code

1. Open `esp32_uart.ino` in Arduino IDE
2. Select your ESP32 board from `Tools` -> `Board`
3. Select correct COM port from `Tools` -> `Port`
4. Click Upload

### 2. Monitor Serial

Use Arduino Serial Monitor at **115200 baud** to verify ESP32 is sending heartbeats.

## Running the Test

### Terminal 1: Run ROS2 Node

```bash
source ~/ros2_ws/install/setup.bash
ros2 run esp32_uart_comm ros2_uart_node
```

### Terminal 2: Send Commands to ESP32

```bash
# Turn on LED
ros2 topic pub /esp32/outgoing std_msgs/String "data: 'H'" --once

# Turn off LED
ros2 topic pub /esp32/outgoing std_msgs/String "data: 'L'" --once

# Request status
ros2 topic pub /esp32/outgoing std_msgs/String "data: 'S'" --once

# Send custom message
ros2 topic pub /esp32/outgoing std_msgs/String "data: 'Hello ESP32'" --once
```

### Terminal 3: Listen for Messages from ESP32

```bash
ros2 topic echo /esp32/incoming
```

## Troubleshooting

### Serial Port Permission Denied

```bash
sudo chmod 666 /dev/ttyAMA0
# Or add user to dialout group (permanent solution)
sudo usermod -aG dialout $USER
```

### Find Available Serial Ports

```bash
# On Raspberry Pi
ls /dev/tty*
ls /dev/serial*

# Common ports:
# /dev/ttyAMA0 - Mini UART (default on RPi 5)
# /dev/ttyS0   - Another serial port
# /dev/ttyUSB0 - USB-serial adapter
```

### Check Serial Port is Working

```bash
# Install minicom
sudo apt install minicom

# Test serial connection
minicom -b 115200 -o -D /dev/ttyAMA0
```

### No Communication

1. Check wiring (TX to RX, RX to TX, GND to GND)
2. Verify baud rates match (115200)
3. Check if serial port is enabled on RPi
4. Ensure no other program is using the serial port

## Commands Reference

| Command | ESP32 Response |
|---------|----------------|
| H       | Turn LED ON |
| L       | Turn LED OFF |
| S       | Send status |
| (any)   | Echo back |

## License

MIT License
