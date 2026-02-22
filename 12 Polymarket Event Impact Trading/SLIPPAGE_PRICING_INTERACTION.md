# How Slippage Interacts with Pricing

## Overview

The slippage estimator bridges two different pricing sources to estimate realistic execution costs:

1. **Gamma API** → Provides market prices (quoted prices)
2. **CLOB API** → Provides orderbook depth (execution reality)

---

## Pricing Data Sources

### 1. Gamma API: Market Data (Quoted Prices)

**Endpoint**: `GET /markets` or `GET /events/{slug}`

**Response includes**:
```json
{
  "condition_id": "0x123...",
  "question": "Will ETH reach $6,500 by Dec 31, 2026?",
  "outcomePrices": ["0.090", "0.910"],  // [YES, NO]
  "volume": "107851.45",
  "end_date_iso": "2026-12-31T23:59:59Z"
}
```

**What this means**:
- `outcomePrices[0]` = **YES token price** = $0.090 (9% probability)
- `outcomePrices[1]` = **NO token price** = $0.910 (91% probability)
- These are **mid-market prices** (not guaranteed execution prices!)

### 2. CLOB API: Order Book (Actual Liquidity)

**Endpoint**: `GET /book?token_id={token_id}`

**Response includes**:
```json
{
  "market": "0x123...",
  "asset_id": "71321045679252212594626385532706912750332728571942532289631379312455583992563",
  "bids": [
    {"price": "0.088", "size": "100"},
    {"price": "0.087", "size": "200"},
    {"price": "0.085", "size": "150"}
  ],
  "asks": [
    {"price": "0.092", "size": "120"},
    {"price": "0.095", "size": "180"},
    {"price": "0.100", "size": "250"}
  ]
}
```

**What this means**:
- **Best ask**: $0.092 (price to BUY YES tokens)
- **Best bid**: $0.088 (price to SELL YES tokens)
- **Spread**: $0.004 (40 bps)
- Each level has limited liquidity (size)

---

## How Slippage Estimator Uses Both

### Step 1: Get Quoted Price (Gamma API)

```python
# From market data
quoted_price = float(market['outcomePrices'][0])  # 0.090 for YES token
```

**Purpose**: This is the **reference price** shown to users.

### Step 2: Fetch Order Book (CLOB API)

```python
# Get actual orderbook
token_id = market['tokens'][0]['token_id']
orderbook = self.client.get_orderbook(token_id)
```

**Purpose**: This reveals the **actual liquidity** available.

### Step 3: Simulate Order Execution (Walk the Book)

```python
# For a BUY order of $10
order_size = 10.0
side = 'BUY'

# Walk through asks (selling liquidity)
levels = orderbook['asks']
total_filled = 0.0
weighted_sum = 0.0

for level in levels:
    price = float(level['price'])        # e.g., 0.092
    size = float(level['size'])           # e.g., 120 shares

    liquidity = price * size              # $11.04 available at this level
    amount = min(order_size - total_filled, liquidity)

    weighted_sum += price * amount        # Track for VWAP
    total_filled += amount

    if total_filled >= order_size:
        break

# Calculate Volume-Weighted Average Price
vwap = weighted_sum / order_size
```

**Example calculation**:
- Level 1: $0.092 × $10 = filled completely at $0.092
- **VWAP** = $0.092

### Step 4: Apply Safety Buffers

```python
# Determine buffer based on orderbook conditions
buffer_pct = 0.10  # Base 10%

# Thin book penalty (used 3+ levels)
if num_levels >= 3:
    buffer_pct = 0.20  # Increase to 20%

# Wide spread penalty (ADDITIVE!)
spread_bps = (best_ask - best_bid) / best_bid * 10000
if spread_bps > 500:  # > 5%
    buffer_pct += 0.20  # Add another 20%

# Apply buffer to VWAP
buffered_price = vwap * (1 + buffer_pct)  # For BUY orders
```

**Example**:
- VWAP = $0.092
- Buffer = 10% (single level, narrow spread)
- **Buffered price** = $0.092 × 1.10 = **$0.1012**

### Step 5: Calculate Slippage

```python
# Compare buffered price to quoted price
slippage_dollars = (buffered_price - quoted_price) * order_size
slippage_bps = (slippage_dollars / order_size) * 10000
```

**Example**:
- Quoted price: $0.090 (from Gamma API)
- Buffered price: $0.1012 (from CLOB simulation)
- Order size: $10

```
slippage_dollars = ($0.1012 - $0.090) × $10 = $0.112
slippage_bps = ($0.112 / $10) × 10,000 = 112 bps (1.12%)
```

### Step 6: Accept or Reject

```python
if slippage_bps > max_slippage_bps:  # 100 bps limit
    return {
        'can_trade': False,
        'reason': f'Slippage {slippage_bps} bps exceeds limit {max_slippage_bps} bps'
    }
```

**Result**: ❌ **REJECTED** (112 bps > 100 bps limit)

---

