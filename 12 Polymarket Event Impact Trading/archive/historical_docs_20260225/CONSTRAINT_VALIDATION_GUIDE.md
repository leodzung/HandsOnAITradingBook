# Constraint Validation System - User Guide

> **Harness Engineering for Polymarket Trading System**
>
> This system transforms manual checklists into executable, self-validating constraints.
> Inspired by OpenAI's harness engineering approach.

## Overview

The constraint validation system automatically enforces architectural patterns, risk management rules, and quality gates that are critical to the trading system's correctness.

### Key Concepts

- **Constraints** → Machine-readable rules defined in `CONSTRAINTS.yml`
- **Validation** → Automated tests that verify constraints are satisfied
- **Telemetry** → Runtime metrics that monitor system health
- **Regression Detection** → Automatic alerts when resolved issues reappear

## Quick Start

### 1. Validate All Constraints

```bash
cd "12 Polymarket Event Impact Trading"
python scripts/validate_constraints.py
```

**Output:**
```
🔍 Polymarket Trading System - Constraint Validation
======================================================================

📋 Category: ARCHITECTURE
──────────────────────────────────────────────────────────────────────

  [ARCH-001] PriceFetcher is single source of truth for price data
  Priority: CRITICAL
    ✅ import_linter: PASSED
       Checked 4 files, no violations
    ✅ structural_test: PASSED
       5 test(s) passed

...

📊 Validation Summary
======================================================================

  Total enforced constraints: 13
  Passed: 13
  Warnings: 0
  Violations: 0

✅ ALL CONSTRAINTS SATISFIED
```

### 2. Validate Specific Category

```bash
# Validate only architecture constraints
python scripts/validate_constraints.py --category architecture

# Validate only risk management
python scripts/validate_constraints.py --category risk_management

# Validate only model quality
python scripts/validate_constraints.py --category model_quality
```

### 3. Validate Specific Constraint

```bash
# Check if PriceFetcher is properly used
python scripts/validate_constraints.py --id ARCH-001

# Check if circuit breaker is working
python scripts/validate_constraints.py --id RISK-002
```

### 4. CI Mode (for automation)

```bash
# No colors, fail fast
python scripts/validate_constraints.py --ci

# Exit code 0 = pass, 1 = fail
echo $?
```

## Understanding CONSTRAINTS.yml

### Constraint Structure

```yaml
constraints:
  architecture:
    - id: "ARCH-001"
      title: "PriceFetcher is single source of truth"
      description: "All price data MUST flow through PriceFetcher"
      status: "enforced"  # or "planned", "deprecated"
      priority: "critical"  # or "high", "medium", "low"
      implemented_date: "2026-02-13"

      validation:
        - type: "import_linter"
          rule: "forbid_direct_market_price_access"
          forbidden_patterns:
            - "market\\['bestBid'\\]"
            - "market\\['bestAsk'\\]"

        - type: "structural_test"
          command: "pytest tests/structural/test_price_fetcher_constraint.py -v"

      telemetry:
        - metric: "direct_market_access_violations"
          threshold: 0
          alert: "critical"
```

### Validation Types

| Type | Purpose | Example |
|------|---------|---------|
| `import_linter` | Check for forbidden imports/patterns | Block `market['bestBid']` |
| `structural_test` | Run pytest structural tests | `pytest tests/structural/...` |
| `integration_test` | Run pytest integration tests | `pytest tests/integration/...` |
| `behavioral_test` | Run pytest behavioral tests | `pytest tests/behavioral/...` |
| `filesystem_check` | Verify files exist/don't exist | `test ! -f old_file.py` |
| `pre_deployment_gate` | Run validation before deployment | `validate_model_quality.py` |

## Current Constraints

### 🏗️ Architecture (4 constraints)

| ID | Title | Status | Priority |
|----|-------|--------|----------|
| ARCH-001 | PriceFetcher single source of truth | ✅ Enforced | Critical |
| ARCH-002 | PositionManager V2 unified | ✅ Enforced | Critical |
| ARCH-003 | Common features centralized | ✅ Enforced | High |
| ARCH-004 | WebSocket orderbook with fallback | ✅ Enforced | High |

### 🛡️ Risk Management (3 constraints)

