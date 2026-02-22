# CRITICAL FIX: Use /price Endpoint Instead of /book

## Problem
The `/book` endpoint returns **stale orderbook data** (showing 0.99/0.01) while the actual market prices are different.

## Root Cause
Known bug in Polymarket CLOB API:
- `/book` endpoint: Returns stale/ghost data ❌
- `/price` endpoint: Returns live accurate prices ✅

Reference: https://github.com/Polymarket/py-clob-client/issues/180

## Evidence
```bash
# WRONG: Using /book endpoint
curl "https://clob.polymarket.com/book?token_id=24168..."
Response: {"asks": [{"price": "0.990", ...}]}  # STALE!

# CORRECT: Using /price endpoint
curl "https://clob.polymarket.com/price?token_id=24168...&side=sell"
Response: {"price": "0.89"}  # ACCURATE!
```

## Solution

### Current (BROKEN) Implementation
```python
# polymarket_client.py - Line 562
def get_orderbook(self, token_id: str) -> Dict:
    response = self.session.get(
        f"{self.BASE_URL}/book",  # ❌ Returns stale data!
        params={'token_id': token_id},
        headers=self._get_headers()
    )
    return response.json()

# Line 615-622 in get_clob_prices()
yes_orderbook = self.get_orderbook(yes_token_id)
if side == 'BUY':
    yes_asks = yes_orderbook.get('asks', [])
    if yes_asks:
        result['yes'] = float(yes_asks[0]['price'])  # ❌ Stale price!
```

### NEW (FIXED) Implementation

Add new method to get accurate prices:

```python
def get_token_price(self, token_id: str, side: str = 'sell') -> Optional[float]:
    """
    Get accurate live price from /price endpoint (not stale /book data).

    Args:
        token_id: Token ID
        side: 'sell' for ask prices (cost to buy), 'buy' for bid prices (proceeds from selling)

    Returns:
        Current price or None

    Note: The /book endpoint returns stale data (0.99/0.01).
          Always use /price endpoint for accurate pricing.
          See: https://github.com/Polymarket/py-clob-client/issues/180
    """
    try:
        response = self.session.get(
            f"{self.BASE_URL}/price",
            params={
                'token_id': token_id,
                'side': side  # 'sell' = ask (buy price), 'buy' = bid (sell price)
            },
            headers=self._get_headers(),
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return float(data.get('price'))
    except Exception as e:
        print(f"Error fetching price for {token_id}: {e}")
        return None
```

Update `get_clob_prices()` to use the new method:

```python
def get_clob_prices(self, condition_id: str, side: str = 'BUY') -> Dict[str, Optional[float]]:
    """Get YES and NO prices from /price endpoint (not stale /book data)."""
    result = {'yes': None, 'no': None}

    # Get token IDs
    token_ids = self.get_token_ids(condition_id)
    yes_token_id = token_ids.get('yes_token_id')
    no_token_id = token_ids.get('no_token_id')

    if not yes_token_id or not no_token_id:
        return result

    # Map side to API parameter
    # BUY = we want to buy = need ask prices = 'sell' side in API
    # SELL = we want to sell = need bid prices = 'buy' side in API
    api_side = 'sell' if side == 'BUY' else 'buy'

    # Get prices from /price endpoint (NOT /book!)
    result['yes'] = self.get_token_price(yes_token_id, side=api_side)
    result['no'] = self.get_token_price(no_token_id, side=api_side)

    return result
```

## Testing

```python
# Test the fix
client = PolymarketClient()

# BTC > $68K market
condition_id = "0xd290ea4b4607f5b107e9988bd33dcd49edd5a1a275d2664fb869edc50af5f888"

# OLD (broken): Returns $0.99
old_prices = client.get_clob_prices_OLD(condition_id, side='BUY')
print(f"OLD /book endpoint: YES = ${old_prices['yes']}")  # 0.99 ❌

# NEW (fixed): Should return $0.89
new_prices = client.get_clob_prices(condition_id, side='BUY')
print(f"NEW /price endpoint: YES = ${new_prices['yes']}")  # 0.89 ✅
```

## Impact

This fix will:
1. ✅ Show correct prices ($0.89 instead of $0.99)
2. ✅ Stop filtering out tradeable markets
3. ✅ Match what users see on Polymarket web interface
4. ✅ Enable trading on markets that were previously rejected

## Files to Update

1. `src/core/polymarket_client.py`:
   - Add `get_token_price()` method
   - Update `get_clob_prices()` to use `/price` endpoint
   - Keep `get_orderbook()` for depth analysis (but don't use for pricing)

2. No changes needed to:
   - `src/core/price_fetcher.py` (uses `get_clob_prices()` which we'll fix)
   - Bot files (use PriceFetcher)
