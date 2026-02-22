# get_clob_prices() - Detailed Explanation

## Function Signature

```python
def get_clob_prices(self, condition_id: str) -> Dict[str, Optional[float]]:
    """
    Get YES and NO prices from CLOB orderbook (not Gamma API estimates).

    Args:
        condition_id: Market condition ID (e.g., "0x246559691ae...")

    Returns:
        Dict with 'yes' and 'no' prices, e.g. {'yes': 0.99, 'no': 0.01}
        Returns None for prices if orderbook unavailable
    """
```

---

## Step-by-Step Walkthrough

### Step 1: Initialize Result Dictionary

```python
result = {'yes': None, 'no': None}
```

**What**: Creates an empty result with placeholders for YES and NO prices
**Why**: If we can't fetch prices, we return None instead of failing

---

### Step 2: Get Token IDs for YES and NO

```python
token_ids = self.get_token_ids(condition_id)
yes_token_id = token_ids.get('yes_token_id')
no_token_id = token_ids.get('no_token_id')
```

**What it does**:
- Calls `get_token_ids(condition_id)` which returns:
  ```python
  {
    'yes_token_id': '9894510651052373088408067031031513212801618531203062911959630395716258202132',
    'no_token_id':  '25335588587775299220522629630450090894992761076711207104201140528353393877506'
  }
  ```

**Why we need this**:
- Each Polymarket market has TWO separate tokens (YES and NO)
- Each token has its own orderbook
- We need both token IDs to fetch both orderbooks

**Example**:
```
Market: "Will Bitcoin reach $200k by Dec 31, 2026?"
├─ YES token (ID: 989451065...)  → "I think it will"
└─ NO token  (ID: 253355885...)  → "I think it won't"
```

---

### Step 3: Safety Check

```python
if not yes_token_id or not no_token_id:
    return result  # Returns {'yes': None, 'no': None}
```

**What**: If we can't find token IDs, bail out early
**Why**: Can't fetch orderbooks without token IDs

---

### Step 4: Fetch YES Token Orderbook

```python
yes_orderbook = self.get_orderbook(yes_token_id)
```

**What this calls**:
```
GET https://clob.polymarket.com/book?token_id=989451065...
```

**Returns**:
```json
{
  "market": "0x246559...",
  "asset_id": "989451065...",
  "bids": [
    {"price": "0.680", "size": "50"},
    {"price": "0.675", "size": "100"},
    {"price": "0.670", "size": "200"}
  ],
  "asks": [
    {"price": "0.999", "size": "100"},
    {"price": "1.000", "size": "500"}
  ]
}
```

**Key parts**:
- **`asks`**: People SELLING YES tokens (you can BUY from them)
- **`bids`**: People BUYING YES tokens (you can SELL to them)

---

### Step 5: Extract Best Ask for YES

```python
yes_asks = yes_orderbook.get('asks', [])
if yes_asks:
    # Best ask = price to BUY YES tokens
    result['yes'] = float(yes_asks[0]['price'])
```

**What**: Gets the **first ask** (best/lowest price to buy YES)

**Example**:
```python
asks = [
    {"price": "0.999", "size": "100"},  ← BEST ASK (cheapest to buy)
    {"price": "1.000", "size": "500"}
]

result['yes'] = 0.999  # This is what you'd pay to buy YES
```

**Why `asks[0]`?**
- Asks are sorted lowest to highest
- First ask = cheapest price to buy
- This is the **actual executable price**

---

### Step 6: Fetch NO Token Orderbook

```python
no_orderbook = self.get_orderbook(no_token_id)
```

**Same as Step 4, but for NO token**:
```
GET https://clob.polymarket.com/book?token_id=253355885...
```

**Returns**:
```json
{
  "asks": [
    {"price": "0.001", "size": "500"},
    {"price": "0.010", "size": "200"}
  ],
  "bids": [
    {"price": "0.000", "size": "100"}
  ]
}
```

---

### Step 7: Extract Best Ask for NO

```python
no_asks = no_orderbook.get('asks', [])
if no_asks:
    # Best ask = price to BUY NO tokens
    result['no'] = float(no_asks[0]['price'])
```

**Example**:
```python
asks = [
    {"price": "0.001", "size": "500"},  ← BEST ASK
    {"price": "0.010", "size": "200"}
]

result['no'] = 0.001  # This is what you'd pay to buy NO
```

---

### Step 8: Return Final Result

```python
return result
```

**Returns**:
```python
{
  'yes': 0.999,  # Best ask price for YES token
  'no': 0.001    # Best ask price for NO token
}
```

---

## Complete Example

### Input

```python
condition_id = "0x246559691ae64806ee51dcc5ca1d1216bf6e25d80127a3425b72ba559190e96f"
prices = client.get_clob_prices(condition_id)
```

### Execution Flow