| ID | Title | Status | Priority |
|----|-------|--------|----------|
| RISK-001 | Stop-loss/take-profit always active | ✅ Enforced | Critical |
| RISK-002 | Circuit breaker after 3 losses | ✅ Enforced | High |
| RISK-003 | Slippage estimation before execution | ✅ Enforced | High |

### 🤖 Model Quality (3 constraints)

| ID | Title | Status | Priority |
|----|-------|--------|----------|
| ML-001 | Cross-validation (k≥5) required | ✅ Enforced | Critical |
| ML-002 | Feature drift detection | ✅ Enforced | High |
| ML-003 | Correct label creation (token mapping) | ✅ Enforced | Critical |

### ⚙️ Operations (2 constraints)

| ID | Title | Status | Priority |
|----|-------|--------|----------|
| OPS-001 | Bot health monitoring | ✅ Enforced | High |
| OPS-002 | Position persistence across restarts | ✅ Enforced | Critical |

## Adding New Constraints

### 1. Define in CONSTRAINTS.yml

```yaml
constraints:
  risk_management:
    - id: "RISK-004"
      title: "Position size limits enforced"
      description: "All trades MUST respect max position size"
      status: "enforced"
      priority: "critical"
      implemented_date: "2026-02-24"

      validation:
        - type: "behavioral_test"
          command: "pytest tests/behavioral/test_position_size_limits.py -v"

      telemetry:
        - metric: "oversized_position_attempts"
          threshold: 0
          alert: "critical"
```

### 2. Create Validation Test

```python
# tests/behavioral/test_position_size_limits.py
import pytest

def test_rejects_oversized_positions():
    """Verify trades exceeding max position size are rejected"""
    from src.core.trade_executor import TradeExecutor

    executor = TradeExecutor(config={'max_position_size': 100})

    # Should reject
    result = executor.execute_trade(market_id='test', size=150)
    assert result['rejected'] == True
    assert 'position size' in result['reason'].lower()

    # Should accept
    result = executor.execute_trade(market_id='test', size=50)
    assert result['rejected'] == False
```

### 3. Validate

```bash
python scripts/validate_constraints.py --id RISK-004
```

## Integration with Improvement Checklist

The constraint system **complements** (not replaces) `IMPROVEMENT_CHECKLIST.md`:

| Aspect | IMPROVEMENT_CHECKLIST.md | CONSTRAINTS.yml |
|--------|-------------------------|-----------------|
| Purpose | Human-readable progress tracker | Machine-executable validation |
| Format | Markdown with checkboxes | YAML with validation rules |
| Usage | Manual updates by developers | Automated CI/CD validation |
| Content | Tasks, plans, lessons learned | Architectural invariants, quality gates |

### Workflow

1. **Planning**: Add item to `IMPROVEMENT_CHECKLIST.md`
2. **Implementation**: Write code, check off task
3. **Enforcement**: Add constraint to `CONSTRAINTS.yml`
4. **Validation**: Run `validate_constraints.py` in CI
5. **Maintenance**: Constraints prevent regression forever

## Regression Detection

When you resolve technical debt, add a validation check:

```yaml
technical_debt:
  resolved:
    - id: "DEBT-001"
      title: "Consolidate duplicated position management"
      status: "resolved"
      resolved_date: "2026-02-14"
      validation:
        - type: "filesystem_check"
          command: "test ! -f src/core/position_manager_v1.py"
```

The validator will **alert if the old file reappears**, catching regressions automatically.

## Best Practices

### ✅ DO

- **Enforce critical patterns** - Architecture, risk, data quality
- **Write testable constraints** - Clear pass/fail criteria
- **Add telemetry metrics** - Monitor at runtime
- **Document rationale** - Explain why constraint exists
- **Set appropriate priority** - Critical/High/Medium/Low

### ❌ DON'T

- **Over-constrain** - Don't enforce style preferences
- **Skip validation** - Every constraint needs tests
- **Forget regression checks** - Resolved debt can reappear
- **Hardcode values** - Use config for thresholds

## CI/CD Integration

### ✅ GitHub Actions Workflow (Phase 2 Complete)

The constraint validation system is **fully integrated** into GitHub Actions CI/CD pipeline.

**Workflow File:** `.github/workflows/validate-constraints.yml`

**Triggers:**
- ✅ Push to `master`/`main` branches
- ✅ Pull requests to `master`/`main`
- ✅ Manual workflow dispatch
- ✅ Only runs when relevant files change (smart path filtering)

**Two Parallel Jobs:**

