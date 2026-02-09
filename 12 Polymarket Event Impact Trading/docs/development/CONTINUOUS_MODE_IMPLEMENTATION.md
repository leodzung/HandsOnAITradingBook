# Continuous Mode Implementation - Complete

## Summary

Both GDELT and Alchemy collectors now support **continuous mode** - they run indefinitely like the trading bots, collecting data automatically at regular intervals.

## What Changed

### 1. GDELT Collector (`gdelt_collector.py`)

**New Features:**
- ✅ `--continuous` flag - Runs forever, collecting updates every 15 minutes
- ✅ `--interval` option - Customize update frequency (default: 15 min)
- ✅ Graceful shutdown on Ctrl+C
- ✅ Error recovery - Retries after failures
- ✅ Collection cycle counter - Tracks progress

**Updated Methods:**
- `__init__()` - Added `is_running` flag
- `collect_recent()` - Improved to handle multiple files per update
- `run_continuous()` - NEW - Main continuous loop
- `stop()` - NEW - Graceful shutdown
- `main()` - Added `--continuous` and `--interval` flags

### 2. Alchemy Collector (`alchemy_collector.py`)

**New Features:**
- ✅ `--continuous` flag - Runs forever, collecting updates every hour
- ✅ `--interval` option - Customize update frequency (default: 60 min)
- ✅ Graceful shutdown on Ctrl+C
- ✅ Error recovery - Retries after failures
- ✅ Collection cycle counter - Tracks progress

**Updated Methods:**
- `__init__()` - Added `is_running` flag
- `run_continuous()` - NEW - Main continuous loop
- `stop()` - NEW - Graceful shutdown
- `main()` - Added `--continuous` and `--interval` flags

### 3. Deploy Script (`deploy.sh`)

**Updated:**
- `deploy_gdelt()` - Now uses `--continuous` instead of `--collect DAYS`
- `deploy_alchemy()` - Now uses `--continuous` instead of `--backfill-days DAYS`
- Removed DAYS parameter from function signatures
- Updated all function calls
- Changed log file names: `alchemy_backfill.out` → `alchemy_collection.out`

## Usage

### Running Collectors Manually

**GDELT Collector:**
```bash
# Continuous mode (recommended for production)
python3 gdelt_collector.py --continuous

# Custom interval (every 30 minutes)
python3 gdelt_collector.py --continuous --interval 30

# One-time historical backfill (still available)
python3 gdelt_collector.py --collect 30

# Single update (still available)
python3 gdelt_collector.py --recent
```

**Alchemy Collector:**
```bash
# Continuous mode (recommended for production)
python3 alchemy_collector.py --continuous

# Custom interval (every 30 minutes)
python3 alchemy_collector.py --continuous --interval 30

# One-time historical backfill (still available)
python3 alchemy_collector.py --backfill-days 30

# Single update (still available)
python3 alchemy_collector.py --incremental
```

### Using Deploy Script

**Deploy GDELT collector:**
```bash
./deploy.sh gdelt
# Deploys in continuous mode (updates every 15 min)
```

**Deploy Alchemy collector:**
```bash
./deploy.sh alchemy
# Deploys in continuous mode (updates every hour)
```

**Deploy both collectors:**
```bash
./deploy.sh collectors
# Deploys both in continuous mode
```

**Stop collectors:**
```bash
./deploy.sh stop-collectors
```

## Behavior Comparison

### Before (Batch Mode)
```
┌─────────────────────────────────────┐
│ Run: ./deploy.sh gdelt 30          │
│                                     │
│ Collector: Collect 30 days → Exit  │
│                                     │
│ ❌ NO MORE UPDATES                 │
│                                     │
│ Must redeploy manually for updates │
└─────────────────────────────────────┘
```

### After (Continuous Mode)
```
┌─────────────────────────────────────┐
│ Run: ./deploy.sh gdelt              │
│                                     │
│ Collector: Loop forever {           │
│   - Collect latest updates          │
│   - Sleep 15 minutes                │
│   - Repeat                          │
│ }                                   │
│                                     │
│ ✅ AUTOMATIC UPDATES FOREVER        │
│                                     │
│ Runs until killed                   │
└─────────────────────────────────────┘
```

## Pattern Consistency

All long-running processes now follow the same pattern:

