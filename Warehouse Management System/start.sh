#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
PID_DIR="$ROOT_DIR/.pids"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

# ─── Flags ────────────────────────────────────────────────
SEED_DEMO=false
ROS_ENABLED=false
GAZEBO_HEADLESS="True"

for arg in "$@"; do
  case "$arg" in
    -d|--demo)       SEED_DEMO=true    ;;
    -r|--ros)        ROS_ENABLED=true  ;;
    -g|--gazebo-gui) ROS_ENABLED=true; GAZEBO_HEADLESS="False" ;;
    *)
      echo "Usage: $0 [-d] [-r] [-g]"
      echo "  -d  Seed demo data (robots, products, orders)"
      echo "  -r  Start ROS 2 simulation (headless)"
      echo "  -g  Start ROS 2 simulation with Gazebo GUI"
      exit 1
      ;;
  esac
done

# ─── Cleanup handler ──────────────────────────────────────
cleanup() {
  echo ""; warn "Shutting down..."
  [ -f "$PID_DIR/daphne.pid" ]   && kill $(cat "$PID_DIR/daphne.pid") 2>/dev/null   && log "Stopped Daphne"
  [ -f "$PID_DIR/listener.pid" ] && kill $(cat "$PID_DIR/listener.pid") 2>/dev/null && log "Stopped MQTT Listener"
  [ -f "$PID_DIR/react.pid" ]    && kill $(cat "$PID_DIR/react.pid") 2>/dev/null    && log "Stopped React"
  if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then
    log "Stopping Docker services..."
    docker compose down 2>/dev/null
  fi
  rm -rf "$PID_DIR"
  exit 0
}
trap cleanup SIGINT SIGTERM

mkdir -p "$PID_DIR"

# ─── Prerequisites ─────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || { err "python3 not found"; exit 1; }
command -v node    >/dev/null 2>&1 || { err "node not found";    exit 1; }
command -v npm     >/dev/null 2>&1 || { err "npm not found";     exit 1; }
log "Prerequisites OK"

# ─── Docker Infrastructure ─────────────────────────────────
if command -v docker >/dev/null 2>&1; then
  if docker ps >/dev/null 2>&1; then
    if [ "$ROS_ENABLED" = true ]; then
      log "Starting Docker services (PostgreSQL, Mosquitto, Redis, ROS 2)..."
      GAZEBO_HEADLESS="$GAZEBO_HEADLESS" docker compose up -d
    else
      log "Starting Docker services (PostgreSQL, Mosquitto, Redis)..."
      docker compose up -d postgres mosquitto redis
    fi
    log "Docker services started"
    warn "Waiting for PostgreSQL to be ready..."
    for i in $(seq 1 10); do
      docker compose exec -T postgres pg_isready -U warehouse_user 2>/dev/null && break
      sleep 1
    done
  else
    warn "Docker not running — start it manually or ensure PostgreSQL/Mosquitto/Redis are available"
  fi
else
  warn "Docker not installed — ensure PostgreSQL, Mosquitto, and Redis are running"
fi

# ─── Kill leftover processes ───────────────────────────────
[ -f "$PID_DIR/daphne.pid" ]   && kill $(cat "$PID_DIR/daphne.pid") 2>/dev/null   && warn "Killed stale Daphne" || true
[ -f "$PID_DIR/listener.pid" ] && kill $(cat "$PID_DIR/listener.pid") 2>/dev/null && warn "Killed stale MQTT Listener" || true
[ -f "$PID_DIR/react.pid" ]    && kill $(cat "$PID_DIR/react.pid") 2>/dev/null    && warn "Killed stale React" || true

# ─── Python Virtual Environment ────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  log "Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

if [ ! -f "$VENV_DIR/.deps_installed" ]; then
  log "Installing Python dependencies..."
  pip install -r "$ROOT_DIR/requirements.txt" -q 2>&1
  touch "$VENV_DIR/.deps_installed"
  log "Python dependencies installed"
fi

# ─── Django Setup ──────────────────────────────────────────
cd "$ROOT_DIR"

if [ ! -f ".env" ]; then
  warn "No .env found — copying from .env.example"
  cp .env.example .env
  warn "Edit .env with your actual credentials before production use"
fi

log "Running database migrations..."
python manage.py migrate

if [ "$SEED_DEMO" = true ]; then
  log "Seeding demo data..."
  python manage.py seed_demo_data 2>&1 | tail -1
else
  log "Skipping demo data (use -d to seed)"
fi

# ─── Start Django ASGI Server ──────────────────────────────
log "Starting Daphne (ASGI server) on port 8000..."
mkdir -p "$ROOT_DIR/logs"
cd "$ROOT_DIR"
nohup daphne -b 0.0.0.0 -p 8000 warehouse_project.asgi:application \
  > "$ROOT_DIR/logs/daphne.log" 2>&1 &
echo $! > "$PID_DIR/daphne.pid"
sleep 2
log "Daphne running on http://localhost:8000"

# ─── Start MQTT Listener ───────────────────────────────────
log "Starting MQTT Listener..."
cd "$ROOT_DIR"
nohup python manage.py run_mqtt_listener \
  > "$ROOT_DIR/logs/listener.log" 2>&1 &
echo $! > "$PID_DIR/listener.pid"
sleep 1
log "MQTT Listener running"

# ─── Start React Frontend ──────────────────────────────────
cd "$ROOT_DIR/frontend"
if [ ! -d node_modules ]; then
  log "Installing frontend dependencies..."
  npm install --silent
else
  log "Frontend dependencies already installed"
fi

log "Starting React dev server..."
nohup npm run dev \
  > "$ROOT_DIR/logs/react.log" 2>&1 &
echo $! > "$PID_DIR/react.pid"

# ─── Done ──────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║          System is starting up...                ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Frontend:  http://localhost:5173                ║"
echo "║  Backend:   http://localhost:8000                ║"
echo "║  API:       http://localhost:8000/api/v1/        ║"
echo "║  Admin:     http://localhost:8000/admin/         ║"
if [ "$SEED_DEMO" = true ]; then
  DEMO_STATUS="seeded (admin / admin123)"
else
  DEMO_STATUS="not seeded"
fi
printf "║  Demo data: %-36s ║\n" "$DEMO_STATUS"

if [ "$ROS_ENABLED" = true ]; then
  if [ "$GAZEBO_HEADLESS" = "False" ]; then
    ROS_STATUS="running (GUI)"
  else
    ROS_STATUS="running (headless)"
  fi
else
  ROS_STATUS="not started"
fi
printf "║  ROS sim:   %-36s ║\n" "$ROS_STATUS"
echo "║  Logs:      logs/                                ║"
echo "║  Stop:      Ctrl+C or ./stop.sh                  ║"
echo "╚══════════════════════════════════════════════════╝"

mkdir -p "$ROOT_DIR/logs"

wait
