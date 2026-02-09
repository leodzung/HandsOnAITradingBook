# GDELT Collection Failure Analysis

## Root Cause

The `deploy.sh` script has **different default collection periods** for different collectors:

```bash
# From deploy.sh
deploy_gdelt() {
    DAYS=${1:-720}  # Default to 720 days (2 years)
    ...
}

deploy_alchemy() {
    DAYS=${1:-180}  # Default to 180 days (6 months)
    ...
}
```

## What Happened

### Run #1 (Jan 26, 2026) - ✅ SUCCESS
- **Command**: Likely `python3 gdelt_collector.py --collect 52 --max-files 5000`
- **Date Range**: 180 days found, but limited to 5,000 files
- **Files Processed**: 5,000 / 17,280 available (29%)
- **Duration**: ~6 hours
- **Result**: 2,219,519 events collected successfully

### Run #2 (Feb 1, 2026) - ❌ FAILURE

**Morning attempts (7:40 AM - 1:08 PM):**
- **Command**: `python3 gdelt_collector.py --collect 180`
- **Files**: 17,280 (all available for 180 days)
- **Status**: Multiple restarts, unclear if completed

**Evening attempt (6:11 PM):**
- **Command**: `./deploy.sh gdelt` (used default!)
- **Date Range**: 720 days (Feb 13, 2024 → Feb 2, 2026)
- **Files Found**: 67,437
- **Files Processed**: 540 before crash (0.8%)
- **Duration**: ~18 minutes before crash
- **Result**: Database corrupted

## The Problem: 720 Days Default is Too Aggressive

**File Count Comparison:**
```
Run #1: 5,000 files → 6 hours → SUCCESS
Run #2: 67,437 files → 540 processed → CRASH (0.8% complete)
```

**If Run #2 had completed:**
- Files to process: 67,437
- Rate: ~500 files/hour (based on Run #1)
- **Estimated time: 135 hours (5.6 days continuous)**
- Database size: ~15-20 GB
- Events collected: ~30 million

**Risk Factors:**
1. **Long duration**: 5+ days of continuous collection
2. **Large database**: Growing to 15+ GB
3. **No checkpointing**: 540 files of work lost on crash
4. **Memory pressure**: Processing 67k files can OOM
5. **Network issues**: 5 days of HTTP requests = high failure probability

## Why 720 Days?

Looking at the comment in deploy.sh:
```bash
DAYS=${1:-720}  # Default to 720 days (2 years)
```

This was likely set to:
- Collect comprehensive historical data
- Cover major crypto events from 2024-2026
- Build a large training dataset

However, **it's unrealistic for a single collection run**.

## Recommended Fix

Change the default to a safer value:

```bash
# BEFORE
deploy_gdelt() {
    DAYS=${1:-720}  # Default to 720 days (2 years)
    
# AFTER  
deploy_gdelt() {
    DAYS=${1:-30}  # Default to 30 days (safe for single run)
    # For larger collections, explicitly pass days: ./deploy.sh gdelt 180
```

**Why 30 days?**
- Files: ~2,880 (96 files/day × 30)
- Duration: ~6 hours (manageable)
- Safe to complete in one run
- For historical data, run multiple 30-day batches

## Safe Collection Strategy

Instead of one massive 720-day collection, use incremental batches:

```bash
# Week 1: Collect recent data
./deploy.sh gdelt 30

# Week 2: Backfill 30 more days
python3 gdelt_collector.py --collect 60  # Will only process new files

# Week 3: Continue backfilling
python3 gdelt_collector.py --collect 90

# Repeat until you have desired history
```

This approach:
- ✅ Completes each batch in 4-8 hours
- ✅ Reduces corruption risk
- ✅ Can resume after failures
- ✅ Monitors progress incrementally

## File Deduplication

The collector already has file tracking:
```python
def is_file_processed(self, filename: str) -> bool:
    """Check if a GDELT file has been processed."""
```

So you can safely run multiple collections - it won't reprocess files.

## Immediate Action Items

1. **Fix deploy.sh default**: Change 720 → 30
2. **Recover database**: Get back the 2.2M events from Jan 26
3. **Resume collection**: Use 30-day increments
4. **Add monitoring**: Alert if collection runs > 12 hours

