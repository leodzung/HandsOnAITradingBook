# Trade Executor - Centralized Position Entry

## Overview

`TradeExecutor` provides **single source of truth** for all trade execution logic across all bots.

**Benefits**:
- ✅ Consistent validation (price, slippage, risk)
- ✅ Single place to update logic
- ✅ Automatic application of all filters
- ✅ Clear success/failure reasons
- ✅ Comprehensive logging

---

## Quick Start

### 1. Initialize in Bot

```python
from core.trade_executor import TradeExecutor, TradeRequest

class MyBot:
    def __init__(self, config_path):
        self.config = load_config(config_path)
        self.client = PolymarketClient()
        self.position_manager = PositionManager(db_path)

        # Initialize trade executor
        self.executor = TradeExecutor(
            client=self.client,
            position_manager=self.position_manager,
            config=self.config,
            paper_trading=self.config.get('paper_trading', True)
        )
```

### 2. Execute Trade

```python
# Build trade request
request = TradeRequest(
    market_id=market['conditionId'],
    token_id=token_id,
    outcome='YES',
    entry_price=0.45,
    position_size=50.0,
    question=market['question'],
    asset='BTC',
    strike_price=120000,
    expiry_date='2026-12-31',
    edge=0.15,
    confidence=0.75,
    signal_reason='positive_momentum'
)

# Execute with full validation
result = self.executor.execute_trade(request)

if result.success:
    logger.info(f"✅ Trade executed at ${result.entry_price:.3f}")
else:
    logger.warning(f"❌ Trade rejected: {result.rejection_reason}")
```

---

## Validation Pipeline

### Automatic Checks Performed

```
1. Price Validation
   ├─ Check: entry_price <= max_entry_price
   ├─ Reject if: price > 0.90 (configurable)
   └─ Stage: 'price'

2. Slippage Estimation (if enabled)
   ├─ Fetch: CLOB orderbook
   ├─ Simulate: Order fill across levels
   ├─ Calculate: VWAP + safety buffers
   ├─ Check: slippage <= max_slippage_bps
   ├─ Reject if: excessive slippage
   └─ Stage: 'slippage'

3. Position Execution
   ├─ Paper trading: Simulate execution
   ├─ Live trading: Submit to CLOB (future)
   ├─ Track: Save to position database
   └─ Stage: 'execution'
```

---

## Before & After Comparison

### Before (Duplicated Logic)

**Price Level Trader**:
```python
def _execute_trade(self, signal, market, position_size):
    # Custom price check
    if entry_price > 0.90:
        logger.warning("Price too high")
        return

    # Custom slippage check
    slippage_est = SlippageEstimator(...)
    result = slippage_est.estimate(...)
    if not result.is_acceptable:
        logger.warning("Slippage too high")
        return

    # Custom position tracking
    position = {...}
    self.position_manager.add_position(position)
```

**Event Trader**:
```python
def _execute_trade(self, signal, market):
    # DIFFERENT price check implementation
    max_price = self.config.get('max_entry_price', 0.90)
    if price > max_price:
        return

    # DIFFERENT slippage check
    # ... similar but slightly different code ...

    # DIFFERENT position tracking
    # ... similar but slightly different format ...
```

**Short-Expiry Trader**:
```python
def _execute_trade(self, signal, market, bucket):
    # YET ANOTHER price check implementation
    # ... bucket-specific logic ...

    # YET ANOTHER slippage check
    # ... bucket-specific limits ...

    # YET ANOTHER position tracking
    # ... bucket-specific metadata ...
```

**Result**: 3 different implementations, hard to maintain!

---

### After (Centralized Logic)

**All Bots**:
```python
from core.trade_executor import TradeExecutor, TradeRequest

def _execute_trade(self, signal, market):
    # Build request (simple!)
    request = TradeRequest(
        market_id=market['conditionId'],
        token_id=token_id,
        outcome=signal['outcome'],
        entry_price=signal['entry_price'],
        position_size=signal['position_size'],
        question=market['question'],
        edge=signal.get('edge'),
        confidence=signal.get('confidence'),
        signal_reason=signal.get('reason')
    )

    # Execute (consistent validation!)
    result = self.executor.execute_trade(request)

    # Handle result (simple!)
    if result.success:
        logger.info(f"✅ Position opened: {result.entry_price:.3f}")
    else:
        logger.warning(f"❌ Rejected ({result.rejection_stage}): {result.rejection_reason}")
```

**Result**: Single implementation, easy to maintain!

---

## Integration by Bot

### 1. Price Level Trader

**Current code** (around line 970):
```python
def _execute_trade(self, signal, parsed_market, market_price, position_size):
    # ... 100+ lines of validation and execution logic ...
```

