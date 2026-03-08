# 🚗 MQTT Remote Control Car — Setup Guide

A web-based remote control for a car powered by an **ESP32** and **MQTT**.
Follow this guide step-by-step to get everything running locally on your laptop.

---

## 📋 Table of Contents

1. [Prerequisites](#1--prerequisites)
2. [Find Your Laptop IP Address](#2--find-your-laptop-ip-address)
3. [Configure Mosquitto](#3--configure-mosquitto)
4. [Configure Windows Firewall](#4--configure-windows-firewall)
5. [Edit the ESP32 Code](#5--edit-the-esp32-code)
6. [Edit index.html](#6--edit-indexhtml)
7. [Run the Website](#7--run-the-website)
8. [Connect & Drive](#8--connect--drive)

---

## 1 — Prerequisites

Install the following on your laptop:

| Software | Download Link |
|----------|--------------|
| **Python** | [python.org/downloads](https://www.python.org/downloads/) |
| **Mosquitto MQTT Broker** | [mosquitto.org/download](https://mosquitto.org/download/) |

> ✅ Make sure to add Python to your system PATH during installation.

---

## 2 — Find Your Laptop IP Address

You will need your laptop's local IP address in **multiple steps** below. To find it:

1. Open **Command Prompt** (`Win` + `R` → type `cmd` → Enter).
2. Run:
   ```
   ipconfig
   ```
3. Look for **Wireless LAN adapter Wi-Fi** (or Ethernet) and find the line:
   ```
   IPv4 Address. . . . . . . . . . . : 192.168.x.x
   ```
4. **Write this IP down.** You will use it throughout this guide.

> 📝 Example: `192.168.1.2` — yours will be different.

---

## 3 — Configure Mosquitto

Locate the Mosquitto configuration file `mosquitto.conf` (usually in `C:\Program Files\mosquitto\`) and **replace its contents** with the following:

```conf
# Mosquitto Configuration for Warehouse Robot Project

# 1. Standard MQTT (for ESP32)
listener 1883
allow_anonymous true

# 2. WebSockets (for the Website)
listener 9001
protocol websockets
allow_anonymous true

# Log everything (helpful for debugging)
log_type all
```

Then **restart the Mosquitto service**:
- Press `Win` + `R`, type `services.msc`, and press Enter.
- Find **Mosquitto Broker**, right-click → **Restart**.

---

## 4 — Configure Windows Firewall

Other devices on your network need to be able to reach the MQTT broker. You must add a firewall rule:

1. Press the **Windows Key** and type **Firewall**. Open **"Windows Defender Firewall with Advanced Security"**.
2. On the left side, click **"Inbound Rules"**.
3. On the right side, click **"New Rule..."**.
4. Select **"Port"** and click **Next**.
5. Select **"TCP"**. Under **"Specific local ports"**, type: `9001`
6. Click **Next**. Select **"Allow the connection"**.
7. Click **Next**. Make sure **Domain**, **Private**, and **Public** are all checked.
8. Click **Next**. Give it a name like `MQTT WebSockets`.
9. Click **Finish**.

---

## 5 — Edit the ESP32 Code

Open your ESP32 Arduino sketch and make the following changes:

### 5.1 — Add Includes (at the very top of the file)

```cpp
#include <WiFi.h>
#include <PubSubClient.h>
```

### 5.2 — Add Global Variables (before any functions)

```cpp
/* ================= WIFI & MQTT ================= */

const char* ssid         = "WIFI_NAME_HERE";      // Your WiFi network name
const char* password     = "WIFI_PASSWORD_HERE";   // Your WiFi password
const char* mqtt_server  = "LAPTOP_IP_HERE";       // Your laptop IP from Step 2
const char* mqtt_topic   = "robot/command";

WiFiClient espClient;
PubSubClient client(espClient);
```

> ⚠️ Replace `WIFI_NAME_HERE`, `WIFI_PASSWORD_HERE`, and `LAPTOP_IP_HERE` with your actual values.

### 5.3 — Add the Callback Function

Place this function **before** `void setup()`:

```cpp
/* ================= MQTT FUNCTIONS ================= */

void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }

  if (msg == "UP") {
    left_ref = DRIVE_RPM;
    right_ref = DRIVE_RPM;
  } else if (msg == "DOWN") {
    left_ref = -DRIVE_RPM;
    right_ref = -DRIVE_RPM;
  } else if (msg == "LEFT") {
    left_ref = -TURN_RPM;
    right_ref = TURN_RPM;
  } else if (msg == "RIGHT") {
    left_ref = TURN_RPM;
    right_ref = -TURN_RPM;
  } else if (msg == "STOP") {
    left_ref = 0;
    right_ref = 0;
  }
}
```

### 5.4 — Add to `void setup()` (after `Serial.begin(...)`)

```cpp
// --- WiFi Setup ---
WiFi.begin(ssid, password);
while (WiFi.status() != WL_CONNECTED) {
  delay(500);
  Serial.print(".");
}
Serial.println("");
Serial.println("WiFi connected");
Serial.println("IP address: ");
Serial.println(WiFi.localIP());

// --- MQTT Setup ---
client.setServer(mqtt_server, 1883);
client.setCallback(callback);

while (!client.connected()) {
  if (client.connect("ESP32Client")) {
    client.subscribe(mqtt_topic);
    Serial.println("MQTT connected & subscribed");
  } else {
    Serial.print("MQTT connect failed, retrying...");
    delay(1000);
  }
}
```

### 5.5 — Add to `void loop()` (at the very top)

```cpp
// Keep MQTT connection alive (Non-blocking)
if (!client.connected()) {
  if (client.connect("ESP32Client")) {
    client.subscribe(mqtt_topic);
    Serial.println("MQTT reconnected");
  }
}
client.loop();
```

---

## 6 — Edit `index.html`

Open `index.html` and search for `MQTT_BROKER_IP`. You will find a line like this:

```js
const MQTT_BROKER_IP = '192.168.1.2'; // REPLACE WITH YOUR LAPTOP IP
```

**Replace the IP** with your laptop's IP address from [Step 2](#2--find-your-laptop-ip-address).

> ⚠️ This must be the **same IP** you used in the ESP32 code.

Also make sure the file **`mqtt.min.js`** is in the **same folder** as `index.html`.

---

## 7 — Run the Website

1. Open **Command Prompt**.
2. Navigate to the folder that contains `index.html`:
   ```
   cd path\to\your\folder
   ```
3. Start a local web server:
   ```
   python -m http.server 8000
   ```
4. Keep this terminal window **open**.

---

## 8 — Connect & Drive

On **any device** connected to the **same WiFi network**, open a browser and go to:

```
http://<YOUR_LAPTOP_IP>:8000
```

> 📝 Example: `http://192.168.1.2:8000`

Use `ipconfig` if you forgot your IP — see [Step 2](#2--find-your-laptop-ip-address).

You should now see the remote control interface. **Happy driving!** 🎮

---

## 🛠 Troubleshooting

| Problem | Solution |
|---------|----------|
| ESP32 won't connect to WiFi | Double-check SSID and password. Make sure the ESP32 is in range. |
| MQTT connection fails | Verify Mosquitto is running (`services.msc`). Check the IP address. |
| Website can't reach broker | Make sure the firewall rule from Step 4 is active. |
| Page won't load from another device | Ensure both devices are on the **same network** and you're using the correct IP. |
| `mqtt.min.js` errors in browser console | Make sure `mqtt.min.js` is in the same folder as `index.html`. |
