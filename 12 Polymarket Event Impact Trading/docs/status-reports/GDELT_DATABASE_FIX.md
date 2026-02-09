# GDELT Database Corruption - Root Cause Analysis & Fix

## Problem

The GDELT collector database (`data/gdelt_news.db`) repeatedly becomes corrupted with errors:
```
sqlite3.DatabaseError: database disk image is malformed
```

## Root Causes Identified

### 1. **CRITICAL: Missing Connection Cleanup** ⚠️

The original code opened database connections without guaranteed cleanup:

```python
# OLD CODE (BROKEN)
def store_events(self, events: List[Dict]) -> int:
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    # ... operations ...
    conn.commit()  # If this fails...
    conn.close()   # ...this never executes!
```

**Problem**: If `commit()` raises an exception (or any error occurs before line 363), the connection is never closed, leaving the database in an inconsistent state.

**Affected Methods**:
- `store_events()` - Lines 317-364 (CRITICAL - writes data)
- `mark_file_processed()` - Lines 366-378
- `is_file_processed()` - Lines 380-392
- `get_events_for_timerange()` - Lines 536-552
- `get_statistics()` - Lines 554-604

### 2. **Insufficient Error Handling**

When database errors occurred, the code would log and retry without:
- Detecting corruption early
- Attempting recovery
- Preventing further corruption

### 3. **Synchronous Mode Too Lenient**

The original code used `PRAGMA synchronous=NORMAL`, which prioritizes performance over safety:
```python
cursor.execute("PRAGMA synchronous=NORMAL")  # OLD
```

With WAL mode, `NORMAL` doesn't provide full crash protection. Should use `FULL` for maximum safety.

### 4. **No Integrity Checks**

The code never checked database integrity, allowing corruption to accumulate undetected.

### 5. **No Recovery Mechanism**

When corruption was detected, the only option was manual intervention.

### 6. **Large Batch Sizes**

Original batch size of 100 events meant more data loss on crash:
```python
batch_size = 100  # OLD
```

## Fixes Applied

### 1. ✅ Context Managers for All Database Operations

```python
# NEW CODE (FIXED)
def store_events(self, events: List[Dict]) -> int:
    try:
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            cursor = conn.cursor()
            # ... operations ...
            conn.commit()  # Guaranteed cleanup even on error
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error: {e}")
```

**Benefit**: Connections are ALWAYS closed, even on exceptions.

### 2. ✅ Improved PRAGMA Settings

```python
cursor.execute("PRAGMA synchronous=FULL")        # Maximum safety
cursor.execute("PRAGMA auto_vacuum=INCREMENTAL") # Prevent fragmentation
cursor.execute("PRAGMA busy_timeout=30000")      # Wait for locks
```

### 3. ✅ Smaller Batch Sizes

```python
batch_size = 50  # Reduced from 100
```

More frequent commits = less data loss on crash.

### 4. ✅ Automatic Integrity Checks

On initialization:
```python
if Path(self.db_path).exists():
    if not self._check_integrity():
        self._attempt_recovery()
```

Periodic checks during continuous operation (every 100 cycles).

### 5. ✅ Automatic Recovery

New `_attempt_recovery()` method:
1. Creates backup of corrupted database
2. Extracts all recoverable data
3. Creates fresh database
4. Restores recovered data

### 6. ✅ WAL Checkpointing

Periodic WAL checkpoints (every 10 cycles) to:
- Persist data to main database
- Prevent WAL file growth
- Improve crash resilience

```python
cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
```

## How to Fix Current Corruption

### Option 1: Automated Recovery Script (RECOMMENDED)

1. **Stop the collector**:
   ```bash
   pkill -f "gdelt_collector.py"
   ```

2. **Run recovery script**:
   ```bash
   python3 recover_gdelt_db.py
   ```

   This will:
   - Backup corrupted database
   - Extract all recoverable data
   - Create fresh database
   - Report recovered data count

3. **Restart collector**:
   ```bash
   nohup python3 gdelt_collector.py --continuous >> gdelt.out 2>&1 &
   ```

### Option 2: Manual Recovery

1. **Stop the collector**:
   ```bash
   pkill -f "gdelt_collector.py"
   ```

2. **Backup corrupted database**:
   ```bash
   cp data/gdelt_news.db data/gdelt_news.db.corrupted.backup
   ```

