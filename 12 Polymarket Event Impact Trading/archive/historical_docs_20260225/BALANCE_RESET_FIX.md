# Balance Reset Fix (2026-02-20)

## Problem Summary

The dashboard's balance reset function was not working because:

1. **Multiple bot instances were running** - The bots had been started multiple times, creating duplicate processes
2. **Bots only load balance once at startup** - The balance is read from the JSON file during initialization and never reloaded
3. **Restart only killed one instance** - The `manage_bots.sh` script uses PID files, which only track one process per bot

## What Was Broken

**Before the fix:**
- Event Trader: $1,000 (correct) ✅
- Price Level Trader: $28,318 (inflated from bug) ❌
- Short Expiry Trader: $93 (depleted) ❌

**Duplicate processes found:**
- `trader_price_levels.py`: 2 instances (PIDs 38101, 89540)
- `trader_short_expiry.py`: 2 instances (PIDs 8264, 89619)
- `trader.py`: 1 instance (PID 74942)

## Solution Applied

### 1. Fixed Dashboard Balance Reset (dashboard.py:1471-1493)

**Changed:**
```python
# OLD: Only restart via manage_bots.sh (which only kills PID file process)
if restart_bot:
    result = subprocess.run(
        ["bash", str(MANAGE_BOTS_SCRIPT), "restart", cfg["bot_arg"]],
        ...
    )
```

**To:**
```python
# NEW: Kill ALL instances before restarting
if restart_bot:
    # Kill ALL instances of the bot (not just the PID file one)
    bot_script = {
        "price_level": "trader_price_levels.py",
        "event": "trader.py",
        "short_expiry": "trader_short_expiry.py"
    }.get(cfg["key"])

    if bot_script:
        # Kill all instances matching the script name
        subprocess.run(["pkill", "-f", bot_script], ...)
        time.sleep(3)

    # Then restart via manage_bots.sh
    result = subprocess.run(
        ["bash", str(MANAGE_BOTS_SCRIPT), "restart", cfg["bot_arg"]],
        ...
    )
```

### 2. Manual Cleanup

Immediately fixed the current situation:
1. Killed all duplicate bot instances: `pkill -f "trader*.py"`
2. Reset balances to fresh values:
   - Event Trader: $1,000
   - Price Level Trader: $500
   - Short Expiry Trader: $500
3. Restarted all bots cleanly via `manage_bots.sh start all`

## Current Status (After Fix)

✅ All bots running with correct balances:
- **Event Trader** (PID 38646): $1,000.00
- **Price Level Trader** (PID 38661): $500.00
- **Short Expiry Trader** (PID 38674): $500.00

✅ Only ONE instance of each bot running
✅ Dashboard balance reset now works correctly

## How to Use Dashboard Balance Reset

1. Go to **Settings** tab in dashboard
2. Expand the trader you want to reset
3. Enter new balance amount
4. **IMPORTANT**: Check "Restart bot after reset" ✅
5. Check the confirmation checkbox
6. Click "Reset Balance"

The dashboard will now:
1. Kill ALL running instances of that bot
2. Write new balance to JSON file
3. Restart the bot cleanly
4. Bot loads the new balance on startup

## Prevention

**To prevent multiple bot instances:**

1. **Always use `manage_bots.sh` to start/stop bots** - Don't run `python trader.py` directly
2. **Check status before starting:** `./manage_bots.sh status`
3. **Use restart instead of manual stop+start:** `./manage_bots.sh restart <bot>`
4. **Check for orphaned processes:**
   ```bash
   ps aux | grep -E "trader.py|trader_price_levels.py|trader_short_expiry.py" | grep -v grep
   ```

## Technical Details

**Why the balance inflated to $28,318:**

The Price Level Trader had a bug (fixed in commit `6483177`) where `close_position()` wasn't passing the `outcome` argument, causing it to credit the account twice - once for YES and once for NO on every trade close. This bug has been fixed.

**Why balances don't update without restart:**

The bots load their balance once during initialization:
```python
def __init__(self, config: dict):
    ...
    self.balance = self._load_balance()  # Loads from JSON file
    ...

def _load_balance(self) -> float:
    with open(self.balance_file, 'r') as f:
        data = json.load(f)
        return data.get('balance', default)
```

The balance is stored in memory (`self.balance`) and only updated when trades are executed via `_save_balance()`. To pick up a manually edited balance file, the bot must be restarted.

## Related Issues

- Balance inflation bug: Fixed in commit `6483177` (2026-02-13)
- Dashboard restart: Now properly kills all instances before restart
- Circuit breaker config: Made explicit in all bot configs (commit `eeb84bb`)
