#!/bin/bash
# Deployment script for Polymarket trading bots
# Usage: ./deploy.sh [price-level|event|both]

set -e
# Change to project root (two levels up from this script)
cd "$(dirname "$0")/../.."

BOT=$1
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to deploy price-level trader
deploy_price_level() {
    log "Deploying Price-Level Trader..."

    # 1. Check for running process
    OLD_PID=$(pgrep -f "trader_price_levels.py" || true)
    if [ -n "$OLD_PID" ]; then
        log "Found running process: PID $OLD_PID"

        # 2. Backup current log
        if [ -f logs/trading_price_levels.out ]; then
            cp logs/trading_price_levels.out "backups/trading_price_levels_${TIMESTAMP}.out"
            log "Backed up log to backups/trading_price_levels_${TIMESTAMP}.out"
        fi

        # 3. Graceful shutdown
        log "Stopping old process..."
        kill $OLD_PID 2>/dev/null || true
        sleep 3

        # Force kill if still running
        if pgrep -f "trader_price_levels.py" > /dev/null; then
            warn "Process still running, force killing..."
            pkill -9 -f "trader_price_levels.py" || true
            sleep 1
        fi
    fi

    # 4. Verify database state
    OPEN_POSITIONS=$(sqlite3 data/positions_price_level.db "SELECT COUNT(*) FROM positions WHERE status='OPEN'" 2>/dev/null || echo "0")
    BALANCE=$(cat data/paper_trading_balance_price_level.json 2>/dev/null | grep balance | grep -oE '[0-9]+\.[0-9]+' || echo "unknown")
    log "Database state: $OPEN_POSITIONS open positions, balance: \$$BALANCE"

    # 5. Start new process
    log "Starting new process..."
    nohup python3 src/bots/trader_price_levels.py >> logs/trading_price_levels.out 2>&1 &
    NEW_PID=$!
    sleep 3

    # 6. Verify startup
    if pgrep -f "trader_price_levels.py" > /dev/null; then
        log "✓ Price-Level Trader started successfully (PID: $NEW_PID)"
        tail -5 logs/trading_price_levels.out
    else
        error "✗ Failed to start Price-Level Trader"
        tail -20 logs/trading_price_levels.out
        return 1
    fi
}

# Function to deploy arbitrage bot
deploy_arbitrage() {
    log "Deploying Arbitrage Bot..."

    # 1. Check for running process
    OLD_PID=$(pgrep -f "arbitrage_bot.py" || true)
    if [ -n "$OLD_PID" ]; then
        log "Found running process: PID $OLD_PID"

        # 2. Backup current log
        if [ -f logs/arbitrage.out ]; then
            cp logs/arbitrage.out "backups/arbitrage_${TIMESTAMP}.out"
            log "Backed up log to backups/arbitrage_${TIMESTAMP}.out"
        fi

        # 3. Graceful shutdown
        log "Stopping old process..."
        kill $OLD_PID 2>/dev/null || true
        sleep 3

        # Force kill if still running
        if pgrep -f "arbitrage_bot.py" > /dev/null; then
            warn "Process still running, force killing..."
            pkill -9 -f "arbitrage_bot.py" || true
            sleep 1
        fi
    fi

    # 4. Start new process
    log "Starting new process..."
    nohup python3 src/bots/arbitrage_bot.py >> logs/arbitrage.out 2>&1 &
    NEW_PID=$!
    sleep 3

    # 5. Verify startup
    if pgrep -f "arbitrage_bot.py" > /dev/null; then
        log "✓ Arbitrage Bot started successfully (PID: $NEW_PID)"
        tail -5 logs/arbitrage.out
    else
        error "✗ Failed to start Arbitrage Bot"
        tail -20 logs/arbitrage.out
        return 1
    fi
}

