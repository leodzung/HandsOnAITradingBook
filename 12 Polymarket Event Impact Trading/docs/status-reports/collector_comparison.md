# Collector Design Comparison

## Current Design

### GDELT Collector (Batch Job)
**Type**: One-time batch collection
**Pattern**: Run → Collect → Exit

```python
# gdelt_collector.py
def main():
    if args.collect:
        collector.collect_crypto_news(days_back=args.collect)
        return  # ← EXITS after collection
```

**Deployment**:
```bash
nohup python3 gdelt_collector.py --collect 720 >> gdelt_collection.out 2>&1 &
# Runs once, collects 720 days, then exits
```

**How to get incremental updates**: 
❌ **NOT AUTOMATIC** - Must manually redeploy each time

### Alchemy Collector (Same Pattern)
**Type**: One-time batch collection  
**Pattern**: Run → Collect → Exit

```python
# alchemy_collector.py
def main():
    if args.incremental:
        collector.incremental_update()
        # ← EXITS after update
```

### Trading Bots (Continuous Service)
**Type**: Long-running service
**Pattern**: Run → Loop Forever

```python
# trader.py
def run(self):
    while self.is_running:  # ← Infinite loop
        self.check_markets()
        self.execute_trades()
        time.sleep(60)
```

**Deployment**:
```bash
nohup python3 trader.py >> trading.out 2>&1 &
# Runs continuously until killed
```

## The Problem

**For historical backfill**:
✅ Batch design is fine - run once with `--collect 180`, get data, done.

**For ongoing collection**:
❌ Batch design requires manual intervention:
1. Run collector → collects data → exits
2. Wait some time
3. Manually run again → collects new data → exits  
4. Repeat forever

**What you need for production**:
- Automatic incremental updates every 15 minutes (GDELT publishes every 15 min)
- No manual intervention
- Continuous data flow for live trading

## Solution Options

### Option 1: Add Continuous Mode to Collector (Recommended)

Modify `gdelt_collector.py` to support continuous collection:

```python
def run_continuous(self, interval_minutes: int = 15):
    """Run collector continuously with periodic updates."""
    logger.info(f"Starting continuous collection (every {interval_minutes} min)")
    
    while True:
        try:
            # Collect latest update
            events = self.collect_recent()
            logger.info(f"Collected {events} new events")
            
        except Exception as e:
            logger.error(f"Collection error: {e}")
        
        # Wait for next interval
        time.sleep(interval_minutes * 60)

# In main():
if args.continuous:
    collector.run_continuous(interval_minutes=15)
```

**Usage**:
```bash
# One-time backfill
python3 gdelt_collector.py --collect 180

# Then start continuous mode
nohup python3 gdelt_collector.py --continuous >> gdelt_collection.out 2>&1 &
```

### Option 2: Use Cron Job (Simple but Less Elegant)

Add to crontab:
```cron
# Collect GDELT updates every 15 minutes
*/15 * * * * cd /path/to/project && python3 gdelt_collector.py --recent >> gdelt_cron.log 2>&1

# Collect Alchemy updates every hour
0 * * * * cd /path/to/project && python3 alchemy_collector.py --incremental >> alchemy_cron.log 2>&1
```

**Pros**: Simple, uses standard tools
**Cons**: Multiple processes, harder to monitor, no graceful shutdown

### Option 3: Separate Scheduler Service

Create a scheduler that manages both collectors:

```python
# collector_scheduler.py
def run_schedulers():
    # GDELT: every 15 minutes
    schedule.every(15).minutes.do(collect_gdelt_recent)
    
    # Alchemy: every hour  
    schedule.every(1).hour.do(collect_alchemy_incremental)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
```

**Pros**: Single process, easy monitoring, graceful shutdown
**Cons**: Additional code to maintain

## Comparison Table

| Aspect | Batch (Current) | Continuous Mode | Cron Job | Scheduler Service |
|--------|----------------|-----------------|----------|-------------------|
| Setup Complexity | ⭐ Simple | ⭐⭐ Moderate | ⭐⭐ Moderate | ⭐⭐⭐ Complex |
| Auto Updates | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| Process Count | 1 per run | 1 | Many | 1 |
| Graceful Shutdown | N/A | ✅ Yes | ❌ No | ✅ Yes |
| Monitoring | Hard | Easy | Medium | Easy |
| Best For | Backfill | Production | Quick fix | Large scale |

## Recommended Approach

**For your use case** (production trading system):

1. **Short term (this week)**:
   - Use **Option 2 (Cron)** for quick deployment
   - Set up automated incremental updates
   - Focus on getting trading bots stable

2. **Long term (next month)**:
   - Implement **Option 1 (Continuous Mode)**
   - Matches trader.py pattern
   - Single process, easy monitoring
   - Can integrate with deploy.sh

## Implementation Priority

**High Priority**:
1. ✅ Fix Alchemy mapping (3 min) - DO THIS FIRST
2. ✅ Recover GDELT database (30 min)
3. ✅ Set up cron for incremental updates (10 min)

**Medium Priority**:
4. Add continuous mode to collectors
5. Update deploy.sh to support continuous mode
6. Add monitoring/alerting

**Low Priority**:
7. Build unified scheduler service
8. Containerize everything with Docker Compose