1. **`validate`** - Full constraint validation
   - Runs `scripts/validate_constraints.py --ci`
   - Uploads validation report as artifact (30-day retention)
   - Fails the build if any violations detected
   - Shows constraint count in success message

2. **`structural-tests`** - Structural tests only
   - Runs `pytest tests/structural/` separately
   - Better visibility of test failures
   - Independent of constraint validation

**Features:**
- 📊 Validation reports saved as artifacts
- 🚨 Clear error messages with violation details
- ✅ Success notices with constraint counts
- 🔄 Automatic on every push/PR
- ⚡ Cached Python dependencies for speed

**Status:** The workflow runs automatically on every commit to validate all 13 constraints.

### Local Pre-Commit Hooks (Optional)

Validate constraints **before committing** to catch violations early.

**Setup (one-time):**
```bash
cd "12 Polymarket Event Impact Trading"
./scripts/setup_git_hooks.sh
```

This installs pre-commit hooks that run:
1. Constraint validation (`scripts/validate_constraints.py`)
2. Structural tests (`pytest tests/structural/`)

**Usage:**
```bash
# Hooks run automatically on git commit
git commit -m "Your message"

# Run manually without committing
pre-commit run --all-files

# Skip hooks for emergency commits (use sparingly)
git commit --no-verify -m "Emergency fix"

# Uninstall hooks
pre-commit uninstall
```

**Benefits:**
- ⚡ Instant feedback (before pushing to CI)
- 🛡️ Prevents committing violations
- 💰 Saves CI minutes
- 🚀 Faster development cycle

**Note:** Pre-commit hooks are **optional** but recommended. The GitHub Actions workflow will catch violations even if hooks aren't installed locally.

## Troubleshooting

### Validation Fails on Missing Test File

**Error:**
```
❌ structural_test: FAILED
   Test file not found: tests/structural/test_new_constraint.py
```

**Solution:**
```bash
# Create the test file
touch tests/structural/test_new_constraint.py

# Or mark constraint as "planned" until test is ready
status: "planned"
```

### False Positive in Import Linter

**Error:**
```
❌ import_linter: FAILED
   Found forbidden pattern: market['bestBid']
   src/bots/trader.py:42 - # Example: market['bestBid']
```

**Solution:**
The linter skips comments automatically, but check if the pattern is actually in code. If it's a false positive, you can:

1. Refine the regex pattern in CONSTRAINTS.yml
2. Add to `allowed_files` list if legitimate usage

### Constraint Keeps Failing

**Debugging:**
```bash
# Run with verbose output
python scripts/validate_constraints.py --id ARCH-001

# Run the underlying test directly
pytest tests/structural/test_price_fetcher_constraint.py -v

# Check the validation report
cat data/constraint_validation_latest.json
```

## Metrics & Reporting

### Validation Report

After each run, a JSON report is saved to `data/constraint_validation_latest.json`:

```json
{
  "timestamp": "2026-02-24T10:30:00",
  "total_constraints": 13,
  "passed": 13,
  "warnings": 0,
  "violations": 0,
  "status": "PASS",
  "violation_details": [],
  "warning_details": []
}
```

### Telemetry Integration (Coming Soon)

The system will integrate with `src/monitoring/telemetry.py` to check runtime metrics:

```python
# Future: Check actual trading metrics
telemetry = TradeTelemetry()
metrics = telemetry.get_latest_metrics()

assert metrics['positions_without_sl_tp'] == 0
assert metrics['circuit_breaker_trips'] < threshold
```

## Next Steps

### Phase 2: Automated Validation
- [ ] Add to CI/CD pipeline
- [ ] Create GitHub Actions workflow
- [ ] Add pre-commit hooks

### Phase 3: Feedback Loops
- [ ] Integrate telemetry checks
- [ ] Auto-suggest constraints from failures
- [ ] Generate improvement checklist from system state

### Phase 4: Self-Improving System
- [ ] Pattern detection in failures
- [ ] Automatic constraint proposals
- [ ] Drift detection dashboards

## Questions?

See also:
- `IMPROVEMENT_CHECKLIST.md` - Current tasks and progress
- `MEMORY.md` - System architecture reference
- `IMPROVEMENT_ROADMAP.md` - Detailed implementation guide

---

**Last updated:** 2026-02-24
**Status:** Phase 1 Complete - 13 constraints enforced
