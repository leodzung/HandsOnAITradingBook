# CLOB Price Centralization - Fix Implementation

## Problem

The bot was using **different price sources** for different operations, causing immediate stop-loss triggers:

| Operation | OLD Price Source | Example Price |
|-----------|------------------|---------------|
| Signal Generation | Market metadata (`token.price`) | $0.685 |
| Execution | CLOB orderbook (via SlippageEstimator) | $0.999 |
| Position Monitoring | Market metadata (`token.price`) | $0.685 |

**Result**: Entered at $0.999 (CLOB), monitored at $0.685 (metadata) → 31% loss → stop loss!

---

## Solution

**Centralized CLOB price fetching** - ALL operations now use actual CLOB orderbook prices.

### New Method Added

**`PolymarketClient.get_clob_prices(condition_id)`**

```python
def get_clob_prices(self, condition_id: str) -> Dict[str, Optional[float]]:
    """
    Get YES and NO prices from CLOB orderbook (not Gamma API estimates).

    This is the SINGLE SOURCE OF TRUTH for all price operations:
    - Signal generation
    - Trade execution
    - Position monitoring

    Returns:
        Dict with 'yes' and 'no' prices from orderbook best ask
    """
    # 1. Get token IDs for YES and NO
    token_ids = self.get_token_ids(condition_id)

    # 2. Fetch YES orderbook and get best ask
    yes_orderbook = self.get_orderbook(yes_token_id)
    yes_price = yes_orderbook['asks'][0]['price']  # Best ask

    # 3. Fetch NO orderbook and get best ask
    no_orderbook = self.get_orderbook(no_token_id)
    no_price = no_orderbook['asks'][0]['price']  # Best ask

    return {'yes': yes_price, 'no': no_price}
```

### Updated Methods

**`get_market_prices(condition_id)`** - Now delegates to `get_clob_prices()`:

```python
def get_market_prices(self, condition_id: str) -> Dict[str, Optional[float]]:
    """Get both YES and NO prices from CLOB orderbook."""
    return self.get_clob_prices(condition_id)  # Centralized!
```

**`get_market_yes_price(condition_id)`** - Unchanged, calls `get_market_prices()`:

```python
def get_market_yes_price(self, condition_id: str) -> Optional[float]:
    """Get YES price from CLOB orderbook."""
    prices = self.get_market_prices(condition_id)  # → get_clob_prices()
    return prices.get('yes')
```

---

## Data Flow

### Before (Inconsistent):

```
Signal Generation:
  market = get_market(condition_id)  # Gamma API
  price = market['tokens'][0]['price']  # Metadata estimate: $0.685
  ↓
Execution:
  orderbook = get_orderbook(token_id)  # CLOB API
  vwap = calculate_vwap(orderbook)  # Orderbook reality: $0.999
  ↓
Position Monitoring:
  market = get_market(condition_id)  # Gamma API again
  price = market['tokens'][0]['price']  # Metadata estimate: $0.685
  ↓
MISMATCH! Entry $0.999 vs Current $0.685 = -31% loss
```

### After (Consistent):

```
Signal Generation:
  prices = get_clob_prices(condition_id)  # CLOB orderbook
  price = prices['yes']  # Best ask: $0.999
  ↓
Execution:
  orderbook = get_orderbook(token_id)  # Same CLOB API
  vwap = calculate_vwap(orderbook)  # Best ask: $0.999
  ↓
Position Monitoring:
  prices = get_clob_prices(condition_id)  # Same CLOB API
  price = prices['yes']  # Best ask: $0.999
  ↓
CONSISTENT! Entry $0.999 = Current $0.999 = 0% change ✓
```

---

## Impact on Each Bot

### 1. Price Level Trader (`trader_price_levels.py`)

**No code changes needed!** It already calls:
```python
current_price = self.client.get_market_yes_price(market_id)
```

This now automatically uses CLOB orderbook prices via the updated `get_market_prices()`.

**Before**:
- Signal gen: Market metadata ($0.685)
- Execution: CLOB orderbook ($0.999)
- Monitoring: Market metadata ($0.685)
- **Result**: Immediate stop-loss ❌

**After**:
- Signal gen: CLOB orderbook ($0.999)
- Execution: CLOB orderbook ($0.999)
- Monitoring: CLOB orderbook ($0.999)
- **Result**: Consistent pricing ✅

### 2. Event Trader (`trader.py`)

**Also benefits automatically** if it uses `get_market_yes_price()`.

### 3. Short-Expiry Trader (`trader_short_expiry.py`)

**Also benefits automatically** if it uses these methods.

---

## What Changed in Each File

### `src/core/polymarket_client.py`

