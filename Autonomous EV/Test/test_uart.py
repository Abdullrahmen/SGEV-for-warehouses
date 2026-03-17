#!/usr/bin/env python3
"""
Simple Python Test Script for UART Communication with ESP32
(Without ROS2 - for initial testing)

Usage:
    python3 test_uart.py

This script tests the basic UART connection between
Raspberry Pi and ESP32 without needing ROS2.
"""

import serial
import serial.tools.list_ports
import time
import threading


def list_available_ports():
    """
    List all available serial ports on the system
    Useful for finding the correct port name
    """
    print("\n=== Available Serial Ports ===")
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("No serial ports found!")
        return []
    
    for port in ports:
        print(f"  Port: {port.device}")
        print(f"    Description: {port.description}")
        print(f"    Hardware ID: {port.hwid}")
        print()
    
    return [port.device for port in ports]


def read_from_uart(ser, running_flag):
    """
    Thread function to continuously read from UART
    
    Args:
        ser: Serial connection object
        running_flag: List with single boolean to control the thread
    """
    while running_flag[0]:
        try:
            if ser.in_waiting > 0:
                # Read line and decode
                line = ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    print(f"\n[ESP32] {line}")
        except Exception as e:
            print(f"\n[ERROR] Read error: {e}")
        time.sleep(0.01)  # Small delay to prevent CPU hogging


def main():
    """
    Main test function
    """
    print("=" * 50)
    print("ESP32 UART Communication Test (No ROS2)")
    print("=" * 50)
    
    # List available ports first
    available_ports = list_available_ports()
    
    if not available_ports:
        print("No serial ports available. Please check your connections.")
        return
    
    # Ask user to select port
    print("\nSelect serial port:")
    for i, port in enumerate(available_ports):
        print(f"  {i + 1}. {port}")
    
    # Default to common Raspberry Pi port
    default_port = '/dev/ttyAMA0'
    if default_port in available_ports:
        print(f"\nUsing default port: {default_port}")
        selected_port = default_port
    else:
        try:
            selection = int(input("Enter port number: ")) - 1
            selected_port = available_ports[selection]
        except (ValueError, IndexError):
            print("Invalid selection, using first available port")
            selected_port = available_ports[0]
    
    # Serial connection settings
    BAUD_RATE = 115200
    TIMEOUT = 1.0
    
    print(f"\nConnecting to {selected_port} at {BAUD_RATE} baud...")
    
    try:
        # Create serial connection
        ser = serial.Serial(
            port=selected_port,
            baudrate=BAUD_RATE,
            timeout=TIMEOUT,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )
        
        print(f"Connected successfully!")
        print("\n" + "=" * 50)
        print("Commands:")
        print("  H - Turn LED ON")
        print("  L - Turn LED OFF")
        print("  S - Request status")
        print("  q - Quit the program")
        print("  Any other text will be sent to ESP32")
        print("=" * 50)
        
        # Clear any existing data in buffer
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Start reading thread
        running_flag = [True]
        read_thread = threading.Thread(
            target=read_from_uart,
            args=(ser, running_flag),
            daemon=True
        )
        read_thread.start()
        
        # Give ESP32 time to send initial message
        time.sleep(0.5)
        
        # Main loop - get user input and send to ESP32
        while True:
            try:
                # Get user input
                user_input = input("\n> ")
                
                # Check for quit command
                if user_input.lower() == 'q':
                    print("Quitting...")
                    break
                
                # Send to ESP32
                if user_input:
                    message = user_input + '\n'
                    ser.write(message.encode('utf-8'))
                    ser.flush()
                    print(f"[Sent] {user_input}")
                    
            except KeyboardInterrupt:
                print("\n\nKeyboard interrupt received...")
                break
            except EOFError:
                print("\nEOF received...")
                break
        
        # Cleanup
        running_flag[0] = False
        read_thread.join(timeout=1.0)
        ser.close()
        print("Serial connection closed.")
        
    except serial.SerialException as e:
        print(f"\n[ERROR] Could not open serial port: {e}")
        print("\nTroubleshooting:")
        print("  1. Check if the port is correct")
        print("  2. Make sure you have permission:")
        print("     sudo chmod 666 " + selected_port)
        print("     sudo usermod -aG dialout $USER")
        print("  3. Check if another program is using the port")
        
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")


if __name__ == '__main__':
    main()