**Replace with**:
```python
def _execute_trade(self, signal, parsed_market, market_price, position_size):
    """Execute trade using centralized executor."""

    # Determine entry price based on outcome
    outcome = signal['outcome']
    if outcome == 'YES':
        entry_price = market_price
    else:
        entry_price = 1.0 - market_price

    # Build request
    request = TradeRequest(
        market_id=parsed_market['condition_id'],
        token_id=parsed_market.get('token_id'),
        outcome=outcome,
        entry_price=entry_price,
        position_size=position_size,
        question=parsed_market.get('question', ''),
        asset=parsed_market.get('asset'),
        strike_price=parsed_market.get('strike_price'),
        expiry_date=parsed_market.get('expiry_date'),
        edge=signal.get('edge'),
        confidence=signal.get('confidence'),
        signal_reason=signal.get('reason'),
        metadata={
            'slug': parsed_market.get('slug'),
            'kelly_fraction': signal.get('kelly_fraction')
        }
    )

    # Execute with full validation
    result = self.executor.execute_trade(request)

    if result.success:
        logger.info(
            f"✅ Position opened | "
            f"{outcome} @ ${result.entry_price:.3f} | "
            f"Size: ${result.position_size:.2f} | "
            f"Slippage: {result.slippage_bps:.0f} bps"
        )
        return True
    else:
        logger.warning(
            f"❌ Trade rejected ({result.rejection_stage}): "
            f"{result.rejection_reason}"
        )
        return False
```

---

### 2. Event Trader

**Replace execution logic** with:
```python
def _open_position(self, market, signal):
    """Execute trade using centralized executor."""

    # Get entry price from market
    prices = self.client.get_clob_prices(market['conditionId'])
    entry_price = prices['yes'] if signal['outcome'] == 'YES' else prices['no']

    # Build request
    request = TradeRequest(
        market_id=market['conditionId'],
        token_id=market['tokens'][0]['token_id'],  # Adjust based on outcome
        outcome=signal['outcome'],
        entry_price=entry_price,
        position_size=signal['position_size'],
        question=market['question'],
        edge=signal.get('expected_return'),
        confidence=signal.get('confidence'),
        signal_reason=signal.get('trigger_type')
    )

    # Execute
    result = self.executor.execute_trade(request)

    return result.success
```

---

### 3. Short-Expiry Trader

**Replace execution logic** with bucket-specific metadata:
```python
def _execute_trade(self, market, signal, bucket, features):
    """Execute trade using centralized executor with bucket metadata."""

    # Get entry price
    prices = self._get_prices(market)
    entry_price = prices['yes'] if signal['outcome'] == 'YES' else prices['no']

    # Build request with bucket metadata
    request = TradeRequest(
        market_id=market['conditionId'],
        token_id=market['tokens'][0]['token_id'],
        outcome=signal['outcome'],
        entry_price=entry_price,
        position_size=signal['position_size'],
        question=market['question'],
        edge=signal.get('edge'),
        confidence=signal.get('confidence'),
        signal_reason=signal.get('reason'),
        metadata={
            'bucket': bucket,
            'hours_to_expiry': features['hours_to_expiry'].iloc[0],
            'features_json': features.to_json()
        }
    )

    # Execute (with bucket-specific slippage limits handled by config)
    result = self.executor.execute_trade(request)

    return result.success
```

---

### 4. Arbitrage Bot

**Replace opportunity execution** with:
```python
def _execute_arbitrage(self, opp):
    """Execute arbitrage opportunity (two legs)."""

    # Leg 1: BUY YES on market 1
    request1 = TradeRequest(
        market_id=opp['market1_id'],
        token_id=opp['yes_token_id'],
        outcome='YES',
        entry_price=opp['yes_price'],
        position_size=opp['position_size'],
        question=opp['market1_question'],
        signal_reason='arbitrage_yes_leg',
        metadata={'arb_pair': opp['market2_id']}
    )

    # Leg 2: BUY NO on market 2
    request2 = TradeRequest(
        market_id=opp['market2_id'],
        token_id=opp['no_token_id'],
        outcome='NO',
        entry_price=opp['no_price'],
        position_size=opp['position_size'],
        question=opp['market2_question'],
        signal_reason='arbitrage_no_leg',
        metadata={'arb_pair': opp['market1_id']}
    )

    # Execute both legs
    result1 = self.executor.execute_trade(request1)
    result2 = self.executor.execute_trade(request2)

    # Only successful if BOTH legs execute
    if result1.success and result2.success:
        logger.info(f"✅ Arbitrage executed: {opp['profit']:.2%} profit")
        return True
    else:
        logger.warning("❌ Arbitrage failed - at least one leg rejected")
        # TODO: Unwind successful leg if other fails
        return False
```

---

