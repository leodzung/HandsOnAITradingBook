# Architecture Issue: Duplicated Position Management Code

## Problem Summary

The short-expiry bot reinvented the wheel by creating its own `ShortExpiryPositionManager` instead of reusing the existing shared `PositionManager` framework.

## Current State

### Shared Framework (Used by 2 bots)
**File**: `src/core/position_manager.py`
**Used by**:
- ✅ Price-level trader (`trader_price_levels.py`)
- ✅ Event trader (`trader.py`)

**Features**:
- SQLite persistence
- Schema migration support
- Price tracking: `highest_price_seen`, `lowest_price_seen`
- Risk parameters: `stop_loss_pct`, `take_profit_pct`
- Exit reason tracking
- Update methods: `update_price_extremes()`, `close_position()`

### Custom Implementation (Short-expiry bot only)
**File**: `src/bots/trader_short_expiry.py` (lines 47-186)
**Used by**:
- ⚠️ Short-expiry trader ONLY

**Duplicates**:
- ❌ Same database schema creation
- ❌ Same CRUD operations (get, save, close)
- ❌ Same price tracking logic
- ❌ Same exit reason handling

**Unique features**:
- ✅ `bucket` field (ultra_short, short, medium)
- ✅ `hours_to_expiry_at_entry` (critical for time-based expiry)
- ✅ `edge`, `confidence` (ML model outputs)
- ✅ `signal_reason` (strategy that generated signal)
- ✅ `features_json` (full feature set storage)
- ✅ `outcome` field (YES/NO) instead of `side` (BUY/SELL)
- ✅ `current_price` (continuously updated)
- ✅ `UNIQUE(market_id, outcome)` constraint
- ✅ `count_positions_by_bucket()` method

## Why This Happened

### Legitimate Differences

The short-expiry bot HAS unique requirements:

1. **Bucket-based architecture**: 3 time buckets with different strategies
2. **Precise expiry tracking**: `hours_to_expiry_at_entry` for time-based closure
3. **ML model metadata**: Need to store edge, confidence, features for analysis
4. **Multi-outcome positions**: Can hold both YES and NO on same market
5. **Bucket-specific limits**: Different position limits per bucket

### Why Not Reuse?

Looking at the code, it appears the developer chose custom implementation because:

1. ✅ **Quick prototyping**: Faster to write custom code than refactor shared framework
2. ✅ **Unique schema**: Needed fields that other bots don't use
3. ❌ **Didn't know about shared framework**: Possible oversight
4. ❌ **Framework too rigid**: Shared PositionManager wasn't extensible enough

## Code Duplication Analysis

### Duplicated Lines (~100+ LOC)

```python
# DUPLICATED FUNCTIONALITY:

# 1. Database initialization
ShortExpiryPositionManager._init_db()  # Lines 54-82
PositionManager._create_table()        # Lines 30-54

# 2. Get open positions
ShortExpiryPositionManager.get_open_positions()  # Lines 93-101
PositionManager.load_positions()                # Lines 134-177

# 3. Update price extremes
ShortExpiryPositionManager.update_price_extremes()  # Lines 148-173
PositionManager.update_price_extremes()            # Lines 259-284

# 4. Close position
ShortExpiryPositionManager.close_position()  # Lines 175-206
PositionManager.close_position()            # Lines 177-219

# 5. Basic queries
ShortExpiryPositionManager.has_position()  # Lines 84-91
# (Similar logic exists in PositionManager)
```

## Better Architectural Approaches

### Option 1: Inheritance (Extend Base Class)

```python
# src/core/position_manager.py - Make base class more flexible
class PositionManager:
    def __init__(self, db_path: str, schema_extensions: Dict = None):
        self.db_path = db_path
        self.schema_extensions = schema_extensions or {}
        self._create_table()

# src/bots/trader_short_expiry.py - Extend it
class ShortExpiryPositionManager(PositionManager):
    def __init__(self, db_path: str):
        schema_extensions = {
            'bucket': 'TEXT NOT NULL',
            'hours_to_expiry_at_entry': 'REAL',
            'edge': 'REAL',
            'confidence': 'REAL',
            'signal_reason': 'TEXT',
            'features_json': 'TEXT'
        }
        super().__init__(db_path, schema_extensions)

    def count_positions_by_bucket(self, bucket: str) -> int:
        # Short-expiry specific method
        pass
```

