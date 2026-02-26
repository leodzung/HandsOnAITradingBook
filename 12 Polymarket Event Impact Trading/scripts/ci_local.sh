#!/bin/bash
# Run CI checks locally before pushing
# Mimics GitHub Actions workflow for faster feedback

set -e

cd "$(dirname "$0")/.."

echo "🚀 Running local CI validation..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Parse arguments
SKIP_SLOW=false
PARALLEL=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            SKIP_SLOW=true
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--fast] [--parallel] [--verbose]"
            exit 1
            ;;
    esac
done

# Setup
START_TIME=$(date +%s)
FAILED_CHECKS=()

# Helper function to run checks
run_check() {
    local name=$1
    local cmd=$2

    echo "▶️  $name"
    if [ "$VERBOSE" = true ]; then
        if eval "$cmd"; then
            echo "   ✅ Passed"
        else
            echo "   ❌ Failed"
            FAILED_CHECKS+=("$name")
        fi
    else
        if eval "$cmd" > /dev/null 2>&1; then
            echo "   ✅ Passed"
        else
            echo "   ❌ Failed"
            FAILED_CHECKS+=("$name")
        fi
    fi
    echo ""
}

# Create required directories
mkdir -p data logs data/models

# 1. FAST: Structural tests (architecture constraints)
run_check "ARCH-001: PriceFetcher constraint" \
    "pytest tests/structural/test_price_fetcher_constraint.py -q"

run_check "ARCH-002: PositionManager constraint" \
    "pytest tests/structural/test_position_manager_constraint.py -q"

run_check "ARCH-003: Common features" \
    "pytest tests/test_common_features.py -q"

# 2. MEDIUM: Integration tests
if [ "$SKIP_SLOW" = false ]; then
    run_check "ARCH-004: WebSocket fallback" \
        "pytest tests/integration/test_orderbook_manager.py -q"

    run_check "RISK-001: Stop-loss/Take-profit" \
        "pytest tests/integration/test_position_monitoring.py -q"

    run_check "RISK-002: Circuit breaker" \
        "pytest tests/behavioral/test_circuit_breaker.py -q"

    run_check "RISK-003: Slippage estimation" \
        "pytest tests/integration/test_slippage_estimation.py -q"
else
    echo "⏩ Skipping slow tests (use without --fast to run all)"
    echo ""
fi

# 3. FAST: Documentation check
run_check "OPS-003: No documentation bloat" \
    "bash scripts/check_no_doc_bloat.sh"

# 4. OPTIONAL: Full constraint validation (slow)
if [ "$SKIP_SLOW" = false ]; then
    echo "▶️  Full constraint validation"
    if python3 scripts/validate_constraints.py > /tmp/constraint_validation.log 2>&1; then
        echo "   ✅ Passed"
    else
        echo "   ⚠️  Warnings detected (check /tmp/constraint_validation.log)"
    fi
    echo ""
fi

# Summary
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏱️  Total time: ${DURATION}s"
echo ""

if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
    echo "✅ All checks passed! Safe to push."
    echo ""
    echo "💡 Next steps:"
    echo "   git push"
    exit 0
else
    echo "❌ ${#FAILED_CHECKS[@]} check(s) failed:"
    for check in "${FAILED_CHECKS[@]}"; do
        echo "   - $check"
    done
    echo ""
    echo "💡 Fix the issues above before pushing."
    echo "   Or run with --verbose to see detailed errors."
    exit 1
fi
