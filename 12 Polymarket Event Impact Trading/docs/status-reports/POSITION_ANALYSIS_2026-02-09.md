# Position Analysis - February 9, 2026

## Executive Summary

Both trading bots are running but **no new positions have been opened since February 6** due to different issues:

1. **Event Trader**: No recent news events available (GDELT collector stale)
2. **Price Level Trader**: Maxed out on exposure limits

---

## Current Position Status

### Event Trader (trader.py)
- **Last position opened**: February 6, 2026 at 08:50 (3 days ago)
- **Total positions in DB**: 7
  - 6 OPEN positions
  - 1 CLOSED position (stopped out)
- **Recent positions**:
  - Feb 6: BTC $30k dip (NO @ 0.815)
  - Feb 5: ETH $800 dip (NO @ 0.805)
  - Feb 5: ETH $7k (YES @ 0.08)
  - Feb 5: ETH $7.5k (YES @ 0.08)
  - Feb 5: BTC $25k dip (NO @ 0.86)
  - Feb 5: BTC $150k (YES @ 0.115)

### Price Level Trader (trader_price_levels.py)
- **Total positions**: 7 (6 OPEN, unknown closed)
- **Current exposure**: $56.37 deployed
- **Unrealized P&L**: -$1.07 (-1.9%)
- **Asset breakdown**:
  - BTC: 3 positions, $29.36 (13% of capital)
  - ETH: 3 positions, $27.01 (12% of capital)

---

## Root Causes: Why No New Positions?

### Issue #1: Event Trader - No Recent Events

**Problem**: GDELT news collector hasn't collected new events since Feb 7, 20:32

**Evidence**:
```
Latest event in database: 2026-02-08T15:00:00 (28 hours old)
Event lookback window: 6 hours (config.json: event_lookback_hours: 6)
Result: NO events found in lookback window
```

**Bot logs show**:
```
2026-02-09 10:53:55 - Found 0 recent events
2026-02-09 10:53:55 - Filtered to 0 crypto-related events
2026-02-09 10:53:56 - Matched 0 event-market pairs
2026-02-09 10:53:56 - Processed 0 signals
```

**GDELT Collector Status**:
- Process running: ✅ (PID 4267, started Saturday 8pm)
- Database size: 19GB
- Total events: 7,499,519
- Last log entry: Feb 7, 20:32 - "No new events (all files already processed)"
- Collector appears stuck - running backfill but not collecting new 15-min files

**Impact**: Without events, the event-based trader cannot generate any signals

### Issue #2: Price Level Trader - Exposure Limits Reached

**Problem**: All exposure limits maxed out, blocking new positions

**Bot logs show**:
```
2026-02-09 10:29:22 - ML Signal: BUY YES (edge: +11.02%, confidence: 88.52%)
2026-02-09 10:29:22 - BLOCKED by exposure limits: Max BTC positions exceeded (3/3)

2026-02-09 10:29:27 - ML Signal: BUY YES (edge: +19.35%, confidence: 82.35%)
2026-02-09 10:29:27 - BLOCKED: Max BTC positions exceeded (3/3)

2026-02-09 10:29:39 - ML Signal: BUY NO (edge: -26.67%, confidence: 73.33%)
2026-02-09 10:29:39 - BLOCKED: Max ETH positions exceeded (3/3)
```

**Current Exposure Limits** (config_price_levels.json):
```json
"exposure_limits": {
  "max_positions_per_asset": 3,           ← MAXED OUT (BTC: 3/3, ETH: 3/3)
  "max_capital_per_asset_pct": 0.40,      ← OK (BTC: 13%, ETH: 12%)
  "max_same_direction_pct": 0.80,         ← OK
  "min_strike_distance_pct": 0.10,        ← OK
  "max_positions_same_expiry_week": 2,    ← VIOLATED (7 positions in 2027-W00)
  "max_total_positions": 10,              ← OK (6/10)
  "max_capital_deployed_pct": 0.70        ← OK (25%)
}
```

**Issues**:
1. All 6 positions expire in the same week (Dec 31, 2026 - 2027-W00)
2. Limit is 2 positions per expiry week, but have 7 in that week
3. Cannot open new positions until:
   - Existing positions close (stop loss, take profit, or expiry)
   - OR configuration is changed

**Impact**: Bot is finding good signals (11-19% edge) but cannot execute

---

## API/Data Issues

### Polymarket API Errors
Both bots show repeated 401 Unauthorized and 404 Not Found errors:

```
Error fetching trades for token_id: 401 Client Error: Unauthorized
Error fetching orderbook for token_id: 404 Client Error: Not Found
```

**Root Cause**: These are NOT blocking - the bot expects some tokens to not have orderbook/trade data. This is normal for:
- Low-liquidity markets
- Markets that are closed
- Markets with outdated token IDs

---

## Recommendations

### Priority 1: Fix GDELT Collector (Event Trader)

**Option A: Restart the collector**
```bash
# Stop the current backfill process
pkill -f "alchemy_collector.py"

# Start fresh GDELT collector for recent events
nohup python3 gdelt_collector.py >> gdelt_collection.out 2>&1 &
```

**Option B: Increase event lookback window** (quick fix)
Edit config.json:
```json
"event_lookback_hours": 48  // Increase from 6 to 48 hours
```
This would find the events from Feb 8, but doesn't solve the root issue.

**Option C: Use RSS feeds instead of GDELT**
The RSS feeds in config.json might be more reliable:
```json
"rss_feeds": [
  "https://www.coindesk.com/arc/outboundfeeds/rss/",
  "https://cointelegraph.com/rss",
  "https://decrypt.co/feed"
]
```
Check if RSS feed parsing is working.

### Priority 2: Adjust Price Level Exposure Limits

**Option A: Increase per-asset limit** (conservative)
```json
"max_positions_per_asset": 5  // Increase from 3 to 5
```

**Option B: Increase expiry week diversification** (recommended)
```json
"max_positions_same_expiry_week": 4  // Increase from 2 to 4
```

**Option C: Close underperforming positions**
Review the 6 open positions and close those with negative P&L or low conviction.

### Priority 3: Monitor Position Performance

Current positions summary:
- Total P&L: -$1.07 unrealized
- Mix of profitable and losing positions
- All expire Dec 31, 2026 (10+ months away)

Consider implementing:
- Weekly expiry diversification (look for markets expiring sooner)
- Trailing stop losses to protect profits
- Regular rebalancing when limits are reached

---

## Database Status

| Database | Size | Status | Notes |
|----------|------|--------|-------|
| gdelt_news.db | 19GB | ⚠️ STALE | Last event: Feb 8, 15:00 (28h old) |
| alchemy_trades.db | 485MB | ✅ OK | Backfill running |
| positions.db | 12KB | ✅ OK | 7 positions (event trader) |
| positions_price_level.db | 12KB | ✅ OK | 7 positions (price trader) |
| price_tracking.db | 7.3MB | ✅ OK | Active tracking |

---

## Next Steps

1. **Immediate**: Restart GDELT collector to get fresh events
2. **Short-term**: Adjust exposure limits to allow new price-level positions
3. **Medium-term**: Review and close underperforming positions
4. **Long-term**: Improve event collection reliability (RSS fallback, monitoring)
