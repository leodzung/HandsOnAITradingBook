# Position Manager Feature Comparison

## Field-by-Field Analysis

### Common Fields (Both Managers)
| Field | Shared PM | Short-Expiry PM | Purpose |
|-------|-----------|-----------------|---------|
| market_id | ✅ | ✅ | Identify the market |
| token_id | ✅ | ✅ | Token being traded |
| entry_time | ✅ | ✅ | When position opened |
| entry_price | ✅ | ✅ | Entry price |
| size | ✅ | ✅ | Position size ($) |
| exit_time | ✅ | ✅ | When position closed |
| exit_price | ✅ | ✅ | Exit price |
| pnl | ✅ | ✅ | Profit/loss ($) |
| status | ✅ | ✅ | OPEN/CLOSED |
| exit_reason | ✅ | ✅ | Why position closed |
| highest_price_seen | ✅ | ✅* | For trailing stops |
| lowest_price_seen | ✅ | ✅* | For trailing stops |

*Short-expiry has these but via migration

---

## Unique Fields - Analysis

### Short-Expiry ONLY

#### 1. **`outcome` (YES/NO) vs `side` (BUY/SELL)**

**Why different?**
- **Shared PM**: Traditional trading terminology (BUY/SELL)
- **Short-Expiry PM**: Prediction market terminology (YES/NO)

**Question:** Should all bots use `outcome`?
- ✅ **YES** - All bots trade prediction markets
- ✅ Event trader and price-level trader also trade YES/NO
- ❌ Using `side` is legacy terminology from traditional trading

**Recommendation:** Shared PM should use `outcome` instead of `side`

---

#### 2. **`bucket` (ultra_short/short/medium)**

**Why unique to short-expiry?**
- Short-expiry has 3-bucket architecture with different strategies:
  - **Ultra-short (0-24h)**: High urgency, time decay focus
  - **Short (24-72h)**: Moderate urgency, momentum signals
  - **Medium (72-168h)**: Lower urgency, fundamental analysis
- Each bucket has different:
  - Position limits
  - Stop-loss/take-profit thresholds
  - Max position sizes
  - Slippage tolerances

**Do other bots need this?**
- Event trader: ❌ No - single strategy
- Price-level trader: ❌ No - single strategy

**Conclusion:** Legitimately unique to short-expiry

---

#### 3. **`hours_to_expiry_at_entry`**

**Why unique to short-expiry?**
- Critical for analyzing time-decay patterns
- Used for pre-expiry exit (close 2 hours before expiry)
- ML feature for model training

**Do other bots need this?**
- Event trader: ⚠️ **MAYBE** - could use for time-based exits
- Price-level trader: ⚠️ **MAYBE** - could use for risk management

**Example use case:**
```python
# Exit positions approaching expiry
if position['hours_to_expiry_at_entry'] < 2:
    close_position(position, reason='pre_expiry_exit')
```

**Recommendation:** Useful for ALL bots, should be in shared PM

---

#### 4. **`edge` (Expected advantage)**

**Why unique to short-expiry?**
- Stores the calculated edge from signal generation
- Example: If market price is 0.40 but model thinks 0.45, edge = 0.05
- Used for position sizing (larger positions when edge is high)

**Do other bots need this?**
- Event trader: ✅ **YES** - calculates edge in signal generation
- Price-level trader: ✅ **YES** - has edge calculation

**Current workaround:** Other bots could store in `metadata` JSON, but less convenient

**Recommendation:** Should be in shared PM

---

#### 5. **`confidence` (Signal confidence 0-1)**

**Why unique to short-expiry?**
- ML model confidence score
- Used for position sizing: `size = max_size * confidence`
- Risk management: only trade when confidence > min_threshold

**Do other bots need this?**
- Event trader: ✅ **YES** - has confidence scoring
- Price-level trader: ✅ **YES** - could use for sizing

**Recommendation:** Should be in shared PM

---

#### 6. **`signal_reason` (Strategy that triggered)**

**Why unique to short-expiry?**
- Tracks which strategy generated the signal:
  - `"arbitrage"` - YES + NO < 0.98
  - `"momentum"` - Price change > 2% in 1h
  - `"mean_reversion"` - Wide spread reversion
- Used for strategy performance analysis

**Do other bots need this?**
- Event trader: ✅ **YES** - uses multiple event sources (GDELT, NewsAPI, RSS)
- Price-level trader: ⚠️ **MAYBE** - single strategy but could expand

**Recommendation:** Should be in shared PM

---

#### 7. **`features_json` (Full feature set)**

**Why unique to short-expiry?**
- Stores all 41 features used for signal generation
- Critical for ML model training (Phase 2)
- Enables post-trade analysis and feature importance

**Example:**
```json
{
  "market_probability": 0.40,
  "hours_to_expiry": 24.0,
  "volume_24h": 112107,
  "price_change_1h": 0.02,
  "spread_pct": 3.5,
  "momentum_score": 0.65,
  ...
}
```

**Do other bots need this?**
- Event trader: ⚠️ **MAYBE** - could help analyze event quality
- Price-level trader: ⚠️ **MAYBE** - could help tune levels

**Conclusion:** Primarily for ML-focused bots, but could be useful for all

