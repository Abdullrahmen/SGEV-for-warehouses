#!/usr/bin/env bash
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$ROOT_DIR/.pids"

# Kill by PID file (if any exist)
for pidfile in daphne.pid listener.pid react.pid; do
  if [ -f "$PID_DIR/$pidfile" ]; then
    kill $(cat "$PID_DIR/$pidfile") 2>/dev/null && echo "Stopped $pidfile"
  fi
done

# Kill any remaining processes by name (in case PID files are stale)
pkill -f "daphne.*warehouse_project.asgi" 2>/dev/null && echo "Stopped lingering Daphne" || true
pkill -f "manage.py run_mqtt_listener" 2>/dev/null && echo "Stopped lingering MQTT Listener" || true
pkill -f "vite" 2>/dev/null && echo "Stopped lingering Vite" || true

rm -rf "$PID_DIR"

# Docker stop helper
if [ "$1" = "--docker" ] || [ "$1" = "-dc" ]; then
  if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then
    echo "Stopping Docker containers..."
    docker compose down
  fi
fi

echo "All processes stopped"
