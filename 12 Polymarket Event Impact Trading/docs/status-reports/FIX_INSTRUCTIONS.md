# Fix Instructions - Database Corruption Issue

## TLDR - Root Cause
**You have duplicate processes running** (2x trader.py, 2x trader_price_levels.py) consuming 198-199% CPU. These zombie processes are causing database corruption by:
1. Concurrent writes to gdelt_news.db
2. Starving disk I/O (high CPU)
3. Creating race conditions during restarts

**This is why logs stopped** - the collector keeps corrupting and restarting.

## Quick Fix (5 minutes)

```bash
# Step 1: Stop everything
./fix_processes_and_db.sh

# Step 2: Add process lock protection
python3 add_process_lock.py

# Step 3: Restart safely
./restart_all.sh

# Step 4: Verify
./check_processes.sh
tail -f gdelt_collection.out
```

## What Each Script Does

### 1. fix_processes_and_db.sh
**Purpose:** Clean up zombie processes and corrupted database

**Actions:**
- Kills ALL trader and collector processes (including duplicates)
- Checks database integrity
- Recovers data if corrupted
- Creates `restart_all.sh` and `check_processes.sh`

**Output:**
```
✓ All processes stopped
✓ Database integrity OK (or recovered)
✓ Created restart_all.sh
✓ Created check_processes.sh
```

### 2. add_process_lock.py
**Purpose:** Prevent duplicate collector instances

**Actions:**
- Adds ProcessLock class to gdelt_collector.py
- Creates PID file locking mechanism
- Prevents duplicate instances from starting

**Safety:** Backs up original file first

### 3. restart_all.sh (created by fix script)
**Purpose:** Safe process launcher

**Features:**
- Only starts if not already running
- Starts processes in correct order
- Shows PID for each process

**Usage:**
```bash
./restart_all.sh
```

### 4. check_processes.sh (created by fix script)
**Purpose:** Health monitoring

**Checks:**
- Duplicate processes (should be 0)
- High CPU usage (flags >50%)
- Recent log activity

**Usage:**
```bash
./check_processes.sh
```

## Detailed Execution

### Step 1: Stop Everything
```bash
./fix_processes_and_db.sh
```

**Expected output:**
```
=== Polymarket Process & Database Fix ===

Step 1: Stopping all trading and collection processes...
✓ All processes stopped

Step 2: Backing up current database...
✓ Backup created: data/gdelt_news.db.backup_20260207_095300

Step 3: Checking database integrity...
✓ Database integrity OK
(or)
⚠️  Database corrupted! Attempting recovery...
✓ Database restored

Step 4: Creating safe process launcher...
✓ Created restart_all.sh

Step 5: Creating process monitor...
✓ Created check_processes.sh

=== Fix Complete ===

Next steps:
1. Run: ./restart_all.sh
2. Run: ./check_processes.sh
3. Monitor: tail -f gdelt_collection.out
```

### Step 2: Add Process Lock
```bash
python3 add_process_lock.py
```

**Expected output:**
```
=== Adding Process Lock to GDELT Collector ===

✓ Backed up original to: gdelt_collector.py.before_lock
✓ Added ProcessLock to gdelt_collector.py
  - Prevents duplicate instances from running
  - Automatically cleans up stale lock files
  - Safe for production use

✓ Patch complete!
```

### Step 3: Restart Safely
```bash
./restart_all.sh
```

**Expected output:**
```
=== Starting Polymarket Processes ===

Starting gdelt_collector.py --continuous...
✓ Started gdelt_collector.py (PID: 12345)

Starting alchemy_collector.py --continuous...
✓ Started alchemy_collector.py (PID: 12346)

Starting trader.py...
✓ Started trader.py (PID: 12347)

Starting trader_price_levels.py...
✓ Started trader_price_levels.py (PID: 12348)

=== Process Status ===
PID   12345  Python trader.py
PID   12346  Python trader_price_levels.py
PID   12347  Python gdelt_collector.py --continuous
PID   12348  Python alchemy_collector.py --continuous
```

### Step 4: Verify (Important!)
```bash
./check_processes.sh
```

**Expected output:**
```
=== Process Health Check ===

✓ trader.py: 1 instance running
✓ trader_price_levels.py: 1 instance running
✓ gdelt_collector.py: 1 instance running
✓ alchemy_collector.py: 1 instance running

=== High CPU Processes ===
None

=== Recent Log Activity ===
trading.out: 2026-02-07 09:55:00 - INFO - Starting trading cycle
trading_price_levels.out: 2026-02-07 09:55:00 - INFO - Starting
gdelt_collection.out: 2026-02-07 09:55:00 - INFO - Collection cycle #1
alchemy_collection.out: 2026-02-07 09:55:00 - INFO - Collection cycle #1
```