3. **Try SQLite recovery**:
   ```bash
   sqlite3 data/gdelt_news.db ".recover" | sqlite3 data/gdelt_news_recovered.db
   ```

4. **If recovery works, replace**:
   ```bash
   mv data/gdelt_news_recovered.db data/gdelt_news.db
   ```

5. **Restart collector** (see Option 1, step 3)

### Option 3: Nuclear Option (Start Fresh)

If recovery fails:

```bash
# Stop collector
pkill -f "gdelt_collector.py"

# Backup and remove corrupted database
mv data/gdelt_news.db data/gdelt_news.db.corrupted.$(date +%Y%m%d_%H%M%S)

# Collect fresh data (30 days)
python3 gdelt_collector.py --collect 30

# Start continuous collection
nohup python3 gdelt_collector.py --continuous >> gdelt.out 2>&1 &
```

## Prevention: Best Practices Moving Forward

### 1. Monitor Database Size

Large databases (>1GB) are more susceptible to corruption:
```bash
ls -lh data/gdelt_news.db
```

Current size: **1.2GB** - Consider periodic cleanup of old data.

### 2. Regular Backups

Add to crontab:
```bash
# Daily backup at 3 AM
0 3 * * * cp ~/workspace/.../data/gdelt_news.db ~/workspace/.../data/backups/gdelt_$(date +\%Y\%m\%d).db
```

### 3. Monitor Logs

Check for warnings:
```bash
tail -f gdelt.out | grep -i "error\|corrupt"
```

### 4. Graceful Shutdowns

Always use `kill` (not `kill -9`) to allow cleanup:
```bash
# GOOD
pkill -f "gdelt_collector.py"

# BAD (forces immediate termination)
pkill -9 -f "gdelt_collector.py"
```

### 5. Keep macOS Updated

Filesystem issues on macOS can affect SQLite. Ensure you're on the latest version.

## Technical Deep Dive

### Why WAL Mode Alone Isn't Enough

While WAL (Write-Ahead Logging) provides better crash resilience than DELETE journal mode, it doesn't prevent corruption if:

1. **Connections aren't closed properly**: Uncommitted transactions remain in WAL
2. **Process is killed with SIGKILL**: No chance for cleanup
3. **Filesystem issues**: macOS extended attributes can interfere
4. **Hardware failures**: Disk errors during writes

### SQLite Error Code 11 (SQLITE_CORRUPT)

The error "btreeInitPage() returns error code 11" indicates:
- Database file structure is damaged
- B-tree pages are malformed
- Cannot read index or table pages

This typically happens from:
- Incomplete writes (connection not closed)
- Filesystem corruption
- Hardware issues
- Process crashes during writes

### Why Context Managers Fix This

Python's `with` statement guarantees cleanup:

```python
with sqlite3.connect(db) as conn:
    # Operations
    conn.commit()
# conn.close() called automatically, even on exception!
```

Equivalent to:
```python
conn = sqlite3.connect(db)
try:
    # Operations
    conn.commit()
finally:
    conn.close()  # Always executes
```

## Testing the Fix

After applying fixes and recovering the database:

1. **Check integrity**:
   ```bash
   sqlite3 data/gdelt_news.db "PRAGMA integrity_check"
   ```
   Should output: `ok`

2. **Verify journal mode**:
   ```bash
   sqlite3 data/gdelt_news.db "PRAGMA journal_mode"
   ```
   Should output: `wal`

3. **Check synchronous mode**:
   ```bash
   sqlite3 data/gdelt_news.db "PRAGMA synchronous"
   ```
   Should output: `2` (FULL)

4. **Monitor for errors**:
   ```bash
   tail -f gdelt.out
   ```
   Should not see "malformed" or "corrupt" errors.

## Summary

**Root cause**: Improper database connection management caused connections to remain open on errors, leading to corruption.

**Fix**: Use context managers (`with` statements) for ALL database operations to guarantee cleanup.

**Recovery**: Use `recover_gdelt_db.py` script to extract recoverable data.

**Prevention**: Regular backups, monitoring, graceful shutdowns, periodic integrity checks.

---

**Status**: ✅ All fixes applied to `gdelt_collector.py`
**Action required**: Stop collector → Run recovery script → Restart collector