# Function to deploy event trader
deploy_event() {
    log "Deploying Event Trader..."

    # 1. Check for running process
    OLD_PID=$(pgrep -f "[^_]trader.py" || true)
    if [ -n "$OLD_PID" ]; then
        log "Found running process: PID $OLD_PID"

        # 2. Backup current log
        if [ -f logs/trading.out ]; then
            cp logs/trading.out "backups/trading_${TIMESTAMP}.out"
            log "Backed up log to backups/trading_${TIMESTAMP}.out"
        fi

        # 3. Graceful shutdown
        log "Stopping old process..."
        kill $OLD_PID 2>/dev/null || true
        sleep 3
    fi

    # 4. Verify database state
    OPEN_POSITIONS=$(sqlite3 data/positions.db "SELECT COUNT(*) FROM positions WHERE status='OPEN'" 2>/dev/null || echo "0")
    BALANCE=$(cat data/paper_trading_balance.json 2>/dev/null | grep balance | grep -oE '[0-9]+\.[0-9]+' || echo "unknown")
    log "Database state: $OPEN_POSITIONS open positions, balance: \$$BALANCE"

    # 5. Start new process
    log "Starting new process..."
    nohup python3 src/bots/trader.py >> logs/trading.out 2>&1 &
    NEW_PID=$!
    sleep 3

    # 6. Verify startup
    if pgrep -f "trader.py" > /dev/null; then
        log "✓ Event Trader started successfully (PID: $NEW_PID)"
        tail -5 logs/trading.out
    else
        error "✗ Failed to start Event Trader"
        tail -20 logs/trading.out
        return 1
    fi
}

# Function to deploy GDELT collector (Docker or direct)
deploy_gdelt() {
    USE_DOCKER=${1:-false}

    log "Deploying GDELT Collector (continuous mode - updates every 15 min)..."

    # Check database state
    if [ -f "data/gdelt_news.db" ]; then
        GDELT_SIZE=$(ls -lh data/gdelt_news.db | awk '{print $5}')
        GDELT_EVENTS=$(sqlite3 data/gdelt_news.db "SELECT COUNT(*) FROM news_events" 2>/dev/null || echo "0")
        log "Database state: $GDELT_SIZE, $GDELT_EVENTS events"
    else
        log "Database state: New database will be created"
    fi

    if [ "$USE_DOCKER" = "true" ]; then
        # Docker deployment
        log "Using Docker deployment..."
        docker-compose up -d --build gdelt-collector
        sleep 3
        if docker ps | grep -q "polymarket-gdelt-collector"; then
            log "✓ GDELT Collector container started successfully"
            docker logs --tail 5 polymarket-gdelt-collector
        else
            error "✗ Failed to start GDELT Collector container"
            docker logs --tail 20 polymarket-gdelt-collector
            return 1
        fi
    else
        # Direct process deployment
        OLD_PID=$(pgrep -f "gdelt_collector.py" || true)
        if [ -n "$OLD_PID" ]; then
            log "Found running process: PID $OLD_PID"
            if [ -f logs/gdelt_collection.out ]; then
                cp logs/gdelt_collection.out "backups/gdelt_collection_${TIMESTAMP}.out"
                log "Backed up log to backups/gdelt_collection_${TIMESTAMP}.out"
            fi
            log "Stopping old process..."
            kill $OLD_PID 2>/dev/null || true
            sleep 3
            if pgrep -f "gdelt_collector.py" > /dev/null; then
                warn "Process still running, force killing..."
                pkill -9 -f "gdelt_collector.py" || true
                sleep 1
            fi
        fi

        log "Starting new process in continuous mode..."
        nohup python3 src/collectors/gdelt_collector.py --continuous >> logs/gdelt_collection.out 2>&1 &
        NEW_PID=$!
        sleep 3

        if pgrep -f "gdelt_collector.py" > /dev/null; then
            log "✓ GDELT Collector started successfully (PID: $NEW_PID)"
            log "  Collecting news updates every 15 minutes"
            tail -5 logs/gdelt_collection.out
        else
            error "✗ Failed to start GDELT Collector"
            tail -20 logs/gdelt_collection.out
            return 1
        fi
    fi
}

