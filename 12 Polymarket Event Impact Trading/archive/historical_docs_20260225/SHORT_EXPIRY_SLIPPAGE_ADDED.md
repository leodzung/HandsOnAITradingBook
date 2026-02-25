# Short-Expiry Bot - Slippage Estimation Added

## Summary

Added comprehensive slippage estimation to the short-expiry bot with **bucket-specific limits** tailored to each time horizon's urgency level.

---

## Changes Made

### 1. Config Update (`config/config_short_expiry.json`)

**Added new `slippage_estimation` section:**

```json
{
  "slippage_estimation": {
    "enabled": true,
    "max_slippage_bps": {
      "ultra_short": 3000,    // 30% - Most urgent (0-24h)
      "short": 2000,          // 20% - Moderate urgency (1-3d)
      "medium": 1500          // 15% - Less urgent (3-7d)
    },
    "max_slippage_dollars": {
      "ultra_short": 15.0,    // Smaller positions ($10-50)
      "short": 20.0,
      "medium": 25.0
    },
    "orderbook_staleness_seconds": 10,
    "depth_buffer_pct": 0.10,
    "volatility_adjustment": false,   // Disabled (like price-level bot)
    "volume_limit_pct": 0.02,         // 2% of daily volume
    "warn_threshold_bps": {
      "ultra_short": 2000,    // 20% warning
      "short": 1500,          // 15% warning
      "medium": 1000          // 10% warning
    }
  }
}
```

**Removed obsolete setting:**
- Deleted `risk_management.max_slippage_bps: 150` (not being used)

### 2. Code Update (`src/bots/trader_short_expiry.py`)

**Added import:**
```python
from core.slippage_estimator import SlippageEstimator
```

**Added initialization (line ~313):**
```python
# Initialize slippage estimator
self.slippage_estimator = SlippageEstimator(
    config=self.config.get('slippage_estimation', {})
)
```

**Added slippage check in `_execute_trade()` (line ~660):**
```python
# Estimate slippage before executing
if slippage_config.get('enabled', True):
    # Get bucket-specific limits
    max_slippage_bps = slippage_config['max_slippage_bps'][bucket]

    # Estimate slippage
    result = estimator.estimate(market, side='BUY', size_usd=size, client=self.client)

    # Reject if excessive
    if not result['can_trade']:
        logger.warning(f"TRADE REJECTED - Slippage: {result['reason']}")
        return  # Don't execute

    # Warn if high but acceptable
    if slippage_bps > warn_threshold_bps:
        logger.warning(f"HIGH SLIPPAGE WARNING: {slippage_bps} bps")
```

---

## Why Bucket-Specific Limits?

### Ultra-Short (0-24h): 3,000 bps (30%)

**Highest urgency** - events resolve within hours:
- ✅ Accept higher slippage to capture time-sensitive opportunities
- ✅ Positions typically smaller ($10-50)
- ✅ Time decay dominates other factors
- ✅ Can't wait for better liquidity

**Example**: Bitcoin price at end of day, news-driven events

### Short (1-3d): 2,000 bps (20%)

**Moderate urgency** - have 1-3 days:
- ✅ Balance between urgency and execution quality
- ✅ Medium position sizes ($20-75)
- ✅ Can wait slightly for better prices
- ✅ Momentum strategies benefit from speed

**Example**: Weekend crypto events, short-term predictions

### Medium (3-7d): 1,500 bps (15%)

**Lower urgency** - have up to a week:
- ✅ More selective on execution quality
- ✅ Larger position sizes ($25-100)
- ✅ Can wait for optimal entry
- ✅ Fundamental analysis-driven

**Example**: Weekly crypto price movements, 7-day events

---

## Comparison with Other Bots

| Bot | Slippage Limit | Rationale |
|-----|---------------|-----------|
| **Price-Level** | 6,000 bps (60%) | Long-dated (321d), very thin books |
| **Event Trader** | 100 bps (1%) | ❌ TOO STRICT (needs update) |
| **Short-Expiry (ultra)** | 3,000 bps (30%) | 0-24h urgency |
| **Short-Expiry (short)** | 2,000 bps (20%) | 1-3d urgency |
| **Short-Expiry (medium)** | 1,500 bps (15%) | 3-7d urgency |

**Progression makes sense:**
- Longer time horizon → can be more selective → lower slippage limit
- Shorter time horizon → must act fast → higher slippage acceptable

---

## Expected Behavior

### Before: No Slippage Protection ❌

```
2026-02-13 10:00:00 - Signal: BUY ultra_short market
2026-02-13 10:00:01 - Opening $50 position @ $0.65
✅ Trade executed (no checks)
```

**Risk**: Could execute on markets with:
- Empty orderbooks
- Extreme slippage (100%+)
- No liquidity

### After: Slippage Protection ✅

**Scenario 1: Good liquidity**
```
2026-02-13 10:00:00 - Signal: BUY ultra_short market
2026-02-13 10:00:01 - Estimating slippage for $50 order...
2026-02-13 10:00:01 - Slippage: 1,200 bps (12%) on $6.00
2026-02-13 10:00:01 - ✅ Slippage check passed (< 3,000 bps limit)
2026-02-13 10:00:02 - Opening $50 position @ $0.65
```

