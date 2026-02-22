# Price Level Trader - TradeExecutor Migration

## Changes Made

### 1. Added Import
```python
from core.trade_executor import TradeExecutor, TradeRequest
```

### 2. Initialized TradeExecutor in __init__
```python
# Initialize trade executor (centralized execution logic)
self.trade_executor = TradeExecutor(
    client=self.client,
    position_manager=self.position_manager,
    config=self.config,
    paper_trading=self.config.get('paper_trading', True)
)
logger.info("✓ Trade executor initialized")
```

### 3. Replaced Execution Logic (~100 lines → ~40 lines)

**Before**: Custom implementation with:
- Manual slippage estimation
- Custom price validation
- Custom position tracking
- ~100 lines of code

**After**: TradeExecutor handles:
- ✅ Automatic price validation (max_entry_price: 0.90)
- ✅ Automatic slippage estimation
- ✅ Automatic position tracking
- ✅ Clear rejection reasons
- ~40 lines of code

---

## Code Comparison

### Before (Old Code - ~110 lines)

```python
# Get quoted price based on outcome
if outcome == 'YES':
    quoted_price = signal['market_price']
else:
    quoted_price = signal.get('no_price', 1.0 - signal['market_price'])

# Get orderbook for slippage estimation
orderbook = self.client.get_orderbook(token_id)

# Estimate slippage
from core.slippage_estimator import SlippageEstimator
estimator = SlippageEstimator(config=self.config.get('slippage_estimation', {}))

# ... 50 more lines ...

# Execute trade
if self.config.get('paper_trading', True):
    logger.info(f"\n  💰 [PAPER TRADE] BUY {outcome} ${position_size:.2f}")
    # ... logging ...

    # Deduct from balance
    self.balance -= position_size
    self._save_balance(self.balance)

    # Track position in memory
    self.active_positions[market_id] = {...}

    # Persist to database
    metadata = {...}
    self.position_manager.save_position(...)

    logger.info(f"  ✓ Position tracked and persisted")

    # Send Telegram notification
    self.telegram.notify_position_opened(...)
```

### After (New Code - ~40 lines)

```python
# Determine entry price based on outcome
if outcome == 'YES':
    entry_price = signal['market_price']
else:
    entry_price = signal.get('no_price', 1.0 - signal['market_price'])

# Build trade request
request = TradeRequest(
    market_id=market_id,
    token_id=token_id,
    outcome=outcome,
    entry_price=entry_price,
    position_size=position_size,
    question=parsed_market.get('question', ''),
    asset=parsed_market['asset'],
    strike_price=parsed_market.get('strike_price'),
    expiry_date=expiry_str,
    edge=signal['edge'],
    confidence=signal.get('model_prob'),
    signal_reason='price_level_strategy',
    metadata={'kelly_fraction': signal.get('kelly_fraction'), 'slug': slug}
)

# Execute trade with centralized executor (handles ALL validation)
result = self.trade_executor.execute_trade(request)

if not result.success:
    logger.warning(f"  ⚠️ Trade REJECTED ({result.rejection_stage}): {result.rejection_reason}")
    return

# Trade successful - update balance and track in memory
self.balance -= position_size
self._save_balance(self.balance)
logger.info(f"     Balance: ${self.balance:.2f} (spent ${position_size:.2f})")

# Track position in memory
self.active_positions[market_id] = {...}

# Send Telegram notification
self.telegram.notify_position_opened(...)
```

---

## What Changed Functionally

### Automatic Validations Now Applied

1. **Price Validation** (NEW):
   - Rejects if entry_price > $0.90
   - Stage: 'price'
   - Example: "Entry price $0.999 exceeds max $0.90"

2. **Slippage Estimation** (IMPROVED):
   - Uses centralized SlippageEstimator
   - Clearer rejection reasons
   - Stage: 'slippage'
   - Example: "Slippage 8990 bps exceeds limit 6000 bps"

3. **Position Tracking** (SAME):
   - Same database storage
   - Same metadata structure
   - Stage: 'execution'

### Improved Error Handling

**Before**:
```python
if not slippage_est.is_acceptable:
    logger.warning(f"Trade REJECTED: {slippage_est.rejection_reason}")
    return
# No indication of which stage failed
```

**After**:
```python
if not result.success:
    logger.warning(
        f"Trade REJECTED ({result.rejection_stage}): "  # Shows WHICH stage
        f"{result.rejection_reason}"
    )
    return
```

---

## Testing Checklist

### Basic Functionality

- [x] Bot initializes successfully
- [ ] Markets are discovered
- [ ] Signals are generated
- [ ] Price filter rejects $0.999 entries
- [ ] Slippage filter works correctly
- [ ] Valid trades execute successfully
- [ ] Positions saved to database
- [ ] Telegram notifications sent
- [ ] Balance updated correctly

