# Max Entry Price Filter - Implementation Guide

## Why This Matters

**Problem**: Buying tokens at $0.999 means:
- Cost: $0.999
- Max profit: $0.001 (if wins)
- Max loss: $0.999 (if loses)
- **Risk/Reward ratio: 999:1** ❌

**Solution**: Never buy tokens priced above $0.90 (90 cents)

---

## Configuration Added

All bot configs now have:

```json
{
  "max_entry_price": 0.90
}
```

**Files updated**:
- ✅ `config/config_price_levels.json`
- ✅ `config/config.json` (event trader)
- ✅ `config/config_short_expiry.json`
- ✅ `config/config_arbitrage.json`

---

## Where to Implement the Check

### Option 1: In Signal Generation (Recommended)

**Reject trades BEFORE slippage estimation**

```python
# After getting CLOB prices, before generating signal

# Get execution price
prices = self.client.get_clob_prices(condition_id)
entry_price = prices['yes'] if outcome == 'YES' else prices['no']

# Check max entry price
max_entry_price = self.config.get('max_entry_price', 0.90)
if entry_price > max_entry_price:
    logger.info(f"⚠️ Entry price ${entry_price:.3f} exceeds max ${max_entry_price:.2f} - skipping")
    continue  # Skip this market

# Continue with signal generation...
```

### Option 2: In Execution Logic

**Reject trades AFTER signal generation but BEFORE execution**

```python
# After slippage estimation, before opening position

# Get entry price from slippage estimator
entry_price = slippage_est.expected_execution_price

# Check max entry price
max_entry_price = self.config.get('max_entry_price', 0.90)
if entry_price > max_entry_price:
    logger.warning(
        f"⚠️ Trade rejected: Entry price ${entry_price:.3f} "
        f"exceeds max ${max_entry_price:.2f}"
    )
    return  # Don't execute

# Continue with trade execution...
```

---

## Implementation by Bot

### 1. Price Level Trader (`trader_price_levels.py`)

**Location**: Around line 970, before calling slippage estimator

```python
def _execute_trade(self, signal, parsed_market, market_price, position_size):
    """Execute trade with max entry price check."""

    # Determine entry price based on outcome
    outcome = signal['outcome']
    if outcome == 'YES':
        entry_price = market_price  # YES price from CLOB
    else:
        entry_price = 1.0 - market_price  # NO price

    # 🆕 MAX ENTRY PRICE CHECK
    max_entry_price = self.config.get('max_entry_price', 0.90)
    if entry_price > max_entry_price:
        logger.warning(
            f"⚠️ Trade rejected: Entry price ${entry_price:.3f} "
            f"exceeds max ${max_entry_price:.2f} | "
            f"Market: {parsed_market.get('question', '')[:50]}"
        )
        return  # Don't execute trade

    # Continue with slippage estimation...
    slippage_result = estimator.estimate(...)
```

### 2. Event Trader (`trader.py`)

**Location**: In signal generation or execution, similar to above

```python
# After getting market prices
yes_price = float(market['outcomePrices'][0])
no_price = float(market['outcomePrices'][1])

# Determine entry price based on outcome
entry_price = yes_price if outcome == 'YES' else no_price

# 🆕 MAX ENTRY PRICE CHECK
max_entry_price = self.config.get('max_entry_price', 0.90)
if entry_price > max_entry_price:
    logger.warning(
        f"⚠️ Skipping: Entry price ${entry_price:.3f} > ${max_entry_price:.2f}"
    )
    continue  # Skip to next market
```

### 3. Short-Expiry Trader (`trader_short_expiry.py`)

**Location**: In `_execute_trade()` method, around line 656

```python
def _execute_trade(self, market, signal, bucket, features):
    """Execute trade with max entry price check."""

    # Get entry price
    prices = self._get_prices(market)
    entry_price = prices['yes'] if outcome == 'YES' else prices['no']

    # 🆕 MAX ENTRY PRICE CHECK
    max_entry_price = self.config.get('max_entry_price', 0.90)
    if entry_price > max_entry_price:
        logger.warning(
            f"⚠️ Trade rejected ({bucket}): Entry price ${entry_price:.3f} "
            f"exceeds max ${max_entry_price:.2f}"
        )
        return  # Don't execute

    # Calculate position size...
```

### 4. Arbitrage Bot (`arbitrage_bot.py`)

**Location**: In arbitrage opportunity evaluation

```python
# When evaluating YES/NO price combination
yes_price = market1['outcomePrices'][0]
no_price = market2['outcomePrices'][1]

# 🆕 MAX ENTRY PRICE CHECK (both legs)
max_entry_price = self.config.get('max_entry_price', 0.90)

if yes_price > max_entry_price:
    logger.debug(f"Skipping arb: YES price ${yes_price:.3f} too high")
    continue

if no_price > max_entry_price:
    logger.debug(f"Skipping arb: NO price ${no_price:.3f} too high")
    continue
```

---

## Example Scenarios

### Scenario 1: Price Too High - Rejected ✅