## Configuration

### Required Config Fields

All bots must have:

```json
{
  "max_entry_price": 0.90,
  "slippage_estimation": {
    "enabled": true,
    "max_slippage_bps": 6000,
    "max_slippage_dollars": 50.0,
    "depth_buffer_pct": 0.10,
    "volatility_adjustment": false,
    "volume_limit_pct": 0.02,
    "warn_threshold_bps": 3000
  }
}
```

### Bucket-Specific Config (Short-Expiry)

```json
{
  "max_entry_price": 0.90,
  "slippage_estimation": {
    "enabled": true,
    "max_slippage_bps": {
      "ultra_short": 3000,
      "short": 2000,
      "medium": 1500
    },
    ...
  }
}
```

**Note**: TradeExecutor will extract bucket-specific limits automatically.

---

## Error Handling

### Trade Rejection Examples

**Price too high**:
```python
result = executor.execute_trade(request)
# result.success = False
# result.rejection_stage = 'price'
# result.rejection_reason = 'Entry price $0.999 exceeds max $0.90'
```

**Slippage too high**:
```python
result = executor.execute_trade(request)
# result.success = False
# result.rejection_stage = 'slippage'
# result.rejection_reason = 'Slippage 8990 bps exceeds limit 6000 bps'
# result.slippage_bps = 8990
```

**Position tracking failed**:
```python
result = executor.execute_trade(request)
# result.success = False
# result.rejection_stage = 'execution'
# result.rejection_reason = 'Failed to save position: Database locked'
```

---

## Testing

### Unit Test

```python
def test_trade_executor():
    """Test TradeExecutor with mock data."""

    # Setup
    client = MockPolymarketClient()
    position_manager = MockPositionManager()
    config = {
        'max_entry_price': 0.90,
        'slippage_estimation': {'enabled': False}  # Disable for simple test
    }

    executor = TradeExecutor(client, position_manager, config, paper_trading=True)

    # Test 1: Valid trade (price within limit)
    request = TradeRequest(
        market_id='0x123',
        token_id='456',
        outcome='YES',
        entry_price=0.45,
        position_size=50.0,
        question='Will BTC reach $120k?'
    )

    result = executor.execute_trade(request)
    assert result.success == True

    # Test 2: Invalid trade (price too high)
    request = TradeRequest(
        market_id='0x123',
        token_id='456',
        outcome='YES',
        entry_price=0.99,  # Too high!
        position_size=50.0,
        question='Will BTC reach $120k?'
    )

    result = executor.execute_trade(request)
    assert result.success == False
    assert result.rejection_stage == 'price'
```

---

## Migration Checklist

For each bot:

- [ ] Import `TradeExecutor` and `TradeRequest`
- [ ] Initialize `TradeExecutor` in `__init__`
- [ ] Replace custom execution logic with `TradeRequest` building
- [ ] Call `executor.execute_trade(request)`
- [ ] Handle `TradeResult` (success/failure)
- [ ] Remove old validation code (price checks, slippage, etc.)
- [ ] Test with paper trading
- [ ] Verify logs show correct rejection reasons

---

## Benefits Summary

### Before Centralization

❌ **3-4 different implementations** of trade execution
❌ **Inconsistent validation** - different checks per bot
❌ **Hard to update** - change 4 places for one fix
❌ **No standardization** - each bot logs differently
❌ **Missed filters** - some bots skip slippage, some skip price checks

### After Centralization

✅ **Single implementation** in `TradeExecutor`
✅ **Consistent validation** - all bots use same checks
✅ **Easy to update** - change once, applies everywhere
✅ **Standardized logging** - consistent format across bots
✅ **Guaranteed filters** - all bots get price + slippage checks

---

## Next Steps

1. ✅ **Created** `TradeExecutor` class
2. ⏭️ **Migrate** price level trader (most complex)
3. ⏭️ **Migrate** event trader
4. ⏭️ **Migrate** short-expiry trader
5. ⏭️ **Migrate** arbitrage bot
6. ⏭️ **Test** each bot after migration
7. ⏭️ **Remove** old execution code
8. ⏭️ **Document** any bot-specific customizations

---

## Files

**Created**:
- ✅ `src/core/trade_executor.py` - Centralized executor

**To Update**:
- [ ] `src/bots/trader_price_levels.py` - Replace execution logic
- [ ] `src/bots/trader.py` - Replace execution logic
- [ ] `src/bots/trader_short_expiry.py` - Replace execution logic
- [ ] `src/bots/arbitrage_bot.py` - Replace execution logic

**Configs** (already have required fields):
- ✅ `config/config_price_levels.json`
- ✅ `config/config.json`
- ✅ `config/config_short_expiry.json`
- ✅ `config/config_arbitrage.json`
