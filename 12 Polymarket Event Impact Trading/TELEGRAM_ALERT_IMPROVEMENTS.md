# Telegram Alert Improvements - 2026-02-15

## Summary
All three trading bots now send Telegram alerts for critical failures instead of failing silently. This ensures you're notified of any issues that could stop the bots from trading.

## Changes by Bot

### 1. Event Trader (`trader.py`)

#### Already Had:
- ✅ Position opened notifications
- ✅ Position closed notifications
- ✅ Circuit breaker notifications

#### Added:
- ⚠️ **Trading cycle errors** - Alert when main loop encounters errors
- ⚠️ **Signal processing errors** - Alert when processing individual market signals fails

**Example scenarios now alerted:**
- API rate limiting
- Network connectivity issues during trading cycle
- Feature extraction failures
- Model prediction errors

---

### 2. Price-Level Trader (`trader_price_levels.py`)

#### Already Had:
- ✅ Position opened notifications
- ✅ Position closed notifications
- ✅ Circuit breaker notifications

#### Added:
- ⚠️ **Trading cycle errors** - Alert when main loop encounters errors
- ⚠️ **Market processing errors** - Alert when processing individual markets fails
- ⚠️ **Position monitoring errors** - Alert when position exit checks fail

**Example scenarios now alerted:**
- Feature extraction failures during market processing
- Price fetching errors during position monitoring
- Database connection issues
- API errors when fetching market data

---

### 3. Short-Expiry Trader (`trader_short_expiry.py`)

#### Already Had:
- ✅ Position opened notifications

#### Added (CRITICAL):
- 🆕 **Position closed notifications** - Was completely missing!
  - Now notifies on all position exits (stop-loss, take-profit, expiry, market closed)
  - Includes P&L, exit reason, and bucket information
- 🆕 **Circuit breaker notifications** - Was missing!
  - Alerts when consecutive losses trigger trading pause

#### Added (Error Alerts):
- ⚠️ **Main loop errors** - Alert on critical failures in main trading loop
- ⚠️ **Market discovery errors** - Alert when discovering ultra-short, short, or medium markets fails
- ⚠️ **Position check errors** - Alert when checking position exit conditions fails

**Example scenarios now alerted:**
- Market discovery API failures (by bucket)
- Price fetching errors during position checks
- Database errors during position management
- Orderbook fetching failures

---

## Alert Types

### Error Alerts (`notify_error()`)
Format:
```
⚠️ ERROR - [Bot Name]

[Error description]

Time: YYYY-MM-DD HH:MM
```

**When sent:**
- Trading cycle crashes
- Market processing failures
- Position monitoring errors
- Market discovery failures

### Position Closed Notifications (`notify_position_closed()`)
Format:
```
✅/❌ CLOSED POSITION - [Bot Name]

Asset: [BTC/ETH/etc]
Side: [YES/NO]
Entry: $X.XXX
Exit: $X.XXX
P&L: $±XX.XX (±XX.X%)
Reason: [Stop Loss/Take Profit/etc]

[Market question...]

[Market ID]
```

**When sent:**
- Stop-loss triggered
- Take-profit triggered
- Trailing stop triggered
- Market expired
- Market closed
- Manual exit

### Circuit Breaker Notifications (`notify_circuit_breaker()`)
Format:
```
⚠️ CIRCUIT BREAKER ACTIVATED - [Bot Name]

Trading paused after [N] consecutive losses.
Will resume in [X.X] hours.

Time: YYYY-MM-DD HH:MM
```

**When sent:**
- Consecutive loss threshold reached (typically 3 losses)
- Trading automatically paused to prevent further losses

---

## Implementation Details

### How It Works

1. **TelegramNotifier class** (`src/monitoring/telegram_notifier.py`)
   - Uses Telegram Bot API to send messages
   - Supports HTML formatting for readability
   - Gracefully handles disabled/missing credentials

2. **Error Handling Pattern**
   ```python
   try:
       # Trading logic
   except Exception as e:
       logger.error(f"Error: {e}", exc_info=True)
       self.telegram.notify_error(
           f"⚠️ [Error type]:\n{str(e)[:200]}",
           bot_name="[Bot Name]"
       )
   ```

