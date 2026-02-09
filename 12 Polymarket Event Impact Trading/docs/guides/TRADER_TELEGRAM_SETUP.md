# Trader Telegram Notifications - Setup Guide

Get instant alerts for your trading activity!

## Status: ✅ Already Configured!

Your traders are **already set up** to send Telegram notifications using the same bot as your monitoring system.

## What You Get

### Event Trader (trader.py)
Sends alerts for:
- ✅ **New positions opened** - Entry price, size, expected edge
- ✅ **Positions closed** - P&L, exit reason, performance
- ✅ **Circuit breaker** - When consecutive losses pause trading
- ✅ **Daily summaries** - Win rate, P&L, open positions
- ✅ **Errors** - Critical issues requiring attention

### Price Level Trader (trader_price_levels.py)
Same notifications for price-level based trades.

## Current Configuration

Both traders are configured with:
```json
{
  "bot_token": "8068515860:AAEi...",
  "chat_id": "6690408994",
  "enabled": true
}
```

**Same bot** as your monitoring system - all alerts in one place!

## Example Notifications

### Position Opened
```
NEW POSITION - Event Trader

Asset: BTC
Side: YES
Size: $50.00
Entry: $0.620
Edge: +8.0%

Will Bitcoin reach $100k by end of February?

0x12345678901234...
```

### Position Closed (Profit)
```
✅ CLOSED POSITION - Event Trader

Asset: BTC
Side: YES
Entry: $0.620
Exit: $0.750
P&L: +$6.50 (+13.0%)
Reason: Take Profit

Will Bitcoin reach $100k by end of February?

0x12345678901234...
```

### Position Closed (Loss)
```
❌ CLOSED POSITION - Price Level Trader

Asset: ETH
Side: NO
Entry: $0.450
Exit: $0.380
P&L: -$2.10 (-7.0%)
Reason: Stop Loss

Will Ethereum ETF be approved this month?

0xabcdef1234567890...
```

### Circuit Breaker
```
🔴 CIRCUIT BREAKER ACTIVATED - Event Trader

Trading paused after 3 consecutive losses.
Will resume in 4.0 hours.

Time: 2026-02-07 10:15
```

### Daily Summary
```
📊 DAILY SUMMARY - Event Trader

Date: 2026-02-07
Trades: 6
Win Rate: 66.7%
P&L: +$12.50
Open Positions: 2
Balance: $1012.50
```

### Error Alert
```
⚠️ ERROR - Price Level Trader

Failed to place order: Insufficient balance

Time: 2026-02-07 10:15
```

## Testing Your Setup

Run the test script to send sample notifications:

```bash
python3 test_trader_telegram.py
```

Choose:
1. Test individual notification types
2. Test all notifications at once

## How It Works

### When Position Opens
The trader:
1. Detects signal (event or price level)
2. Checks risk management rules
3. Places order on Polymarket
4. **Sends Telegram alert** with entry details
5. Starts monitoring for exit conditions

### When Position Closes
The trader:
1. Detects exit condition (stop loss, take profit, time, etc.)
2. Closes position on Polymarket
3. Calculates P&L
4. **Sends Telegram alert** with results
5. Updates risk management counters

### Circuit Breaker
If you hit 3 consecutive losses:
1. Trading automatically pauses
2. **Sends Telegram alert** immediately
3. Waits cooldown period (4 hours default)
4. Automatically resumes after cooldown
5. **Sends reset notification** when trading resumes

### Daily Summary
Every day at midnight (or configured time):
1. Calculates daily statistics
2. **Sends summary** with:
   - Total trades
   - Win rate %
   - Daily P&L
   - Open positions
   - Current balance

## Configuration Files

### Centralized Config (telegram_config.json)
```json
{
  "bot_token": "8068515860:AAEi...",
  "chat_id": "6690408994"
}
```
**Shared by:** Monitoring system + Both traders

### Trader Configs (config.json, config_price_levels.json)
```json
{
  ...
  "telegram": {
    "enabled": true,
    "bot_token": "8068515860:AAEi...",
    "chat_id": "6690408994"
  }
}
```

## Customization

### Disable Notifications for a Trader

Edit `config.json` (or `config_price_levels.json`):
```json
"telegram": {
  "enabled": false,
  ...
}
```

Restart trader:
```bash
./restart_all.sh
```

### Change Notification Frequency

Daily summaries are configured in the trader code. To change:

1. Edit `trader.py` (or `trader_price_levels.py`)
2. Find `schedule_daily_summary()` function
3. Modify the schedule
4. Restart trader