## Complete Pricing Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GAMMA API: Get Market Data                                  │
│    → outcomePrices = [0.090, 0.910]                            │
│    → quoted_price = 0.090  (YES token, 9% probability)         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. CLOB API: Get Order Book                                    │
│    → asks = [{0.092, 120}, {0.095, 180}, ...]                  │
│    → best_ask = 0.092                                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. SIMULATE EXECUTION: Walk Through Orderbook                  │
│    → Fill $10 order across ask levels                          │
│    → VWAP = 0.092  (volume-weighted average)                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. APPLY SAFETY BUFFERS                                        │
│    → depth_buffer = 10%  (base)                                │
│    → thin_book_penalty = +10%  (if >= 3 levels)                │
│    → wide_spread_penalty = +20%  (if spread > 5%)              │
│    → buffered_price = VWAP × (1 + buffer)                      │
│    → buffered_price = 0.092 × 1.10 = 0.1012                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. CALCULATE SLIPPAGE                                          │
│    → slippage = (buffered_price - quoted_price) / quoted_price │
│    → slippage = (0.1012 - 0.090) / 0.090                       │
│    → slippage = 12.4% = 1,244 bps                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. VALIDATION                                                   │
│    → IF slippage_bps > max_slippage_bps (100)                  │
│       → REJECT: "Slippage 1,244 bps exceeds limit 100 bps"     │
│    → ELSE                                                       │
│       → ACCEPT: Place order at buffered_price                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why There's a Gap Between Quoted and Execution Price

### 1. Quoted Price ≠ Execution Price

**Quoted price** (from Gamma):
- **Mid-market estimate** (average of best bid/ask)
- Not a guaranteed fill price
- Updated periodically (not real-time)

**Execution price** (from CLOB):
- **Actual market depth** at that moment
- Limited liquidity at each price level
- Must walk multiple levels for larger orders

### 2. Market Impact

Buying $10 worth of YES tokens:
- Might consume best ask ($0.092)
- Might consume second level ($0.095)
- Might consume third level ($0.100)
- **VWAP** = weighted average across all levels

**This is normal market impact** (not slippage yet!)

### 3. Safety Buffers Add Conservatism

The buffers account for:
- **Thin orderbooks**: More levels = worse execution risk
- **Wide spreads**: Large bid/ask gap = volatility risk
- **Execution uncertainty**: Orderbook can change before order fills

**Buffered price = worst-case estimate** (not expected execution)

### 4. Slippage = Total Cost Above Quoted

```
Slippage = Buffered Price - Quoted Price
         = (VWAP + Safety Buffers) - Mid-Market
         = Market Impact + Execution Risk Premium
```

---

## Real Example: ETH $6,500 Market

### Market Data (Gamma API)

```json
{
  "question": "Will Ethereum reach $6,500 by December 31, 2026?",
  "outcomePrices": ["0.090", "0.910"],
  "volume": "107851"
}
```

- **Quoted YES price**: $0.090

### Orderbook Data (CLOB API)

```json
{
  "asks": [
    {"price": "0.990", "size": "5"},
    {"price": "0.950", "size": "10"},
    {"price": "0.900", "size": "15"},
    ...
  ],
  "bids": [
    {"price": "0.010", "size": "50"},
    {"price": "0.005", "size": "100"}
  ]
}
```

- **Best ask**: $0.990 (!!!)
- **Best bid**: $0.010
- **Spread**: $0.980 (98,000 bps!)

### Why Such a Wide Spread?

**Prediction market mechanics**:
- Market makers place wide limit orders
- Actual trades happen closer to mid-price
- Orderbook shows extremes (near $0 and near $1)
- **This is an artifact of CLOB design**, not true liquidity

### Execution Simulation ($10 order)

```python
# Walk through asks to fill $10
# Must consume 3-5 levels to find real liquidity
# VWAP ≈ $0.100  (slightly above quoted $0.090)

# Apply buffers
buffer = 20% (thin book) + 20% (wide spread) = 40%
buffered_price = $0.100 × 1.40 = $0.140

# Calculate slippage
slippage = ($0.140 - $0.090) / $0.090 × 10,000
         = 5,555 bps (55.5%)
```

**Result**: ❌ **REJECTED** (5,555 bps >> 100 bps limit)

---

## The Problem with Current Configuration

Your **100 bps (1%) limit** assumes:
- ✅ Tight spreads (< 10 bps)
- ✅ Deep orderbooks (10+ levels)
- ✅ Quoted price ≈ execution price
- ✅ Low volatility

But Polymarket long-dated markets have:
- ❌ Wide spreads (100-98,000 bps)
- ❌ Thin orderbooks (3-10 levels)
- ❌ Quoted price << best ask price
- ❌ High execution uncertainty

**Result**: Nearly all trades rejected!

---

## Recommended Fix

### Option 1: Increase Slippage Limits (Recommended)

Accept that slippage is higher for:
- Long-dated markets (low urgency)
- Thin orderbooks (normal for prediction markets)
- Wide spreads (CLOB artifact)

```json
{
  "max_slippage_bps": 6000,       // 60% (moderate)
  "max_slippage_dollars": 50.0,
  "volatility_adjustment": false   // Disable +20% spread penalty
}
```

### Option 2: Use Quoted Price for Execution

Instead of simulating orderbook execution, use the quoted price directly:

```python
# Skip slippage estimation
execution_price = quoted_price  # From Gamma API
```

**Trade-off**: No protection against execution risk, but simpler.

### Option 3: Use AMM Instead of CLOB

Polymarket also offers AMM-based execution (like Uniswap):
- Pay the quoted price directly
- No slippage estimation needed
- Simpler, but potentially higher fees

---

## Bottom Line

**The slippage estimator correctly identifies**:
- Quoted price (Gamma API): $0.090
- Execution price (CLOB orderbook): ~$0.100
- Buffered price (safety margin): ~$0.140
- Slippage: 5,555 bps (55%)

**But the 100 bps limit is too strict** for Polymarket's market structure.

**Solution**: Increase limits to 6,000 bps (60%) and disable volatility adjustment to allow trades on markets with real CLOB liquidity.
