# Warehouse Management & Robot Control System

Web dashboard to monitor and control warehouse robots in real time. Django
backend, React frontend, MQTT communication, optional ROS 2 robot simulation.

## Architecture

```
[React App] ←HTTP/WS→ [Django] ←MQTT→ [Mosquitto] ←MQTT→ [Robot Fleet]
                          ↕
                    [PostgreSQL]
```

Django runs as two processes (same codebase, connected via Redis):
- **Daphne** — serves HTTP REST API + WebSocket to the browser
- **MQTT Listener** — subscribes to robot telemetry from Mosquitto

## Prerequisites

- Python 3.10+
- Node 18+
- Docker + Docker Compose (for PostgreSQL, Mosquitto, Redis)
- ROS 2 Jazzy + Gazebo (optional — robot simulation only)

## Quick start

### Bare web app (no demo data, no simulation)

```bash
git clone <repo-url> && cd SGEV
cp .env.example .env
./start.sh
```

Opens `http://localhost:5173`. Empty database — you start from scratch.

### With demo data

```bash
./start.sh -d
```

Adds sample robots, products, and an admin account. Login: **admin** / **admin123**.

### With demo data + ROS 2 simulation

```bash
./start.sh -d -g
```

Same as above plus Gazebo robot simulation with GUI. Use `-r` instead of `-g`
for headless simulation (no Gazebo window).

### Flags reference

| Flag | What it does |
|------|-------------|
| *(none)* | Raw web app. Docker: postgres, mosquitto, redis. No demo data, no ROS. |
| `-d` | Seed demo data after migrations (robots, products, orders, admin user). |
| `-r` | Start ROS 2 simulation container (Gazebo headless, Nav2, SLAM, MQTT bridge). |
| `-g` | Same as `-r` but with Gazebo GUI window. |
| `-d -g` | Full system: demo data + ROS 2 with Gazebo GUI. |

Combine flags freely. `./stop.sh` stops all local processes. Docker containers
persist between runs (use `docker compose down` to fully stop).

## Manual start

If you want to run each component separately instead of using the script:

### 1. Environment file

```bash
cp .env.example .env
```

### 2. Infrastructure (Docker)

```bash
# Core services only:
docker compose up -d postgres mosquitto redis

# Or include ROS 2 simulation:
GAZEBO_HEADLESS="True" docker compose up -d
```

PostgreSQL, Mosquitto, and Redis are required. ROS 2 is optional — if you
don't start it, the robots just stay OFFLINE.

### 3. Backend setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
```

### 4. Demo data (optional)

```bash
# Only if you want sample robots, products, and an admin account:
python manage.py seed_demo_data
```

Creates:
- Admin user `admin` / `admin123`
- Two robots: R1 "Warehouse Bot Alpha", R2 "Warehouse Bot Beta" (OFFLINE)
- Sample products placed in the warehouse

Safe to run multiple times — skips existing entries.

### 5. Run backend

Two processes in two terminals:

```bash
# Terminal 1 — Daphne: HTTP + WebSocket server
daphne -b 0.0.0.0 -p 8000 warehouse_project.asgi:application

# Terminal 2 — MQTT Listener
source venv/bin/activate
python manage.py run_mqtt_listener
```

### 6. Run frontend

```bash
cd frontend
npm install
npm run dev
```

### 7. Open browser

```
http://localhost:5173
```

## ROS 2 Simulation (optional)

The ROS 2 simulation provides a Gazebo robot that can navigate and scan maps.
It runs inside a Docker container (`osrf/ros:jazzy-desktop-full`).

```bash
# Start with GUI:
docker compose up -d

