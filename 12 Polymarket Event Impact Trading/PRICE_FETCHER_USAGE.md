# PriceFetcher Usage Guide

## Overview

`PriceFetcher` is a centralized service for all price operations across Polymarket bots.

**Benefits:**
- ✅ Single source of truth for prices
- ✅ Consistent bid/ask handling
- ✅ CLOB-only (no Gamma API)
- ✅ Clear separation: entry vs exit prices
- ✅ Built-in validation
- ✅ Spread calculation

---

## Quick Start

```python
from core.price_fetcher import PriceFetcher, MarketPrices
from core.polymarket_client import PolymarketClient

# Initialize
client = PolymarketClient()
price_fetcher = PriceFetcher(client)

# Get entry prices (for new trades)
entry_prices = price_fetcher.get_entry_prices(condition_id)
if entry_prices:
    print(f"Entry: YES=${entry_prices.yes_price}, NO=${entry_prices.no_price}")

# Get exit prices (for position monitoring)
exit_prices = price_fetcher.get_exit_prices(condition_id)
if exit_prices:
    print(f"Exit: YES=${exit_prices.yes_price}, NO=${exit_prices.no_price}")
```

---

## API Reference

### get_entry_prices(condition_id)

Get ASK prices (cost to buy tokens) for entering new positions.

**Use Cases:**
- Signal generation
- Calculating entry price
- Position sizing

**Returns:** `MarketPrices` with ASK prices from CLOB orderbook

**Example:**
```python
prices = price_fetcher.get_entry_prices(condition_id)
if prices:
    # For YES position
    entry_price = prices.yes_price

    # For NO position
    entry_price = prices.no_price

    # Or use helper
    entry_price = prices.get_outcome_price('YES')
```

---

### get_exit_prices(condition_id)

Get BID prices (proceeds from selling tokens) for exiting positions.

**Use Cases:**
- Position monitoring
- Stop-loss/take-profit checks
- P&L calculation
- Position closing

**Returns:** `MarketPrices` with BID prices from CLOB orderbook

**Example:**
```python
prices = price_fetcher.get_exit_prices(condition_id)
if prices:
    # Calculate P&L for YES position
    pnl = (prices.yes_price - entry_price) / entry_price * 100

    # Check stop-loss
    if pnl < -20:
        print("Stop-loss triggered!")
```

---

### get_entry_and_exit_prices(condition_id)

Get both entry (ask) and exit (bid) prices in one call.

**Use Cases:**
- Spread analysis
- Arbitrage detection
- Liquidity assessment

**Returns:** `Tuple[MarketPrices, MarketPrices]` - (entry, exit)

**Example:**
```python
result = price_fetcher.get_entry_and_exit_prices(condition_id)
if result:
    entry_prices, exit_prices = result

    # Calculate spread
    yes_spread = entry_prices.yes_price - exit_prices.yes_price
    print(f"YES spread: ${yes_spread:.4f}")
```

---

### calculate_spread(condition_id)

Calculate bid-ask spread metrics.

**Returns:** Dict with spread information:
- `yes_spread_bps`: YES spread in basis points
- `no_spread_bps`: NO spread in basis points
- `yes_ask`, `yes_bid`: Individual prices
- `no_ask`, `no_bid`: Individual prices

**Example:**
```python
spread = price_fetcher.calculate_spread(condition_id)
if spread:
    print(f"YES spread: {spread['yes_spread_bps']:.0f} bps")
    print(f"YES: Ask ${spread['yes_ask']:.3f}, Bid ${spread['yes_bid']:.3f}")

    # Check if market is liquid
    if spread['yes_spread_bps'] > 5000:  # 50%
        print("⚠️ Warning: Wide spread - illiquid market!")
```

---

### validate_prices(prices, max_price)

Validate prices are within acceptable range.

**Args:**
- `prices`: MarketPrices to validate
- `max_price`: Maximum acceptable price (default 0.90)

**Returns:** `Tuple[bool, Optional[str]]` - (is_valid, rejection_reason)

**Example:**
```python
prices = price_fetcher.get_entry_prices(condition_id)
if prices:
    is_valid, reason = price_fetcher.validate_prices(prices, max_price=0.90)

    if not is_valid:
        print(f"❌ Invalid prices: {reason}")
    else:
        print("✅ Prices validated")
```

---

## Migration Guide

### Before (Old Code)

```python
# Manual CLOB price fetching - ERROR PRONE!
prices = self.client.get_market_prices(condition_id)  # Forgot side='BUY'!
yes_price = prices.get('yes')
no_price = prices.get('no') or (1.0 - yes_price)  # Inference - WRONG!

# Different code in each bot
# Hard to maintain
# Easy to use wrong price type
```

### After (Using PriceFetcher)

```python
# Centralized, consistent, correct
prices = self.price_fetcher.get_entry_prices(condition_id)
if prices:
    yes_price = prices.yes_price
    no_price = prices.no_price
    # Both fetched independently from CLOB
    # Always uses correct side (ASK for entry)
```

