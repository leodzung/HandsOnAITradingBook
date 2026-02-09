#!/bin/bash
# Run test suite for Polymarket Event Impact Trading

set -e  # Exit on error

echo "================================"
echo "Polymarket Trading Test Suite"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}pytest not found!${NC}"
    echo "Installing test dependencies..."
    pip install -r requirements-test.txt
fi

# Parse command line arguments
TEST_TYPE=${1:-all}
VERBOSE=${2:-}

case $TEST_TYPE in
    "quick")
        echo -e "${YELLOW}Running quick tests (unit tests only)...${NC}"
        pytest tests/ -m "unit and not slow" -v $VERBOSE
        ;;

    "unit")
        echo -e "${YELLOW}Running unit tests...${NC}"
        pytest tests/ -m unit -v $VERBOSE
        ;;

    "integration")
        echo -e "${YELLOW}Running integration tests...${NC}"
        pytest tests/ -m integration -v $VERBOSE
        ;;

    "models")
        echo -e "${YELLOW}Running ML model tests...${NC}"
        pytest tests/test_models.py -v $VERBOSE
        ;;

    "coverage")
        echo -e "${YELLOW}Running all tests with coverage report...${NC}"
        pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
        echo ""
        echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"
        ;;

    "fast")
        echo -e "${YELLOW}Running fast tests only...${NC}"
        pytest tests/ -m "not slow" -v $VERBOSE
        ;;

    "db")
        echo -e "${YELLOW}Running database tests...${NC}"
        pytest tests/ -m db -v $VERBOSE
        ;;

    "client")
        echo -e "${YELLOW}Running API client tests...${NC}"
        pytest tests/test_polymarket_client.py -v $VERBOSE
        ;;

    "trader")
        echo -e "${YELLOW}Running trader tests...${NC}"
        pytest tests/test_trader.py -v $VERBOSE
        ;;

    "all")
        echo -e "${YELLOW}Running full test suite...${NC}"
        pytest tests/ -v --cov=. --cov-report=term-missing $VERBOSE
        ;;

    "help")
        echo "Usage: ./run_tests.sh [TEST_TYPE] [OPTIONS]"
        echo ""
        echo "TEST_TYPE:"
        echo "  all          - Run all tests with coverage (default)"
        echo "  quick        - Run fast unit tests only"
        echo "  unit         - Run all unit tests"
        echo "  integration  - Run integration tests"
        echo "  models       - Run ML model tests"
        echo "  coverage     - Generate detailed coverage report"
        echo "  fast         - Skip slow tests"
        echo "  db           - Run database tests only"
        echo "  client       - Run API client tests"
        echo "  trader       - Run trader tests"
        echo "  help         - Show this help"
        echo ""
        echo "OPTIONS:"
        echo "  -vv          - Extra verbose output"
        echo "  -x           - Stop on first failure"
        echo "  --pdb        - Drop into debugger on failure"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh quick          # Quick test run"
        echo "  ./run_tests.sh unit -vv       # Verbose unit tests"
        echo "  ./run_tests.sh all -x --pdb   # Stop on first failure and debug"
        exit 0
        ;;

    *)
        echo -e "${RED}Unknown test type: $TEST_TYPE${NC}"
        echo "Run './run_tests.sh help' for usage information"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo ""
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