# Function to deploy Alchemy collector (Docker or direct)
deploy_alchemy() {
    USE_DOCKER=${1:-false}

    log "Deploying Alchemy Collector (continuous mode - updates every hour)..."

    # Check database state
    if [ -f "data/alchemy_trades.db" ]; then
        ALCHEMY_SIZE=$(ls -lh data/alchemy_trades.db | awk '{print $5}')
        ALCHEMY_TRADES=$(sqlite3 data/alchemy_trades.db "SELECT COUNT(*) FROM on_chain_trades" 2>/dev/null || echo "0")
        log "Database state: $ALCHEMY_SIZE, $ALCHEMY_TRADES on-chain trades"
    else
        log "Database state: New database will be created"
    fi

    if [ "$USE_DOCKER" = "true" ]; then
        # Docker deployment
        log "Using Docker deployment..."
        docker-compose up -d --build alchemy-collector
        sleep 3
        if docker ps | grep -q "polymarket-alchemy-collector"; then
            log "✓ Alchemy Collector container started successfully"
            docker logs --tail 5 polymarket-alchemy-collector
        else
            error "✗ Failed to start Alchemy Collector container"
            docker logs --tail 20 polymarket-alchemy-collector
            return 1
        fi
    else
        # Direct process deployment
        OLD_PID=$(pgrep -f "alchemy_collector.py" || true)
        if [ -n "$OLD_PID" ]; then
            log "Found running process: PID $OLD_PID"
            if [ -f logs/alchemy_collection.out ]; then
                cp logs/alchemy_collection.out "backups/alchemy_collection_${TIMESTAMP}.out"
                log "Backed up log to backups/alchemy_collection_${TIMESTAMP}.out"
            fi
            log "Stopping old process..."
            kill $OLD_PID 2>/dev/null || true
            sleep 3
            if pgrep -f "alchemy_collector.py" > /dev/null; then
                warn "Process still running, force killing..."
                pkill -9 -f "alchemy_collector.py" || true
                sleep 1
            fi
        fi

        log "Starting new process in continuous mode..."
        nohup python3 src/collectors/alchemy_collector.py --continuous >> logs/alchemy_collection.out 2>&1 &
        NEW_PID=$!
        sleep 3

        if pgrep -f "alchemy_collector.py" > /dev/null; then
            log "✓ Alchemy Collector started successfully (PID: $NEW_PID)"
            log "  Collecting on-chain trades every hour"
            tail -5 logs/alchemy_collection.out
        else
            error "✗ Failed to start Alchemy Collector"
            tail -20 logs/alchemy_collection.out
            return 1
        fi
    fi
}

