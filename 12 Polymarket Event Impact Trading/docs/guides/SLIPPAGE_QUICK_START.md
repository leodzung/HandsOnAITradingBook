# Slippage Estimation - Quick Start Guide

## What It Does

Slippage estimation prevents your trading bots from executing trades with excessive costs by:
- Analyzing orderbook depth before placing orders
- Calculating expected execution price (volume-weighted average)
- Rejecting trades that exceed cost thresholds
- Improving entry price accuracy

## Quick Start

### 1. Verify Installation

```bash
# Run integration test
cd "12 Polymarket Event Impact Trading"
python3 test_slippage_integration.py
```

Expected output: "✓ All tests passed!"

### 2. Start Bots

```bash
# Stop any running instances
pkill -f trader.py
pkill -f trader_price_levels.py

# Start with slippage estimation enabled
nohup python3 trader.py >> trading.out 2>&1 &
nohup python3 trader_price_levels.py >> trading_price_levels.out 2>&1 &
```

### 3. Monitor Slippage

```bash
# Watch real-time slippage estimates
tail -f trading.out | grep -i slippage

# Count rejections
grep -c "Trade REJECTED" trading.out
```

## Configuration

Edit `config.json` or `config_price_levels.json`:

```json
{
  "slippage_estimation": {
    "enabled": true,              // Turn on/off
    "max_slippage_bps": 100,      // 1% max slippage
    "max_slippage_dollars": 5.0,  // $5 absolute max
    "warn_threshold_bps": 50      // Warn at 0.5%
  }
}
```

**Restart bots after config changes.**

## Common Adjustments

### Too Many Rejections?

Increase limits in config:
```json
"max_slippage_bps": 150,        // Allow 1.5%
"max_slippage_dollars": 10.0    // Allow $10
```

### Not Enough Protection?

Decrease limits:
```json
"max_slippage_bps": 75,         // Stricter 0.75%
"max_slippage_dollars": 3.0     // Stricter $3
```

### Emergency Disable

Set `"enabled": false` and restart bots.

## Understanding Logs

### Normal Trade
```
Slippage estimate: $0.16 (35 bps), levels: 2
[PAPER TRADE] BUY YES $50.00 at $0.502
```
**Meaning:** Trade accepted with 35 basis points slippage.

### Rejected Trade
```
Trade REJECTED - Slippage 150 bps exceeds limit 100 bps
```
**Meaning:** Trade blocked because slippage (1.5%) exceeds limit (1%).

### Warning
```
Slippage warning: Thin orderbook (3 levels consumed), using 20% buffer
```
**Meaning:** Order requires many levels, extra safety buffer applied.

## Monitoring Metrics

### Check Daily Stats
```bash
# Average slippage
grep "Slippage estimate" trading.out | grep -oP '\d+ bps' | sed 's/ bps//' | awk '{sum+=$1; count++} END {print "Avg:", sum/count, "bps"}'

# Rejection count
grep -c "Trade REJECTED" trading.out

# Rejection rate
TOTAL=$(grep -c "Slippage estimate" trading.out)
REJECTED=$(grep -c "Trade REJECTED" trading.out)
echo "Rejection rate: $((REJECTED * 100 / TOTAL))%"
```

### Target Metrics (After 3-7 Days)
- Average slippage: 30-50 bps ✓
- Rejection rate: 5-15% ✓
- Max slippage: <100 bps ✓

## Troubleshooting

### Issue: No slippage logs

**Check:**
```bash
# Verify enabled in config
jq '.slippage_estimation.enabled' config.json

# Check if bots are running
ps aux | grep trader.py
```

**Fix:** Ensure `"enabled": true` and restart bots.

### Issue: All trades rejected

**Check:**
```bash
# View recent rejections
tail -20 trading.out | grep "REJECTED"
```

**Fix:** Increase `max_slippage_bps` or `max_slippage_dollars`.

### Issue: Slippage seems too high

**Possible causes:**
- Thin orderbooks (low liquidity)
- Wide spreads (volatile markets)
- Large order sizes

**Fix:** Reduce position sizes or increase limits.

## Key Files

- `slippage_estimator.py` - Core estimation logic
- `config.json` - Event trader settings
- `config_price_levels.json` - Price-level trader settings
- `SLIPPAGE_IMPLEMENTATION_SUMMARY.md` - Full documentation

## Support

For detailed information, see `SLIPPAGE_IMPLEMENTATION_SUMMARY.md`.

For issues, check:
1. Integration test: `python3 test_slippage_integration.py`
2. Unit tests: `python3 -m pytest tests/test_slippage_estimator.py -v`
3. Bot logs: `tail -100 trading.out` or `trading_price_levels.out`