**Scenario 2: High but acceptable slippage**
```
2026-02-13 10:00:00 - Signal: BUY short market
2026-02-13 10:00:01 - Estimating slippage for $75 order...
2026-02-13 10:00:01 - Slippage: 1,800 bps (18%) on $13.50
2026-02-13 10:00:01 - ⚠️  HIGH SLIPPAGE WARNING: 1,800 bps (> 1,500 bps threshold)
2026-02-13 10:00:02 - ✅ ACCEPTED: Within 2,000 bps limit
2026-02-13 10:00:03 - Opening $75 position @ $0.42
```

**Scenario 3: Excessive slippage - REJECTED**
```
2026-02-13 10:00:00 - Signal: BUY medium market
2026-02-13 10:00:01 - Estimating slippage for $100 order...
2026-02-13 10:00:01 - Slippage: 2,100 bps (21%) on $21.00
2026-02-13 10:00:01 - ❌ TRADE REJECTED - Slippage
2026-02-13 10:00:01 - Reason: Slippage 2,100 bps exceeds limit 1,500 bps
2026-02-13 10:00:01 - Market: [Question...]
```

---

## Safety Features Retained

All standard SlippageEstimator protections apply:

✅ **Volume limits**: Max 2% of daily volume
✅ **Orderbook depth checks**: Rejects empty books
✅ **VWAP simulation**: Walks through price levels
✅ **Safety buffers**: 10% base buffer + thin book penalty
✅ **Spread penalty**: DISABLED (volatility_adjustment: false)

---

## Testing Checklist

Before deploying to production:

- [ ] Verify config loads correctly
- [ ] Test with real market data
- [ ] Check slippage logs show correct bucket limits
- [ ] Confirm rejections happen at correct thresholds
- [ ] Monitor warning messages for high slippage
- [ ] Validate trades execute when slippage is acceptable

---

## How to Test

### 1. Start the Bot

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"
nohup python3 src/bots/trader_short_expiry.py >> trading_short_expiry.out 2>&1 &
```

### 2. Monitor Logs

```bash
# Watch all activity
tail -f trading_short_expiry.out

# Filter for slippage checks
grep -E "Slippage|REJECTED|WARNING" trading_short_expiry.out | tail -20

# Check trades by bucket
grep "TRADE OPENED" trading_short_expiry.out | grep "ultra_short"
grep "TRADE OPENED" trading_short_expiry.out | grep "short"
grep "TRADE OPENED" trading_short_expiry.out | grep "medium"
```

### 3. Verify Bucket-Specific Limits

**Expected rejections by bucket:**

```bash
# Ultra-short: Should reject at 3,000+ bps
grep "ultra_short.*REJECTED" trading_short_expiry.out

# Short: Should reject at 2,000+ bps
grep "short.*REJECTED" trading_short_expiry.out

# Medium: Should reject at 1,500+ bps
grep "medium.*REJECTED" trading_short_expiry.out
```

---

## Configuration Options

### Disable Slippage Checks (Not Recommended)

```json
{
  "slippage_estimation": {
    "enabled": false
  }
}
```

### Adjust Bucket Limits

More conservative (tighter limits):
```json
{
  "max_slippage_bps": {
    "ultra_short": 2000,  // 20%
    "short": 1500,        // 15%
    "medium": 1000        // 10%
  }
}
```

More aggressive (looser limits):
```json
{
  "max_slippage_bps": {
    "ultra_short": 5000,  // 50%
    "short": 3000,        // 30%
    "medium": 2000        // 20%
  }
}
```

---

## Monitoring Recommendations

### Telegram Alerts

No changes needed - existing trade notifications will continue.

**If trade is rejected**, no Telegram message is sent (by design).

**To add rejection alerts**, modify `_execute_trade()`:

```python
if not result['can_trade']:
    logger.warning(f"TRADE REJECTED - Slippage: {result['reason']}")

    # Optional: Send Telegram alert
    self.telegram.send_message(
        f"🚫 <b>TRADE REJECTED - Slippage</b>\n\n"
        f"<b>Bucket:</b> {bucket}\n"
        f"<b>Reason:</b> {result['reason']}\n"
        f"<b>Slippage:</b> {result['slippage_bps']:.0f} bps\n"
        f"<b>Limit:</b> {max_slippage_bps} bps\n\n"
        f"<i>{market.get('question', '')[:80]}</i>"
    )

    return
```

### Slippage Metrics

Track slippage distribution:

```bash
# Extract slippage values
grep "Slippage:" trading_short_expiry.out | \
  awk '{print $NF}' | \
  sed 's/bps//' | \
  sort -n

# Count rejections by reason
grep "REJECTED" trading_short_expiry.out | \
  cut -d'|' -f3 | \
  sort | uniq -c
```

---

## Summary

✅ **Added**: Comprehensive slippage estimation with bucket-specific limits
✅ **Config**: 3 tiers (30%, 20%, 15%) based on time urgency
✅ **Protection**: Volume limits, orderbook checks, safety buffers
✅ **Flexibility**: Easy to adjust per bucket or disable entirely

**Next step**: Restart the short-expiry bot to enable slippage protection.
