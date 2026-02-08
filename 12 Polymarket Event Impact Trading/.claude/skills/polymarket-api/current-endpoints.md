# Current Polymarket API Usage in Project

This document lists all Polymarket API endpoints currently used in `polymarket_client.py`.

**IMPORTANT:** Before modifying any of these methods or assuming their behavior, check the official Polymarket API documentation using WebFetch.

## Gamma API Endpoints (Market Data - Public)

Base URL: `https://gamma-api.polymarket.com`

### Market Discovery

| Method | Endpoint | Purpose | Parameters |
|--------|----------|---------|------------|
| `get_markets()` | `GET /markets` | List all markets | limit, offset, active, closed |
| `get_market()` | `GET /markets/{condition_id}` | Get specific market by condition_id | condition_id |
| `get_event()` | `GET /events/{slug}` | Get event details (includes restricted markets) | slug |
| `get_markets_from_event()` | `GET /events/{slug}` | Extract markets from event | slug |

### Price Data

| Method | Endpoint | Purpose | Notes |
|--------|----------|---------|-------|
| `get_market_prices()` | Derived from market data | Get YES/NO prices | Uses token prices from market object |
| `get_market_yes_price()` | Derived from market data | Get YES price only | Falls back to event slug lookup |
| `get_market_outcome_price()` | Derived from market data | Get specific outcome price | Searches tokens by outcome string |
| `get_price_from_market()` | Local parsing | Extract price from market dict | Pure data transformation |

### Historical Data

| Method | Endpoint | Purpose | Parameters |
|--------|----------|---------|------------|
| `get_historical_prices()` | Unknown/Not documented | Historical price series | token_id, start_ts, end_ts, interval |

**⚠️ WARNING:** `get_historical_prices()` implementation needs verification against docs - endpoint path and parameters may be incorrect.

## CLOB API Endpoints (Order Book - Requires Auth)

Base URL: `https://clob.polymarket.com`

### Market Data

| Method | Endpoint | Purpose | Parameters |
|--------|----------|---------|------------|
| `get_clob_market()` | Unknown path | Get CLOB market data | condition_id |
| `get_token_ids()` | Derived from CLOB market | Extract token IDs for YES/NO | condition_id |
| `get_orderbook()` | Unknown path | Get order book | token_id |
| `get_trades()` | Unknown path | Get recent trades | token_id, limit |

### Execution Prices

| Method | Endpoint | Purpose | Notes |
|--------|----------|---------|-------|
| `get_execution_prices()` | Unknown path | Get best bid/ask | Returns execution prices for token |
| `get_market_price()` | Derived from orderbook | Get mid price | Calculates from best bid/ask |
| `get_market_spread()` | Derived from orderbook | Get bid-ask spread | Calculates from orderbook |

### Trading Operations

| Method | Endpoint | Purpose | Auth Required |
|--------|----------|---------|---------------|
| `place_order()` | Unknown path | Place limit order | Yes - API key + signature |
| `get_positions()` | Unknown path | Get open positions | Yes |
| `get_balance()` | Unknown path | Get USDC balance | Yes |

**⚠️ CRITICAL:** All CLOB endpoint paths in the table marked "Unknown path" need to be verified against official documentation before use or modification.

## Known Issues & Documentation Gaps

1. **CLOB endpoint paths** - Many methods don't show explicit endpoint paths in code. Need to verify:
   - `/orderbook` vs `/order-book` vs `/books/{token_id}`
   - `/trades` vs `/trade-history`
   - Authentication endpoint structure

2. **Historical prices** - Implementation exists but endpoint is unclear. Verify:
   - Correct Gamma or CLOB API?
   - Parameter names and formats
   - Response structure

3. **WebSocket feeds** - `orderbook_websocket.py` exists but not analyzed here. Verify:
   - Connection URL
   - Message format
   - Subscription mechanism

4. **Rate limits** - No rate limiting visible in current implementation. Check docs for:
   - Requests per second/minute
   - Different limits for public vs authenticated
   - Backoff strategies

## Helper/Utility Methods (No API Calls)

These methods transform data but don't make API calls:
- `get_market_category()` - Static method to categorize markets
- `_get_headers()` - Generate request headers
- `_sign_request()` - Sign authenticated requests

## Recommended Actions

Before working with any Polymarket API code:

1. **Fetch official docs:** Use WebFetch to get latest API documentation
2. **Verify endpoints:** Check that paths match official docs
3. **Validate parameters:** Ensure parameter names and types are correct
4. **Check responses:** Verify response structure matches expectations
5. **Review authentication:** Confirm auth header format for CLOB API
6. **Test error handling:** Ensure proper handling of 4xx/5xx responses

## Quick Reference Commands

```python
# Fetch CLOB API docs
WebFetch("https://docs.polymarket.com/#clob-api", "Extract all available endpoints with their paths, methods, parameters, and response formats")

# Fetch Gamma API docs
WebFetch("https://docs.polymarket.com/#gamma-api", "Extract all available endpoints with their paths, methods, parameters, and response formats")

# Check for Python SDK
WebFetch("https://github.com/Polymarket", "Search for official Python SDK or client library")
```
