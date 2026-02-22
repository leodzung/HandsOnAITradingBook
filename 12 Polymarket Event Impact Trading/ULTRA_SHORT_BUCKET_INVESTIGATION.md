# Ultra-Short Bucket Investigation - Root Cause Analysis

**Date:** 2026-02-21
**Issue:** Ultra-short bucket (0-24h) finds 0 markets despite 44+ markets being available
**Status:** ✅ ROOT CAUSE IDENTIFIED

---

## Summary

The ultra-short bucket fails to discover markets due to a **timezone/off-by-one error** in the daily crypto event slug generation. The bot only fetches events for TODAY, which have already expired, instead of fetching TOMORROW's events.

---

## Investigation Timeline

### 1. Initial Hypothesis: Quality Filters Too Strict ❌
- **Tested:** Volume/liquidity requirements ($100/$50)
- **Result:** 44 markets pass these filters easily (avg: $28k volume, $18k liquidity)
- **Conclusion:** NOT the issue

### 2. Discovery Phase Analysis ✅
Traced through the full `discover_markets()` flow:

| Step | Input | Output | Removed |
|------|-------|--------|---------|
| 1. Fetch from /markets | - | 300 | - |
| 2. Fetch from crypto events | - | 86 | - |
| 3. Deduplication | 386 | 386 | 0 |
| 4. Filter active | 386 | 342 | 44 |
| 5. Filter time (0-24h) | 342 | 300 | 42 |
| 6. **Filter crypto** | **300** | **0** | **300** ❌ |

**Key Finding:** All 300 markets in the 0-24h range are Winter Olympics markets (NOT crypto).

### 3. Crypto Event Markets Investigation ✅

The 86 markets from crypto events are **long-term** (7500+ hours), filtered out by time-to-expiry:

| Event | Markets | Expiry | In Range (0-24h)? |
|-------|---------|--------|-------------------|
| bitcoin-hit-before-2027 | 28 | 313 days | ❌ No |
| ethereum-hit-before-2027 | 14 | 313 days | ❌ No |
| ethereum-above-on-february-21 | 11 | **EXPIRED** | ❌ No |
| bitcoin-above-on-february-21 | 11 | **EXPIRED** | ❌ No |
| solana-above-on-february-21 | 11 | **EXPIRED** | ❌ No |
| xrp-above-on-february-21 | 11 | **EXPIRED** | ❌ No |

**Key Finding:** Daily events for Feb 21 expired at 17:00 UTC (markets checked at 17:28 UTC).

### 4. Tomorrow's Markets Investigation ✅

Checked `ethereum-above-on-february-22`:

```
✓ Event exists
✓ 11 markets
✓ Expire in 23.5 hours
✓ Active: True
✓ Closed: False
```

**THIS IS THE MISSING DATA!** The ultra-short bucket should be finding tomorrow's daily events.

---

## Root Cause

### The Bug: `crypto_event_days_ahead=1`

In `trader_short_expiry.py` line 394:

```python
ultra_short_markets = MarketFilter.discover_markets(
    client=client,
    category=category,
    min_hours_to_expiry=config['ultra_short_hours'][0],
    max_hours_to_expiry=config['ultra_short_hours'][1],
    min_volume=config['min_volume']['ultra_short'],
    min_liquidity=config['min_liquidity']['ultra_short'],
    max_pages=3,
    include_crypto_events=True,
    crypto_event_days_ahead=1,  # ❌ BUG: Only fetches TODAY's events
    logger=logger
)
```

The `get_daily_crypto_event_slugs()` function (polymarket_client.py line 1450):

```python
def get_daily_crypto_event_slugs(days_ahead: int = 7) -> List[str]:
    slugs = []
    assets = ['ethereum', 'bitcoin', 'solana', 'xrp']

    for days in range(days_ahead):  # range(1) = [0] (TODAY ONLY!)
        date = datetime.now(timezone.utc) + timedelta(days=days)
        month = date.strftime('%B').lower()
        day = date.day

        for asset in assets:
            slug = f"{asset}-above-on-{month}-{day}"
            slugs.append(slug)

    return slugs
```

When `days_ahead=1`:
- `range(1)` = `[0]` (only iterates once with `days=0`)
- `timedelta(days=0)` = TODAY
- Generates slugs like `ethereum-above-on-february-21` (expired at 17:00 UTC)

**To include tomorrow's markets, we need `days_ahead=2` or higher.**

---

## Solution

### Option 1: Increase `crypto_event_days_ahead` for Ultra-Short ✅ RECOMMENDED

```python
# trader_short_expiry.py line 394
ultra_short_markets = MarketFilter.discover_markets(
    # ... other params ...
    crypto_event_days_ahead=2,  # ✅ Fetch today + tomorrow
    logger=logger
)
```

**Pros:**
- Minimal code change (1 line)
- Captures markets from today (if still active) AND tomorrow
- Aligns with 24h bucket range

**Cons:**
- None

### Option 2: Fix `range()` Logic in `get_daily_crypto_event_slugs()` ⚠️ BREAKING CHANGE

```python
# polymarket_client.py line 1468
for days in range(1, days_ahead + 1):  # Start from tomorrow (days=1)
```

**Pros:**
- More intuitive parameter behavior

**Cons:**
- **BREAKING CHANGE:** Short and medium buckets also call this function
- Requires updating all 3 bucket calls simultaneously

### Option 3: Start Daily Event Slugs from Tomorrow 🤔 ALTERNATIVE

```python
# polymarket_client.py line 1468
for days in range(1, days_ahead + 1):  # range(1, 3) = [1, 2] (tomorrow, day after)
```

Then update caller to account for offset.

**Pros:**
- Daily events that expire "today" are usually already closed by the time bots run

**Cons:**
- More complex to reason about

---

## Recommended Fix

**Use Option 1:** Change all three buckets to fetch `days_ahead + 1`:

```python
# Ultra-short (0-24h)
crypto_event_days_ahead=2,  # Fetch today + tomorrow

# Short (24-72h)
crypto_event_days_ahead=4,  # Fetch 3 days ahead (current: 3)

# Medium (72-168h)
crypto_event_days_ahead=8,  # Fetch 7 days ahead (current: 7)
```

This ensures:
- Ultra-short always has access to tomorrow's daily markets (23.5h expiry)
- Short bucket captures markets 2-3 days out
- Medium bucket captures markets 4-7 days out

---

## Expected Impact

After fix:
- **Ultra-short bucket:** 44+ markets (4 assets × 11 price levels each)
- **Short bucket:** 88+ markets (4 assets × 11 price levels × 2 days)
- **Medium bucket:** 132+ markets (4 assets × 11 price levels × 3-4 days)

---

## Testing

```bash
# Before fix
python3 diagnose_ultra_short.py
# Result: 0 markets

# After fix (change crypto_event_days_ahead=2)
python3 diagnose_ultra_short.py
# Expected: 44+ markets
```

---

## Related Files

- `src/bots/trader_short_expiry.py` - Lines 384-413 (market discovery)
- `src/core/polymarket_client.py` - Lines 1450-1477 (`get_daily_crypto_event_slugs()`)
- `config/config_short_expiry.json` - Discovery config

---

## Conclusion

✅ **Root cause:** `crypto_event_days_ahead=1` only fetches TODAY's events, which expire at 17:00 UTC
✅ **Solution:** Increase to `crypto_event_days_ahead=2` to include tomorrow's markets
✅ **Impact:** Ultra-short bucket will discover 44+ markets (vs current 0)

**Estimated fix time:** 5 minutes (1-line change + testing)
