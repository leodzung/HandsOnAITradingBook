# Short-Expiry Trading Bot - Quick Start Guide

## TL;DR

```bash
# Test the system
./launch_short_expiry.sh test

# Start the bot
./launch_short_expiry.sh start

# Check status
./launch_short_expiry.sh status

# Watch logs
./launch_short_expiry.sh logs
```

---

## What This Bot Does

Trades **short-expiry Polymarket prediction markets** (0-7 days) using:
- **3 time buckets:** Ultra-short (0-24h), Short (24-72h), Medium (72-168h)
- **3 trading rules:** Arbitrage, Mean Reversion, Momentum
- **Paper trading:** $500 virtual balance, no real money

**Current Coverage:** ~138 markets across all buckets

---

## Quick Start

### 1. Run Tests (First Time)

```bash
cd "12 Polymarket Event Impact Trading"
./launch_short_expiry.sh test
```

**Expected output:**
```
✓ Config loaded
✓ Feature extraction working (41 features)
✓ Position management working
✓ Risk management working
✓ Signal generation working
✓ ALL TESTS PASSED

✓ Markets discovered: 138 total
  - Ultra-short (0-24h):  66 markets
  - Short (24-72h):       51 markets
  - Medium (72-168h):     21 markets
```

### 2. Start the Bot

```bash
./launch_short_expiry.sh start
```

**Expected output:**
```
🚀 Starting Short-Expiry Trading Bot...
✅ Bot started (PID: 12345)

Monitor logs with: ./launch_short_expiry.sh logs
Check status with: ./launch_short_expiry.sh status
```

### 3. Monitor Performance

```bash
./launch_short_expiry.sh status
```

**Example output:**
```
✅ Bot is RUNNING (PID: 12345)

Paper Trading Balance:
{
  "balance": 487.50,
  "updated": "2026-02-11T16:30:00+00:00"
}

Open Positions by Bucket:
ultra_short|3
short|2

Closed Positions Summary:
trades|win_rate|avg_pnl_pct|total_pnl
8|62.5|4.5|12.50
```

### 4. Watch Live Logs

```bash
./launch_short_expiry.sh logs
```

**Press Ctrl+C to stop tailing**

---

## Understanding the Logs

### Market Discovery Cycle (Every 5 min)

```
2026-02-11 16:00:00 - INFO - Markets discovered | Ultra-short: 66 | Short: 51 | Medium: 21
```

**Meaning:** Bot found 138 tradeable markets

### Trade Opened

```
2026-02-11 16:05:23 - INFO - TRADE OPENED | Market: Will BTC > $60k? |
Bucket: ultra_short | Outcome: YES | Size: $35.00 | Entry: 0.6500 |
Reason: momentum | Balance: $465.00
```

**Meaning:**
- Opened a YES position on "BTC > $60k"
- Bucket: ultra_short (0-24h expiry)
- Size: $35 invested
- Entry price: 0.65 (65% implied probability)
- Reason: Momentum signal triggered
- Remaining balance: $465

### Trade Closed

```
2026-02-11 16:45:12 - INFO - Closed position: market_123 YES |
Entry: 0.6500 | Exit: 0.7500 | P&L: 3.50 (10.77%) | Reason: take_profit
```

**Meaning:**
- Position closed with profit
- Entry: 0.65 → Exit: 0.75 (price moved up 10 cents)
- P&L: +$3.50 (+10.77%)
- Exit reason: Hit take-profit target (30% gain)

---

## Trading Rules Explained

### Rule 1: Arbitrage

**What:** Market pricing error (YES + NO ≠ 1.00)

**Example:**
```
Market: "Will ETH > $3000?"
YES price: 0.45
NO price: 0.52
Total: 0.97 (should be ~1.00)

→ Signal: BUY YES (cheaper side)
→ Edge: 0.03 (3%)
→ Confidence: 95%
```

**Why it works:** Market inefficiency guarantees profit regardless of outcome

### Rule 2: Mean Reversion (Ultra-short only)

**What:** Extreme prices in low-liquidity markets revert to 0.5

**Example:**
```
Market: "Will BTC > $65k by midnight?"
Price: 0.35 (very low)
Spread: 6% (wide, low liquidity)
Volume: $2000 (decent activity)

→ Signal: BUY YES (price should rise toward 0.5)
→ Edge: 0.15 (15%)
→ Confidence: 60%
```

**Why it works:** Thin markets overreact, then correct

### Rule 3: Momentum

**What:** Follow strong recent price movements

**Example:**
```
Market: "Will BTC > $60k by tomorrow?"
Price 1h ago: 0.55
Price now: 0.60
Change: +5% (strong momentum)
Volume: $1500

→ Signal: BUY YES (follow trend)
→ Edge: 0.08 (8%)
→ Confidence: 65%
```

**Why it works:** Information cascades continue in short term

---

## Risk Management

