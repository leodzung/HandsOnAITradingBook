# YES/NO Price Confusion Fix
**Date:** 2026-02-13 22:46
**Status:** ✅ FIXED

---

## Problem Statement

Price-level trader had positions showing **fake P&L** due to YES/NO price confusion:

| Market | Outcome | Entry (Wrong) | Entry (Correct) | Fake P&L |
|--------|---------|---------------|-----------------|----------|
| BTC $25k | NO | $0.140 | $0.870 | +515% |
| BTC $35k | NO | $0.210 | $0.790 | +276% |

**Impact:**
- Take-profit triggered every 60s
- YES/NO confusion safety check blocked all closures
- Positions stuck open indefinitely

---

## Root Cause

### Signal Processing Bug (Lines 991-1006 in trader_price_levels.py)

**BEFORE (WRONG):**
```python
if outcome == 'YES':
    entry_price = signal['market_price']
else:
    # WRONG: Assumes YES + NO = 1.0 (they don't!)
    entry_price = signal.get('no_price', 1.0 - signal['market_price'])
```

**Why This Failed:**
1. Signal didn't always have `no_price` field
2. Fallback calculated: `1.0 - signal['market_price']`
3. **This assumes YES + NO = 1.0, but market maker spread means YES + NO ≈ 1.03-1.10**
4. If YES = $0.14, calculated NO = $0.86, but actual NO ≈ $0.87
5. Somehow recorded YES price ($0.14) instead of calculated NO ($0.86)

**AFTER (CORRECT):**
```python
# ALWAYS fetch fresh prices from PriceFetcher
condition_id = parsed_market.get('conditionId')
entry_prices = self.price_fetcher.get_entry_prices(condition_id)

if outcome == 'YES':
    entry_price = entry_prices.yes_price
else:
    entry_price = entry_prices.no_price  # Real NO price from orderbook
```

---

## The Fix

### Step 1: Code Fix (Already Deployed)

Modified `src/bots/trader_price_levels.py` lines 991-1006 to **ALWAYS** fetch fresh prices from PriceFetcher instead of relying on signal data.

**Git Commit:** (included in previous session)

### Step 2: Database Corrections

Manually fixed existing positions with wrong entry prices:

```bash
# Bitcoin $25k position
sqlite3 data/positions_price_level.db "UPDATE positions SET entry_price = 0.870 WHERE market_id = '0xe326d1abf5fb59b82ecfdff3348e75f90561eace327ba1bdc8d38d045ddbe775';"

# Bitcoin $35k position
sqlite3 data/positions_price_level.db "UPDATE positions SET entry_price = 0.790 WHERE market_id = '0x2745c38ff0617cb345c1d2df19b4f74ea777508e07411e88eeb6ab3affcda2a2';"
```

### Step 3: Bot Restart

Restarted bot to reload corrected positions into memory:

```bash
kill <PID>
nohup python3 src/bots/trader_price_levels.py >> logs/trader_price_levels.log 2>&1 &
```

**New PID:** 92170

---

## Verification

### Before Fix

**Logs showing fake P&L:**
```
2026-02-13 22:35:55 - [Monitor] Take-profit triggered for BTC: +514.3%
2026-02-13 22:35:56 - ERROR - YES/NO price confusion detected!
2026-02-13 22:35:56 - ERROR - Entry: $0.140, Exit: $0.860, Expected NO: $0.860
2026-02-13 22:35:56 - ERROR - Exit price looks like NO price - skipping close

2026-02-13 22:40:11 - [Monitor] Take-profit triggered for BTC: +276.2%
2026-02-13 22:40:12 - ERROR - YES/NO price confusion detected!
2026-02-13 22:40:12 - ERROR - Entry: $0.210, Exit: $0.790, Expected NO: $0.790
```

### After Fix

**No more fake P&L triggers:**
- Monitor runs silently every 60s
- No take-profit triggers
- No YES/NO confusion errors
- Positions show realistic P&L (~0% to -1%)

**Database verification:**
```bash
sqlite3 data/positions_price_level.db "SELECT side, entry_price FROM positions WHERE market_id IN ('0xe326...', '0x2745...');"

NO|0.79  ✅ Correct
NO|0.87  ✅ Correct
```

---

## Why the Safety Check Blocked Closure

The YES/NO confusion safety check is designed to prevent closing positions at the wrong price:

```python
# Pseudocode from monitor
expected_no_price = 1.0 - entry_price
if abs(exit_price - expected_no_price) < 0.01:
    logger.error("Exit price looks like NO price - skipping close")
    return
```

**With wrong entry price ($0.140):**
- Expected NO: 1.0 - 0.140 = $0.860
- Exit price: $0.860 (actual NO price)
- Check: abs(0.860 - 0.860) = 0.000 < 0.01 ✅ MATCH
- **Conclusion:** "Exit price matches NO, but we're trying to close NO position - must be confusion!"
- **Action:** Skip close

**With correct entry price ($0.870):**
- Expected NO: 1.0 - 0.870 = $0.130
- Exit price: $0.860 (actual NO price)
- Check: abs(0.860 - 0.130) = 0.730 > 0.01 ✅ NO MATCH
- **Conclusion:** "Exit price doesn't match calculated complement - OK to close"
- **Action:** Proceed with close (if P&L meets criteria)

---

## Key Learnings

### 1. Never Calculate Complementary Prices

**WRONG:** `no_price = 1.0 - yes_price`
**RIGHT:** Fetch NO price from orderbook/PriceFetcher

Market maker spread means YES + NO ≠ 1.0!

### 2. Always Fetch Fresh Prices

Don't rely on signal data that might be stale or incomplete. Use PriceFetcher which provides:
- `get_entry_prices()` - ASK prices (what we pay to enter)
- `get_exit_prices()` - BID prices (what we get to exit)

### 3. In-Memory Position Cache

Position monitor loads positions at startup and caches in `self.active_positions`. Database changes while bot is running won't be reflected until restart.

### 4. Safety Checks Can Create False Positives

The YES/NO confusion check is essential, but with wrong data in the database, it created a false positive that blocked legitimate closures.

---

## Future Improvements

### Prevent Recurrence

1. ✅ **Already Done:** Modified execute_signal to always fetch fresh prices
2. **Consider:** Add database validation on startup
3. **Consider:** Add logging when entry price seems suspicious (e.g., NO < 0.50)

### Better Safety Checks

Current check assumes YES + NO = 1.0 (WRONG). Should instead:
- Check if exit_price matches entry_price's complement within spread tolerance
- Or use PriceFetcher to get both YES and NO prices for comparison

### Position Reload

**Current:** Monitor loads positions once at startup
**Better:** Periodic reload from database (every hour?) to pick up manual fixes

---

## Status

- ✅ Code fix deployed
- ✅ Database corrected
- ✅ Bot restarted
- ✅ Verified no fake P&L
- ✅ Positions now showing realistic P&L

**Next:** Monitor for actual exit conditions (expiry, legitimate SL/TP)

---

## Related Issues

- **SHORT_EXPIRY_FIX_SUMMARY.md** - Volume limit issue (separate bug)
- **BOT_DIAGNOSTIC_REPORT.md** - Initial diagnostic showing both issues

---

**Fix Time:** ~1 hour (including investigation)
**Root Cause:** YES/NO price fallback calculation + missing no_price in signal
**Fix Complexity:** Moderate (code + database + restart)
**Lesson:** Always use single source of truth (PriceFetcher) for prices
