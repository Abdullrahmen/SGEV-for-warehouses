/*
 * ESP32 UART Communication Test with ROS2
 * 
 * Hardware Connections:
 * - ESP32 TX0 (GPIO1) -> Raspberry Pi RX (GPIO15/Pin 8 on RPi)
 * - ESP32 RX0 (GPIO3) -> Raspberry Pi TX (GPIO14/Pin 8 on RPi)
 * - GND -> GND (common ground is REQUIRED!)
 * 
 * Note: ESP32 uses 3.3V logic, Raspberry Pi also uses 3.3V logic
 * No level shifter needed between ESP32 and RPi5
 */

// ============================================
// SETUP - Runs once at startup
// ============================================
void setup() {
  // Initialize Serial0 (UART0) at 115200 baud rate
  // Serial0 uses TX0(GPIO1) and RX0(GPIO3) by default
  // Baud rate must match the ROS2 node setting
  Serial.begin(115200);
  
  // Wait for serial connection to establish
  // Useful for debugging - remove in production
  while (!Serial) {
    delay(10);
  }
  
  // Print startup message to confirm ESP32 is running
  Serial.println("ESP32: UART Communication Ready!");
  Serial.println("ESP32: Waiting for messages from ROS2...");
}

// ============================================
// LOOP - Runs repeatedly
// ============================================
void loop() {
  // Check if data is available in the serial buffer
  // Serial.available() returns number of bytes in buffer
  if (Serial.available() > 0) {
    // Read the incoming byte from UART
    // Serial.read() returns one byte at a time
    char incomingByte = Serial.read();
    
    // Echo back the received byte with acknowledgment
    // This confirms two-way communication works
    Serial.print("ESP32 received: ");
    Serial.println(incomingByte);
    
    // If we receive 'H', turn on LED (GPIO2 built-in)
    // If we receive 'L', turn off LED
    // This provides visual feedback of communication
    if (incomingByte == 'H') {
      // Turn on built-in LED (active LOW on most ESP32 boards)
      pinMode(2, OUTPUT);
      digitalWrite(2, LOW);   // LOW = LED ON for active-low LED
      Serial.println("ESP32: LED ON");
    } 
    else if (incomingByte == 'L') {
      pinMode(2, OUTPUT);
      digitalWrite(2, HIGH);  // HIGH = LED OFF
      Serial.println("ESP32: LED OFF");
    }
    // If we receive 'S', send status back
    else if (incomingByte == 'S') {
      Serial.println("ESP32: Status OK - Running");
    }
  }
  
  // Send heartbeat message every 2 seconds
  // This helps verify ESP32 is still alive
  static unsigned long lastHeartbeat = 0;
  unsigned long currentTime = millis();  // Get current time in ms
  
  if (currentTime - lastHeartbeat >= 2000) {
    lastHeartbeat = currentTime;
    Serial.println("ESP32: Heartbeat - Alive!");
  }
  
  // Small delay to prevent overwhelming the serial buffer
  delay(10);
}
