#!/usr/bin/env bash
# ============================================================
# CAKRA AI - Fast & Streamlined Service Launcher
# ============================================================
# Usage:
#   ./start_services.sh              → fast restart all services in parallel
#   ./start_services.sh stop         → kill all services
#   ./start_services.sh reset-vram   → stop services + flush GPU VRAM
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
    nohup "$VENV_PYTHON" "$ROOT/$script" > "$log" 2>&1 &
    echo $! > "$LOG_DIR/${name}.pid"
    echo "  🚀 $name launched (PID $!)"
}

start_frontend() {
    local log="$LOG_DIR/frontend.log"
    nohup bash "$FRONTEND_DIR/start_frontends.sh" > "$log" 2>&1 &
    echo $! > "$LOG_DIR/frontend.pid"
    echo "  🚀 Frontend launched (PID $!)"
}

stop_services() {
    echo "🛑 Stopping running CAKRA services..."
    # 1. Kill via PID files
    for pidfile in "$LOG_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            kill -9 "$pid" 2>/dev/null || true
            rm -f "$pidfile"
        fi
    done

    # 2. Fast kill all associated python & vite processes
    pkill -9 -f "run_chat_service.py" 2>/dev/null || true
    pkill -9 -f "run_gateway.py" 2>/dev/null || true
    pkill -9 -f "run_auth_service.py" 2>/dev/null || true
    pkill -9 -f "run_analytics_service.py" 2>/dev/null || true
    pkill -9 -f "start_frontends.sh" 2>/dev/null || true
    pkill -9 -f "vite" 2>/dev/null || true

    # 3. Clean network ports
    fuser -k -9 8000/tcp 8001/tcp 8002/tcp 8003/tcp 5173/tcp 5174/tcp 2>/dev/null || true
    rm -rf "$FRONTEND_DIR/node_modules/.vite" 2>/dev/null || true
}

reset_vram() {
    echo "🧹 Membersihkan VRAM Ollama..."
    if command -v ollama &>/dev/null; then
        for model in $(ollama ps 2>/dev/null | awk 'NR>1 {print $1}'); do
            if [ -n "$model" ]; then
                echo "   🔄 Unloading $model..."
                ollama stop "$model" 2>/dev/null || true
            fi
        done
    fi
}

case "${1:-all}" in
    stop)
        stop_services
        echo "✅ All CAKRA services stopped."
        ;;
    reset-vram)
        stop_services
        reset_vram
        echo "✨ All services stopped & VRAM flushed."
        ;;
    gateway)
        pkill -9 -f "run_gateway.py" 2>/dev/null || true
        fuser -k -9 8000/tcp 2>/dev/null || true
        start_service "gateway" "run_gateway.py"
        ;;
    chat)
        pkill -9 -f "run_chat_service.py" 2>/dev/null || true
        fuser -k -9 8001/tcp 2>/dev/null || true
        start_service "chat_service" "run_chat_service.py"
        ;;
    analytics)
        pkill -9 -f "run_analytics_service.py" 2>/dev/null || true
        fuser -k -9 8002/tcp 2>/dev/null || true
        start_service "analytics_service" "run_analytics_service.py"
        ;;
    auth)
        pkill -9 -f "run_auth_service.py" 2>/dev/null || true
        fuser -k -9 8003/tcp 2>/dev/null || true
        start_service "auth_service" "run_auth_service.py"
        ;;
    frontend)
        pkill -9 -f "start_frontends.sh" 2>/dev/null || true
        pkill -9 -f "vite" 2>/dev/null || true
        fuser -k -9 5173/tcp 5174/tcp 2>/dev/null || true
        start_frontend
        ;;
    all|start|restart)
        echo "============================================================"
        echo "  ⚡ CAKRA AI - Ultra-Fast Parallel Service Launch"
        echo "============================================================"
        stop_services
        
        echo "🚀 Meluncurkan seluruh service secara paralel..."
        start_service "auth_service"      "run_auth_service.py"
        start_service "analytics_service" "run_analytics_service.py"
        start_service "chat_service"      "run_chat_service.py"
        start_service "gateway"           "run_gateway.py"
        start_frontend

        echo "============================================================"
        echo "  ✅ All services launched in parallel in < 1 second!"
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
        echo "Usage: $0 [all|stop|reset-vram|gateway|chat|analytics|auth|frontend]"
        exit 1
        ;;
esac