# Or headless (no Gazebo window):
GAZEBO_HEADLESS="True" docker compose up -d
```

The simulation includes:
- **Gazebo** — robot physics and sensor simulation
- **Nav2** — autonomous navigation / path planning
- **slam_toolbox** — real-time warehouse map building
- **MQTT bridge** — translates ROS 2 topics ↔ MQTT

Without the simulation, the web app works fine — robots just show as OFFLINE.
You can also skip Docker and run ROS 2 natively if you have it installed:

```bash
cd ros2_ws
colcon build
source install/setup.bash
ros2 launch robot_simulation simulation.launch.py
```

### Connecting a real robot

Any device that speaks MQTT can act as a robot. The broker expects messages
on these topics:

| Topic | Payload | QoS |
|-------|---------|-----|
| `warehouse/robots/{id}/system_status` | `ONLINE` / `OFFLINE` / `ERROR` | 1 (retained) |
| `warehouse/robots/{id}/pose` | `{"x": 0.0, "y": 0.0, "yaw": 0.0}` | 0 |
| `warehouse/robots/{id}/mission_status` | `COMPLETED` / `FAILED` | 1 |
| `warehouse/robots/{id}/map_preview` | base64 PNG of live map | 0 |
| `warehouse/robots/{id}/map_complete` | base64 PNG of final map | 1 |

Commands from the browser arrive on:

| Topic | Payload | QoS |
|-------|---------|-----|
| `warehouse/robots/{id}/cmd_auto` | `{"nav_to": {"x": 1.0, "y": 2.0}}` | 1 |
| `warehouse/robots/{id}/cmd_manual` | `W` / `A` / `S` / `D` / ` ` (stop) | 0 |
| `warehouse/robots/{id}/cmd_mapping` | `START` / `STOP_AND_SAVE` | 1 |

The robot must connect to Mosquitto with credentials matching what's in `.env`.

## Access from other devices on LAN

The frontend dev server (Vite) binds to all network interfaces. Access from
a phone or another laptop at:

```
http://LAPTOP_IP:5173
```

Find your laptop's IP with `ip addr` or `hostname -I`. Vite proxies API
and WebSocket calls to Django automatically — single port for everything.

## Project structure

```
Warehouse Management System/
                          ├── api/                  # Django app (models, views, consumers, utils)
                          ├── warehouse_project/    # Django project configuration (settings, URLs, ASGI)
                          ├── frontend/             # React + Vite frontend
                          │   └── src/
                          │       ├── components/   # Reusable UI components (MapCanvas, robot cards, etc.)
                          │       ├── contexts/     # React contexts (WebSocket, theme, robot state)
                          │       └── pages/        # Page components (Dashboard, LiveMap, Orders, etc.)
                          ├── ros2_ws/              # ROS 2 workspace
                          │   ├── Dockerfile        # Ubuntu 24.04 + ROS 2 Jazzy + Gazebo
                          │   └── src/
                          │       ├── mqtt_bridge/           # ROS 2 ↔ MQTT translation node
                          │       ├── robot_simulation/      # Gazebo simulation launch + Nav2 / SLAM config
                          │       └── robot_description/     # TurtleBot4 + custom warehouse robot URDFs
                          ├── mosquitto/config/     # Mosquitto config + ACL
                          ├── docker-compose.yml    # PostgreSQL, Mosquitto, Redis, ROS 2 containers
                          ├── requirements.txt      # Python dependencies
                          ├── Makefile              # Dev commands (make logs, make migrate, etc.)
                          ├── start.sh              # One-command startup with flags
                          └── stop.sh               # Stop all background processes
```

## Default credentials

| Role | Username | Password |
|------|----------|----------|
| Admin dashboard | `admin` | `admin123` |
| MQTT (Django) | `django_user` | set via mosquitto_passwd |
| MQTT (robots) | `robot_user` | set via mosquitto_passwd |

## Limitations

- **Simulation only** — robots run in Gazebo, not physical hardware.
  Sensors, odometry, and navigation are all simulated.
- **Single machine** — all services run on one laptop for development.
  Production deployment would separate PostgreSQL, Django, Mosquitto,
  and Redis onto different servers.
- **No HTTPS** — communication is over plain HTTP/WS. Fine for LAN, but
  add a reverse proxy (nginx + Let's Encrypt) for internet access.
- **MQTT passwords** — must be created manually after first `docker compose up`
  (see Mosquitto section above). The MQTT Listener silently fails without them.
- **Vite in dev mode** — frontend runs on Vite's development server, not
  optimised for production. Run `npm run build` in `frontend/` and serve
  the static files from Django or nginx for production.
- **ROS 2 in Docker** — the Gazebo simulation runs inside a Docker container.
  On a machine without an NVIDIA GPU, remove the `runtime: nvidia` line from
  `docker-compose.yml` and it will fall back to software rendering.
