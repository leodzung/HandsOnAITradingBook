# Market Filtering Centralization

## Overview
Centralized market quality filtering logic to ensure consistency across all trading bots.

## Location
**`src/core/polymarket_client.py`** - `MarketFilter.filter_by_quality()`

## Method Signature
```python
@staticmethod
def filter_by_quality(markets: List[Dict],
                     price_fetcher,
                     min_price: float = 0.05,
                     max_price: float = 0.95,
                     max_spread_pct: float = 10.0,
                     check_last_trade: bool = True) -> List[Dict]
```

## What It Filters

### 1. **Spread Filter**
- Calculates bid-ask spread percentage
- Rejects markets with `spread_pct > max_spread_pct`
- Ensures sufficient liquidity

### 2. **Price Range Filter**
- Rejects extreme probabilities (< 5% or > 95% by default)
- Uses PriceFetcher to get current ASK prices
- Handles None prices gracefully:
  - Skips if both YES and NO are None
  - Accepts if at least one price is valid
  - Checks whichever price is available

### 3. **Price Complementarity**
- Since YES + NO ≈ 1.0, checking one validates both
- If YES = 0.05, then NO = 0.95 (both at extremes)
- If YES = 0.50, then NO = 0.50 (both in range)

### 4. **Trade Activity Filter** (optional)
- Checks if market has `lastTradePrice` (recent trades)
- Can be disabled with `check_last_trade=False`

## Usage Example

### Short-Expiry Bot
```python
from core.polymarket_client import MarketFilter

filtered_markets = MarketFilter.filter_by_quality(
    markets=markets,
    price_fetcher=self.price_fetcher,
    min_price=0.05,
    max_price=0.95,
    max_spread_pct=10.0,  # Bucket-specific
    check_last_trade=True
)
```

### Other Bots
Any bot can use this method by:
1. Having a `PriceFetcher` instance
2. Calling `MarketFilter.filter_by_quality()` with appropriate parameters

## Benefits

1. **Consistency** - All bots use the same quality criteria
2. **Maintainability** - One place to update filtering logic
3. **Testability** - Single method to test
4. **Flexibility** - Configurable parameters per bot/bucket
5. **None Handling** - Proper handling of missing price data

## Configuration

Each bot can customize filtering by adjusting parameters:
- `min_price` / `max_price` - Probability boundaries
- `max_spread_pct` - Liquidity threshold (can vary by bucket)
- `check_last_trade` - Whether to require recent trading activity

## Migration Status

- ✅ **Short-Expiry Bot** (`trader_short_expiry.py`) - Migrated to use centralized filter
- ✅ **Event Bot** (`trader.py`) - Migrated to use centralized filter
- ✅ **Price-Level Bot** (`trader_price_levels.py`) - Migrated to use centralized filter

**All three bots now use the centralized quality filtering!**

## Configuration Added

### Event Bot (`config/config.json`)
```json
"quality_filters": {
  "enabled": true,
  "min_price": 0.05,
  "max_price": 0.95,
  "max_spread_pct": 10.0,
  "check_last_trade": true
}
```

### Price-Level Bot (`config/config_price_levels.json`)
```json
"quality_filters": {
  "enabled": true,
  "min_price": 0.05,
  "max_price": 0.95,
  "max_spread_pct": 15.0,
  "check_last_trade": true
}
```

### Short-Expiry Bot (`config/config_short_expiry.json`)
Uses bucket-specific `max_spread_pct` values:
- Ultra-short: 10.0%
- Short: 8.0%
- Medium: 6.0%

## Next Steps

1. ✅ Migrate all three bots - **COMPLETE**
2. Monitor performance to tune quality filter thresholds
3. Add unit tests for `MarketFilter.filter_by_quality()`
4. Consider adding optional filters (e.g., min_volume at quality filter stage)