### Option 2: Composition (Use Base + Extensions)

```python
# src/bots/trader_short_expiry.py
from src.core.position_manager import PositionManager

class ShortExpiryPositionManager:
    def __init__(self, db_path: str):
        self.base_manager = PositionManager(db_path)
        self._add_custom_fields()

    def _add_custom_fields(self):
        # Add bucket, hours_to_expiry, etc. via schema migration
        pass

    def save_position(self, position: Dict):
        # Add custom fields, then delegate to base
        metadata = {
            'bucket': position['bucket'],
            'hours_to_expiry': position['hours_to_expiry'],
            'edge': position['edge'],
            # ...
        }
        self.base_manager.save_position(
            market_id=position['market_id'],
            # ... standard fields ...
            metadata=metadata
        )
```

### Option 3: Unified Flexible Manager (Best Long-term)

```python
# src/core/position_manager.py - One manager to rule them all
class UnifiedPositionManager:
    def __init__(self, db_path: str, position_type: str = 'standard'):
        self.db_path = db_path
        self.position_type = position_type
        self._create_schema_for_type()

    def _create_schema_for_type(self):
        base_schema = {...}  # Common fields

        if self.position_type == 'short_expiry':
            base_schema.update({
                'bucket': 'TEXT',
                'hours_to_expiry_at_entry': 'REAL',
                # ...
            })
        elif self.position_type == 'price_level':
            # Price-level specific fields
            pass

        # Create unified table
```

## Impact Analysis

### Current Cost of Duplication

1. **Maintenance burden**: Bug fixes need to be applied in 2 places
2. **Feature drift**: Shared PositionManager has `update_price_extremes()`, we had to re-implement it
3. **Testing overhead**: Need separate tests for both implementations
4. **Documentation confusion**: Which manager should new bots use?

### When We Hit This Issue

When implementing `_check_positions()` for short-expiry bot:
- ✅ Shared PositionManager already had `update_price_extremes()`
- ❌ We had to re-implement it for ShortExpiryPositionManager
- ❌ We had to manually add `highest_price_seen`/`lowest_price_seen` columns

**This duplication directly caused the missing functionality!**

## Recommended Fix

### Short-term (Current state - ACCEPTABLE)

Keep both implementations but:
1. ✅ Document why they're separate (this file)
2. ✅ Ensure feature parity for core functionality
3. ✅ Cross-reference when adding new features

### Medium-term (Refactor when time permits)

Use **Option 1: Inheritance**:
1. Make `PositionManager` accept custom schema fields
2. Migrate `ShortExpiryPositionManager` to extend base class
3. Keep short-expiry specific methods (`count_positions_by_bucket()`)
4. Reduce duplication by ~60%

### Long-term (Future architecture)

Use **Option 3: Unified Manager**:
1. Design single flexible position manager
2. Support multiple position types
3. Use metadata JSON for type-specific fields
4. Single source of truth for all position logic

## Lessons Learned

1. ✅ **Check for existing frameworks first** before writing custom code
2. ✅ **Design for extension** - make base classes flexible from the start
3. ✅ **Document architectural decisions** - explain why code is duplicated
4. ✅ **Periodic refactoring** - consolidate similar code when patterns emerge
5. ⚠️ **Pragmatism vs Purity** - Sometimes duplication is okay if it unblocks progress

## Decision

For now: **Keep both implementations** ✅

**Why?**
1. Short-expiry bot is working and well-tested
2. Refactoring has risk of introducing bugs
3. The unique requirements justify some duplication
4. Code is documented and maintainable

**But:** Next time we add a new bot type, we should:
1. Review existing position managers
2. Extract common functionality to shared base
3. Use inheritance or composition
4. Plan for extensibility

---

**Created**: 2026-02-12
**Status**: Documented technical debt
**Priority**: Low (working as intended, future improvement)