3. **Position Closed Pattern**
   ```python
   # Close position logic
   self.position_manager.close_position(...)

   # Send notification
   self.telegram.notify_position_closed(
       market_id=market_id,
       asset=asset,
       outcome=outcome,
       entry_price=entry_price,
       exit_price=exit_price,
       position_size=size,
       pnl=pnl,
       pnl_pct=pnl_pct,
       exit_reason=reason,
       bot_name="[Bot Name]"
   )
   ```

### Configuration

Telegram notifications are configured in each bot's config file:

```json
"telegram": {
    "enabled": true,
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
}
```

**To enable:**
1. Create a Telegram bot via @BotFather
2. Get your chat ID via @userinfobot
3. Add credentials to config files

---

## Testing

Before deploying, test Telegram alerts:

```bash
cd "12 Polymarket Event Impact Trading"

# Test event trader notifications
python3 tests/test_trader_telegram.py

# Test by triggering a position (paper trading)
python3 src/bots/trader.py  # Watch for position opened/closed alerts

# Simulate an error (optional)
# Temporarily add a raise Exception("Test error") in trading cycle
```

---

## Benefits

1. **No more silent failures** - You're notified immediately when something breaks
2. **Complete position tracking** - All position opens/closes are logged to Telegram
3. **Risk management alerts** - Circuit breaker triggers are visible
4. **Faster debugging** - Error alerts include truncated error messages
5. **Peace of mind** - You know the bots are alive and working

---

## Files Modified

1. `src/bots/trader.py`
   - Added error alerts to trading cycle and signal processing

2. `src/bots/trader_price_levels.py`
   - Added error alerts to trading cycle, market processing, and position monitoring

3. `src/bots/trader_short_expiry.py`
   - Added position closed notifications (was completely missing!)
   - Added circuit breaker notifications
   - Added error alerts to main loop, market discovery, and position checks

---

## Next Steps

1. **Enable Telegram** - Add bot token and chat ID to all config files
2. **Monitor alerts** - Watch for any alerts during next trading session
3. **Adjust thresholds** - Fine-tune which errors warrant alerts vs. just logging
4. **Add more alerts** (optional):
   - Daily summary notifications
   - Low balance warnings
   - High slippage warnings (already logged, could notify)
   - Unusual market conditions

---

## Technical Notes

- All error messages are truncated to 200 characters to prevent spam
- Alerts use HTML formatting for better readability
- TelegramNotifier gracefully handles disabled state (enabled=false)
- Alerts never block trading - if Telegram fails, trading continues
- All bots log errors to both file logs AND Telegram

---

## Example Alert Flow

**Scenario:** Price-level bot encounters API error while processing BTC market

1. **Error occurs** - API rate limit hit during feature extraction
2. **Logged to file** - Full stack trace in `logs/` directory
3. **Telegram alert sent**:
   ```
   ⚠️ ERROR - Price-Level Trader

   Market processing error:
   Market: Will BTC hit $100K by Feb 28?
   Error: HTTPError: 429 Too Many Requests

   Time: 2026-02-15 14:23
   ```
4. **Bot continues** - Moves to next market, doesn't crash
5. **You respond** - See alert, check logs, adjust rate limits

---

## Maintenance

### Rotating Bot Tokens
If you need to rotate bot tokens:
1. Create new bot via @BotFather
2. Update all 3 config files
3. Send test message to verify
4. Revoke old bot token

### Muting Notifications
To temporarily disable without changing code:
```json
"telegram": {
    "enabled": false  // Set to false
}
```

### Alert Volume
Expected alert frequency (normal operation):
- **Position opened**: 0-10 per day (depends on market opportunities)
- **Position closed**: 0-10 per day (depends on hold times)
- **Errors**: 0-5 per day (rare if bots are stable)
- **Circuit breaker**: 0-1 per week (only if multiple losses)

If you're seeing >20 error alerts per day, investigate bot stability.
