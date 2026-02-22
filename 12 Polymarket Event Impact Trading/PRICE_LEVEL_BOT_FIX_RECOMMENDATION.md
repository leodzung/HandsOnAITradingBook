# Price Level Bot - Fix Recommendation

## Problem Summary

The bot uses **inconsistent price sources** causing immediate stop-loss triggers:

| Operation | Price Source | Example Price |
|-----------|--------------|---------------|
| Signal Generation | Gamma API (`outcomePrices`) | $0.685 |
| Trade Execution | CLOB API (`orderbook` → VWAP) | $0.999 |
| Position Monitoring | Gamma API (`outcomePrices`) | $0.685 |

**Result**: Entered at $0.999, monitored at $0.685 → 31% loss → stop loss triggered!

---

## Root Cause

### Gamma API vs CLOB API Price Divergence

**Gamma API** (`/markets` endpoint):
```json
{
  "outcomePrices": ["0.685", "0.315"]
}
```
- Mid-market **estimates**
- Updated periodically (not real-time)
- Represents aggregate market sentiment
- **NOT executable prices**

**CLOB API** (`/book` endpoint):
```json
{
  "asks": [{"price": "0.999", "size": "100"}],
  "bids": [{"price": "0.001", "size": "500"}]
}
```
- Actual limit orders on the book
- Real-time executable prices
- Can be extremely wide for thin markets
- **Actual trading prices**

### Why They Diverge

For thin/illiquid markets:
- **Gamma API**: Calculates mid-price from recent trades or model estimates
- **CLOB API**: Shows only extreme limit orders (market makers at $0.001 and $0.999)

**Example:**
- Last trade: $0.685 (Gamma shows this)
- Current orderbook: Best bid $0.001, best ask $0.999 (CLOB shows this)
- **No overlap!**

---

## Solution Options

### Option 1: Use Gamma API Prices for Execution (Recommended)

**Change the execution logic to use Gamma API prices instead of VWAP.**

#### Pros:
- ✅ **Consistent pricing** across signal → execution → monitoring
- ✅ **Simpler logic** - single price source
- ✅ **No more immediate stop-loss triggers**
- ✅ **Reflects realistic mid-market prices**

#### Cons:
- ⚠️ Paper trading won't match actual CLOB execution
- ⚠️ Real trading will experience slippage vs paper results

#### Implementation:

```python
# In trader_price_levels.py, around line 990

# CURRENT (uses CLOB VWAP):
entry_price = slippage_est.expected_execution_price  # ← VWAP from orderbook

# FIX (use Gamma API price):
entry_price = float(market['outcomePrices'][outcome_index])

# Still check slippage, but don't use it for execution price
if not slippage_est.is_acceptable:
    logger.warning(f"Trade rejected: {slippage_est.rejection_reason}")
    return
```

#### Modified Slippage Logic:

```python
# Slippage becomes a "feasibility check" not an execution price setter
slippage_result = estimator.estimate(market, side, size, client)

if not slippage_result['can_trade']:
    # Reject if orderbook too thin or spread too wide
    logger.warning(f"Trade rejected: {slippage_result['reason']}")
    return

# But use Gamma API price for execution
entry_price = float(market['outcomePrices'][0])  # For YES token
```

---

### Option 2: Add Price Consistency Check

**Only trade when Gamma and CLOB prices are within acceptable range.**

#### Pros:
- ✅ **Avoids price mismatch trades**
- ✅ **More conservative** - only trades liquid markets
- ✅ **Protects against stale Gamma data**

#### Cons:
- ❌ **Fewer trading opportunities** - rejects many markets
- ❌ **Still have the mismatch issue** for accepted trades

#### Implementation:

```python
# After slippage estimation
slippage_est = estimator.estimate(market, side, size, client)

# Get Gamma API price
gamma_price = float(market['outcomePrices'][outcome_index])

# Get CLOB price (VWAP)
clob_price = slippage_est.expected_execution_price

# Check consistency
price_diff_pct = abs(clob_price - gamma_price) / gamma_price

MAX_PRICE_DIVERGENCE = 0.15  # 15% tolerance

if price_diff_pct > MAX_PRICE_DIVERGENCE:
    logger.warning(
        f"Price mismatch: Gamma=${gamma_price:.3f}, CLOB=${clob_price:.3f} "
        f"({price_diff_pct:.1%} divergence) - skipping trade"
    )
    return

# Use Gamma price for execution (consistent with monitoring)
entry_price = gamma_price
```

---

### Option 3: Use CLOB Prices for Everything

**Fetch CLOB orderbook prices for signal generation AND monitoring.**

#### Pros:
- ✅ **Matches actual trading reality**
- ✅ **Most accurate for live trading**
- ✅ **Consistent pricing throughout**

#### Cons:
- ❌ **Much slower** - need orderbook fetch for every market
- ❌ **API rate limits** - hundreds of orderbook calls per cycle
- ❌ **Thin markets show unrealistic prices** (0.001 / 0.999)

#### Implementation:

```python
# In signal generation, fetch orderbook
def _generate_signal(self, market, parsed_market):
    token_id = market['tokens'][0]['token_id']

    # Fetch CLOB orderbook
    orderbook = self.client.get_orderbook(token_id)

    if not orderbook or not orderbook.get('asks'):
        logger.warning("No orderbook available")
        return {'action': 'HOLD', 'reason': 'no_orderbook'}

    # Use best ask as market price
    market_price_yes = float(orderbook['asks'][0]['price'])

    # Generate signal using CLOB price
    signal = self.ml_model.predict(market_price_yes, features)

    # Execution also uses CLOB price
    entry_price = market_price_yes

    # Monitoring also uses CLOB price
    current_orderbook = self.client.get_orderbook(token_id)
    current_price = float(current_orderbook['asks'][0]['price'])
```

**This is NOT recommended** - too slow and still has thin market issues.

---

## Recommended Approach

### **Hybrid: Option 1 + Option 2**

1. **Use Gamma API prices for execution** (consistent with monitoring)
2. **Add price consistency check** (safety valve)
3. **Keep slippage estimator** (for liquidity/feasibility checks)

#### Complete Fix:

```python
# In _execute_trade() method around line 970

# 1. Estimate slippage (feasibility check)
slippage_result = estimator.estimate(market, side='BUY', size=position_size, client=self.client)

if not slippage_result['can_trade']:
    logger.warning(f"Trade rejected: {slippage_result['reason']}")
    return

# 2. Get prices from both sources
gamma_price = float(market['outcomePrices'][outcome_index])
clob_vwap = slippage_result['expected_execution_price']

# 3. Check price consistency
price_divergence_pct = abs(clob_vwap - gamma_price) / gamma_price

MAX_PRICE_DIVERGENCE = 0.20  # 20% tolerance (configurable)

if price_divergence_pct > MAX_PRICE_DIVERGENCE:
    logger.warning(
        f"⚠️ Price mismatch: Gamma=${gamma_price:.3f}, CLOB=${clob_vwap:.3f} "
        f"({price_divergence_pct:.1%} divergence > {MAX_PRICE_DIVERGENCE:.0%} limit)"
    )
    return  # Skip trade

# 4. Use Gamma price for execution (consistent with monitoring)
entry_price = gamma_price

logger.info(f"Slippage: ${slippage_result['slippage_dollars']:.3f} "
           f"({slippage_result['slippage_bps']:.0f} bps), "
           f"depth: {slippage_result['levels_consumed']} levels")

logger.info(f"Price consistency check passed: "
           f"Gamma=${gamma_price:.3f}, CLOB=${clob_vwap:.3f} "
           f"({price_divergence_pct:.1%} divergence)")

# ... continue with trade execution using entry_price = gamma_price
```

---

## Configuration Addition

Add to `config/config_price_levels.json`:

```json
{
  "execution": {
    "use_gamma_prices": true,
    "max_price_divergence_pct": 0.20,
    "require_price_consistency": true
  }
}
```

---

## Expected Behavior After Fix

### Before (Current - Broken):
```
Signal: BUY YES (Gamma price: $0.685)
Slippage check: PASS (CLOB VWAP: $0.999)
Execute: Entry at $0.999 ← From CLOB
Monitor: Current $0.685 ← From Gamma
Loss: 31% → STOP LOSS ❌
```

### After (Fixed):
```
Signal: BUY YES (Gamma price: $0.685)
Slippage check: PASS (CLOB VWAP: $0.999)
Price consistency check: FAIL (45.8% divergence > 20% limit)
Result: Trade SKIPPED ✅
```

**OR** (if prices are consistent):
```
Signal: BUY YES (Gamma price: $0.185)
Slippage check: PASS (CLOB VWAP: $0.195)
Price consistency check: PASS (5.4% divergence < 20% limit)
Execute: Entry at $0.185 ← From Gamma
Monitor: Current $0.185 ← From Gamma (consistent!)
Loss: 0% → Position remains open ✅
```

---

## Implementation Steps

1. **Add price consistency check** to `trader_price_levels.py`
2. **Change execution price** from VWAP to Gamma API price
3. **Add configuration** for max divergence tolerance
4. **Test with paper trading** to verify no immediate stop-losses
5. **Monitor logs** for price divergence warnings
6. **Adjust MAX_PRICE_DIVERGENCE** based on results

---

## Testing Plan

1. **Run bot with fix** for 1 hour
2. **Check positions**: Should NOT immediately close
3. **Check logs**: Look for price divergence warnings
4. **Verify P&L**: Should be realistic (not -30% on entry)
5. **Compare trades**: Before vs after fix

---

## Files to Modify

1. **`src/bots/trader_price_levels.py`** (line ~970-1000)
   - Add price consistency check
   - Change `entry_price` from VWAP to Gamma price

2. **`config/config_price_levels.json`**
   - Add `execution.max_price_divergence_pct`
   - Add `execution.use_gamma_prices`

---

## Rollback Plan

If the fix causes issues:

```python
# Revert to CLOB VWAP execution (original behavior)
entry_price = slippage_est.expected_execution_price

# But be aware this causes immediate stop-losses!
```

---

## Summary

**Root Cause**: Gamma API and CLOB API report different prices for thin markets

**Fix**: Use Gamma API prices for execution + add price consistency check

**Benefit**: Consistent pricing → no more immediate stop-losses

**Trade-off**: Fewer trades (rejects markets with large Gamma/CLOB divergence)

**Expected Result**: Positions stay open, realistic P&L, circuit breaker doesn't trigger immediately
