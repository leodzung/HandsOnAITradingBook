# Arbitrage Bot Deduplication Fix

**Date**: 2026-02-07
**Issue**: Arbitrage opportunities were being logged multiple times (44 duplicate entries for the same opportunity)
**Status**: ✅ Fixed

## Root Cause

The WebSocket continuously receives order book updates, and every update triggered arbitrage checking without any deduplication:

```
WebSocket price update
→ check_arbitrage()
→ Finds SAME opportunity (prices still profitable)
→ on_arb_signal callback
→ logs it AGAIN (every few milliseconds)
```

**Example**: The "Cardi B Super Bowl" market with YES ask=$0.50 + NO ask=$0.39 = $0.89 (11% profit) was logged 44 times in a few seconds because the order book kept sending updates.

## Solution Implemented

Added **deduplication logic** in `RealTimeArbitrageMonitor` class (`orderbook_websocket.py`):

### 1. Tracking State
```python
self._last_signal_time: Dict[str, datetime] = {}
self._last_signal_prices: Dict[str, tuple] = {}
self._signal_count: Dict[str, int] = {}
```

### 2. Deduplication Rules
An opportunity is only signaled if:
- **First time seeing this market** (new opportunity), OR
- **Cooldown expired** (>30 seconds since last signal), OR
- **Significant price change** (>1% price movement within cooldown)

### 3. Configuration Parameters
Added to `config_arbitrage.json`:
```json
"websocket": {
  "signal_cooldown_seconds": 30,
  "min_price_change_pct": 0.01
}
```

### 4. Enhanced Statistics
Now tracks:
- `unique_opportunities` - Number of distinct markets with arbitrage
- `total_signals` - Total signals fired (including re-signals after cooldown)
- `avg_signals_per_opportunity` - How many times each opportunity was signaled on average

## Files Modified

1. **`orderbook_websocket.py`**
   - Modified `RealTimeArbitrageMonitor.__init__()` - Added deduplication parameters
   - Modified `RealTimeArbitrageMonitor._on_arb_signal()` - Implemented deduplication logic
   - Modified `RealTimeArbitrageMonitor.get_stats()` - Added deduplication statistics

2. **`arbitrage_bot.py`**
   - Updated WebSocket monitor initialization to use config parameters
   - Enhanced statistics logging to show deduplication metrics

3. **`config_arbitrage.json`**
   - Added `signal_cooldown_seconds` (default: 30)
   - Added `min_price_change_pct` (default: 0.01 = 1%)

## Expected Behavior After Fix

### Before (Without Deduplication):
```
2026-02-07 11:10:33 - ARBITRAGE OPPORTUNITY: Cardi B...
2026-02-07 11:10:33 - ARBITRAGE OPPORTUNITY: Cardi B...
2026-02-07 11:10:33 - ARBITRAGE OPPORTUNITY: Cardi B...
... (44 times in a few seconds)
```

### After (With Deduplication):
```
2026-02-07 11:10:33 - ARBITRAGE OPPORTUNITY #1: Cardi B...
  YES: bid=0.610, ask=0.500
  NO:  bid=0.500, ask=0.390
  Buy both cost: $0.890 -> Profit: $0.110

[30 seconds pass...]

2026-02-07 11:11:03 - ARBITRAGE OPPORTUNITY #2: Cardi B...
  [Only logs if prices changed >1% OR cooldown expired]
```

## Testing

To test the fix:
1. Restart the arbitrage bot
2. Observe that opportunities are no longer spammed
3. Check statistics show `unique_opportunities` vs `total_signals`

```bash
# Kill existing bots
pkill -f arbitrage_bot.py

# Start fresh
nohup python3 arbitrage_bot.py >> arbitrage.out 2>&1 &

# Watch logs
tail -f arbitrage.out
```

## Next Steps

This fix addresses **duplicate logging** but does NOT address the main issue that **NO EXECUTION HAPPENS**.

The bot still needs:
- [ ] Trade execution logic implementation
- [ ] Order placement via Polymarket API
- [ ] Position tracking
- [ ] Risk management
- [ ] Transaction fee handling

See `arbitrage_bot.py:1089-1096` - the execution logic is just a `TODO` comment.