```
1. get_token_ids(condition_id)
   ↓
   Returns: {
     'yes_token_id': '9894510651...',
     'no_token_id': '25335588587...'
   }

2. get_orderbook('9894510651...')  # YES token
   ↓
   API Call: GET /book?token_id=9894510651...
   ↓
   Returns: {
     'asks': [
       {'price': '0.999', 'size': '100'},
       {'price': '1.000', 'size': '500'}
     ]
   }
   ↓
   Extract: yes_price = 0.999

3. get_orderbook('25335588587...')  # NO token
   ↓
   API Call: GET /book?token_id=25335588587...
   ↓
   Returns: {
     'asks': [
       {'price': '0.001', 'size': '500'},
       {'price': '0.010', 'size': '200'}
     ]
   }
   ↓
   Extract: no_price = 0.001

4. Return: {'yes': 0.999, 'no': 0.001}
```

### Output

```python
{
  'yes': 0.999,  # Cost to BUY YES token from orderbook
  'no': 0.001    # Cost to BUY NO token from orderbook
}
```

---

## Key Concepts

### Why Use "Best Ask"?

**Ask** = Someone is ASKING this price to SELL to you
- You BUY from the asks
- Best ask = lowest price = cheapest to buy

**Bid** = Someone is BIDDING this price to BUY from you
- You SELL to the bids
- Best bid = highest price = best price to sell at

**Our bots always BUY** (open positions), so we use **best ask**.

### YES vs NO Tokens

In Polymarket:
- **YES token**: Pays $1 if event happens
- **NO token**: Pays $1 if event doesn't happen
- They're **separate tradable tokens** with separate orderbooks

**Example**:
```
Market: "Will BTC reach $200k by Dec 31, 2026?"

YES token:
  - Buy at: $0.999 (best ask)
  - Pays $1 if BTC reaches $200k
  - Expected profit: $0.001 (0.1%)

NO token:
  - Buy at: $0.001 (best ask)
  - Pays $1 if BTC doesn't reach $200k
  - Expected profit: $0.999 (99,900%)
```

### Why NOT Use Gamma API Prices?

**Gamma API** (`/markets/{id}`):
```json
{
  "outcomePrices": ["0.685", "0.315"]  ← Estimates/aggregates
}
```
- These are **estimates** (not from live orderbook)
- Updated periodically (not real-time)
- Don't reflect actual executable prices

**CLOB API** (`/book?token_id=...`):
```json
{
  "asks": [{"price": "0.999", "size": "100"}]  ← Actual limit orders
}
```
- These are **real limit orders** on the book
- Real-time executable prices
- What you actually pay when trading

---

## Why This Function Matters

### Before (Inconsistent):

```python
# Signal generation
market = get_market(condition_id)  # Gamma API
price = market['outcomePrices'][0]  # 0.685 (estimate)

# Execution
orderbook = get_orderbook(token_id)  # CLOB API
price = orderbook['asks'][0]['price']  # 0.999 (actual)

# Monitoring
market = get_market(condition_id)  # Gamma API again
price = market['outcomePrices'][0]  # 0.685 (estimate)

# Result: Entry at 0.999, monitoring at 0.685 → -31% loss!
```

### After (Consistent):

```python
# Signal generation
prices = get_clob_prices(condition_id)  # CLOB orderbook
price = prices['yes']  # 0.999 (actual)

# Execution
orderbook = get_orderbook(token_id)  # CLOB orderbook
price = orderbook['asks'][0]['price']  # 0.999 (actual)

# Monitoring
prices = get_clob_prices(condition_id)  # CLOB orderbook
price = prices['yes']  # 0.999 (actual)

# Result: Entry at 0.999, monitoring at 0.999 → 0% change ✓
```

---

## API Calls Made

Each call to `get_clob_prices()` makes **3 API requests**:

1. `GET /markets/{condition_id}` - Get token IDs
2. `GET /book?token_id={yes_token}` - Get YES orderbook
3. `GET /book?token_id={no_token}` - Get NO orderbook

**Performance impact**:
- 3x more API calls than before
- Slower, but more accurate
- May hit rate limits faster (monitor for 429 errors)

---

## Error Handling

### If Orderbook is Empty

```python
yes_asks = yes_orderbook.get('asks', [])
if yes_asks:  # ← Check if not empty
    result['yes'] = float(yes_asks[0]['price'])
```

**What happens if empty**:
- `result['yes']` stays `None`
- Function returns `{'yes': None, 'no': None}`
- Calling code must handle `None` prices

### If Token IDs Not Found

```python
if not yes_token_id or not no_token_id:
    return result  # Returns {'yes': None, 'no': None}
```

**When this happens**:
- Market doesn't exist
- Invalid condition_id
- API error

---

## Summary

**What it does**: Gets actual executable prices from CLOB orderbook

**How it works**:
1. Get YES and NO token IDs
2. Fetch orderbook for each token
3. Extract best ask (cheapest to buy)
4. Return both prices

**Why it matters**: Ensures consistent pricing across all bot operations

**Trade-off**: 3x more API calls, but accurate and consistent