---

## Use Case Examples

### 1. Signal Generation (Price Level Bot)

```python
def generate_signal(self, market):
    condition_id = market.get('conditionId')

    # Get entry prices
    prices = self.price_fetcher.get_entry_prices(condition_id)
    if not prices:
        logger.warning("No prices available")
        return None

    # Validate prices BEFORE generating signal
    is_valid, reason = self.price_fetcher.validate_prices(prices, max_price=0.90)
    if not is_valid:
        logger.warning(f"Price validation failed: {reason}")
        return None

    # Use prices for ML model
    return {
        'action': 'BUY',
        'outcome': 'YES',
        'market_price': prices.yes_price,
        'no_price': prices.no_price
    }
```

### 2. Position Monitoring (All Bots)

```python
def check_position_exits(self):
    for position in self.active_positions.values():
        condition_id = position['market_id']

        # Get exit prices (bid - what we'd get for selling)
        prices = self.price_fetcher.get_exit_prices(condition_id)
        if not prices:
            continue

        # Calculate P&L using correct exit price
        entry_price = position['entry_price']
        outcome = position['outcome']

        current_price = prices.get_outcome_price(outcome)
        pnl_pct = (current_price - entry_price) / entry_price * 100

        # Check stop-loss
        if pnl_pct < -20:
            self.close_position(condition_id, exit_price=current_price)
```

### 3. Arbitrage Detection

```python
def find_arbitrage(self, condition_id):
    # Get both entry and exit prices
    result = self.price_fetcher.get_entry_and_exit_prices(condition_id)
    if not result:
        return None

    entry_prices, exit_prices = result

    # Check for arbitrage: YES + NO < 1
    total_cost = entry_prices.yes_price + entry_prices.no_price
    if total_cost < 0.98:
        profit_pct = (1.0 - total_cost) / total_cost * 100
        logger.info(f"🎯 Arbitrage found! Profit: {profit_pct:.2f}%")

        return {
            'yes_price': entry_prices.yes_price,
            'no_price': entry_prices.no_price,
            'total_cost': total_cost,
            'profit_pct': profit_pct
        }
```

### 4. Spread Analysis

```python
def analyze_market_liquidity(self, condition_id):
    spread = self.price_fetcher.calculate_spread(condition_id)
    if not spread:
        return "No data"

    # Check if market is liquid
    if spread['yes_spread_bps'] > 5000 or spread['no_spread_bps'] > 5000:
        return "⚠️ ILLIQUID - Wide spread"
    elif spread['yes_spread_bps'] > 2000 or spread['no_spread_bps'] > 2000:
        return "⚠️ Moderate liquidity"
    else:
        return "✅ Liquid market"
```

---

## Common Pitfalls (Now Avoided!)

### ❌ DON'T: Mix up ask/bid

```python
# WRONG - Using entry prices for exit
prices = price_fetcher.get_entry_prices(condition_id)
exit_value = prices.yes_price  # This is ASK, not BID!
```

### ✅ DO: Use correct price type

```python
# CORRECT - Separate entry and exit
entry_prices = price_fetcher.get_entry_prices(condition_id)  # ASK
exit_prices = price_fetcher.get_exit_prices(condition_id)    # BID
```

### ❌ DON'T: Infer NO from YES

```python
# WRONG - Inferring NO price
yes_price = prices.yes_price
no_price = 1.0 - yes_price  # NEVER DO THIS!
```

### ✅ DO: Fetch independently

```python
# CORRECT - Both fetched from CLOB
yes_price = prices.yes_price  # From YES orderbook
no_price = prices.no_price    # From NO orderbook
```

---

## Testing

```python
# Test entry prices
prices = price_fetcher.get_entry_prices(condition_id)
assert prices is not None
assert 0 <= prices.yes_price <= 1
assert 0 <= prices.no_price <= 1
assert prices.source == 'CLOB_ASK'

# Test exit prices
exit_prices = price_fetcher.get_exit_prices(condition_id)
assert exit_prices.source == 'CLOB_BID'

# Test spread
spread = price_fetcher.calculate_spread(condition_id)
assert spread['yes_ask'] >= spread['yes_bid']  # Ask >= Bid always
assert spread['no_ask'] >= spread['no_bid']
```

---

## Next Steps

1. **Migrate Price Level Bot** - Replace manual price fetching
2. **Migrate Event Trader** - Consistent entry/exit prices
3. **Migrate Short Expiry Trader** - Better position monitoring
4. **Update TradeExecutor** - Use PriceFetcher for validation

---

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| Code duplication | Each bot has own logic | Single shared service |
| Bid/Ask handling | Manual, error-prone | Automatic, correct |
| Price source | Mixed Gamma/CLOB | CLOB only |
| Validation | Scattered | Centralized |
| Inference | NO = 1 - YES | Independent fetch |
| Maintainability | Hard | Easy |
| Consistency | Low | High |
| Testing | Difficult | Simple |

**Result:** Safer, cleaner, more maintainable code! ✅
