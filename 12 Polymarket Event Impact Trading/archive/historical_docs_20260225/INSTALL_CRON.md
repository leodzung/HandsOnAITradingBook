# Installing Cron Jobs for Polymarket Trading System

## What Gets Automated

1. **@reboot** - Auto-restart collectors on system reboot
   - Alchemy collector (blockchain trades)
   - GDELT collector (news events)

2. **Every 5 minutes** - Health monitoring
   - Check if collectors are running
   - Verify data freshness (< 1 hour staleness)
   - Send Telegram alerts on failures

3. **Daily 2 AM** - Market mapper update
   - Update token-condition mappings
   - Populate condition_ids for new trades

4. **Weekly Sunday 3 AM** - Refresh resolved markets
   - Collect new resolved markets from Polymarket API
   - Update polymarket_history.db

5. **Monthly 1st @ 4 AM** - Regenerate training labels
   - Create new labeled dataset with latest resolved markets

## Installation

### Option 1: Direct Install (Replaces existing crontab)

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"
crontab crontab_polymarket.txt
```

**⚠️ WARNING**: This will REPLACE your entire crontab. If you have other cron jobs, use Option 2.

### Option 2: Merge with Existing Crontab (Recommended)

```bash
# Backup existing crontab
crontab -l > ~/crontab_backup.txt

# View current crontab
crontab -l

# Edit crontab manually
crontab -e

# Then copy/paste the contents of crontab_polymarket.txt
# (excluding the header comments)
```

### Option 3: Append to Existing Crontab

```bash
# Append Polymarket jobs to existing crontab
crontab -l > /tmp/current_cron
cat crontab_polymarket.txt >> /tmp/current_cron
crontab /tmp/current_cron
rm /tmp/current_cron
```

## Verification

```bash
# View installed crontab
crontab -l

# Check if cron daemon is running (macOS)
sudo launchctl list | grep cron

# Test monitoring script manually
cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"
python3 src/monitoring/monitor_collectors.py
```

## Logs

All cron jobs write to `logs/` directory:
- `logs/alchemy_collection.out` - Alchemy collector
- `logs/gdelt_collection.out` - GDELT collector
- `logs/monitoring.out` - Health checks
- `logs/mapper.out` - Market mapper
- `logs/history_refresh.out` - Polymarket history
- `logs/label_creation.out` - Label generation

## Telegram Alerts

For Telegram monitoring to work:
1. Ensure `telegram_config.json` exists and is configured
2. Test alerts: `python3 src/monitoring/monitor_collectors.py --test`

## Troubleshooting

### Cron jobs not running
```bash
# Check cron logs (macOS)
log show --predicate 'process == "cron"' --last 1h

# Verify PATH in cron
* * * * * echo $PATH > /tmp/cron_path.txt

# Test command manually
cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"
/usr/bin/python3 src/collectors/gdelt_collector.py --help
```

### Permission denied
```bash
chmod +x src/collectors/*.py
chmod +x src/monitoring/*.py
chmod +x src/utils/*.py
```

## Removing Cron Jobs

```bash
# Remove all cron jobs
crontab -r

# Or edit and remove specific lines
crontab -e
```
