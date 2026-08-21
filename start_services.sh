#!/usr/bin/env bash
# ============================================================
# CAKRA AI - Service Launcher (Microservices Mode)
# ============================================================
# Usage:
#   ./start_services.sh              → start all services + frontend
#   ./start_services.sh gateway      → start only gateway
#   ./start_services.sh chat         → start only chat service
#   ./start_services.sh analytics    → start only analytics service
#   ./start_services.sh auth         → start only auth service
#   ./start_services.sh frontend     → start only frontend (chat + analytics)
#   ./start_services.sh stop         → kill all services + frontend
# ============================================================

VENV_PYTHON="${VENV_PYTHON:-$(dirname "$0")/rag_env/bin/python}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT/logs/services"
FRONTEND_DIR="$ROOT/webui"
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

start_frontend() {
    local log="$LOG_DIR/frontend.log"
    echo "🚀 Starting Frontend (Chat + Analytics)..."
    nohup bash "$FRONTEND_DIR/start_frontends.sh" > "$log" 2>&1 &
    echo $! > "$LOG_DIR/frontend.pid"
    echo "   PID: $(cat "$LOG_DIR/frontend.pid") | Log: $log"
}

stop_services() {
    echo "🛑 Stopping all CAKRA services & resetting VRAM..."
    for pidfile in "$LOG_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            name=$(basename "$pidfile" .pid)
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
                echo "   ✅ Stopped $name (PID $pid)"
            fi
            rm -f "$pidfile"
        fi
    done

    # 1. Bersihkan semua process Python & Vite terkait Cakra
    echo "🧹 Membersihkan proses python & vite..."
    pkill -9 -f "run_chat_service.py" 2>/dev/null || true
    pkill -9 -f "run_gateway.py" 2>/dev/null || true
    pkill -9 -f "run_auth_service.py" 2>/dev/null || true
    pkill -9 -f "run_analytics_service.py" 2>/dev/null || true
    pkill -9 -f "start_frontends.sh" 2>/dev/null || true
    pkill -9 -f "vite" 2>/dev/null || true

    # 2. Bebaskan port jaringan & cache frontend
    echo "🧹 Membersihkan port backend (8000-8003) & frontend (5173-5176)..."
    fuser -k -9 8000/tcp 8001/tcp 8002/tcp 8003/tcp 2>/dev/null || true
    fuser -k -9 5173/tcp 5174/tcp 5175/tcp 5176/tcp 2>/dev/null || true
    rm -rf "$FRONTEND_DIR/node_modules/.vite" 2>/dev/null || true

    # 3. Flush & Reset VRAM Ollama (Unload semua model nyangkut di GPU)
    echo "🧹 Membersihkan VRAM Ollama..."
    if command -v ollama &>/dev/null; then
        for model in $(ollama ps 2>/dev/null | awk 'NR>1 {print $1}'); do
            if [ -n "$model" ]; then
                echo "   🔄 Unloading $model dari VRAM..."
                ollama stop "$model" 2>/dev/null || true
            fi
        done
    fi
    sleep 1
    echo "✨ System reset & VRAM bersih 100%!"
}

case "${1:-all}" in
    stop)
        stop_services
        ;;
    gateway)
        pkill -9 -f "run_gateway.py" 2>/dev/null || true
        fuser -k -9 8000/tcp 2>/dev/null || true
        sleep 1
        start_service "gateway" "run_gateway.py"
        ;;
    chat)
        pkill -9 -f "run_chat_service.py" 2>/dev/null || true
        fuser -k -9 8001/tcp 2>/dev/null || true
        sleep 1
        start_service "chat_service" "run_chat_service.py"
        ;;
    analytics)
        pkill -9 -f "run_analytics_service.py" 2>/dev/null || true
        fuser -k -9 8002/tcp 2>/dev/null || true
        sleep 1
        start_service "analytics_service" "run_analytics_service.py"
        ;;
    auth)
        pkill -9 -f "run_auth_service.py" 2>/dev/null || true
        fuser -k -9 8003/tcp 2>/dev/null || true
        sleep 1
        start_service "auth_service" "run_auth_service.py"
        ;;
    frontend)
        pkill -9 -f "start_frontends.sh" 2>/dev/null || true
        pkill -9 -f "vite" 2>/dev/null || true
        fuser -k -9 5173/tcp 5174/tcp 2>/dev/null || true
        sleep 1
        start_frontend
        ;;
    all)
        echo "============================================================"
        echo "  CAKRA AI - Full Clean Reset & Starting Microservices"
        echo "============================================================"
        # Selalu reset dan matikan proses zombie/VRAM nyangkut terlebih dahulu
        stop_services
        echo ""
        echo "🚀 Memulai ulang seluruh microservices..."
        start_service "auth_service"      "run_auth_service.py"
        sleep 2
        start_service "analytics_service" "run_analytics_service.py"
        sleep 2
        start_service "chat_service"      "run_chat_service.py"
        sleep 3
        start_service "gateway"           "run_gateway.py"
        sleep 2
        start_frontend
        echo ""
        echo "============================================================"
        echo "  ✅ All services + frontend launched successfully!"
        echo "  API Gateway     → http://localhost:8000"
        echo "  Chat Service    → http://localhost:8001"
        echo "  Analytics Svc   → http://localhost:8002"
        echo "  Auth Service    → http://localhost:8003"
        echo "  FE Chat         → http://localhost:5173"
        echo "  FE Analytics    → http://localhost:5174"
        echo "============================================================"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Usage: $0 [all|stop|gateway|chat|analytics|auth|frontend]"
        exit 1
        ;;
esac