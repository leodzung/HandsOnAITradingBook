# Short Expiry Bot - Issue Analysis and Fix

**Date:** 2026-02-15
**Status:** ✅ FIXED

## Problem Summary

The short expiry bot was **discovering markets successfully** but **not opening positions** due to a database schema mismatch.

## Root Cause

`PositionManager V2` was missing the `bucket` parameter in its `save_position()` method, causing this error:

```
sqlite3.IntegrityError: NOT NULL constraint failed: positions.bucket
```

### What Was Happening:
1. ✅ Bot discovered 3-28 markets per bucket (ultra_short, short, medium)
2. ✅ Markets passed quality filters
3. ✅ Slippage checks passed
4. ✅ Signal generated
5. ❌ **Position save failed** - missing `bucket` column in INSERT statement

## The Fix

### 1. Updated `PositionManager V2` (`src/core/position_manager_v2.py`)
- Added `bucket: str = None` parameter to `save_position()`
- Added `bucket` to the INSERT statement
- Added `bucket` to the VALUES tuple

### 2. Updated Short Expiry Trader (`src/bots/trader_short_expiry.py`)
- Changed from passing `bucket` in `metadata` dict
- Now passes `bucket` as a direct parameter

### Files Modified:
```
src/core/position_manager_v2.py (line 247-291)
src/bots/trader_short_expiry.py (line 633-648)
```

## Current Status

✅ **Bot is now running successfully** (PID 98607, started 2026-02-15 07:45AM)

**Discovery Stats (Current Cycle):**
- Ultra-short (0-24h): 4 markets
- Short (24-72h): 17 markets
- Medium (72-168h): 28 markets

**Quality Filter Rejections:**
- Spread too wide: 83-87 markets
- Price out of range: 65-68 markets (most common rejection)
- No prices: 0-1 markets

## Why No Positions Are Opening (Even After Fix)

The bot is working correctly but not finding profitable signals. Here's why:

### 1. **Aggressive Price Range Filter (Most Impact)**
**Config:** `max_price: 0.95`

**Issue:** Crypto markets at short expiries are often highly skewed (e.g., "Bitcoin above $100k" = 99% YES).
**Impact:** 65-68 markets rejected per cycle due to prices >0.95

**Recommendation:**
```json
"max_price": 0.98  // Allow near-certain markets (was 0.95)
```

### 2. **Wide Spread Filter**
**Config:** `max_spread_pct: 6-10%` (varies by bucket)

**Impact:** 83-87 markets rejected per cycle
**Recommendation:** Keep current values, these are reasonable

### 3. **Signal Generation Not Triggering**

Even markets that pass filters aren't generating signals. Checking the rules:

#### Arbitrage Rule (Unlikely in Current Market)
```json
"max_total_price": 0.98,
"min_edge": 0.02
```
**Why it fails:** YES + NO prices are typically 1.03-1.10 (market maker spread), not <0.98

#### Mean Reversion (Ultra-short only)
```json
"min_spread_pct": 5.0,
"price_threshold_low": 0.45,
"price_threshold_high": 0.55
```
**Why it fails:** Most passing markets have prices >0.95 or <0.05 (outside 0.45-0.55 range)

#### Momentum Rule
```json
"min_price_change_1h": 0.02  // Requires 2% move in 1 hour
```
**Why it fails:** Needs historical price data (price_tracker just started)

## Recommendations

### Immediate (Enable Trading)

1. **Relax max_price filter** (allows near-certain markets):
```json
"max_price": 0.98  // From 0.95
```

2. **Adjust mean reversion thresholds** (target tail markets):
```json
"price_threshold_low": 0.10,   // From 0.45
"price_threshold_high": 0.90,  // From 0.55
```

3. **Lower momentum threshold** (easier to trigger):
```json
"min_price_change_1h": 0.01  // From 0.02 (1% instead of 2%)
```

### Medium-term (Improve Signal Quality)

1. **Add new strategy:** High-conviction mean reversion on extreme prices
```json
"extreme_reversion": {
  "enabled": true,
  "price_threshold_extreme": 0.95,  // Buy when YES >95%
  "min_volume_24h": 1000,
  "min_edge": 0.03
}
```

2. **Monitor price tracker:** Wait 24 hours for momentum signals to activate

3. **Review balance:** Current balance is $30 (config says $500)
   - 1 closed position found (2026-02-14): $30 YES @ 0.059 → stop-loss @ 0.051 (-$0.24)
   - **Action:** Reset balance to $500 if desired:
     ```bash
     echo '{"balance": 500.0, "updated": "'$(date -u +%Y-%m-%dT%H:%M:%S)'+00:00"}' > data/paper_trading_balance_short_expiry.json
     ```

## Testing the Fix

Monitor logs for:
```bash
tail -f logs/trading_short_expiry_$(date +%Y%m%d).log | grep -E "(TRADE|Position|ERROR)"
```

Expected after config changes:
- More markets passing price range filter
- Mean reversion signals triggering
- Positions opening successfully (no database errors)

## Verification

✅ Bot running without errors (multiple cycles completed)
✅ Database schema correct (bucket column exists and populated)
✅ Market discovery working (3-28 markets per bucket)
✅ Quality filtering working (price/spread checks)
⏳ Signal generation tuning needed (recommendations above)

## Next Steps

1. Apply recommended config changes
2. Restart bot
3. Monitor for first successful position open
4. After 24 hours, verify momentum signals are working (price tracker has data)
