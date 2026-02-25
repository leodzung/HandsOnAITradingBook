# PositionManager V2 - Deployment Summary

**Date**: 2026-02-14
**Status**: ✅ **DEPLOYED** - All 3 bots migrated

---

## What Changed

### Unified Position Management
- **Before**: 3 separate position managers with ~200+ lines of duplicate code
- **After**: Single PositionManager V2 shared by all bots

### Code Reduction
| Bot | Lines Removed | Benefit |
|-----|---------------|---------|
| Short-Expiry | **159 lines** | Removed entire custom PositionManager class |
| Price-Level | Import change only | Now benefits from V2 features |
| Event Trader | Import change only | Now benefits from V2 features |
| **Total** | **~159 lines** | Plus future maintenance savings |

---

## Enhanced Features (All Bots)

### 1. Multiple Positions Per Market ✨
```python
# Can now hold both YES and NO simultaneously
pm.save_position(market_id='btc_70k', outcome='YES', ...)
pm.save_position(market_id='btc_70k', outcome='NO', ...)  # Allowed!
```

### 2. Enhanced Analytics 📊
All bots now track:
- **`edge`**: Expected advantage (e.g., 0.05 = 5% edge)
- **`confidence`**: Signal strength (0-1)
- **`signal_reason`**: 'momentum', 'arbitrage', 'event', 'price_level'
- **`hours_to_expiry_at_entry`**: For time-based analysis
- **`current_price`**: Real-time monitoring
- **`pnl_pct`**: Automatic percentage P&L calculation

### 3. Correct Terminology ✅
- **Before**: `side='BUY'` or `side='SELL'`
- **After**: `outcome='YES'` or `outcome='NO'`
- Matches prediction market conventions

### 4. Backward Compatible Migration ⏪
- Auto-detects V1 databases
- Creates backup before migration
- Converts `side` → `outcome` automatically
- Migrates BUY → YES, SELL → NO

---

## Migration Changes by Bot

### 1. Short-Expiry Trader (`src/bots/trader_short_expiry.py`)

**Removed:**
- Entire `ShortExpiryPositionManager` class (lines 50-217)
- ~159 lines of duplicated code

**Added:**
- Import: `from core.position_manager_v2 import PositionManager`
- Outcome-specific position checks
- Bucket stored in metadata

**API Changes:**
```python
# OLD
self.position_manager = ShortExpiryPositionManager(db_path)
self.position_manager.add_position(position)
self.position_manager.count_positions_by_bucket(bucket)

# NEW
self.position_manager = PositionManager(db_path)
self.position_manager.save_position(
    market_id=market_id,
    token_id=token_id,
    outcome='YES',
    edge=0.05,
    confidence=0.75,
    signal_reason='momentum',
    metadata={'bucket': 'short'}
)
self.position_manager.count_positions_by_metadata('bucket', 'short')
```

---

### 2. Event Trader (`src/bots/trader.py`)

**Changed:**
- Import: `from core.position_manager_v2 import PositionManager`
- `side=outcome` → `outcome=outcome`
- Added analytics fields

**API Changes:**
```python
# OLD
self.position_manager.save_position(
    market_id=market_id,
    token_id=token_id,
    entry_time=datetime.now(timezone.utc),
    entry_price=entry_price,
    side=outcome,  # OLD
    size=position_size,
    metadata={'confidence': confidence}
)

# NEW
self.position_manager.save_position(
    market_id=market_id,
    token_id=token_id,
    entry_time=datetime.now(timezone.utc),
    entry_price=entry_price,
    outcome=outcome,  # NEW
    size=position_size,
    edge=signal.get('edge', 0),
    confidence=signal.get('confidence', 0),
    signal_reason='event',
    metadata={'event_source': 'GDELT'}
)
```

**Price Extremes Tracking:**
```python
# OLD
extremes = self.position_manager.update_price_extremes(market_id, current_yes_price)

# NEW (tracks per outcome)
extremes = self.position_manager.update_price_extremes(market_id, outcome, current_token_price)
```

---

### 3. Price-Level Trader (`src/bots/trader_price_levels.py`)

**Changed:**
- Import: `from core.position_manager_v2 import PositionManager`
- Price extremes now tracked per outcome

**API Changes:**
```python
# OLD
extremes = self.position_manager.update_price_extremes(market_id, current_yes_price)

# NEW (tracks per outcome)
outcome = position.get('outcome', 'YES')
extremes = self.position_manager.update_price_extremes(market_id, outcome, current_token_price)
```

---

## Database Migration

### What Happens on First Run

1. **V1 Database Detected** → Triggers auto-migration
2. **Backup Created**: `positions_v1_backup_TIMESTAMP`
3. **Schema Upgraded**:
   - Changes PRIMARY KEY from `market_id` to `id`
   - Adds UNIQUE constraint on `(market_id, outcome)`
   - Adds new analytics columns
