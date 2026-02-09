#!/bin/bash
# Dashboard management script
# Usage: ./dashboard.sh [start|stop|restart|status]

set -e
# Change to project root
cd "$(dirname "$0")/../.."

ACTION=${1:-start}

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DASHBOARD]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

stop_dashboard() {
    PID=$(pgrep -f "streamlit run.*dashboard.py" || true)
    if [ -n "$PID" ]; then
        log "Stopping dashboard (PID: $PID)..."
        kill $PID 2>/dev/null || true
        sleep 2
        if pgrep -f "streamlit run.*dashboard.py" > /dev/null; then
            warn "Force killing dashboard..."
            pkill -9 -f "streamlit run.*dashboard.py" || true
        fi
        log "Dashboard stopped"
    else
        warn "Dashboard is not running"
    fi
}

start_dashboard() {
    # Check if already running
    if pgrep -f "streamlit run.*dashboard.py" > /dev/null; then
        error "Dashboard is already running. Use 'restart' to restart it."
        return 1
    fi

    log "Starting dashboard on port 8502..."
    nohup streamlit run src/monitoring/dashboard.py --server.port 8502 >> logs/dashboard.out 2>&1 &
    sleep 3

    if pgrep -f "streamlit run.*dashboard.py" > /dev/null; then
        log "✓ Dashboard started successfully"
        log "  Access at: http://localhost:8502"
        tail -5 logs/dashboard.out
    else
        error "✗ Failed to start dashboard"
        tail -20 logs/dashboard.out
        return 1
    fi
}

show_status() {
    PID=$(pgrep -f "streamlit run.*dashboard.py" || true)
    if [ -n "$PID" ]; then
        START_TIME=$(ps -o lstart= -p $PID 2>/dev/null || echo "unknown")
        echo -e "Dashboard: ${GREEN}RUNNING${NC} (PID: $PID, started: $START_TIME)"
        echo "  URL: http://localhost:8502"
    else
        echo -e "Dashboard: ${RED}STOPPED${NC}"
    fi
}

case "$ACTION" in
    start)
        start_dashboard
        ;;
    stop)
        stop_dashboard
        ;;
    restart)
        stop_dashboard
        sleep 2
        start_dashboard
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
