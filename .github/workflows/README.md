# GitHub Actions Workflows

This directory contains CI/CD workflows for the Polymarket Trading System.

## Active Workflows

### `validate-constraints.yml` - Constraint Validation

**Purpose:** Automatically validates system constraints on every commit/PR.

**Triggers:**
- Push to `master`/`main` branches
- Pull requests to `master`/`main`
- Manual dispatch (workflow_dispatch)

**Smart Path Filtering:**
Only runs when these files change:
- `12 Polymarket Event Impact Trading/src/**` - Source code
- `12 Polymarket Event Impact Trading/CONSTRAINTS.yml` - Constraint definitions
- `12 Polymarket Event Impact Trading/tests/**` - Tests
- `12 Polymarket Event Impact Trading/scripts/validate_constraints.py` - Validation script

**Jobs:**

1. **`validate`** (Required)
   - Runs full constraint validation system
   - Validates 13 enforced constraints across 4 categories:
     - Architecture (4): PriceFetcher, PositionManager V2, common features, WebSocket
     - Risk Management (3): SL/TP, circuit breaker, slippage estimation
     - Model Quality (3): Cross-validation, drift detection, label correctness
     - Operations (2): Health monitoring, position persistence
   - Generates validation report
   - Uploads report as artifact (30-day retention)
   - **Fails build** if violations detected

2. **`structural-tests`** (Optional)
   - Runs structural tests independently
   - Provides granular test results
   - Better visibility for debugging failures

**Artifacts:**
- `constraint-validation-report` - JSON report with full validation details

**Exit Codes:**
- `0` - All constraints satisfied ✅
- `1` - Violations detected ❌

## Viewing Results

### In GitHub UI

1. Go to **Actions** tab in repository
2. Select the workflow run
3. View job logs for details
4. Download validation report from **Artifacts** section

### Example Success Output
```
🔍 Validating system constraints...
✅ ALL CONSTRAINTS SATISFIED
Total constraints validated: 13
```

### Example Failure Output
```
🔍 Validating system constraints...
❌ VALIDATION FAILED

[CRITICAL] ARCH-002: PositionManager V2 is single source for position data
  Found direct SQLite access: src/bots/trader_short_expiry.py:26
```

## Local Development

Run validation locally before pushing:

```bash
cd "12 Polymarket Event Impact Trading"

# Full validation
python scripts/validate_constraints.py

# CI mode (same as GitHub Actions)
python scripts/validate_constraints.py --ci

# Specific constraint
python scripts/validate_constraints.py --id ARCH-001

# Install pre-commit hooks (optional)
./scripts/setup_git_hooks.sh
```

## Maintenance

### Adding New Constraints

1. Add constraint to `CONSTRAINTS.yml`
2. Create validation tests (if needed)
3. Workflow automatically picks up new constraints

### Modifying Workflow

1. Edit `.github/workflows/validate-constraints.yml`
2. Test locally with `act` (GitHub Actions local runner)
3. Push changes - workflow validates itself!

### Troubleshooting

**Workflow not triggering:**
- Check path filters match changed files
- Verify branch name (master vs main)

**Build failing unexpectedly:**
- Download validation report artifact
- Review violation details
- Run `scripts/validate_constraints.py` locally

**Need to skip validation (emergency):**
- Not recommended, but possible:
- Add `[skip ci]` to commit message
- Note: This bypasses all safety checks!

## Related Files

- `12 Polymarket Event Impact Trading/CONSTRAINTS.yml` - Constraint definitions
- `12 Polymarket Event Impact Trading/scripts/validate_constraints.py` - Validation runner
- `12 Polymarket Event Impact Trading/CONSTRAINT_VALIDATION_GUIDE.md` - User guide
- `.pre-commit-config.yaml` - Local pre-commit hooks

## Philosophy

This workflow embodies **harness engineering** principles:
- Constraints are executable, not just documented
- Violations prevent merging, not just warned about
- System is self-validating and self-documenting
- Regressions are caught automatically

The CI pipeline ensures that **architectural invariants are maintained** across all code changes, making the trading system more robust and maintainable.
