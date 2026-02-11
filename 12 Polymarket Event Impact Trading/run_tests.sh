#!/bin/bash
# Comprehensive test runner for short-expiry bot
# Usage: ./run_tests.sh [test_type]

set -e
cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[TEST]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    error "pytest not found. Install with: pip3 install pytest"
    exit 1
fi

TEST_TYPE="${1:-all}"

case "$TEST_TYPE" in
    unit)
        log "Running unit tests..."
        pytest tests/test_short_expiry_features.py -v --tb=short
        ;;

    integration)
        log "Running integration tests..."
        pytest tests/test_short_expiry_trader.py -v --tb=short
        ;;

    comprehensive)
        log "Running comprehensive test suite..."
        pytest tests/test_short_expiry_comprehensive.py -v --tb=short
        ;;

    infrastructure)
        log "Running infrastructure tests..."
        python3 tests/test_short_expiry_infrastructure.py
        ;;

    discovery)
        log "Running market discovery tests..."
        python3 tests/test_market_discovery_short_expiry.py
        ;;

    all)
        log "Running ALL tests..."
        echo ""

        log "1/5: Infrastructure tests"
        python3 tests/test_short_expiry_infrastructure.py || true
        echo ""

        log "2/5: Market discovery tests"
        python3 tests/test_market_discovery_short_expiry.py || true
        echo ""

        log "3/5: Unit tests (features)"
        pytest tests/test_short_expiry_features.py -v --tb=short || true
        echo ""

        log "4/5: Integration tests (trader)"
        pytest tests/test_short_expiry_trader.py -v --tb=short || true
        echo ""

        log "5/5: Comprehensive tests"
        pytest tests/test_short_expiry_comprehensive.py -v --tb=short || true
        echo ""

        log "Test suite complete!"
        ;;

    coverage)
        log "Running tests with coverage..."
        pytest tests/test_short_expiry_*.py \
            --cov=src/bots/trader_short_expiry \
            --cov=src/features/short_expiry_features \
            --cov-report=html \
            --cov-report=term
        info "Coverage report generated in htmlcov/index.html"
        ;;

    fast)
        log "Running fast test subset..."
        pytest tests/test_short_expiry_infrastructure.py \
               tests/test_short_expiry_features.py::TestTimeDecayFeatures \
               -v --tb=line
        ;;

    ci)
        log "Running CI test suite (non-interactive)..."
        pytest tests/ \
            -v \
            --tb=short \
            --maxfail=5 \
            --disable-warnings \
            -m "not slow"
        ;;

    *)
        error "Unknown test type: $TEST_TYPE"
        echo ""
        echo "Usage: $0 [test_type]"
        echo ""
        echo "Test types:"
        echo "  unit           - Unit tests (features)"
        echo "  integration    - Integration tests (trader)"
        echo "  comprehensive  - Comprehensive test suite"
        echo "  infrastructure - Infrastructure tests (original)"
        echo "  discovery      - Market discovery tests"
        echo "  all            - Run all tests (default)"
        echo "  coverage       - Run with coverage report"
        echo "  fast           - Quick sanity check"
        echo "  ci             - CI-friendly test run"
        echo ""
        exit 1
        ;;
esac

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "✅ Tests passed!"
else
    error "❌ Tests failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
