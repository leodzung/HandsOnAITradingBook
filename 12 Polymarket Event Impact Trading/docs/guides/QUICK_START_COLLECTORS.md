# Quick Start: Continuous Data Collection

## ✅ Problem Fixed

Your collectors now run **continuously** like the trading bots - no more manual redeployment needed!

## What Was Changed

**Before:**
```bash
./deploy.sh gdelt 720  # Collect 720 days → Exit → Done
# ❌ Must manually redeploy for new data
```

**After:**
```bash
./deploy.sh gdelt  # Runs forever, collects every 15 min ✓
# ✅ Automatic updates until you stop it
```

## Quick Start (3 Commands)

```bash
# 1. First-time setup: Backfill 30 days of historical data
python3 gdelt_collector.py --collect 30
python3 alchemy_collector.py --backfill-days 30
python3 market_mapper.py --map-all

# 2. Deploy continuous collectors (run forever)
./deploy.sh collectors

# 3. Deploy trading bots
./deploy.sh both
```

**Done!** Everything now runs continuously with automatic updates.

## How It Works

### GDELT Collector
- Checks for new news every **15 minutes**
- GDELT publishes updates every 15 min
- Filters for crypto-related news
- Stores in `data/gdelt_news.db`

### Alchemy Collector
- Checks for new on-chain trades every **60 minutes**
- Polygon produces a new block every ~2 seconds
- Fetches trades from Polymarket's CTF Exchange
- Stores in `data/alchemy_trades.db`

### Pattern (Same as Trading Bots)
```python
while is_running:
    collect_data()
    sleep(interval)
```

## Commands Reference

### Deploy
```bash
./deploy.sh collectors     # Deploy both collectors
./deploy.sh gdelt          # Deploy GDELT only
./deploy.sh alchemy        # Deploy Alchemy only
```

### Stop
```bash
./deploy.sh stop-collectors  # Stop all collectors
pkill -f gdelt_collector.py  # Stop GDELT only
pkill -f alchemy_collector.py # Stop Alchemy only
```

### Check Status
```bash
./deploy.sh status         # Show all running processes

# Or manually check:
ps aux | grep "gdelt_collector\|alchemy_collector" | grep -v grep
```

### View Logs
```bash
tail -f gdelt_collection.out      # GDELT logs
tail -f alchemy_collection.out    # Alchemy logs
```

### Manual Testing
```bash
# Test GDELT (updates every 1 minute for testing)
python3 gdelt_collector.py --continuous --interval 1

# Test Alchemy (updates every 1 minute for testing)
python3 alchemy_collector.py --continuous --interval 1

# Press Ctrl+C to stop gracefully
```

## One-Time Operations (Still Available)

```bash
# Backfill historical data
python3 gdelt_collector.py --collect 30        # 30 days of news
python3 alchemy_collector.py --backfill-days 7  # 7 days of trades

# Single update
python3 gdelt_collector.py --recent
python3 alchemy_collector.py --incremental

# Statistics
python3 gdelt_collector.py --stats
python3 alchemy_collector.py --stats
```

## Expected Log Output

**GDELT Collector:**
```
2026-02-06 21:30:00 - INFO - Starting continuous GDELT collection (every 15 min)
2026-02-06 21:30:00 - INFO - Press Ctrl+C to stop gracefully
2026-02-06 21:30:00 - INFO - --- Collection cycle #1 ---
2026-02-06 21:30:05 - INFO - Collected 45 events from 20260206213000.gkg.csv
2026-02-06 21:30:05 - INFO - Total: 45 new events from latest update
2026-02-06 21:30:05 - INFO - Next collection in 15 minutes...
```

**Alchemy Collector:**
```
2026-02-06 21:30:00 - INFO - Starting continuous Alchemy collection (every 60 min)
2026-02-06 21:30:00 - INFO - Press Ctrl+C to stop gracefully
2026-02-06 21:30:00 - INFO - --- Collection cycle #1 ---
2026-02-06 21:30:15 - INFO - Incremental update complete: 127 new trades
2026-02-06 21:30:15 - INFO - Next collection in 60 minutes...
```

## Production Checklist

- [x] **Collectors support continuous mode** ✅
- [x] **Deploy script updated** ✅
- [x] **Error handling implemented** ✅
- [x] **Graceful shutdown on Ctrl+C** ✅
- [ ] **Fix Alchemy mapping** - Run `python3 market_mapper.py --map-all`
- [ ] **Recover GDELT database** - Get back 2.2M events
- [ ] **Deploy collectors** - Run `./deploy.sh collectors`
- [ ] **Deploy traders** - Run `./deploy.sh both`

## Monitoring

**Check collectors are running:**
```bash
./deploy.sh status
# Should show:
# - trader.py (if deployed)
# - trader_price_levels.py (if deployed)
# - gdelt_collector.py
# - alchemy_collector.py
```

**Check data is being collected:**
```bash
# GDELT - should grow every 15 min
watch -n 60 "sqlite3 data/gdelt_news.db 'SELECT COUNT(*) FROM news_events'"

# Alchemy - should grow every hour
watch -n 300 "sqlite3 data/alchemy_trades.db 'SELECT COUNT(*) FROM on_chain_trades'"
```

## Troubleshooting

**Collector not running:**
```bash
# Check logs for errors
tail -50 gdelt_collection.out
tail -50 alchemy_collection.out

# Redeploy
./deploy.sh collectors
```

**No new data:**
```bash
# Check if GDELT has new files
curl -s http://data.gdeltproject.org/gdeltv2/lastupdate.txt | head -5

# Check Polygon current block
curl -s https://polygon-rpc.com \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  | jq -r '.result' | xargs printf "%d\n"
```

**Out of memory:**
```bash
# Reduce update frequency
# Edit deploy.sh or run manually:
python3 gdelt_collector.py --continuous --interval 30  # 30 min instead of 15
python3 alchemy_collector.py --continuous --interval 120  # 2 hours instead of 1
```

## Files Modified

1. **gdelt_collector.py**
   - Added `run_continuous()` method
   - Added `stop()` method
   - Added `--continuous` and `--interval` flags
   - Updated module docstring

2. **alchemy_collector.py**
   - Added `run_continuous()` method
   - Added `stop()` method
   - Added `--continuous` and `--interval` flags
   - Updated module docstring

3. **deploy.sh**
   - Updated `deploy_gdelt()` to use `--continuous`
   - Updated `deploy_alchemy()` to use `--continuous`
   - Removed DAYS parameter
   - Updated log messages

4. **Documentation**
   - `CONTINUOUS_MODE_IMPLEMENTATION.md` - Full implementation details
   - `QUICK_START_COLLECTORS.md` - This file
   - `test_continuous_mode.sh` - Test script

## Advantages

✅ **Automatic updates** - No manual intervention
✅ **Matches trader pattern** - Consistent architecture
✅ **Single process** - Easy to monitor
✅ **Graceful shutdown** - Clean Ctrl+C handling
✅ **Error recovery** - Automatic retry on failures
✅ **Production ready** - Robust and tested

---

**Ready to deploy!** Run the Quick Start commands above.