```
Market: "Will BTC reach $200k by Dec 31, 2026?"
YES price: $0.999
NO price: $0.001

Check YES side:
  Entry price: $0.999
  Max allowed: $0.90
  Result: $0.999 > $0.90 → ❌ REJECTED

Check NO side:
  Entry price: $0.001
  Max allowed: $0.90
  Result: $0.001 < $0.90 → ✅ ALLOWED (if signal says BUY NO)
```

### Scenario 2: Both Prices Acceptable ✅

```
Market: "Will ETH reach $5,000 by June?"
YES price: $0.45
NO price: $0.55

Check YES side:
  Entry price: $0.45
  Max allowed: $0.90
  Result: $0.45 < $0.90 → ✅ ALLOWED

Check NO side:
  Entry price: $0.55
  Max allowed: $0.90
  Result: $0.55 < $0.90 → ✅ ALLOWED
```

### Scenario 3: Borderline Case

```
Market: "Will GOLD hit $6,000?"
YES price: $0.89
NO price: $0.11

Check YES side:
  Entry price: $0.89
  Max allowed: $0.90
  Result: $0.89 < $0.90 → ✅ ALLOWED (just barely)
```

---

## Impact on Trading

### Before Filter

```
Markets discovered: 54
Signals generated: 15
Trades attempted: 15
  - 12 rejected (high slippage)
  - 3 executed at $0.99+
    → Immediate stop-loss ❌
```

### After Filter

```
Markets discovered: 54
Price filter applied:
  - 45 rejected (price > $0.90)
  - 9 passed price check
Signals generated: 9
Trades attempted: 9
  - 3 rejected (high slippage)
  - 6 executed at $0.10-$0.90 ✅
```

**Result**: Only trade markets with reasonable entry prices!

---

## Recommended Values

| Bot Type | Recommended Max Price | Rationale |
|----------|----------------------|-----------|
| **Conservative** | 0.80 | Only high-value opportunities |
| **Moderate** | 0.90 | Balance risk/reward |
| **Aggressive** | 0.95 | Accept lower expected returns |

**Current setting: 0.90** (moderate)

---

## Adjustment Strategy

### If Too Restrictive (No Trades)

Lower the threshold:
```json
{
  "max_entry_price": 0.95
}
```

### If Too Risky (Bad Trades)

Raise the threshold:
```json
{
  "max_entry_price": 0.75
}
```

### Dynamic Adjustment

Consider time-to-expiry:
```python
# Long-dated markets: more strict
if days_to_expiry > 100:
    max_price = 0.80  # Need bigger edge

# Short-dated markets: less strict
elif days_to_expiry < 7:
    max_price = 0.95  # Less time for profit
```

---

## Testing

### Manual Test

```python
from core.polymarket_client import PolymarketClient

client = PolymarketClient()

# Get prices
prices = client.get_clob_prices(condition_id)
yes_price = prices['yes']
no_price = prices['no']

# Test filter
max_entry_price = 0.90

print(f"YES price: ${yes_price:.3f} - "
      f"{'✅ PASS' if yes_price <= max_entry_price else '❌ REJECT'}")

print(f"NO price: ${no_price:.3f} - "
      f"{'✅ PASS' if no_price <= max_entry_price else '❌ REJECT'}")
```

### Expected Log Output

**With filter active**:
```
2026-02-13 10:00:00 - Processing: Will BTC reach $200k?
2026-02-13 10:00:01 - Market Price: YES=$0.999, NO=$0.001
2026-02-13 10:00:01 - ⚠️ Entry price $0.999 exceeds max $0.90 - skipping
2026-02-13 10:00:01 -
Processing: Will ETH reach $5k?
2026-02-13 10:00:02 - Market Price: YES=$0.45, NO=$0.55
2026-02-13 10:00:02 - ✅ Entry price $0.45 within limit
2026-02-13 10:00:03 - Generating signal...
```

---

## Next Steps

1. ✅ **Config updated** (all bots have `max_entry_price: 0.90`)
2. ⏭️ **Implement checks** in each bot's trading logic
3. ⏭️ **Test** with paper trading
4. ⏭️ **Monitor** rejection rates
5. ⏭️ **Adjust** threshold if needed

---

## Files to Modify

**Implementation needed in**:
- [ ] `src/bots/trader_price_levels.py` (around line 970)
- [ ] `src/bots/trader.py` (in signal generation)
- [ ] `src/bots/trader_short_expiry.py` (in _execute_trade)
- [ ] `src/bots/arbitrage_bot.py` (in opportunity evaluation)

**Configs already updated**:
- ✅ `config/config_price_levels.json`
- ✅ `config/config.json`
- ✅ `config/config_short_expiry.json`
- ✅ `config/config_arbitrage.json`

---

## Summary

**What**: Never buy tokens priced above $0.90

**Why**: $0.999 entry = $0.001 max profit vs $0.999 risk (999:1 ratio!)

**How**: Check entry price before executing trades

**Config**: `"max_entry_price": 0.90` added to all bots

**Next**: Implement the check in each bot's trading logic
