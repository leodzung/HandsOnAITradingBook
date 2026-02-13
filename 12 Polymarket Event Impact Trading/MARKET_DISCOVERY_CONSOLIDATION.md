# Market Discovery Consolidation

## Overview

All Polymarket bots now use a unified market discovery system through `MarketFilter.discover_markets()` in `src/core/polymarket_client.py`.

## Architecture

### Consolidated Discovery Method

**Location:** `src/core/polymarket_client.py` → `MarketFilter.discover_markets()`

**Features:**
1. **API-level filtering** - Uses /markets endpoint with filters (volume, expiry, liquidity)
2. **Event-based fetching** - Retrieves restricted markets from crypto events
3. **Client-side filtering** - Applies category filters (crypto, politics, sports, etc.)
4. **De-duplication** - Removes duplicate markets by conditionId

### Key Components

#### 1. Daily Crypto Event Slug Generator
```python
MarketFilter.get_daily_crypto_event_slugs(days_ahead=7)
```
Generates slugs for daily crypto price prediction events:
- `ethereum-above-on-february-13`
- `bitcoin-above-on-february-13`
- `solana-above-on-february-13`
- `xrp-above-on-february-13`

#### 2. All Crypto Events
```python
MarketFilter.get_all_crypto_event_slugs(days_ahead=7)
```
Combines:
- **Long-term events:** "what-price-will-bitcoin-hit-before-2027"
- **Daily events:** Generated dynamically for next N days

#### 3. Crypto Market Filter
```python
MarketFilter.filter_crypto_markets(markets)
```
Smart keyword-based filtering with:
- Long crypto keywords (bitcoin, ethereum, solana, etc.)
- Short keywords with word boundaries (btc, eth, sol, etc.)
- Sports exclusion keywords (to avoid false positives)

## Bot Updates

### Event-Based Bot (`src/bots/trader.py`)
**Status:** ✅ Updated

**Changes:**
- Uses `MarketFilter.get_all_crypto_event_slugs()` instead of static `CRYPTO_EVENT_SLUGS`
- Now fetches both long-term and daily crypto events

### Short-Expiry Bot (`src/bots/trader_short_expiry.py`)
**Status:** ✅ Updated

**Changes:**
- Replaced custom discovery logic with `MarketFilter.discover_markets()`
- Uses consolidated method for all 3 buckets (ultra-short, short, medium)
- Removed obsolete `_is_crypto_market()` method
- Crypto filtering now handled centrally

**Discovery Configuration:**
- **Ultra-short (0-24h):** Fetches 1 day of crypto events
- **Short (24-72h):** Fetches 3 days of crypto events
- **Medium (72-168h):** Fetches 7 days of crypto events

### Price-Level Bot (`src/bots/trader_price_levels.py`)
**Status:** ⚠️ Not updated (different discovery pattern for long-term markets)

## Test Results

**Ultra-short crypto markets (0-24h):**
- ✅ Found 44 markets
- Retrieved 200 markets from API
- Added 92 unique event-based markets from 6 events
- Filtered to 44 crypto markets

**Example markets found:**
- "Will the price of Ethereum be above $1,800 on February 13?"
- "Will the price of Bitcoin be above $60,000 on February 13?"
- "Will the price of Solana be above $40 on February 13?"

## Benefits

1. **Consistency** - All bots use the same discovery logic
2. **Maintainability** - Single source of truth for market discovery
3. **Completeness** - Automatically fetches restricted crypto events
4. **Flexibility** - Easy to add new event types or categories
5. **Performance** - Efficient de-duplication and filtering

## API Documentation Findings

### Working Approach
- ✅ Use `tag_id=21` for crypto markets (NOT `tag='crypto'`)
- ✅ Use `tag_id=1312` for crypto price markets
- ✅ Fetch restricted markets via event slugs

### Issues Found
- ❌ `category='crypto'` parameter returns wrong markets (Trump deportations)
- ❌ `tag='crypto'` parameter also returns wrong markets
- ❌ Daily crypto price markets don't appear in /markets endpoint (restricted)

### Solution
Use hybrid approach:
1. Standard /markets with filters
2. Event-based fetching for restricted markets
3. Client-side category filtering

## Configuration

### Short-Expiry Bot Config (`config/config_short_expiry.json`)

Key settings:
```json
{
  "discovery": {
    "crypto_only": true,  // ✅ Now working!
    "ultra_short_hours": [0, 24],
    "short_hours": [24, 72],
    "medium_hours": [72, 168],
    "min_volume": {
      "ultra_short": 100,
      "short": 200,
      "medium": 300
    },
    "min_liquidity": {
      "ultra_short": 50,
      "short": 100,
      "medium": 150
    }
  }
}
```

## Next Steps

1. ✅ Consolidate discovery logic
2. ✅ Update event-based bot
3. ✅ Update short-expiry bot
4. ⏭️ Test short-expiry bot with new discovery
5. ⏭️ Restart short-expiry bot
6. ⏭️ Monitor for crypto position openings

## Related Files

- `src/core/polymarket_client.py` - MarketFilter class
- `src/bots/trader.py` - Event-based bot
- `src/bots/trader_short_expiry.py` - Short-expiry bot
- `config/config_short_expiry.json` - Short-expiry config
