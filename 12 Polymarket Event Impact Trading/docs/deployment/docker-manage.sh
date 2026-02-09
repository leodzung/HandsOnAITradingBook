#!/bin/bash
# Docker management script for Polymarket Trading Bots

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "Polymarket Trading Bots - Docker Management"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start [service]    Start all services or a specific service"
    echo "  stop [service]     Stop all services or a specific service"
    echo "  restart [service]  Restart all services or a specific service"
    echo "  status             Show status of all services"
    echo "  logs [service]     Show logs (tail -f) for all or specific service"
    echo "  build              Build/rebuild Docker images"
    echo "  clean              Stop and remove all containers, networks"
    echo "  shell <service>    Open a shell in a running container"
    echo ""
    echo "Services:"
    echo "  price-level-trader  Price level trading bot"
    echo "  event-trader        Event-based trading bot"
    echo "  arbitrage-bot       Arbitrage detection bot"
    echo "  dashboard           Streamlit monitoring dashboard"
    echo "  data-collector      Alchemy data collector"
    echo ""
    echo "Examples:"
    echo "  $0 start                    # Start all services"
    echo "  $0 start price-level-trader # Start only price level trader"
    echo "  $0 logs arbitrage-bot       # Follow logs for arbitrage bot"
    echo "  $0 status                   # Check status of all services"
}

case "$1" in
    start)
        print_status "Starting services..."
        if [ -n "$2" ]; then
            docker compose up -d "$2"
            print_status "Started $2"
        else
            docker compose up -d
            print_status "All services started"
        fi
        ;;

    stop)
        print_status "Stopping services..."
        if [ -n "$2" ]; then
            docker compose stop "$2"
            print_status "Stopped $2"
        else
            docker compose stop
            print_status "All services stopped"
        fi
        ;;

    restart)
        print_status "Restarting services..."
        if [ -n "$2" ]; then
            docker compose restart "$2"
            print_status "Restarted $2"
        else
            docker compose restart
            print_status "All services restarted"
        fi
        ;;

    status)
        echo ""
        echo "=== Container Status ==="
        docker compose ps
        echo ""
        echo "=== Health Status ==="
        docker ps --format "table {{.Names}}\t{{.Status}}" | grep polymarket || echo "No containers running"
        echo ""
        ;;

    logs)
        if [ -n "$2" ]; then
            docker compose logs -f "$2"
        else
            docker compose logs -f
        fi
        ;;

    build)
        print_status "Building Docker images..."
        docker compose build --no-cache
        print_status "Build complete"
        ;;

    clean)
        print_warning "This will stop and remove all containers..."
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker compose down -v --remove-orphans
            print_status "Cleanup complete"
        else
            print_status "Cancelled"
        fi
        ;;

    shell)
        if [ -z "$2" ]; then
            print_error "Please specify a service name"
            exit 1
        fi
        docker compose exec "$2" /bin/bash
        ;;

    *)
        show_help
        ;;
esac
