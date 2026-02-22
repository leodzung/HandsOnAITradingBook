# WebSocket Centralization Plan

**Date:** 2026-02-14
**Issue:** 3 separate WebSocket connections causing instability
**Solution:** Centralize WebSocket in PriceFetcher singleton

## Implementation Steps

### 1. Create Singleton PriceFetcher
- Add class-level `_instance` and `_lock`
- Implement `__new__()` to enforce singleton
- Move OrderbookManager to PriceFetcher
- Initialize WebSocket connection once

### 2. Update Bots
- Change from `PriceFetcher(client)` to `PriceFetcher.get_instance(client)`
- All bots will share the same instance
- No other code changes needed

### 3. Benefits
- ✅ Single WebSocket connection (reduces load)
- ✅ Better stability (no connection competition)
- ✅ Shared orderbook cache across bots
- ✅ Reduced memory usage
- ✅ Easier debugging (one connection to monitor)

### 4. Migration Path
1. Implement singleton pattern in PriceFetcher
2. Update bot initialization code
3. Restart all bots
4. Monitor WebSocket stability

## Code Changes

### price_fetcher.py
```python
import threading

class PriceFetcher:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, client=None, config=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, client=None, config=None):
        if self._initialized:
            return

        self.client = client
        self.config = config or {}

        # Initialize orderbook manager (WebSocket)
        orderbook_source = self.config.get('orderbook_source', 'websocket')
        self.client.initialize_orderbook_manager(source=orderbook_source)

        self._initialized = True
        logger.info("PriceFetcher singleton initialized with shared WebSocket")
```

### Bots (trader.py, trader_price_levels.py, trader_short_expiry.py)
```python
# OLD
self.price_fetcher = PriceFetcher(self.client)

# NEW
self.price_fetcher = PriceFetcher(self.client, config=self.config)
```

## Testing
1. Start all 3 bots
2. Check logs for "PriceFetcher singleton initialized" (should appear ONCE)
3. Monitor WebSocket connections (should be only 1)
4. Verify orderbook data is shared across bots
