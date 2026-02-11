#!/bin/bash

# Launch script for Short-Expiry Trading Bot
# Usage: ./launch_short_expiry.sh [test|start|stop|status|logs]

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

BOT_SCRIPT="src/bots/trader_short_expiry.py"
PID_FILE="data/short_expiry.pid"
LOG_FILE="logs/short_expiry.out"

# Create directories
mkdir -p data logs

case "$1" in
    test)
        echo "=========================================="
        echo "Running Infrastructure Tests"
        echo "=========================================="
        python3 tests/test_short_expiry_infrastructure.py
        echo ""
        echo "=========================================="
        echo "Running Market Discovery Test"
        echo "=========================================="
        python3 tests/test_market_discovery_short_expiry.py
        ;;

    start)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null 2>&1; then
                echo "❌ Bot is already running (PID: $PID)"
                exit 1
            fi
        fi

        echo "🚀 Starting Short-Expiry Trading Bot..."
        nohup python3 "$BOT_SCRIPT" >> "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"

        echo "✅ Bot started (PID: $(cat $PID_FILE))"
        echo ""
        echo "Monitor logs with: ./launch_short_expiry.sh logs"
        echo "Check status with: ./launch_short_expiry.sh status"
        ;;

    stop)
        if [ ! -f "$PID_FILE" ]; then
            echo "❌ No PID file found. Bot may not be running."
            exit 1
        fi

        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "🛑 Stopping bot (PID: $PID)..."
            kill $PID
            rm "$PID_FILE"
            echo "✅ Bot stopped"
        else
            echo "❌ Bot not running (stale PID file)"
            rm "$PID_FILE"
        fi
        ;;

    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null 2>&1; then
                echo "✅ Bot is RUNNING (PID: $PID)"

                # Show paper trading balance
                if [ -f "data/paper_trading_balance_short_expiry.json" ]; then
                    echo ""
                    echo "Paper Trading Balance:"
                    cat data/paper_trading_balance_short_expiry.json | python3 -m json.tool
                fi

                # Show position counts
                if [ -f "data/positions_short_expiry.db" ]; then
                    echo ""
                    echo "Open Positions by Bucket:"
                    sqlite3 data/positions_short_expiry.db "
                        SELECT bucket, COUNT(*) as count
                        FROM positions
                        WHERE status = 'open'
                        GROUP BY bucket
                    " 2>/dev/null || echo "  (No open positions)"

                    echo ""
                    echo "Closed Positions Summary:"
                    sqlite3 data/positions_short_expiry.db "
                        SELECT
                            COUNT(*) as trades,
                            ROUND(AVG(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100, 1) as win_rate,
                            ROUND(AVG(pnl_pct), 2) as avg_pnl_pct,
                            ROUND(SUM(pnl), 2) as total_pnl
                        FROM positions
                        WHERE status = 'closed'
                    " 2>/dev/null || echo "  (No closed positions yet)"
                fi
            else
                echo "❌ Bot is NOT running (stale PID file)"
                rm "$PID_FILE"
            fi
        else
            echo "❌ Bot is NOT running (no PID file)"
        fi
        ;;

    logs)
        if [ -f "$LOG_FILE" ]; then
            echo "📊 Tailing logs from $LOG_FILE"
            echo "Press Ctrl+C to stop"
            echo "=========================================="
            tail -f "$LOG_FILE"
        else
            echo "❌ No log file found at $LOG_FILE"
        fi
        ;;

    *)
        echo "Short-Expiry Trading Bot - Launch Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  test     - Run infrastructure and market discovery tests"
        echo "  start    - Start the bot in background"
        echo "  stop     - Stop the bot"
        echo "  status   - Check bot status and show stats"
        echo "  logs     - Tail the log file"
        echo ""
        echo "Examples:"
        echo "  $0 test          # Run tests before starting"
        echo "  $0 start         # Start bot"
        echo "  $0 status        # Check if running + show P&L"
        echo "  $0 logs          # Monitor live logs"
        echo "  $0 stop          # Stop bot"
        ;;
esac
