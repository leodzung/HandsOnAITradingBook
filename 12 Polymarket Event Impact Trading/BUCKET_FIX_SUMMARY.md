# Bucket Extraction Fix - Short-Expiry Trader

## Issue Summary
**Date**: 2026-02-15
**Error**: `KeyError: 'unknown'` when checking positions in Short-Expiry Trader
**Affected Market**: `0xa9d14f354e7a44...` (and potentially all positions)

## Root Cause
The Short-Expiry Trader's `_check_positions()` method was incorrectly trying to extract the `bucket` value from the `metadata` JSON field instead of the dedicated `bucket` column in the database.

### The Problem
```python
# OLD CODE (INCORRECT)
metadata = pos.get('metadata', {})
bucket = metadata.get('bucket', 'unknown') if isinstance(metadata, dict) else 'unknown'
```

This caused:
1. `bucket` would default to `'unknown'` because it's not in the metadata JSON
2. When `risk_manager.should_exit()` tried to access `config['risk_management']['stop_loss_pct']['unknown']`, it raised a `KeyError`
3. The error was caught and sent to Telegram as "Error: 'unknown'"

### Database Schema
The actual database has TWO places where bucket information is stored:
- **`bucket` column** (TEXT) - Contains `'ultra_short'`, `'short'`, or `'medium'`
- **`metadata` JSON** - Contains `features_json` with nested data, but NOT a top-level `bucket` key

## Fix Applied

### 1. Fixed Bucket Extraction in `trader_short_expiry.py` (line 697-702)
```python
# NEW CODE (CORRECT)
# Get bucket from column (V2 stores it as a column, not in metadata)
bucket = pos.get('bucket')
if not bucket:
    # Fallback to metadata for old positions
    metadata = pos.get('metadata', {})
    bucket = metadata.get('bucket', 'short') if isinstance(metadata, dict) else 'short'
```

This change:
- First tries to read from the `bucket` column (where it actually exists)
- Falls back to metadata for backward compatibility with old positions
- Uses `'short'` as the final fallback instead of `'unknown'` to prevent KeyError

### 2. Fixed Schema in `position_manager_v2.py`
Added `bucket TEXT` column to:
- CREATE TABLE statement (line 86)
- Migration column list (line 232)
- V1→V2 migration schema (line 147)

This ensures the schema matches the actual database structure and future databases will be created correctly.

## Testing
Created two test scripts to verify the fix:

### Test 1: Bucket Extraction (`test_bucket_fix.py`)
- Verified all 7 open positions correctly extract bucket as `'short'`
- Confirmed the problematic market `0xa9d14f354e7a44...` now works

### Test 2: Risk Manager (`test_risk_manager_fix.py`)
- Tested `risk_manager.should_exit()` with all 7 positions
- All positions passed without KeyError
- Risk manager correctly evaluates stop-loss/take-profit thresholds

## Results
✅ **FIXED**: All positions now correctly extract bucket value
✅ **TESTED**: Risk manager processes all positions without errors
✅ **VERIFIED**: No more `'unknown'` KeyError in position checks

## Impact
- **Immediate**: Eliminates the recurring Telegram error alerts
- **Stability**: Prevents position checks from failing
- **Correctness**: Ensures proper risk management with correct bucket-specific thresholds

## Files Modified
1. `src/bots/trader_short_expiry.py` - Fixed bucket extraction logic
2. `src/core/position_manager_v2.py` - Added `bucket` column to schema and migration

## Recommendation
Monitor the next few position check cycles to confirm the error no longer appears in logs or Telegram alerts.