### Edge Cases

- [ ] Empty orderbook → Rejected
- [ ] Price > $0.90 → Rejected at 'price' stage
- [ ] Slippage > 6,000 bps → Rejected at 'slippage' stage
- [ ] Database error → Rejected at 'execution' stage
- [ ] All fields in TradeRequest → Saved correctly

---

## Expected Behavior

### Scenario 1: Price Too High ($0.999)

**Before migration**:
```
Market Price: YES=$0.999
Slippage check: PASS (4134 bps)
Execution: Opens position at $0.999
Result: Position opened → Immediate stop-loss ❌
```

**After migration**:
```
Market Price: YES=$0.999
Price check: FAIL (> $0.90 limit)
Result: ⚠️ Trade REJECTED (price): Entry price $0.999 exceeds max $0.90
```

### Scenario 2: Valid Trade ($0.45)

**Before migration**:
```
Market Price: YES=$0.45
Slippage check: PASS (450 bps)
Execution: Opens position at $0.45
Result: Position opened ✅
```

**After migration**:
```
Market Price: YES=$0.45
Price check: PASS (< $0.90 limit)
Slippage check: PASS (450 bps)
Execution: Opens position at $0.45
Result: Position opened ✅
```

### Scenario 3: High Slippage

**Before migration**:
```
Market Price: YES=$0.45
Slippage check: FAIL (8990 bps)
Result: ⚠️ Trade REJECTED: Slippage 8990 bps exceeds limit 6000 bps
```

**After migration**:
```
Market Price: YES=$0.45
Price check: PASS
Slippage check: FAIL (8990 bps)
Result: ⚠️ Trade REJECTED (slippage): Slippage 8990 bps exceeds limit 6000 bps
```

---

## Log Format Changes

### Before
```
2026-02-13 10:00:00 - Market Price: YES=$0.685
2026-02-13 10:00:01 - Slippage: $8.408 (4134 bps), depth: 1 levels
2026-02-13 10:00:01 - [PAPER TRADE] BUY YES $20.34
2026-02-13 10:00:01 - YES Price: $0.999
2026-02-13 10:00:02 - ✓ Position tracked and persisted
```

### After
```
2026-02-13 10:00:00 - Market Price: YES=$0.685
2026-02-13 10:00:01 - ⚠️ Trade rejected - Price too high | YES @ $0.999 | Max: $0.90
(Trade stops here - never executes!)
```

**OR** (if price is OK):
```
2026-02-13 10:00:00 - Market Price: YES=$0.45
2026-02-13 10:00:01 - Slippage estimate: 450 bps ($2.25) | Levels: 2
2026-02-13 10:00:02 - [PAPER TRADE] BUY YES $50.00
2026-02-13 10:00:02 - ✓ Position tracked and persisted
2026-02-13 10:00:02 - Balance: $450.00 (spent $50.00)
```

---

## Benefits

### Code Quality
- ✅ 60% less code (~110 lines → ~40 lines)
- ✅ Easier to maintain
- ✅ Consistent with other bots
- ✅ Single source of truth

### Functionality
- ✅ Price filter now enforced (was missing!)
- ✅ Better error messages
- ✅ Clear rejection stages
- ✅ Consistent validation

### Safety
- ✅ Can't accidentally bypass price check
- ✅ Can't accidentally bypass slippage check
- ✅ All trades go through same validation

---

## Files Modified

1. **`src/bots/trader_price_levels.py`**
   - Added TradeExecutor import
   - Initialized TradeExecutor in __init__
   - Replaced execution logic (lines 955-1040)
   - Reduced from ~1100 lines to ~1040 lines

2. **`src/core/trade_executor.py`** (created earlier)
   - Centralized execution logic

3. **Config** (already updated)
   - `config/config_price_levels.json` has `max_entry_price: 0.90`

---

## Rollback Plan

If issues arise, the old code is preserved in git history:

```bash
git diff HEAD~1 src/bots/trader_price_levels.py
```

To rollback:
```bash
git checkout HEAD~1 -- src/bots/trader_price_levels.py
```

---

## Next Steps

1. ✅ **Migration complete** - Price level trader now uses TradeExecutor
2. ⏭️ **Test** - Run bot and verify correct behavior
3. ⏭️ **Monitor** - Watch logs for rejection reasons
4. ⏭️ **Migrate other bots** - Event trader, short-expiry, arbitrage

---

## Success Criteria

✅ Bot starts successfully
✅ No more $0.999 entries (rejected at 'price' stage)
✅ Slippage rejections show clear reasons
✅ Valid trades execute as before
✅ Positions saved correctly
✅ Telegram notifications work
✅ Balance tracking correct
