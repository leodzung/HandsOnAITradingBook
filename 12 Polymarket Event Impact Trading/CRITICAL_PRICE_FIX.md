# Critical Price Validation Fix - Feb 13, 2026

## Problem Discovered

The price filter ($0.90 max) was being bypassed, allowing entries at $0.99!

### Root Cause

**TradeExecutor validation order bug:**

1. **Stage 1 - Price Validation:** Checked signal price ($0.82) ✅ PASSED
2. **Stage 2 - Slippage Estimation:** Fetched CLOB orderbook, got VWAP $0.99
3. **Bug:** Overwrote `entry_price` to $0.99 WITHOUT re-validating!
4. **Stage 3 - Execute:** Used $0.99 (bypassed filter!)

### Evidence

From logs:
```
Market Price: YES=$0.180, NO=$0.820  <-- Signal price
...
Slippage estimate: 2690 bps
...
NO Price: $0.990  <-- Actual execution price (NOT validated!)
✓ Saved position: ... @ $0.990
```

Positions entered after "fix":
- 8 positions at $0.99 or $0.999 between 10:33-10:59 AM

---

## Fixes Applied

### 1. Validate Recommended Price (TradeExecutor)
**File:** `src/core/trade_executor.py`

**Before:**
```python
if slippage_check.get('recommended_price'):
    request.entry_price = slippage_check['recommended_price']  # NO VALIDATION!
```

**After:**
```python
if slippage_check.get('recommended_price'):
    recommended_price = slippage_check['recommended_price']

    # Validate BEFORE accepting
    if recommended_price > self.max_entry_price:
        return TradeResult(
            success=False,
            rejection_stage='price',
            rejection_reason=f"Recommended price ${recommended_price:.3f} exceeds max"
        )

    request.entry_price = recommended_price
```

**Impact:** Now validates price AFTER slippage estimation updates it!

---

### 2. Use CLOB Prices Exclusively (All Bots)

**Problem:** Bots were still using Gamma API `outcomePrices` as primary source

**Files Fixed:**
- `src/bots/trader_price_levels.py` - Removed `outcomePrices` usage
- `src/bots/trader.py` - Removed `get_price_from_market()` Gamma fallback

**Before (trader_price_levels.py):**
```python
# Get prices from Gamma API (outcomePrices) - consistent source
outcome_prices = orig_market.get('outcomePrices', '[]')
...
# Fallback to CLOB
if market_price is None:
    prices = self.client.get_market_prices(condition_id, side='BUY')
```

**After:**
```python
# Get prices EXCLUSIVELY from CLOB API (not Gamma)
prices = self.client.get_market_prices(condition_id, side='BUY')
market_price = prices.get('yes')  # YES ask price
no_price = prices.get('no')        # NO ask price
```

**Impact:**
- Always uses actual CLOB orderbook ask prices
- No more inference (`1.0 - YES`)
- Consistent with TradeExecutor validation

---

### 3. Fetch NO Price Independently

**Problem:** Was calculating `NO = 1.0 - YES` instead of fetching directly

**Before:**
```python
entry_price = signal.get('no_price', 1.0 - signal['market_price'])
```

**After:**
Uses `get_market_prices()` which fetches both YES and NO from separate orderbooks:
```python
prices = self.client.get_market_prices(condition_id, side='BUY')
yes_price = prices.get('yes')  # From YES orderbook
no_price = prices.get('no')    # From NO orderbook (NOT inferred!)
```

**Impact:** NO prices are real orderbook prices, not calculated

---

## Test Plan

1. **Price Validation Test:**
   - Signal at $0.82, CLOB returns $0.99
   - Expected: REJECT with "Recommended price $0.99 exceeds max $0.90"

2. **NO Price Test:**
   - Market: YES ask = $0.01, NO ask = $0.99
   - Expected: Both prices fetched independently, NO = $0.99 rejected

3. **CLOB-Only Test:**
   - Verify no Gamma API prices used
   - Check logs for "CLOB" mentions, not "Gamma" or "outcomePrices"

---

## Expected Behavior

### Scenario: Bitcoin dip to $30k

**Signal Generation:**
```
CLOB: YES ask = $0.18, NO ask = $0.82
Signal: BUY NO at $0.82
```

**Trade Execution:**
```
Stage 1 - Price check: $0.82 < $0.90 ✅ PASS
Stage 2 - Slippage: Fetch orderbook, VWAP = $0.99
Stage 2b - Validate recommended: $0.99 > $0.90 ❌ REJECT
Result: Trade REJECTED (recommended price too high)
```

**Logs Should Show:**
```
⚠️ Trade rejected - Recommended price too high |
   NO @ $0.990 | Max: $0.90 |
   Market: Will Bitcoin dip to $30,000...
```

---

## Files Modified

1. `src/core/trade_executor.py`
   - Added recommended_price validation

2. `src/bots/trader_price_levels.py`
   - Removed Gamma API `outcomePrices` usage
   - Use CLOB exclusively for price fetching

3. `src/bots/trader.py`
   - Removed `get_price_from_market()` Gamma fallback
   - Use CLOB exclusively

---

## Verification Commands

```bash
# Check for price rejections
grep "Recommended price too high" trading_price_levels.out

# Check for Gamma API usage (should be NONE)
grep -i "gamma\|outcomePrices" trading_price_levels.out

# Check recent positions (should see NO entries at $0.99+)
sqlite3 data/positions_price_level.db \
  "SELECT entry_price, entry_time FROM positions
   WHERE entry_time > '2026-02-13T12:05:00'
   ORDER BY entry_time DESC;"
```

---

## Status

- ✅ TradeExecutor validates recommended_price
- ✅ All bots use CLOB exclusively
- ✅ NO prices fetched independently (not inferred)
- ⏳ Testing in progress (bot restarted at 12:05 PM)

**Next:** Monitor logs for rejection messages and verify no $0.99 entries

---

## User Requests

1. ✅ Fix $0.99 entries
2. ✅ Get NO price directly (not inferred)
3. ✅ Remove all Gamma API price usage
4. ⏭️ **TODO:** Centralize price fetching logic for all bots
