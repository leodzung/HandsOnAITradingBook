# Position Monitoring Fix - Short Expiry Bot

## Issue Summary

**Problem**: Ultra-short positions were showing as "open" in the dashboard even though they had expired days ago.

**Root Cause**: The `_check_positions()` method in `trader_short_expiry.py` was a stub that only logged positions without actually:
- Checking if markets had expired
- Fetching current prices
- Applying stop-loss/take-profit rules
- Closing positions

## Solution Implemented

### 1. Cleanup Script (`scripts/cleanup_expired_positions.py`)

A one-time cleanup script to close currently expired positions:

**Features:**
- Calculates expiry time from entry_time + hours_to_expiry_at_entry
- Fetches current market status (closed/active) via API
- Gets current prices for active markets
- Closes positions with appropriate exit reasons:
  - `expiry` - Time expired, market still active
  - `expiry_closed` - Market closed
  - `expiry_unknown` - Cannot fetch market data

**Usage:**
```bash
# Dry run (preview what will be closed)
python3 scripts/cleanup_expired_positions.py --dry-run

# Actually close expired positions
python3 scripts/cleanup_expired_positions.py

# Force close all open positions
python3 scripts/cleanup_expired_positions.py --force
```

**Results from Feb 12, 2026:**
- ✅ Closed 10 expired positions
- 9 markets were already closed (neutral P&L)
- 1 market still active but expired (recorded actual price)

### 2. Enhanced Position Monitoring (`trader_short_expiry.py`)

Implemented full position monitoring in the `_check_positions()` method:

**Features:**

1. **Expiry Time Check**
   - Calculates expiry based on entry_time + hours_to_expiry_at_entry
   - Auto-closes positions that have passed their expiry time

2. **Market Status Check**
   - Fetches current market data via API
   - Detects if market is closed or inactive
   - Closes positions for closed markets

3. **Price Monitoring**
   - Fetches current prices for both YES and NO outcomes
   - Updates current_price in database
   - Tracks highest_price_seen and lowest_price_seen for trailing stops

4. **Exit Condition Checks**
   - Stop-loss: Exits if loss exceeds configured threshold
   - Take-profit: Exits if profit exceeds configured threshold
   - Pre-expiry exit: Exits before market expires (if configured)

5. **Price Extremes Tracking**
   - New method `update_price_extremes()` in ShortExpiryPositionManager
   - Tracks highest and lowest prices seen
   - Enables trailing stop logic (future feature)

### 3. Database Schema Update

Added columns to support tracking:
```sql
ALTER TABLE positions ADD COLUMN highest_price_seen REAL;
ALTER TABLE positions ADD COLUMN lowest_price_seen REAL;
```

## Testing

### Verify Cleanup Worked

```bash
# Should show 0 open positions
sqlite3 data/positions_short_expiry.db \
  "SELECT COUNT(*) FROM positions WHERE status = 'open'"

# Should show 10 closed positions
sqlite3 data/positions_short_expiry.db \
  "SELECT COUNT(*) FROM positions WHERE status = 'closed'"

# View exit reasons
sqlite3 data/positions_short_expiry.db \
  "SELECT exit_reason, COUNT(*) FROM positions WHERE status = 'closed' GROUP BY exit_reason"
```

### Monitor Bot Logs

The bot now logs position checks with more detail:
```
Checking position: {market_id} | Outcome: {outcome} | Entry: {price}
Position expired: {market_id} | Expired {hours}h ago
Market closed: {market_id}
Exit signal: {market_id} | {outcome} | {entry} → {exit} | {reason}
```

## Configuration

Position monitoring respects these config settings:

**Risk Management** (`config/config_short_expiry.json`):
```json
{
  "risk_management": {
    "stop_loss_pct": {
      "ultra_short": 15,
      "short": 20,
      "medium": 25
    },
    "take_profit_pct": {
      "ultra_short": 30,
      "short": 40,
      "medium": 50
    },
    "pre_expiry_exit_hours": 1.0
  }
}
```

## Next Steps

1. **Monitor Live Performance**: Watch logs to ensure positions are being closed properly
2. **Implement Trailing Stops**: Use highest_price_seen/lowest_price_seen for dynamic exits
3. **Add Position Alerts**: Notify when positions are approaching expiry
4. **Historical Analysis**: Analyze closed positions to refine exit strategies

## Files Modified

- ✅ `src/bots/trader_short_expiry.py` - Enhanced `_check_positions()` method
- ✅ `src/bots/trader_short_expiry.py` - Added `update_price_extremes()` method
- ✅ `scripts/cleanup_expired_positions.py` - New cleanup utility
- ✅ `data/positions_short_expiry.db` - Schema update (added price tracking columns)

## Maintenance

Run the cleanup script periodically if you suspect stale positions:
```bash
# Safe check
python3 scripts/cleanup_expired_positions.py --dry-run

# Apply cleanup
python3 scripts/cleanup_expired_positions.py
```

The bot's position monitoring should now handle expiries automatically, so manual cleanup should rarely be needed.