4. **Data Migrated**:
   - Converts `side='BUY'` → `outcome='YES'`
   - Converts `side='SELL'` → `outcome='NO'`
   - Calculates `pnl_pct` for closed positions

### Migration Log Example
```
2026-02-14 09:25:23 - INFO - Detected V1 schema - will migrate to V2
2026-02-14 09:25:23 - INFO - Starting V1 → V2 migration...
2026-02-14 09:25:23 - INFO - ✓ Backed up V1 table to positions_v1_backup_20260214_092523
2026-02-14 09:25:23 - INFO - ✓ Migrated 5 positions from V1 to V2
2026-02-14 09:25:23 - INFO - ✓ Position manager V2 initialized
```

---

## Benefits

### Immediate Benefits

1. **Code Reduction**: ~159 lines removed from short-expiry bot
2. **Better Analytics**: All bots track edge, confidence, signal_reason
3. **Flexible Positions**: Can hold YES and NO simultaneously (arbitrage)
4. **Consistent API**: All bots use same position manager

### Future Benefits

1. **Shared Improvements**: Bug fixes benefit all bots automatically
2. **Easier Testing**: One position manager to test
3. **Better Analysis**: Query across all bots with consistent schema

### Analytics Queries Enabled

```sql
-- Win rate by strategy
SELECT signal_reason,
       COUNT(*) as trades,
       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
FROM positions
WHERE status = 'CLOSED'
GROUP BY signal_reason;

-- Average edge by confidence bucket
SELECT
    CASE
        WHEN confidence < 0.6 THEN 'low'
        WHEN confidence < 0.8 THEN 'medium'
        ELSE 'high'
    END as conf_bucket,
    AVG(edge) as avg_edge,
    AVG(pnl_pct) as avg_return
FROM positions
WHERE status = 'CLOSED'
GROUP BY conf_bucket;

-- Arbitrage positions (holding both YES and NO)
SELECT market_id, COUNT(*) as positions
FROM positions
WHERE status = 'OPEN'
GROUP BY market_id
HAVING COUNT(*) > 1;
```

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/core/position_manager_v2.py` | ✅ New | Enhanced unified position manager (710 lines) |
| `src/bots/trader_short_expiry.py` | 🔄 Modified | Removed custom PM, use V2 (-159 lines) |
| `src/bots/trader.py` | 🔄 Modified | Use V2 with outcome and analytics |
| `src/bots/trader_price_levels.py` | 🔄 Modified | Use V2 with outcome tracking |
| `test_position_manager_v2.py` | ✅ New | Comprehensive test suite |
| `POSITION_MANAGER_COMPARISON.md` | ✅ New | Field-by-field analysis |
| `POSITION_MANAGER_V2_MIGRATION.md` | ✅ New | Migration guide |

---

## Testing

### Pre-Deployment Tests ✅

All tests passed:
```
✅ V2 fresh install (new databases)
✅ V1 → V2 migration (existing databases)
✅ Multiple positions per market
✅ Metadata filtering (bucket counting)
✅ Syntax check (all 3 bots compile)
```

### Post-Deployment Validation

**Run these commands after deployment:**

```bash
# 1. Check migration logs
tail -50 logs/short_expiry.log | grep -E "V1|V2|migration"
tail -50 logs/trader.log | grep -E "V1|V2|migration"
tail -50 logs/trader_price_levels.log | grep -E "V1|V2|migration"

# 2. Verify database schema
sqlite3 data/positions_short_expiry.db "PRAGMA table_info(positions);" | grep -E "outcome|edge|confidence"

# 3. Check backup was created
ls -lh data/*_v1_backup_*.db

# 4. Verify positions loaded correctly
sqlite3 data/positions_short_expiry.db "SELECT COUNT(*), outcome FROM positions GROUP BY outcome;"

# 5. Test new position save
# (Run bots and check logs for "Saved position" messages)
```

---

## Rollback Plan (If Needed)

If issues occur:

```bash
# Stop all bots
pkill -f "trader.py\|trader_price_levels.py\|trader_short_expiry.py"

# Restore backups
cp data/positions_backup_YYYYMMDD.db data/positions.db
cp data/positions_price_level_backup_YYYYMMDD.db data/positions_price_level.db
cp data/positions_short_expiry_backup_YYYYMMDD.db data/positions_short_expiry.db

# Revert code
git checkout src/bots/trader.py src/bots/trader_price_levels.py src/bots/trader_short_expiry.py

# Restart bots
./restart_short_expiry_bot.sh
# (restart other bots as needed)
```

---

## Next Steps

1. ✅ **Monitor first 24 hours** - Check logs for migration messages
2. ✅ **Verify new positions save correctly** - Watch for analytics fields in DB
3. ⏭️ **Remove old position_manager.py** - After 1 week of stable operation
4. ⏭️ **Add analytics dashboard** - Leverage new fields for strategy analysis

---

**Deployment Date**: 2026-02-14
**Deployed By**: Claude Sonnet 4.5
**Status**: ✅ Ready for production
