#!/usr/bin/env python3
"""
ROS2 Node for UART Communication with ESP32

Hardware Connections:
- Raspberry Pi TX (GPIO14/Pin 8) -> ESP32 RX0 (GPIO3)
- Raspberry Pi RX (GPIO15/Pin 10) -> ESP32 TX0 (GPIO1)
- GND -> GND (common ground is REQUIRED!)

Setup on Raspberry Pi 5:
1. Enable serial port: sudo raspi-config -> Interface Options -> Serial Port
   - Disable serial console (login shell)
   - Enable serial port hardware
2. Add user to dialout group: sudo usermod -aG dialout $USER
3. Logout and login again for changes to take effect

Run the node:
    ros2 run <package_name> ros2_uart_node
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial
import serial.tools.list_ports
import threading
import time


class ESP32UARTNode(Node):
    """
    ROS2 Node that communicates with ESP32 via UART
    """
    
    def __init__(self):
        # Initialize the ROS2 node with name 'esp32_uart_node'
        super().__init__('esp32_uart_node')
        
        # ============================================
        # Declare parameters (can be set from launch file)
        # ============================================
        self.declare_parameter('port', '/dev/ttyAMA0')  # Default serial port on RPi
        self.declare_parameter('baud_rate', 115200)     # Must match ESP32 baud rate
        self.declare_parameter('timeout', 1.0)          # Serial read timeout in seconds
        
        # Get parameter values
        self.port = self.get_parameter('port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.timeout = self.get_parameter('timeout').value
        
        # ============================================
        # Initialize Serial Connection
        # ============================================
        try:
            # Create serial connection
            # parity=serial.PARITY_NONE - no parity bit
            # stopbits=serial.STOPBITS_ONE - 1 stop bit
            # bytesize=serial.EIGHTBITS - 8 data bits
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            self.get_logger().info(f'Connected to {self.port} at {self.baud_rate} baud')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to open serial port: {e}')
            self.get_logger().info('Available ports:')
            # List available serial ports for debugging
            for port in serial.tools.list_ports.comports():
                self.get_logger().info(f'  - {port.device}: {port.description}')
            raise
        
        # ============================================
        # Create ROS2 Publishers
        # ============================================
        # Publisher for messages received from ESP32
        self.pub_from_esp32 = self.create_publisher(
            String,                          # Message type
            'esp32/incoming',                # Topic name
            10                               # Queue size
        )
        
        # ============================================
        # Create ROS2 Subscribers
        # ============================================
        # Subscribe to messages to send to ESP32
        self.sub_to_esp32 = self.create_subscription(
            String,                          # Message type
            'esp32/outgoing',                # Topic name
            self.send_to_esp32_callback,     # Callback function
            10                               # Queue size
        )
        
        # ============================================
        # Create Timer for Reading from UART
        # ============================================
        # Timer runs at 100Hz (every 0.01 seconds)
        self.timer = self.create_timer(0.01, self.read_from_uart)
        
        # Flag to control the reading thread
        self.running = True
        
        # Log node started
        self.get_logger().info('ESP32 UART Node started!')
        self.get_logger().info('Publish commands to /esp32/outgoing to send to ESP32')
        self.get_logger().info('Subscribe to /esp32/incoming to receive from ESP32')
        
    def send_to_esp32_callback(self, msg):
        """
        Callback function for subscriber
        Called when a message is published to /esp32/outgoing topic
        
        Args:
            msg: String message to send to ESP32
        """
        try:
            # Add newline character - ESP32 Serial.println() expects it
            message = msg.data + '\n'
            
            # Encode string to bytes and write to serial port
            # .encode() converts Python string to bytes (UTF-8 by default)
            self.serial_conn.write(message.encode('utf-8'))
            
            # Flush the buffer to ensure data is sent immediately
            # Without flush, data may stay in buffer
            self.serial_conn.flush()
            
            self.get_logger().info(f'Sent to ESP32: {msg.data}')
            
        except serial.SerialException as e:
            self.get_logger().error(f'Error sending to ESP32: {e}')
    
    def read_from_uart(self):
        """
        Timer callback function
        Reads incoming data from ESP32 via UART
        """
        try:
            # Check if data is available in serial buffer
            # in_waiting returns number of bytes in input buffer
            if self.serial_conn.in_waiting > 0:
                # Read a line from serial (until newline character)
                # .decode() converts bytes back to Python string
                # .strip() removes trailing newline and whitespace
                line = self.serial_conn.readline().decode('utf-8').strip()
                
                if line:  # Only process non-empty lines
                    # Create and publish ROS2 message
                    msg = String()
                    msg.data = line
                    self.pub_from_esp32.publish(msg)
                    
                    self.get_logger().info(f'Received from ESP32: {line}')
                    
        except serial.SerialException as e:
            self.get_logger().error(f'Error reading from ESP32: {e}')
        except UnicodeDecodeError as e:
            self.get_logger().warn(f'Unicode decode error: {e}')
    
    def destroy_node(self):
        """
        Cleanup when node is shutdown
        Closes the serial connection properly
        """
        self.get_logger().info('Shutting down ESP32 UART Node...')
        self.running = False
        
        # Close serial connection
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.get_logger().info('Serial port closed')
        
        # Call parent class destroy
        super().destroy_node()


def main(args=None):
    """
    Main entry point for the ROS2 node
    """
    # Initialize ROS2 client library
    rclpy.init(args=args)
    
    try:
        # Create the node instance
        node = ESP32UARTNode()
        
        # Spin the node - keeps it running and processing callbacks
        # This is a blocking call that runs until node is shutdown
        rclpy.spin(node)
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print('\nKeyboard interrupt received, shutting down...')
        
    except Exception as e:
        print(f'Error: {e}')
        
    finally:
        # Cleanup
        if 'node' in locals():
            node.destroy_node()
        
        # Shutdown ROS2 client library
        rclpy.shutdown()


if __name__ == '__main__':
    main()