| Component | Pattern | Update Frequency |
|-----------|---------|------------------|
| **trader.py** | Continuous loop | Every 5 minutes |
| **trader_price_levels.py** | Continuous loop | Every 5 minutes |
| **gdelt_collector.py** | Continuous loop | Every 15 minutes |
| **alchemy_collector.py** | Continuous loop | Every 60 minutes |

## Production Deployment

**Recommended workflow:**

1. **First time setup** - Backfill historical data:
   ```bash
   # Backfill 30 days of GDELT news
   python3 gdelt_collector.py --collect 30

   # Backfill 30 days of on-chain trades
   python3 alchemy_collector.py --backfill-days 30

   # Map trades to markets
   python3 market_mapper.py --map-all
   ```

2. **Deploy continuous collectors:**
   ```bash
   ./deploy.sh collectors
   ```

3. **Deploy trading bots:**
   ```bash
   ./deploy.sh both
   ```

4. **Monitor:**
   ```bash
   # Check status
   ./deploy.sh status

   # Tail logs
   tail -f gdelt_collection.out
   tail -f alchemy_collection.out
   tail -f trading.out
   tail -f trading_price_levels.out
   ```

## Error Handling

Both collectors implement robust error handling:

**Network Errors:**
- Catches `RequestException`
- Logs error
- Waits 1 minute
- Retries automatically

**Keyboard Interrupt:**
- Catches `Ctrl+C`
- Calls `stop()` method
- Logs graceful shutdown
- Exits cleanly

**Unknown Errors:**
- Catches all exceptions
- Logs full traceback
- Waits 1 minute
- Retries automatically

## Monitoring

**Check if collectors are running:**
```bash
ps aux | grep "gdelt_collector.py\|alchemy_collector.py" | grep -v grep
```

**View recent activity:**
```bash
# GDELT - should show cycle every 15 min
tail -20 gdelt_collection.out

# Alchemy - should show cycle every 60 min
tail -20 alchemy_collection.out
```

**Expected log output:**
```
2026-02-06 21:30:00 - INFO - Starting continuous GDELT collection (every 15 min)
2026-02-06 21:30:00 - INFO - Press Ctrl+C to stop gracefully
2026-02-06 21:30:00 - INFO - --- Collection cycle #1 ---
2026-02-06 21:30:05 - INFO - Collected 45 events from 20260206213000.gkg.csv
2026-02-06 21:30:05 - INFO - Total: 45 new events from latest update
2026-02-06 21:30:05 - INFO - Next collection in 15 minutes...
```

## Backward Compatibility

✅ **All existing functionality preserved:**
- One-time backfill still works (`--collect`, `--backfill-days`)
- Single update still works (`--recent`, `--incremental`)
- Statistics still work (`--stats`)
- Export still works (`--export`)

✅ **No breaking changes:**
- Existing scripts can continue using batch mode
- training_pipeline.py unaffected
- All database schemas unchanged

## Advantages Over Cron

| Aspect | Continuous Mode | Cron Jobs |
|--------|----------------|-----------|
| **Process Count** | 1 | Many |
| **Monitoring** | Easy (single PID) | Hard (multiple PIDs) |
| **Error Recovery** | Automatic retry | Depends on script |
| **Graceful Shutdown** | ✅ Yes | ❌ No |
| **Resource Usage** | Lower | Higher |
| **Deployment** | Single command | Edit crontab |
| **Logs** | Single file | Multiple files |

## Testing

To verify the implementation works:

```bash
# Test GDELT continuous mode (press Ctrl+C after 30 seconds)
python3 gdelt_collector.py --continuous --interval 1

# Test Alchemy continuous mode (press Ctrl+C after 30 seconds)
python3 alchemy_collector.py --continuous --interval 1

# Should see:
# - "Starting continuous collection" message
# - First cycle completes
# - "Next collection in X minutes" message
# - Graceful shutdown on Ctrl+C
```

## Next Steps

1. ✅ **Fixed token mapping** - Run `python3 market_mapper.py --map-all`
2. ✅ **Continuous collectors implemented** - Deploy with `./deploy.sh collectors`
3. ⏭️ **Recover GDELT database** - Get back 2.2M events
4. ⏭️ **Deploy to production** - Start all bots with continuous data collection

---

**Status:** ✅ Implementation Complete
**Author:** Claude Code
**Date:** 2026-02-06
