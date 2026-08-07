#!/usr/bin/env bash
# ============================================================
# CAKRA AI - Service Launcher (Microservices Mode)
# ============================================================
# Usage:
#   ./start_services.sh           → start all services
#   ./start_services.sh gateway   → start only gateway
#   ./start_services.sh chat      → start only chat service
#   ./start_services.sh analytics → start only analytics service
#   ./start_services.sh auth      → start only auth service
#   ./start_services.sh stop      → kill all services
# ============================================================

VENV_PYTHON="${VENV_PYTHON:-$(dirname "$0")/rag_env/bin/python}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT/logs/services"
mkdir -p "$LOG_DIR"

start_service() {
    local name="$1"
    local script="$2"
    local log="$LOG_DIR/${name}.log"
    echo "🚀 Starting $name..."
    nohup "$VENV_PYTHON" "$ROOT/$script" > "$log" 2>&1 &
    echo $! > "$LOG_DIR/${name}.pid"
    echo "   PID: $(cat "$LOG_DIR/${name}.pid") | Log: $log"
}

stop_services() {
    echo "🛑 Stopping all CAKRA services..."
    for pidfile in "$LOG_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            name=$(basename "$pidfile" .pid)
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                echo "   ✅ Stopped $name (PID $pid)"
            else
                echo "   ⚠️  $name (PID $pid) was not running"
            fi
            rm -f "$pidfile"
        fi
    done
}

case "${1:-all}" in
    stop)
        stop_services
        ;;
    gateway)
        start_service "gateway" "run_gateway.py"
        ;;
    chat)
        start_service "chat_service" "run_chat_service.py"
        ;;
    analytics)
        start_service "analytics_service" "run_analytics_service.py"
        ;;
    auth)
        start_service "auth_service" "run_auth_service.py"
        ;;
    all)
        echo "============================================================"
        echo "  CAKRA AI - Starting all microservices"
        echo "============================================================"
        start_service "auth_service"      "run_auth_service.py"
        sleep 2
        start_service "analytics_service" "run_analytics_service.py"
        sleep 2
        start_service "chat_service"      "run_chat_service.py"
        sleep 3
        start_service "gateway"           "run_gateway.py"
        echo ""
        echo "============================================================"
        echo "  ✅ All services launched!"
        echo "  API Gateway     → http://localhost:8000"
        echo "  Chat Service    → http://localhost:8001"
        echo "  Analytics Svc   → http://localhost:8002"
        echo "  Auth Service    → http://localhost:8003"
        echo "  FE Chat         → http://localhost:5173  (npm run dev:chat)"
        echo "  FE Analytics    → http://localhost:5174  (npm run dev:analytics)"
        echo "============================================================"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Usage: $0 [all|stop|gateway|chat|analytics|auth]"
        exit 1
        ;;
esac
