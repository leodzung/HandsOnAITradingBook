# Database Corruption - Root Cause Analysis & Fix

**Date:** 2026-02-07
**Issue:** GDELT collector database repeatedly corrupts with "database disk image is malformed"

## Root Cause

### The Problem
Database corruption was caused by **multiple processes running simultaneously**, not by a bug in the collector code itself.

### Evidence

1. **Duplicate Processes Running:**
```
PID     Started         Running For    CPU     Process
45159   Feb 1 18:07     5 days 15hr    198% ⚠️  trader.py
86925   Feb 5 22:27     1 day  11hr    199% ⚠️  trader.py
45095   Feb 1 18:07     5 days 15hr    Normal   trader_price_levels.py
87123   Feb 5 22:27     1 day  11hr    Normal   trader_price_levels.py
```

Two `trader.py` processes consuming 198-199% CPU indicate:
- Processes stuck in infinite loops
- Likely starving disk I/O
- Zombie processes from failed restarts

2. **GDELT Collector Restart Pattern (gdelt.out):**
```
09:23:51 - Started, collected 285 events ✓
09:37:14 - Database corrupted! Recovery attempted
09:40:03 - Started again (duplicate instance)
09:41:10 - Started again (another duplicate)
09:45:14 - Corrupted again! Recovery attempted
09:46:53 - Started again (current instance)
```

6 restarts in 30 minutes = multiple concurrent instances accessing the same database

3. **Corruption Pattern:**
The error occurs in `store_events()` at line 362, during batch writes:
```python
sqlite3.DatabaseError: database disk image is malformed
```

This specific error indicates **concurrent writes** or **interrupted I/O operations**.

## Why This Happened

### Sequence of Events:
1. User noticed issues and restarted collectors (likely multiple times)
2. Old processes didn't die cleanly, remained as zombies
3. New instances started while old ones still running
4. Multiple processes tried to write to `gdelt_news.db` simultaneously
5. SQLite corruption occurred due to:
   - Concurrent writes from multiple collector instances
   - High CPU from zombie trader.py processes starving disk I/O
   - Interrupted writes during process kills

### Why SQLite Corrupted:
Even with proper PRAGMA settings:
```python
PRAGMA journal_mode=DELETE
PRAGMA busy_timeout=30000
PRAGMA synchronous=FULL
```

SQLite can still corrupt if:
- Multiple processes write simultaneously (race condition)
- Process crashes during transaction
- Disk I/O is starved (high CPU usage)
- macOS file system quirks with concurrent access

## The Fix

### Immediate Actions (fix_processes_and_db.sh)

1. **Kill all duplicate processes:**
```bash
pkill -f "trader.py"
pkill -f "trader_price_levels.py"
pkill -f "gdelt_collector.py"
```

2. **Verify database integrity:**
```bash
sqlite3 data/gdelt_news.db "PRAGMA integrity_check;"
```

3. **Recover data if corrupted:**
```bash
sqlite3 data/gdelt_news.db ".dump" | sqlite3 data/gdelt_news_recovered.db
```

4. **Use safe restart script:**
```bash
./restart_all.sh  # Only starts if not already running
```

### Long-term Prevention

#### 1. Process Lock (add_process_lock.py)
Adds a PID file mechanism to `gdelt_collector.py`:
- Prevents duplicate instances from starting
- Automatically cleans up stale locks
- Fails gracefully if already running

```python
class ProcessLock:
    """Simple PID file lock to prevent duplicate processes."""
    # Creates data/gdelt_collector.lock with PID
    # Checks if process is alive before allowing start
```

#### 2. Process Monitoring (check_processes.sh)
Daily health check:
```bash
./check_processes.sh
```
Detects:
- Duplicate processes
- High CPU processes (>50%)
- Stale log files

#### 3. Safe Restart Procedure
**Never** use `nohup python3 ...` directly. Always use:
```bash
./restart_all.sh
```

Which ensures:
1. No duplicates are running
2. Processes start in correct order
3. Logs are properly rotated

## Testing the Fix

### 1. Apply the fix:
```bash
chmod +x fix_processes_and_db.sh
./fix_processes_and_db.sh
```

### 2. Apply process lock:
```bash
python3 add_process_lock.py
```

### 3. Restart safely:
```bash
./restart_all.sh
```

### 4. Monitor for 1 hour:
```bash
# Terminal 1: Watch logs
tail -f gdelt_collection.out

# Terminal 2: Check processes every 5 min
watch -n 300 ./check_processes.sh

# Terminal 3: Monitor database size
watch -n 60 'ls -lh data/gdelt_news.db'
```

### 5. Verify no corruption:
```bash
# After 1 hour
sqlite3 data/gdelt_news.db "PRAGMA integrity_check;"
# Should output: ok
```

## Prevention Checklist

- [ ] Kill all old processes before restarting
- [ ] Always use `restart_all.sh` to start processes
- [ ] Run `check_processes.sh` daily
- [ ] Monitor log files for "already running" warnings
- [ ] Check database integrity weekly
- [ ] Keep only 1 instance of each process running

## Why Previous "Fixes" Failed

If you previously:
- Restarted the collector manually → Created duplicates
- Changed database settings → Didn't address root cause
- Restored from backup → Didn't kill zombie processes
- Added recovery logic → Masked the symptom, not the cause

The real issue was **process management**, not database code.

## Future Improvements

Consider:
1. **Systemd/launchd service** - Proper process supervision
2. **Docker containers** - Process isolation
3. **Separate databases per process** - No shared writes
4. **Database connection pooling** - Better concurrency handling
5. **Prometheus metrics** - Real-time process monitoring

## Key Takeaway

**Database corruption was a symptom, not the disease.**

The disease was: **Uncontrolled process proliferation**

The cure: **Process locking + safe restart procedures**
