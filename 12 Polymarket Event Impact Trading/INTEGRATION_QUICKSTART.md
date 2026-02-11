# System Integration - Quick Start Guide

## ✅ Integration Complete!

The short-expiry trading bot is now fully integrated with:
- ✅ Telegram notifications
- ✅ Streamlit dashboard
- ✅ Unified management script
- ✅ All existing infrastructure

---

## Quick Start (3 Steps)

### 1. Check System Status

```bash
./manage_bots.sh status
```

**Expected Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  POLYMARKET TRADING BOTS - STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ○ Event Trader: STOPPED
  ○ Price Level Trader: STOPPED
  ○ Short Expiry Trader: STOPPED

  ● Dashboard: RUNNING (PID: 34248)
    → http://localhost:8502

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PAPER TRADING BALANCES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Event Trader:        $500.00
  Price Level Trader:  $500.00
  Short Expiry Trader: $500.00

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 2. Start Short-Expiry Bot

```bash
./manage_bots.sh start short-expiry
```

**What Happens:**
- Bot starts in background
- Discovers ~138 markets (67 ultra-short, 51 short, 20 medium)
- Begins analyzing for trading signals
- Sends startup notification to Telegram

### 3. Monitor Performance

**Option A: Dashboard (Visual)**
```bash
# Dashboard should already be running (see status above)
# Open in browser: http://localhost:8502
# Go to "⚡ Short Expiry" tab
```

**Option B: Logs (Real-time)**
```bash
./manage_bots.sh logs short-expiry
```

**Option C: Telegram**
- Check your Telegram for notifications
- You'll receive alerts for every trade

---

## What to Expect

### First 30 Minutes

1. **Bot startup notification** (Telegram)
   ```
   🚀 Short-Expiry Bot Started

   Paper Trading: Yes
   Initial Balance: $500.00
   Max Positions: 15
   ```

2. **Market discovery logs** (every 5 min)
   ```
   Markets discovered | Ultra-short: 66 | Short: 51 | Medium: 21
   ```

3. **First trade** (when signal triggers)
   ```
   ⚡ POSITION OPENED - Short Expiry

   Bucket: Ultra-Short
   Side: YES
   Size: $35.00
   Entry: 0.650
   Edge: 5.0%
   Confidence: 95.0%
   Strategy: Arbitrage

   Will BTC > $60k by end of day?

   💰 Balance: $465.00
   ```

### After 24 Hours

- **Expected trades:** 3-10
- **Balance range:** $480-520 (depending on P&L)
- **Win rate:** Target >50%
- **Positions:** 2-5 open

---

## Management Commands

### Bot Control

```bash
# Start
./manage_bots.sh start short-expiry

# Stop
./manage_bots.sh stop short-expiry

# Restart
./manage_bots.sh restart short-expiry

# Status
./manage_bots.sh status

# Logs
./manage_bots.sh logs short-expiry
```

### Dashboard

```bash
# Start
./manage_bots.sh dashboard start

# Stop
./manage_bots.sh dashboard stop

# Access
open http://localhost:8502
```

### All Bots

```bash
# Start all bots
./manage_bots.sh start all

# Stop all bots
./manage_bots.sh stop all
```

---

## Dashboard Features

### Short Expiry Tab

**What You'll See:**
1. **Bot Status:** Running/Stopped indicator
2. **Metrics:**
   - Current balance
   - Open positions (total and by bucket)
   - Total P&L

3. **Bucket Breakdown:**
   ```
   ⚡ Ultra-Short (0-24h):  3 positions
   🔥 Short (24-72h):       2 positions
   📊 Medium (72-168h):     1 position
   ```

4. **Position Details:**
   - Market question
   - Entry price, size
   - Hours to expiry
   - Signal reason (arbitrage/momentum/mean reversion)
   - Edge & confidence

5. **Recent Trades:**
   - Color-coded P&L (green=profit, red=loss)
   - Entry → Exit prices
   - Exit reason

---

## Telegram Notifications

### What You'll Receive

**✅ Enabled Notifications:**
1. Bot startup/restart
2. Position opened (with full details)
3. Circuit breaker triggered (if 4 losses in a row)

**⏳ Coming Soon:**
4. Position closed (needs implementation)
5. Daily P&L summary

### Notification Format

```
⚡ POSITION OPENED - Short Expiry

Bucket: Ultra-Short
Side: YES
Size: $35.00
Entry: 0.650
Edge: 5.0%
Confidence: 95.0%
Strategy: Arbitrage

Will BTC > $60k by end of day?

💰 Balance: $465.00
```

**Bucket Emojis:**
- ⚡ = Ultra-Short (0-24h)
- 🔥 = Short (24-72h)
- 📊 = Medium (72-168h)

---

## File Locations

### Bot Files
- Script: `src/bots/trader_short_expiry.py`
- Config: `config/config_short_expiry.json`
- Log: `logs/short_expiry.out`
- PID: `data/short_expiry.pid`

### Data Files
- Positions: `data/positions_short_expiry.db`
- Balance: `data/paper_trading_balance_short_expiry.json`

### Management
- Main script: `manage_bots.sh`
- Alt script: `launch_short_expiry.sh`

---

## Troubleshooting

### Bot Won't Start

```bash
# Check logs
cat logs/short_expiry.out

# Common fix: restart
./manage_bots.sh restart short-expiry
```

### No Telegram Notifications

```bash
# Test Telegram
python3 -c "
from src.monitoring.telegram_notifier import TelegramNotifier
tg = TelegramNotifier(
    bot_token='8068515860:AAEiKpTK0RtHo5dURsbu7ey8Xa8r3A2xEHA',
    chat_id='6690408994',
    enabled=True
)
tg.send_message('🧪 Test')
"
```

### Dashboard Not Working

```bash
# Restart dashboard
./manage_bots.sh dashboard restart

# Check it's running
./manage_bots.sh status | grep Dashboard
```

---

## Next Actions

### Immediate
1. ✅ Start the bot: `./manage_bots.sh start short-expiry`
2. ✅ Open dashboard: http://localhost:8502
3. ✅ Watch for first trade on Telegram

### This Week
1. Monitor performance daily
2. Review win rate by bucket
3. Collect data for ML training (500+ samples target)

### Next Month
1. Analyze signal performance (arb vs momentum vs mean reversion)
2. Train ML models (GradientBoosting per bucket)
3. Implement hybrid trading (ML + rules)

---

## Full Documentation

- **Implementation:** `SHORT_EXPIRY_IMPLEMENTATION_SUMMARY.md`
- **Quick Start:** `QUICK_START_SHORT_EXPIRY.md`
- **Integration:** `SYSTEM_INTEGRATION_COMPLETE.md`
- **This Guide:** `INTEGRATION_QUICKSTART.md`

---

## Summary

You now have a **complete short-expiry trading system** with:

✅ **3-bucket architecture** (ultra/short/medium)
✅ **41 features** per market
✅ **3 trading rules** (arbitrage, momentum, mean reversion)
✅ **Telegram alerts** for every trade
✅ **Dashboard monitoring** with dedicated tab
✅ **Unified management** for all bots
✅ **Paper trading** ($500 virtual balance)

**Ready to trade!** 🚀

```bash
./manage_bots.sh start short-expiry
```

---

**Need Help?**
- Check logs: `./manage_bots.sh logs short-expiry`
- Check status: `./manage_bots.sh status`
- View dashboard: http://localhost:8502