# Function to show status
show_status() {
    echo ""
    log "=== Bot Status ==="

    # Price-Level Trader
    PL_PID=$(pgrep -f "trader_price_levels.py" || true)
    if [ -n "$PL_PID" ]; then
        PL_START=$(ps -o lstart= -p $PL_PID 2>/dev/null || echo "unknown")
        echo -e "  Price-Level Trader: ${GREEN}RUNNING${NC} (PID: $PL_PID, started: $PL_START)"
    else
        echo -e "  Price-Level Trader: ${RED}STOPPED${NC}"
    fi

    # Event Trader
    EV_PID=$(pgrep -f "[^_]trader.py" || true)
    if [ -n "$EV_PID" ]; then
        EV_START=$(ps -o lstart= -p $EV_PID 2>/dev/null || echo "unknown")
        echo -e "  Event Trader: ${GREEN}RUNNING${NC} (PID: $EV_PID, started: $EV_START)"
    else
        echo -e "  Event Trader: ${RED}STOPPED${NC}"
    fi

    # Arbitrage Bot
    ARB_PID=$(pgrep -f "arbitrage_bot.py" || true)
    if [ -n "$ARB_PID" ]; then
        ARB_START=$(ps -o lstart= -p $ARB_PID 2>/dev/null || echo "unknown")
        echo -e "  Arbitrage Bot: ${GREEN}RUNNING${NC} (PID: $ARB_PID, started: $ARB_START)"
    else
        echo -e "  Arbitrage Bot: ${RED}STOPPED${NC}"
    fi

    # GDELT Collector (check Docker first, then process)
    GDELT_DOCKER=$(docker ps --format "{{.Names}}" 2>/dev/null | grep "polymarket-gdelt-collector" || true)
    GDELT_PID=$(pgrep -f "gdelt_collector.py" || true)
    if [ -n "$GDELT_DOCKER" ]; then
        GDELT_STATUS=$(docker ps --filter "name=polymarket-gdelt-collector" --format "{{.Status}}" 2>/dev/null)
        echo -e "  GDELT Collector: ${GREEN}RUNNING${NC} (Docker: $GDELT_STATUS)"
    elif [ -n "$GDELT_PID" ]; then
        GDELT_START=$(ps -o lstart= -p $GDELT_PID 2>/dev/null || echo "unknown")
        echo -e "  GDELT Collector: ${GREEN}RUNNING${NC} (PID: $GDELT_PID, started: $GDELT_START)"
    else
        echo -e "  GDELT Collector: ${RED}STOPPED${NC}"
    fi

    # Alchemy Collector (check Docker first, then process)
    ALCHEMY_DOCKER=$(docker ps --format "{{.Names}}" 2>/dev/null | grep "polymarket-alchemy-collector" || true)
    ALCHEMY_PID=$(pgrep -f "alchemy_collector.py" || true)
    if [ -n "$ALCHEMY_DOCKER" ]; then
        ALCHEMY_STATUS=$(docker ps --filter "name=polymarket-alchemy-collector" --format "{{.Status}}" 2>/dev/null)
        echo -e "  Alchemy Collector: ${GREEN}RUNNING${NC} (Docker: $ALCHEMY_STATUS)"
    elif [ -n "$ALCHEMY_PID" ]; then
        ALCHEMY_START=$(ps -o lstart= -p $ALCHEMY_PID 2>/dev/null || echo "unknown")
        echo -e "  Alchemy Collector: ${GREEN}RUNNING${NC} (PID: $ALCHEMY_PID, started: $ALCHEMY_START)"
    else
        echo -e "  Alchemy Collector: ${RED}STOPPED${NC}"
    fi

    echo ""
    log "=== Database Status ==="

    # GDELT database (separate)
    if [ -f "data/gdelt_news.db" ]; then
        GDELT_SIZE=$(ls -lh data/gdelt_news.db | awk '{print $5}')
        GDELT_EVENTS=$(sqlite3 data/gdelt_news.db "SELECT COUNT(*) FROM news_events" 2>/dev/null || echo "0")
        GDELT_FILES=$(sqlite3 data/gdelt_news.db "SELECT COUNT(*) FROM gdelt_files_processed" 2>/dev/null || echo "0")
        echo -e "  gdelt_news.db: ${GDELT_SIZE}"
        echo -e "    News events: ${GDELT_EVENTS}"
        echo -e "    Files processed: ${GDELT_FILES}"
    else
        echo -e "  gdelt_news.db: ${YELLOW}Not created yet${NC}"
    fi

    # Alchemy database (separate)
    if [ -f "data/alchemy_trades.db" ]; then
        ALCHEMY_SIZE=$(ls -lh data/alchemy_trades.db | awk '{print $5}')
        ALCHEMY_TRADES=$(sqlite3 data/alchemy_trades.db "SELECT COUNT(*) FROM on_chain_trades" 2>/dev/null || echo "0")
        echo -e "  alchemy_trades.db: ${ALCHEMY_SIZE}"
        echo -e "    On-chain trades: ${ALCHEMY_TRADES}"
    else
        echo -e "  alchemy_trades.db: ${YELLOW}Not created yet${NC}"
    fi

    # Legacy database warning
    if [ -f "data/training_history.db" ]; then
        LEGACY_SIZE=$(ls -lh data/training_history.db | awk '{print $5}')
        echo -e "  ${YELLOW}training_history.db (LEGACY): ${LEGACY_SIZE} - can be deleted${NC}"
    fi
    echo ""
}