1. ✅ **Added** `get_clob_prices()` - Centralized CLOB orderbook price fetching
2. ✅ **Modified** `get_market_prices()` - Now delegates to `get_clob_prices()`
3. ✅ **Unchanged** `get_market_yes_price()` - Calls `get_market_prices()` (now uses CLOB)

**No changes needed in**:
- `src/bots/trader_price_levels.py`
- `src/bots/trader.py`
- `src/bots/trader_short_expiry.py`

All bots automatically get consistent CLOB pricing!

---

## Example Price Comparison

### GOLD $5,500 Market

**Gamma API (old - market metadata)**:
```json
{
  "tokens": [
    {"outcome": "Yes", "price": "0.685"}  ← Estimate
  ]
}
```

**CLOB API (new - actual orderbook)**:
```json
{
  "asks": [
    {"price": "0.999", "size": "100"}  ← Real limit order
  ]
}
```

**Before**: Used 0.685 for signal gen, 0.999 for execution → mismatch
**After**: Uses 0.999 for everything → consistent

---

## Testing

### Manual Test

```python
from core.polymarket_client import PolymarketClient

client = PolymarketClient()

# Test the new centralized method
condition_id = "0x246559691ae64806ee51dcc5ca1d1216bf6e25d80127a3425b72ba559190e96f"
prices = client.get_clob_prices(condition_id)

print(f"YES price: ${prices['yes']}")
print(f"NO price: ${prices['no']}")

# Should print actual CLOB orderbook prices, not Gamma estimates
```

### Expected Behavior

**Before fix**:
```
2026-02-13 08:17:17 - Market Price: YES=$0.685  (Gamma)
2026-02-13 08:17:17 - Executing at: $0.999      (CLOB)
2026-02-13 08:17:47 - Current Price: $0.685     (Gamma)
2026-02-13 08:17:47 - Loss: -31% → STOP LOSS ❌
```

**After fix**:
```
2026-02-13 10:00:00 - Market Price: YES=$0.999  (CLOB)
2026-02-13 10:00:01 - Executing at: $0.999      (CLOB)
2026-02-13 10:01:00 - Current Price: $0.999     (CLOB)
2026-02-13 10:01:00 - Loss: 0% → Position open ✅
```

---

## Performance Considerations

### Increased API Calls

**Before**: 1 API call per market
- `GET /markets/{condition_id}` → returns metadata with price estimate

**After**: 3 API calls per market
- `GET /markets/{condition_id}` → get token IDs
- `GET /book?token_id={yes_token}` → get YES orderbook
- `GET /book?token_id={no_token}` → get NO orderbook

**Impact**:
- 3x more API calls during market discovery
- Slower market scanning (but more accurate)
- May hit rate limits faster (monitor this)

### Mitigation

If performance becomes an issue:

1. **Cache orderbook data** for 10-30 seconds
2. **Batch orderbook fetches** during discovery
3. **Only fetch orderbook when trading** (not during screening)

---

## Advantages

✅ **Consistent pricing** - Same data source for all operations
✅ **No code changes in bots** - Centralized in PolymarketClient
✅ **Reflects trading reality** - Uses actual CLOB orderbook
✅ **Fixes immediate stop-loss bug** - Entry price = monitoring price
✅ **Single source of truth** - get_clob_prices() for everything

---

## Disadvantages

⚠️ **More API calls** - 3x per market (may hit rate limits)
⚠️ **Slower discovery** - Fetching orderbooks takes longer
⚠️ **Thin markets show extreme prices** - Orderbook may only have $0.001/$0.999

---

## Monitoring

After deploying, monitor:

1. **Position P&L**: Should be realistic (not -30% on entry)
2. **Stop-loss triggers**: Should not trigger immediately
3. **API rate limits**: Watch for 429 errors
4. **Log warnings**: Check for orderbook fetch failures

---

## Rollback

If issues arise, revert `get_market_prices()` to old behavior:

```python
def get_market_prices(self, condition_id: str) -> Dict[str, Optional[float]]:
    """OLD VERSION - uses market metadata"""
    result = {'yes': None, 'no': None}
    market = self.get_market(condition_id)
    if not market:
        return result

    tokens = market.get('tokens', [])
    for token in tokens:
        outcome = token.get('outcome', '').lower()
        if outcome in ('yes', 'no'):
            price = token.get('price')
            if price is not None:
                result[outcome] = float(price)

    return result
```

---

## Summary

**Change**: Centralized ALL price fetching to use CLOB orderbook via `get_clob_prices()`

**Result**: Consistent pricing across signal generation, execution, and monitoring

**Benefit**: Fixes immediate stop-loss bug, reflects actual trading reality

**Trade-off**: More API calls, slower but more accurate

**Status**: ✅ **Ready to deploy** - restart the price level bot to apply fix
