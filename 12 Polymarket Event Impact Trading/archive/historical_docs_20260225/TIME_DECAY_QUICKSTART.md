# Time-Decay TP/SL Quick Start Guide

## What Changed?

✅ **Fixed critical bug** in short-expiry trader that caused immediate position exits
✅ **Added dynamic TP/SL** that tightens as markets approach expiry
✅ **Force-exit logic** closes positions <1h to expiry (avoid liquidity risk)

## How to Use

### Enable/Disable

In any bot config (`config.json`, `config_price_levels.json`, `config_short_expiry.json`):

```json
"time_decay_tp_sl": {
  "enabled": true,   // Set to false to use static TP/SL
  ...
}
```

### Monitoring

Check logs for dynamic threshold messages:

```bash
tail -f logs/*.log | grep "Dynamic TP/SL"
```

Expected output:
```
Dynamic TP/SL: hours_remaining=25.3h, tp=50%, sl=15%
Dynamic TP/SL: hours_remaining=13.3h, tp=40%, sl=12%
Pre-expiry exit: 0.8h < 1.0h
```

### Telegram Notifications

Exit notifications now show dynamic thresholds:
```
🔴 Position Closed (LOSS)
Market: Bitcoin > $68k by Feb 14?
Exit Reason: stop_loss
Threshold: 12% (dynamic, 13h to expiry)
P&L: -$8.50 (-13.2%)
```

## Configuration Examples

### Conservative (hold longer, wider thresholds)

```json
"time_decay_tp_sl": {
  "enabled": true,
  "thresholds": [
    {"min_hours": 48, "tp_pct": 100, "sl_pct": 25},
    {"min_hours": 24, "tp_pct": 75, "sl_pct": 20},
    {"min_hours": 12, "tp_pct": 50, "sl_pct": 15},
    {"min_hours": 1, "tp_pct": 25, "sl_pct": 10}
  ],
  "force_exit_hours": 0.5
}
```

### Aggressive (exit early, tight thresholds)

```json
"time_decay_tp_sl": {
  "enabled": true,
  "thresholds": [
    {"min_hours": 24, "tp_pct": 30, "sl_pct": 10},
    {"min_hours": 12, "tp_pct": 20, "sl_pct": 8},
    {"min_hours": 4, "tp_pct": 15, "sl_pct": 5},
    {"min_hours": 1, "tp_pct": 10, "sl_pct": 3}
  ],
  "force_exit_hours": 2.0
}
```

### Only Apply to TP (keep SL static)

```json
"time_decay_tp_sl": {
  "enabled": true,
  "apply_to_tp": true,
  "apply_to_sl": false,   // SL stays at static 15%
  "thresholds": [
    {"min_hours": 24, "tp_pct": 50, "sl_pct": 15},
    {"min_hours": 12, "tp_pct": 40, "sl_pct": 15},
    {"min_hours": 4, "tp_pct": 30, "sl_pct": 15}
  ]
}
```

## Testing

Run integration tests:

```bash
cd "12 Polymarket Event Impact Trading"
python3 test_time_decay_tp_sl.py
```

Expected: All 25 tests pass ✅

## Deployment Checklist

- [x] Config files updated with `time_decay_tp_sl` section
- [x] Bot files updated with dynamic TP/SL logic
- [x] All tests passing (25/25)
- [x] No syntax errors in Python files
- [x] Valid JSON in all config files
- [ ] Restart all three bots
- [ ] Monitor logs for 1 hour
- [ ] Verify Telegram notifications show dynamic thresholds
- [ ] Check first pre-expiry exit (should be <1h to expiry)
- [ ] Verify no positions expire with active positions

## Restart Commands

```bash
cd "12 Polymarket Event Impact Trading"

# Stop existing bots
pkill -f trader.py
pkill -f trader_price_levels.py
pkill -f trader_short_expiry.py

# Start with new time-decay logic
nohup python3 src/bots/trader.py config/config.json >> logs/event_trader.log 2>&1 &
nohup python3 src/bots/trader_price_levels.py >> logs/price_level_trader.log 2>&1 &
nohup python3 src/bots/trader_short_expiry.py config/config_short_expiry.json >> logs/short_expiry.log 2>&1 &

# Verify running
ps aux | grep trader
```

## Rollback Plan

If issues occur, disable time-decay in all configs:

```bash
# Edit each config file
"time_decay_tp_sl": {
  "enabled": false,
  ...
}

# Restart bots (use commands above)
```

This reverts to static TP/SL behavior without code changes.

## Support

For issues or questions:
1. Check logs: `tail -f logs/*.log`
2. Run tests: `python3 test_time_decay_tp_sl.py`
3. Review implementation: `TIME_DECAY_TP_SL_IMPLEMENTATION.md`

---
**Last Updated**: 2026-02-15
**Version**: 1.0