# Function to reset positions
reset_positions() {
    log "Resetting all positions..."

    # Price-Level Trader
    if [ -f "data/positions_price_level.db" ]; then
        sqlite3 data/positions_price_level.db "DELETE FROM positions"
        log "✓ Cleared price-level positions"
    fi

    # Event Trader
    if [ -f "data/positions.db" ]; then
        sqlite3 data/positions.db "DELETE FROM positions"
        log "✓ Cleared event trader positions"
    fi

    # Reset balances
    echo '{"balance": 250.0, "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%S)'", "note": "Reset by deploy.sh"}' > data/paper_trading_balance_price_level.json
    log "✓ Reset price-level balance to \$250"

    echo '{"balance": 1000.0, "last_updated": "'$(date -u +%Y-%m-%dT%H:%M:%S)'", "note": "Reset by deploy.sh"}' > data/paper_trading_balance.json
    log "✓ Reset event trader balance to \$1000"

    log "All positions reset!"
}

# Ensure backups directory exists
mkdir -p backups

# Main
case "$BOT" in
    price-level|pl)
        deploy_price_level
        ;;
    event|ev)
        deploy_event
        ;;
    arbitrage|arb)
        deploy_arbitrage
        ;;
    gdelt)
        deploy_gdelt false
        ;;
    alchemy)
        deploy_alchemy false
        ;;
    collectors)
        deploy_gdelt false
        echo ""
        deploy_alchemy false
        ;;
    gdelt-docker)
        deploy_gdelt true
        ;;
    alchemy-docker)
        deploy_alchemy true
        ;;
    collectors-docker)
        deploy_gdelt true
        echo ""
        deploy_alchemy true
        ;;
    stop-collectors)
        log "Stopping all collectors..."
        # Stop Docker containers
        docker stop polymarket-gdelt-collector 2>/dev/null && log "Stopped GDELT Docker container" || true
        docker stop polymarket-alchemy-collector 2>/dev/null && log "Stopped Alchemy Docker container" || true
        # Stop direct processes
        pkill -f "gdelt_collector.py" 2>/dev/null && log "Stopped GDELT process" || true
        pkill -f "alchemy_collector.py" 2>/dev/null && log "Stopped Alchemy process" || true
        log "All collectors stopped"
        ;;
    both)
        deploy_price_level
        echo ""
        deploy_event
        ;;
    all)
        deploy_price_level
        echo ""
        deploy_event
        echo ""
        deploy_arbitrage
        ;;
    status|st)
        show_status
        ;;
    reset)
        reset_positions
        ;;
    reset-and-deploy)
        reset_positions
        echo ""
        deploy_price_level
        echo ""
        deploy_event
        ;;
    *)
        echo "Usage: ./deploy.sh [command]"
        echo ""
        echo "Trading Bots (direct process):"
        echo "  price-level, pl  - Deploy price-level trader"
        echo "  event, ev        - Deploy event trader"
        echo "  arbitrage, arb   - Deploy arbitrage bot"
        echo "  both             - Deploy price-level + event traders"
        echo "  all              - Deploy all three trading bots"
        echo ""
        echo "Data Collectors (direct process):"
        echo "  gdelt [days]     - Deploy GDELT news collector (default: 720 days)"
        echo "  alchemy [days]   - Deploy Alchemy on-chain collector (default: 180 days)"
        echo "  collectors       - Deploy both collectors"
        echo ""
        echo "Data Collectors (Docker):"
        echo "  gdelt-docker     - Deploy GDELT collector in Docker"
        echo "  alchemy-docker   - Deploy Alchemy collector in Docker"
        echo "  collectors-docker - Deploy both collectors in Docker"
        echo "  stop-collectors  - Stop all collectors (Docker + process)"
        echo ""
        echo "Management:"
        echo "  status, st       - Show bot and collector status"
        echo "  reset            - Clear all positions and reset balances"
        echo "  reset-and-deploy - Reset positions and deploy both traders"
        echo ""
        show_status
        ;;
esac