### Per-Bucket Limits

| Bucket | Max Positions | Max Size | Stop Loss | Take Profit |
|--------|--------------|----------|-----------|-------------|
| Ultra-short (0-24h) | 5 | $50 | -10% | +30% |
| Short (24-72h) | 7 | $75 | -15% | +50% |
| Medium (72-168h) | 8 | $100 | -20% | +75% |

### Safety Features

1. **Circuit Breaker:** Bot stops after 4 consecutive losses
2. **Pre-expiry Exit:** All positions closed 2 hours before market expiry
3. **Spread Filter:** Only trade markets with tight spreads
4. **Price Range:** Skip extreme prices (< 0.05 or > 0.95)
5. **Paper Trading:** No real money at risk

---

## Performance Metrics

### Check P&L

```bash
sqlite3 data/positions_short_expiry.db "
SELECT
  COUNT(*) as total_trades,
  ROUND(AVG(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100, 1) as win_rate,
  ROUND(AVG(pnl_pct), 2) as avg_return,
  ROUND(SUM(pnl), 2) as total_pnl
FROM positions
WHERE status = 'closed'
"
```

### Check by Bucket

```bash
sqlite3 data/positions_short_expiry.db "
SELECT
  bucket,
  COUNT(*) as trades,
  ROUND(AVG(pnl_pct), 2) as avg_return,
  ROUND(SUM(pnl), 2) as total_pnl
FROM positions
WHERE status = 'closed'
GROUP BY bucket
"
```

### Recent Trades

```bash
sqlite3 data/positions_short_expiry.db "
SELECT
  substr(entry_time, 1, 16) as time,
  bucket,
  outcome,
  ROUND(entry_price, 3) as entry,
  ROUND(exit_price, 3) as exit,
  ROUND(pnl_pct, 1) as return,
  signal_reason as signal,
  exit_reason as exit
FROM positions
WHERE status = 'closed'
ORDER BY entry_time DESC
LIMIT 10
"
```

---

## Troubleshooting

### Bot Not Finding Markets

**Check API connectivity:**
```bash
python3 tests/test_raw_api.py
```

**Adjust filters in `config/config_short_expiry.json`:**
- Lower `min_volume` thresholds
- Increase `max_spread_pct`
- Set `crypto_only: false` to include all markets

### Bot Not Trading

**Check signal generation:**
```bash
python3 tests/test_short_expiry_infrastructure.py
```

**Adjust rules in `config/config_short_expiry.json`:**
- Lower `min_edge` (currently 0.03)
- Lower `min_confidence` (currently 0.55)
- Enable/disable specific rules

### Bot Stopped Unexpectedly

**Check logs:**
```bash
tail -100 logs/short_expiry.out
```

**Common issues:**
- Circuit breaker triggered (4 consecutive losses)
- API rate limit exceeded
- Network connectivity issue

**Restart:**
```bash
./launch_short_expiry.sh stop
./launch_short_expiry.sh start
```

---

## Configuration

Edit `config/config_short_expiry.json`:

### Increase Trading Activity

```json
{
  "risk_management": {
    "min_edge": 0.02,        // Lower from 0.03
    "min_confidence": 0.50   // Lower from 0.55
  }
}
```

### Reduce Risk

```json
{
  "position_limits": {
    "max_position_size": {
      "ultra_short": 25,     // Lower from 50
      "short": 50,           // Lower from 75
      "medium": 75           // Lower from 100
    }
  }
}
```

### Focus on One Bucket

```json
{
  "position_limits": {
    "max_positions_per_bucket": {
      "ultra_short": 10,     // Increase from 5
      "short": 0,            // Disable
      "medium": 0            // Disable
    }
  }
}
```

---

## Stopping the Bot

```bash
./launch_short_expiry.sh stop
```

**Important:** This will close all open positions at current market prices.

---

## Next Steps (Phase 2)

After 1-2 weeks of paper trading:

1. **Collect 500+ samples** for ML training
2. **Train bucket-specific models** (GradientBoosting)
3. **Implement hybrid trading** (ML + rules)
4. **Consider live trading** with small capital ($100-200)

---

## File Locations

| File | Purpose |
|------|---------|
| `config/config_short_expiry.json` | Bot configuration |
| `data/positions_short_expiry.db` | Position tracking |
| `data/paper_trading_balance_short_expiry.json` | Virtual balance |
| `logs/short_expiry.out` | Bot logs |
| `data/short_expiry.pid` | Process ID (when running) |

---

## Support

**Read implementation details:**
```bash
cat SHORT_EXPIRY_IMPLEMENTATION_SUMMARY.md
```

**Test components:**
```bash
./launch_short_expiry.sh test
```

**Check market availability:**
```bash
python3 tests/test_raw_api.py
```

---

**Happy Trading! 📈**

*Remember: This is paper trading with virtual money. No real funds are at risk.*
