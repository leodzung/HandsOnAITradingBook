# URL Builder Added to PolymarketClient

## Summary

Added a centralized `build_market_url()` method to `PolymarketClient` for building correct Polymarket web URLs.

## Problem

- Multi-market events (BTC/ETH/GOLD price levels) require event-level URLs
- Standalone markets use individual market URLs
- Different URL formats were scattered across codebase (dashboard, etc.)
- No centralized way to build URLs consistently

## Solution

Added `PolymarketClient.build_market_url()` classmethod that:
- ✅ Handles multi-market event URLs (event-level)
- ✅ Handles standalone market URLs (market-level)
- ✅ Supports multiple input formats (asset, event_slug, market dict, market_slug)
- ✅ Provides sensible fallbacks

## Usage Examples

```python
from core.polymarket_client import PolymarketClient

# Using asset symbol (for known multi-market events)
url = PolymarketClient.build_market_url(asset='BTC')
# Returns: https://polymarket.com/event/what-price-will-bitcoin-hit-before-2027

# Using event slug directly
url = PolymarketClient.build_market_url(event_slug='my-event-slug')
# Returns: https://polymarket.com/event/my-event-slug

# Using market dictionary
market = {'slug': 'my-market-slug'}
url = PolymarketClient.build_market_url(market=market)
# Returns: https://polymarket.com/market/my-market-slug

# Using market slug directly
url = PolymarketClient.build_market_url(market_slug='my-market-slug')
# Returns: https://polymarket.com/market/my-market-slug
```

## Known Event Slugs

Currently configured multi-market events:

```python
EVENT_SLUGS = {
    'BTC': 'what-price-will-bitcoin-hit-before-2027',
    'ETH': 'what-price-will-ethereum-hit-before-2027',
    'GOLD': 'what-will-gold-gc-hit-by-end-of-february',
}
```

To add more events, update this dictionary in `PolymarketClient`.

## Benefits

1. **Consistency**: Single source of truth for URL building
2. **Maintainability**: Easy to update if Polymarket changes URL structure
3. **Flexibility**: Supports both event-level and market-level URLs
4. **Documentation**: Clear docstring with examples
5. **Future-proof**: Easy to extend with new event types

## Where to Use

Use this method anywhere you need Polymarket web URLs:
- Logging
- Telegram notifications
- Dashboard links
- Email reports
- Error messages
- Documentation

## Testing

All tests passing:
- Asset-based URL building ✅
- Event slug URL building ✅
- Market dict URL building ✅
- Direct market slug URL building ✅
- Fallback behavior ✅
- Real market data ✅

## Files Changed

- `src/core/polymarket_client.py` - Added `build_market_url()` method and `EVENT_SLUGS` constant