---

#### 8. **`current_price` (Continuously updated)**

**Why unique to short-expiry?**
- Tracks current market price for open positions
- Updated every position check cycle (60s)
- Used for real-time P&L monitoring

**Do other bots need this?**
- Event trader: ✅ **YES** - checks positions every cycle
- Price-level trader: ✅ **YES** - monitors price levels

**Recommendation:** Should be in shared PM

---

#### 9. **`pnl_pct` (Percentage P&L)**

**Why unique to short-expiry?**
- Calculated as: `(exit_price - entry_price) / entry_price * 100`
- More intuitive than dollar P&L for comparing trades
- Used for stop-loss/take-profit (e.g., "close if down 10%")

**Do other bots need this?**
- Event trader: ✅ **YES** - easier to compare trades
- Price-level trader: ✅ **YES** - percentage-based stops

**Recommendation:** Should be in shared PM

---

#### 10. **Multiple positions per market (UNIQUE constraint)**

**Schema difference:**
```python
# Shared PM: One position per market
PRIMARY KEY (market_id)

# Short-Expiry PM: Multiple positions per market
id INTEGER PRIMARY KEY AUTOINCREMENT,
UNIQUE(market_id, outcome)  # Can hold YES and NO simultaneously
```

**Why unique to short-expiry?**
- Can trade BOTH sides of a market:
  - Hold YES on "BTC > $70k"
  - Hold NO on "BTC > $70k"
- Useful for arbitrage strategies

**Do other bots need this?**
- Event trader: ❌ **NO** - picks one side per event
- Price-level trader: ❌ **NO** - single position per level

**Conclusion:** Legitimately unique to short-expiry

---

## Summary: Which Fields Should Be Shared?

### ✅ Should be in Shared PositionManager

| Field | Current Status | Benefit |
|-------|----------------|---------|
| `outcome` (not `side`) | ❌ Shared uses `side` | Correct terminology for prediction markets |
| `hours_to_expiry_at_entry` | ❌ Short-expiry only | Pre-expiry exits for ALL bots |
| `edge` | ❌ Short-expiry only | Better position sizing for ALL bots |
| `confidence` | ❌ Short-expiry only | Risk-adjusted sizing for ALL bots |
| `signal_reason` | ❌ Short-expiry only | Strategy performance tracking for ALL bots |
| `current_price` | ❌ Short-expiry only | Real-time P&L for ALL bots |
| `pnl_pct` | ❌ Short-expiry only | Easier trade comparison for ALL bots |

### ⚠️ Optional (Could use `metadata` JSON)

| Field | Current Status | Use Case |
|-------|----------------|----------|
| `features_json` | ❌ Short-expiry only | ML training, analysis |
| `stop_loss_pct` | ✅ Shared PM has it | Per-position SL thresholds |
| `take_profit_pct` | ✅ Shared PM has it | Per-position TP thresholds |

### ✅ Legitimately Unique to Short-Expiry

| Field | Reason |
|-------|--------|
| `bucket` | Only short-expiry has 3-bucket architecture |
| UNIQUE(market_id, outcome) | Only short-expiry holds multiple positions per market |

---

## Root Cause: Why Did This Happen?

### Historical Timeline

1. **Event trader created first** → Simple shared `PositionManager`
2. **Price-level trader reused** → Shared PM was sufficient
3. **Short-expiry trader created** → Advanced requirements:
   - ML model integration planned
   - Bucket-based architecture
   - Need to store features for training
   - Multiple outcomes per market

4. **Decision point:**
   - ❌ Enhance shared PM → Risk breaking event/price-level traders
   - ✅ Create custom PM → Fast, no risk to existing bots

### The Real Issue

**Shared PositionManager wasn't designed for extensibility**

The `metadata` JSON field exists, but:
- ❌ Less convenient than typed columns
- ❌ Can't query efficiently (e.g., "show all momentum signals")
- ❌ No type safety

---

## Recommended Solution

### Phase 1: Enhanced Shared PositionManager (2-3 hours)

Add missing fields to shared PM:
```python
class PositionManager:
    def _create_table(self):
        conn.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                # Existing fields...
                outcome TEXT,  # Replace 'side'
                hours_to_expiry_at_entry REAL,
                edge REAL,
                confidence REAL,
                signal_reason TEXT,
                current_price REAL,
                pnl_pct REAL,
                # ... rest
            )
        ''')
```

### Phase 2: Migrate Short-Expiry (1-2 hours)

Keep custom schema but use shared utilities:
```python
# src/bots/trader_short_expiry.py
from core.position_manager import PositionManager

class ShortExpiryPositionManager(PositionManager):
    def _create_table(self):
        # Call parent to get base schema
        super()._create_table()

        # Add short-expiry specific fields
        self._add_custom_fields(['bucket', 'features_json'])

    # Override to support multiple positions per market
    # ... custom methods ...
```

---

## Conclusion

**Most fields in short-expiry PM should actually be in the shared PM!**

The duplication happened because:
1. ✅ Shared PM wasn't extensible enough
2. ✅ Faster to create custom manager than enhance shared one
3. ❌ But now we have significant duplication

**Solution:** Enhance shared PM with missing fields, then consolidate.
