# Slippage Configuration Across Bots

## Summary

**Each bot has its own separate slippage configuration**, but they use the same `SlippageEstimator` class.

---

## Configuration Files

| Bot | Config File | Slippage Config Section |
|-----|------------|------------------------|
| **Event Trader** | `config/config.json` | ✅ `slippage_estimation` |
| **Price-Level Trader** | `config/config_price_levels.json` | ✅ `slippage_estimation` |
| **Short-Expiry Trader** | `config/config_short_expiry.json` | ⚠️ `risk_management.max_slippage_bps` (different structure!) |
| **Arbitrage Bot** | `config/config_arbitrage.json` | ❌ No slippage config |

---

## Detailed Comparison

### 1. Event Trader (trader.py)

**Config**: `config/config.json`

```json
{
  "slippage_estimation": {
    "enabled": true,
    "max_slippage_bps": 100,           // 1% limit
    "max_slippage_dollars": 5.0,
    "orderbook_staleness_seconds": 10,
    "depth_buffer_pct": 0.10,          // 10% base buffer
    "volatility_adjustment": true,      // +20% for wide spreads
    "volume_limit_pct": 0.01,          // Max 1% of daily volume
    "warn_threshold_bps": 50           // Warning at 0.5%
  }
}
```

**Usage** (line 786):
```python
from slippage_estimator import SlippageEstimator
estimator = SlippageEstimator(config=self.config.get('slippage_estimation', {}))
```

---

### 2. Price-Level Trader (trader_price_levels.py)

**Config**: `config/config_price_levels.json`

```json
{
  "slippage_estimation": {
    "enabled": true,
    "max_slippage_bps": 100,           // 1% limit (SAME AS EVENT TRADER)
    "max_slippage_dollars": 5.0,
    "orderbook_staleness_seconds": 10,
    "depth_buffer_pct": 0.10,
    "volatility_adjustment": true,
    "volume_limit_pct": 0.01,
    "warn_threshold_bps": 50
  }
}
```

**Usage** (line 961):
```python
from core.slippage_estimator import SlippageEstimator
estimator = SlippageEstimator(config=self.config.get('slippage_estimation', {}))
```

**Note**: Identical config to event trader, but separate file allows independent tuning.

---

### 3. Short-Expiry Trader (trader_short_expiry.py)

**Config**: `config/config_short_expiry.json`

```json
{
  "risk_management": {
    "stop_loss_pct": { ... },
    "take_profit_pct": { ... },
    "max_slippage_bps": 150,  // 1.5% limit (DIFFERENT STRUCTURE!)
    "min_edge": 0.03,
    "min_confidence": 0.55
  }
}
```

**Usage**: ❌ **Does NOT use SlippageEstimator class!**
- Config exists but is not currently used in code
- Only has a `max_slippage_bps` value (150 bps)
- No orderbook simulation or buffer logic

**Status**: Placeholder config, not actively enforced.

---

### 4. Arbitrage Bot (arbitrage_bot.py)

**Config**: `config/config_arbitrage.json`

```json
{
  "risk_limits": {
    "max_single_position": 100,
    "max_total_exposure": 500,
    "min_volume_24h": 1000,
    "max_risk_score": 0.7
  }
}
```

**Usage**: ❌ **No slippage configuration**
- Only has a code comment: "Don't exceed 1% of 24h volume to avoid slippage"
- Uses volume limits instead of explicit slippage checks

**Status**: No slippage protection.

---

## Key Findings

### ✅ Bots That Use SlippageEstimator

Only **2 bots** currently use the SlippageEstimator class:
1. **Event Trader** (trader.py)
2. **Price-Level Trader** (trader_price_levels.py)

Both have:
- **Identical slippage settings** (100 bps max, 10% buffer, volatility adjustment enabled)
- **Separate config files** (can be tuned independently)
- **Same underlying logic** (share the `SlippageEstimator` class)

### ❌ Bots That Don't Use SlippageEstimator

2 bots do NOT use slippage estimation:
1. **Short-Expiry Trader** - Has config placeholder (150 bps) but doesn't enforce it
2. **Arbitrage Bot** - No slippage config at all

---

## Implications for Your Situation

### Problem Scope

The **100 bps slippage limit** is blocking trades in:
- ✅ Event Trader (trader.py)
- ✅ Price-Level Trader (trader_price_levels.py)

It does NOT affect:
- ❌ Short-Expiry Trader (no slippage checks)
- ❌ Arbitrage Bot (no slippage checks)

### Solution: Update Two Config Files

To fix the blocking issue, you need to update **BOTH**:

1. **config/config.json** (event trader)
2. **config/config_price_levels.json** (price-level trader)

**Recommended update**:
```json
{
  "slippage_estimation": {
    "enabled": true,
    "max_slippage_bps": 6000,        // 60% (was 100)
    "max_slippage_dollars": 50.0,    // $50 (was $5)
    "depth_buffer_pct": 0.10,
    "volatility_adjustment": false,   // DISABLE (was true)
    "volume_limit_pct": 0.01,
    "warn_threshold_bps": 3000       // 30% (was 50)
  }
}
```

### Option to Diverge Settings

Since each bot has its own config, you can:

**Option 1: Keep them identical** (easier to maintain)
- Update both to 6,000 bps
- Both bots use same risk tolerance

**Option 2: Customize per bot** (more flexibility)
- Event trader: 6,000 bps (moderate - more markets)
- Price-level trader: 1,500 bps (conservative - best markets only)
- Allows different risk profiles per strategy

**Option 3: Disable for one bot**
- Event trader: `"enabled": false` (no slippage checks)
- Price-level trader: Keep enabled at 6,000 bps

---

## Testing After Changes

After updating configs:

1. **Restart both bots**:
   ```bash
   pkill -f trader.py
   pkill -f trader_price_levels.py
   nohup python3 trader.py >> trading.out 2>&1 &
   nohup python3 trader_price_levels.py >> trading_price_levels.out 2>&1 &
   ```

2. **Monitor logs**:
   ```bash
   tail -f trading.out
   tail -f trading_price_levels.out
   ```

3. **Check for slippage warnings**:
   ```bash
   grep "slippage" trading*.out | tail -20
   ```

---

## Recommendation

**Update both config files to 6,000 bps (60%) and disable volatility_adjustment.**

This will:
- ✅ Allow both bots to open positions on the 54 active markets
- ✅ Keep safety buffers (10-20% orderbook depth protection)
- ✅ Remove excessive spread penalty (was adding +20%)
- ✅ Maintain volume limits (1% of daily volume)
- ✅ Still reject truly illiquid markets

**Changes needed**:
```bash
# File 1: config/config.json
# File 2: config/config_price_levels.json
# Both need the same updates
```
