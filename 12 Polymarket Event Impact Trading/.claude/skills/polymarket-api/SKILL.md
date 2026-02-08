---
name: polymarket-api
description: Reference Polymarket API documentation (CLOB, Gamma, and related endpoints) before making assumptions about API behavior. Use when working with Polymarket API calls, endpoints, parameters, or responses.
user-invocable: false
allowed-tools: WebFetch, Read, Grep
---

# Polymarket API Documentation Reference

When working with Polymarket APIs, ALWAYS consult the official documentation before making assumptions about:
- Endpoint URLs and paths
- Request parameters and their types
- Response structures and fields
- Authentication requirements
- Rate limits and best practices

## API Endpoints

### 1. CLOB API (Central Limit Order Book)
**Base URL:** `https://clob.polymarket.com`

**Documentation:** https://docs.polymarket.com/#clob-api

The CLOB API handles:
- Order placement and management
- Trade execution
- Order book data
- Authenticated trading operations

**Before using CLOB endpoints:**
1. Fetch the latest docs: `https://docs.polymarket.com/#clob-api`
2. Verify the endpoint path, method, and parameters
3. Check authentication requirements (API key, signature, etc.)
4. Understand the response structure

### 2. Gamma API (Market Data)
**Base URL:** `https://gamma-api.polymarket.com`

**Documentation:** https://docs.polymarket.com/#gamma-api

The Gamma API provides:
- Market discovery and search
- Event and market metadata
- Historical market data
- Public market information (no auth required)

**Before using Gamma endpoints:**
1. Fetch the latest docs: `https://docs.polymarket.com/#gamma-api`
2. Verify endpoint paths (e.g., `/markets`, `/events/{slug}`, `/markets/{condition_id}`)
3. Check query parameters (limit, offset, active, closed, etc.)
4. Understand pagination and filtering options

### 3. Other Related APIs

**Subgraph/GraphQL API:** For historical trades and on-chain data
- May require different authentication
- Check docs before querying

**WebSocket Feeds:** For real-time order book updates
- Verify connection parameters and message formats
- Check reconnection logic requirements

## Workflow

When you need to use or modify Polymarket API code:

1. **Identify the endpoint** being used or needed
2. **Fetch documentation** using WebFetch:
   - Main docs: `https://docs.polymarket.com/`
   - Specific sections: Navigate to CLOB or Gamma sections
3. **Verify current implementation** against docs:
   - Are parameters correct?
   - Is the response structure as expected?
   - Are we handling errors properly?
4. **Check for updates** - API may have changed since code was written
5. **Document assumptions** - If docs are unclear, note what you're assuming

## Common Documentation URLs

- **Main Docs:** https://docs.polymarket.com/
- **CLOB API Reference:** https://docs.polymarket.com/#clob-api
- **Gamma API Reference:** https://docs.polymarket.com/#gamma-api
- **Authentication Guide:** https://docs.polymarket.com/#authentication
- **Python SDK (if available):** Check for official py-clob-client or similar

## Examples of When to Check Docs

### ✅ DO check docs when:
- Adding a new API endpoint call
- Debugging unexpected API responses
- Implementing error handling
- Understanding rate limits
- Adding new parameters to existing calls
- Seeing API errors or 4xx/5xx responses

### ❌ DON'T assume:
- Parameter names without checking
- Response field structures
- Default values for optional parameters
- Authentication header formats
- Endpoint paths based on convention

## Current Implementation Files

The following files in this project make Polymarket API calls:
- `polymarket_client.py` - Main API client wrapper
- `trader.py` - Event-based trading bot
- `trader_price_levels.py` - Price-level trading bot
- `price_tracker.py` - Price tracking system
- `orderbook_websocket.py` - WebSocket order book feed
- `arbitrage_bot.py` - Arbitrage detection bot

**Before modifying these files, review the relevant API documentation section.**

## Action Items

When invoked or when working with Polymarket API code:

1. Use WebFetch to retrieve the relevant documentation page
2. Extract the specific endpoint, parameters, and response format
3. Compare with the current implementation
4. Point out any discrepancies or assumptions
5. Suggest corrections based on official docs

## Notes

- Polymarket APIs may evolve - always check for updates
- Some endpoints may be undocumented - use with caution
- Rate limits exist - implement proper backoff and retry logic
- Consider caching documentation locally for faster reference
