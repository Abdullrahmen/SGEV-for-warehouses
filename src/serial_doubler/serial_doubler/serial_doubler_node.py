#!/usr/bin/env python3
"""
ROS2 Node: Serial USB communication with ESP32
Publishes: /encoder1 (Int32), /encoder2 (Int32), /voltage (Float32)
Subscribes: /cmd_vel (Twist) -> sends "Linear vx\nAngular wz\n" over serial
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Float32
from geometry_msgs.msg import Twist
import serial
import threading
import time


class SerialNode(Node):
    def __init__(self):
        super().__init__('serial_node')

        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)

        port      = self.get_parameter('port').get_parameter_value().string_value
        baud_rate = self.get_parameter('baud_rate').get_parameter_value().integer_value

        self.pub_enc1    = self.create_publisher(Int32,   'encoder1', 10)
        self.pub_enc2    = self.create_publisher(Int32,   'encoder2', 10)
        self.pub_voltage = self.create_publisher(Float32, 'voltage',  10)
        self.pub_voltage = self.create_publisher(Float32, 'linear',  10)


        self.create_subscription(Twist, 'cmd_vel', self._cmd_vel_callback, 10)

        try:
            self.ser = serial.Serial(port=port, baudrate=baud_rate, timeout=2.0)
            self.get_logger().info(f'Opened {port} @ {baud_rate} baud')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to open serial port: {e}')
            raise SystemExit(1)

        time.sleep(2.0)
        self.ser.reset_input_buffer()

        self._stop = threading.Event()
        threading.Thread(target=self._read_loop, daemon=True).start()

    def _cmd_vel_callback(self, msg: Twist):
        """Send cmd_vel to ESP32 as two lines: 'Linear vx' and 'Angular wz'"""
        if self.ser.is_open:
            try:
                payload = f'Linear {msg.linear.x:.4f}\nAngular {msg.angular.z:.4f}\n'
                self.ser.write(payload.encode('utf-8'))
                self.get_logger().debug(f'Sent: Linear {msg.linear.x:.4f}, Angular {msg.angular.z:.4f}')
            except serial.SerialException as e:
                self.get_logger().error(f'Write error: {e}')

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='replace').strip()
                    self._parse(line)
                else:
                    time.sleep(0.01)
            except serial.SerialException as e:
                self.get_logger().error(f'Read error: {e}')
                time.sleep(0.5)

    def _parse(self, line: str):
        """Expected formats: 'Encoder1 42'  'Encoder2 7'  'Voltage 3.31'"""
        parts = line.split()
        if len(parts) != 2:
            self.get_logger().debug(f'Ignored: {line}')
            return

        key, val = parts[0], parts[1]

        try:
            if key == 'Encoder1':
                msg = Int32(); msg.data = int(val);     self.pub_enc1.publish(msg)
                self.get_logger().info(f'Encoder1 {msg.data}')
            elif key == 'Encoder2':
                msg = Int32(); msg.data = int(val);     self.pub_enc2.publish(msg)
                self.get_logger().info(f'Encoder2 {msg.data}')
            elif key == 'Voltage':
                msg = Float32(); msg.data = float(val); self.pub_voltage.publish(msg)
                self.get_logger().info(f'Voltage {msg.data}')
            elif key == 'linear':
                msg = Float32(); msg.data = float(val); self.pub_voltage.publish(msg)
                self.get_logger().info(f'Linear {msg.data}')    
            else:
                self.get_logger().debug(f'Unknown key: {key}')
        except ValueError:
            self.get_logger().warn(f'Bad value in: {line}')

    def destroy_node(self):
        self._stop.set()
        if self.ser.is_open:
            self.ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()