**If you see duplicates:**
```
⚠️  WARNING: 2 instances of trader.py running (should be 1)
```
Run `./fix_processes_and_db.sh` again.

### Step 5: Monitor
```bash
tail -f gdelt_collection.out
```

**You should see:**
```
2026-02-07 09:55:00,123 - INFO - Process lock acquired: data/gdelt_collector.lock
2026-02-07 09:55:00,124 - INFO - Starting continuous GDELT collection (every 15 min)
2026-02-07 09:55:00,125 - INFO - --- Collection cycle #1 ---
2026-02-07 09:55:01,234 - INFO - Collected 150 events from 20260207175500.gkg.csv.zip
2026-02-07 09:55:01,235 - INFO - Total: 150 new events from latest update
2026-02-07 09:55:01,236 - INFO - Next collection in 15 minutes...
```

**If successful:**
- No corruption errors
- Events being collected (>0)
- Logs continue updating every 15 minutes

## Troubleshooting

### Problem: "Another instance is already running"
```
2026-02-07 09:55:00 - ERROR - Another instance is already running. Exiting.
```

**Cause:** Lock file exists from previous run

**Fix:**
```bash
# Check if process actually running
ps aux | grep gdelt_collector

# If not running, remove stale lock
rm data/gdelt_collector.lock

# Restart
./restart_all.sh
```

### Problem: Database still corrupting
```
sqlite3.DatabaseError: database disk image is malformed
```

**Check:**
```bash
# 1. Verify no duplicates
./check_processes.sh

# 2. Check CPU usage
top -o cpu | head -20

# 3. Check disk space
df -h data/

# 4. If still failing, start fresh
mv data/gdelt_news.db data/gdelt_news.db.old
./restart_all.sh
```

### Problem: Alchemy collector not logging
```
alchemy_collection.out: Last log from Feb 6 23:00
```

**Fix:**
```bash
# Check if running
ps aux | grep alchemy_collector

# If not running (likely crashed)
./restart_all.sh

# Monitor
tail -f alchemy_collection.out
```

## Daily Maintenance

### Morning Check (run once daily):
```bash
./check_processes.sh
```

### If restarting needed:
```bash
# WRONG - creates duplicates
nohup python3 trader.py >> trading.out 2>&1 &

# RIGHT - prevents duplicates
pkill -f trader.py
./restart_all.sh
```

### Weekly Database Check:
```bash
sqlite3 data/gdelt_news.db "PRAGMA integrity_check;"
# Should output: ok
```

## Success Criteria

After applying fix, you should see:

1. **No duplicate processes:**
   - 1x trader.py
   - 1x trader_price_levels.py
   - 1x gdelt_collector.py
   - 1x alchemy_collector.py

2. **Normal CPU usage:**
   - trader.py: <5% CPU
   - trader_price_levels.py: <5% CPU
   - collectors: <2% CPU

3. **Logs updating:**
   - gdelt_collection.out: New entries every 15 min
   - alchemy_collection.out: New entries every 60 min
   - trading.out: New entries every 5 min

4. **No corruption errors:**
   - No "database disk image is malformed"
   - No "disk I/O error"
   - Events being collected successfully

## Files Created

- `fix_processes_and_db.sh` - Main fix script
- `add_process_lock.py` - Adds locking to collector
- `restart_all.sh` - Safe restart script (created by fix)
- `check_processes.sh` - Health monitor (created by fix)
- `DATABASE_CORRUPTION_ROOT_CAUSE.md` - Full analysis
- `FIX_INSTRUCTIONS.md` - This file

## Backup Files Created

- `data/gdelt_news.db.backup_TIMESTAMP` - Database backups
- `gdelt_collector.py.before_lock` - Original collector
- `data/gdelt_news.db.corrupted_TIMESTAMP` - Corrupted DBs

## Questions?

1. **Why did this happen?**
   - See DATABASE_CORRUPTION_ROOT_CAUSE.md

2. **Is my data lost?**
   - Backups in `data/*.backup_*`
   - Recent data recoverable
   - Collector will re-collect missing data

3. **Will this happen again?**
   - Not if you use `restart_all.sh`
   - Process lock prevents duplicates
   - Monitor with `check_processes.sh`

4. **Can I undo the changes?**
   ```bash
   mv gdelt_collector.py.before_lock gdelt_collector.py
   ```