### Use Different Chat for Traders

To send trader alerts to a different chat:

1. Get new chat_id (use @userinfobot)
2. Update `config.json`:
   ```json
   "telegram": {
     "enabled": true,
     "bot_token": "8068515860:AAEi...",
     "chat_id": "YOUR_NEW_CHAT_ID"
   }
   ```
3. Restart traders

## Notification Settings

### What Triggers Alerts

**Always:**
- Position opened
- Position closed
- Circuit breaker activation/reset
- Critical errors

**Configurable:**
- Daily summaries (default: enabled)
- Test notifications (manual only)

### Alert Frequency

**No spam protection needed** because:
- Positions open/close at natural trading pace
- Circuit breaker only triggers after consecutive losses
- Daily summary is once per day
- Errors only on critical issues

## Troubleshooting

### Not receiving trading alerts?

1. **Check if Telegram is enabled:**
   ```bash
   grep '"enabled"' config.json config_price_levels.json
   # Should show: "enabled": true
   ```

2. **Test notifications work:**
   ```bash
   python3 test_trader_telegram.py
   # Choose option 1 to test
   ```

3. **Check trader logs:**
   ```bash
   tail -50 trading.out | grep -i telegram
   # Look for "Telegram notifications enabled"
   ```

4. **Verify traders are running:**
   ```bash
   ./check_processes.sh
   # Should show both traders running
   ```

### Receiving too many alerts?

**Disable notifications temporarily:**
```bash
# Edit config
nano config.json
# Change "enabled": true to "enabled": false
# Restart
./restart_all.sh
```

### Want monitoring AND trading in same chat?

Good news: **You already have this!** Both use the same bot and chat_id.

Your Telegram will show:
- 🚨 Collector issues (from monitoring)
- 📊 Trading activity (from traders)
- ✅ All in one place

## Real-World Example

Here's what a typical trading day looks like in Telegram:

```
09:00 - ✅ GDELT collector: OK (monitoring)
09:15 - 📊 NEW POSITION - Event Trader
        BTC YES $50 @ $0.62

10:30 - ✅ CLOSED POSITION - Event Trader
        BTC +$3.50 (+7.0%)

12:00 - 🚨 Alchemy Collector Alert (monitoring)
        Log not updated in 90 minutes

14:15 - 📊 NEW POSITION - Price Level Trader
        ETH NO $30 @ $0.45

15:00 - ✅ Alchemy collector: OK (monitoring)

16:45 - ❌ CLOSED POSITION - Price Level Trader
        ETH -$1.20 (-4.0%) Stop Loss

18:00 - 📊 NEW POSITION - Event Trader
        BTC YES $50 @ $0.58

23:59 - 📊 DAILY SUMMARY - Event Trader
        6 trades, 66.7% win rate, +$8.30
```

## Monitoring vs Trading Alerts

| Feature | Monitoring | Trading |
|---------|-----------|---------|
| Purpose | System health | Trade execution |
| Frequency | Every 5 min check | Per trade event |
| Alert Types | Process/log issues | Positions/P&L |
| Urgency | ⚠️ Warnings | 📊 Info + ⚠️ Errors |
| Same Bot | ✅ Yes | ✅ Yes |
| Same Chat | ✅ Yes | ✅ Yes |

## Advanced: Custom Notifications

Want to add your own custom alerts? Edit `trader.py`:

```python
# Example: Alert on large wins
if pnl > 10:
    self.telegram.send_message(
        f"<b>🎉 BIG WIN!</b>\n\n"
        f"Made ${pnl:.2f} on {asset}!",
        parse_mode="HTML"
    )
```

## Useful Commands

```bash
# Test notifications
python3 test_trader_telegram.py

# Check if enabled
grep telegram config.json

# View trader logs
tail -f trading.out

# Check if traders running
./check_processes.sh

# Restart traders
./restart_all.sh
```

## Files

```
telegram_config.json          # Centralized bot config
config.json                   # Event trader config
config_price_levels.json      # Price level trader config
telegram_notifier.py          # Notification logic
test_trader_telegram.py       # Test script
TRADER_TELEGRAM_SETUP.md      # This file
```

## Support

Your Telegram notifications are **already working**!

The traders have been sending notifications since you enabled them in the config.

To verify:
1. Run test script: `python3 test_trader_telegram.py`
2. Check recent logs: `tail -50 trading.out | grep -i telegram`
3. Look for past trade notifications in your Telegram chat

---

**Status:** ✅ **ENABLED AND WORKING**

Both traders are configured and sending Telegram alerts using your existing bot!
