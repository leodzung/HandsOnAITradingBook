#!/bin/bash
# Unified Bot Management Script
# Manages all Polymarket trading bots: event, price-level, short-expiry, and dashboard

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[BOT MANAGER]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Bot configuration helper functions
get_bot_script() {
    case "$1" in
        event) echo "trader.py" ;;
        price-level) echo "trader_price_levels.py" ;;
        short-expiry) echo "src/bots/trader_short_expiry.py" ;;
    esac
}

get_bot_name() {
    case "$1" in
        event) echo "Event Trader" ;;
        price-level) echo "Price Level Trader" ;;
        short-expiry) echo "Short Expiry Trader" ;;
    esac
}

get_bot_log() {
    case "$1" in
        event) echo "logs/trading.out" ;;
        price-level) echo "logs/trading_price_levels.out" ;;
        short-expiry) echo "logs/short_expiry.out" ;;
    esac
}

get_bot_pid_file() {
    case "$1" in
        event) echo "data/event_trader.pid" ;;
        price-level) echo "data/price_level_trader.pid" ;;
        short-expiry) echo "data/short_expiry.pid" ;;
    esac
}

# Create directories
mkdir -p logs data

# Check if bot is running
is_bot_running() {
    local bot=$1
    local pid_file=$(get_bot_pid_file "$bot")

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo $pid
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

# Start a bot
start_bot() {
    local bot=$1
    local script=$(get_bot_script "$bot")
    local name=$(get_bot_name "$bot")
    local log_file=$(get_bot_log "$bot")
    local pid_file=$(get_bot_pid_file "$bot")

    if is_bot_running $bot > /dev/null; then
        warn "$name is already running (PID: $(is_bot_running $bot))"
        return 1
    fi

    log "Starting $name..."
    nohup python3 "$script" >> "$log_file" 2>&1 &
    local pid=$!
    echo $pid > "$pid_file"

    sleep 2
    if ps -p $pid > /dev/null 2>&1; then
        log "✅ $name started (PID: $pid)"
        info "   Log: $log_file"
    else
        error "❌ Failed to start $name"
        tail -20 "$log_file"
        rm -f "$pid_file"
        return 1
    fi
}

# Stop a bot
stop_bot() {
    local bot=$1
    local name=$(get_bot_name "$bot")
    local pid_file=$(get_bot_pid_file "$bot")

    if ! is_bot_running $bot > /dev/null; then
        warn "$name is not running"
        rm -f "$pid_file"
        return 1
    fi

    local pid=$(is_bot_running $bot)
    log "Stopping $name (PID: $pid)..."
    kill $pid 2>/dev/null || true
    sleep 2

    if ps -p $pid > /dev/null 2>&1; then
        warn "Force killing $name..."
        kill -9 $pid 2>/dev/null || true
    fi

    rm -f "$pid_file"
    log "✅ $name stopped"
}

# Show status of all bots
show_status() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  POLYMARKET TRADING BOTS - STATUS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Check bots
    for bot in event price-level short-expiry; do
        local name=$(get_bot_name "$bot")
        if is_bot_running $bot > /dev/null; then
            local pid=$(is_bot_running $bot)
            echo -e "  ${GREEN}●${NC} $name: ${GREEN}RUNNING${NC} (PID: $pid)"
        else
            echo -e "  ${RED}○${NC} $name: ${RED}STOPPED${NC}"
        fi
    done

    echo ""

    # Check dashboard
    if pgrep -f "streamlit run.*dashboard.py" > /dev/null; then
        local pid=$(pgrep -f "streamlit run.*dashboard.py")
        echo -e "  ${GREEN}●${NC} Dashboard: ${GREEN}RUNNING${NC} (PID: $pid)"
        echo -e "    ${BLUE}→${NC} http://localhost:8502"
    else
        echo -e "  ${RED}○${NC} Dashboard: ${RED}STOPPED${NC}"
    fi

    echo ""

    # Show balances
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  PAPER TRADING BALANCES"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Event trader balance
    if [ -f "data/paper_trading_balance.json" ]; then
        local balance=$(python3 -c "import json; print(f\"\${json.load(open('data/paper_trading_balance.json'))['balance']:.2f}\")" 2>/dev/null || echo "N/A")
        echo "  Event Trader:        $$balance"
    fi

    # Price level balance
    if [ -f "data/paper_trading_balance_price_level.json" ]; then
        local balance=$(python3 -c "import json; print(f\"\${json.load(open('data/paper_trading_balance_price_level.json'))['balance']:.2f}\")" 2>/dev/null || echo "N/A")
        echo "  Price Level Trader:  $$balance"
    fi

    # Short expiry balance
    if [ -f "data/paper_trading_balance_short_expiry.json" ]; then
        local balance=$(python3 -c "import json; print(f\"\${json.load(open('data/paper_trading_balance_short_expiry.json'))['balance']:.2f}\")" 2>/dev/null || echo "N/A")
        echo "  Short Expiry Trader: $$balance"
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# Start dashboard
start_dashboard() {
    if pgrep -f "streamlit run.*dashboard.py" > /dev/null; then
        warn "Dashboard is already running"
        return 1
    fi

    log "Starting dashboard on port 8502..."
    nohup streamlit run src/monitoring/dashboard.py --server.port 8502 >> logs/dashboard.out 2>&1 &
    sleep 3

    if pgrep -f "streamlit run.*dashboard.py" > /dev/null; then
        log "✅ Dashboard started"
        info "   Access at: http://localhost:8502"
    else
        error "❌ Failed to start dashboard"
        tail -20 logs/dashboard.out
        return 1
    fi
}

# Stop dashboard
stop_dashboard() {
    local pid=$(pgrep -f "streamlit run.*dashboard.py" || true)
    if [ -n "$pid" ]; then
        log "Stopping dashboard (PID: $pid)..."
        kill $pid 2>/dev/null || true
        sleep 2
        if pgrep -f "streamlit run.*dashboard.py" > /dev/null; then
            warn "Force killing dashboard..."
            pkill -9 -f "streamlit run.*dashboard.py" || true
        fi
        log "✅ Dashboard stopped"
    else
        warn "Dashboard is not running"
    fi
}

# Show help
show_help() {
    cat << EOF

Polymarket Bot Manager - Control all trading bots

USAGE:
    ./manage_bots.sh [command] [bot]

COMMANDS:
    start [bot]     Start a bot (event, price-level, short-expiry, or all)
    stop [bot]      Stop a bot (event, price-level, short-expiry, or all)
    restart [bot]   Restart a bot
    status          Show status of all bots
    logs [bot]      Tail logs for a bot
    dashboard       Start/stop dashboard
    test            Run tests for all bots

BOTS:
    event           Event-based trader
    price-level     Price level trader
    short-expiry    Short expiry trader (2h-7d markets)
    all             All bots
    dashboard       Streamlit dashboard

EXAMPLES:
    ./manage_bots.sh start all              # Start all bots
    ./manage_bots.sh start short-expiry     # Start short-expiry bot only
    ./manage_bots.sh stop event             # Stop event trader
    ./manage_bots.sh status                 # Show status
    ./manage_bots.sh logs short-expiry      # Watch short-expiry logs
    ./manage_bots.sh dashboard start        # Start dashboard

EOF
}

# Main command routing
case "${1:-help}" in
    start)
        case "${2:-all}" in
            all)
                for bot in event price-level short-expiry; do
                    start_bot $bot
                done
                ;;
            event|price-level|short-expiry)
                start_bot $2
                ;;
            *)
                error "Unknown bot: $2"
                show_help
                exit 1
                ;;
        esac
        ;;

    stop)
        case "${2:-all}" in
            all)
                for bot in event price-level short-expiry; do
                    stop_bot $bot
                done
                ;;
            event|price-level|short-expiry)
                stop_bot $2
                ;;
            *)
                error "Unknown bot: $2"
                show_help
                exit 1
                ;;
        esac
        ;;

    restart)
        case "${2:-all}" in
            all)
                for bot in event price-level short-expiry; do
                    stop_bot $bot 2>/dev/null || true
                    sleep 1
                    start_bot $bot
                done
                ;;
            event|price-level|short-expiry)
                stop_bot $2 2>/dev/null || true
                sleep 1
                start_bot $2
                ;;
            *)
                error "Unknown bot: $2"
                show_help
                exit 1
                ;;
        esac
        ;;

    status)
        show_status
        ;;

    logs)
        bot="${2:-short-expiry}"
        log_file=$(get_bot_log "$bot")
        if [ -z "$log_file" ]; then
            error "Unknown bot: $bot"
            exit 1
        fi
        log "Tailing $log_file (Ctrl+C to stop)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        tail -f "$log_file"
        ;;

    dashboard)
        case "${2:-start}" in
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
            *)
                error "Usage: $0 dashboard [start|stop|restart]"
                exit 1
                ;;
        esac
        ;;

    test)
        log "Running tests for all bots..."
        echo ""

        # Short-expiry tests
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  SHORT-EXPIRY BOT TESTS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        python3 tests/test_short_expiry_infrastructure.py
        echo ""
        python3 tests/test_market_discovery_short_expiry.py
        ;;

    help|--help|-h)
        show_help
        ;;

    *)
        error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
