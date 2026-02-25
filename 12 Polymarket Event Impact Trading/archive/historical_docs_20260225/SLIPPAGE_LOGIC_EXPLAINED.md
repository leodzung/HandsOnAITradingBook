# Slippage Estimation Logic - Detailed Explanation

## Overview

The `SlippageEstimator` simulates order execution by walking through orderbook levels and applying safety buffers to estimate worst-case execution price.

---

## Current Configuration

```json
{
  "enabled": true,
  "max_slippage_bps": 100,        // 1% limit (VERY STRICT)
  "max_slippage_dollars": 5.0,     // $5 absolute limit
  "depth_buffer_pct": 0.10,        // 10% base safety buffer
  "volatility_adjustment": true,    // Add buffer for wide spreads
  "volume_limit_pct": 0.01,        // Max 1% of daily volume
  "warn_threshold_bps": 50         // Warning at 0.5%
}
```

---

## How Slippage is Calculated

### Step 1: Pre-Flight Checks

**Volume Limit Check**
```
IF order_size > 1% of market's 24h volume
  → REJECT: "Order size exceeds 1% of daily volume"
```

**Orderbook Availability Check**
```
IF orderbook is empty (no bids/asks)
  → REJECT: "No liquidity available in orderbook"
```

### Step 2: Simulate Order Fill

**Walk through orderbook levels** to fill the order:

```python
For each price level:
    level_liquidity = price × size  # Dollar liquidity at this level
    amount_to_fill = min(remaining_order, level_liquidity)

    Track: price, size, amount_filled
```

**Calculate VWAP** (Volume-Weighted Average Price):
```
VWAP = Σ(price × amount_filled) / order_size
```

**Check if fully filled**:
```
IF total_filled < order_size
  → REJECT: "Insufficient liquidity"
```

### Step 3: Apply Safety Buffers ⚠️ (This is where slippage gets high!)

**Base Buffer**: 10% (depth_buffer_pct)

**Thin Orderbook Penalty**:
```
IF num_levels >= 3
  buffer = 20%  (instead of 10%)

Why: Consuming 3+ levels indicates thin liquidity
```

**Wide Spread Penalty** (ADDITIVE):
```
IF spread > 500 bps (5%)
  buffer += 20%  (ADDS to existing buffer!)

Result: Thin book + wide spread = 40% total buffer!
```

**Calculate Buffered Price**:
```python
IF BUY order:
    buffered_price = VWAP × (1 + buffer_pct)
ELSE (SELL):
    buffered_price = VWAP × (1 - buffer_pct)
```

### Step 4: Calculate Final Slippage

```python
IF BUY:
    slippage_dollars = (buffered_price - quoted_price) × order_size
ELSE:
    slippage_dollars = (quoted_price - buffered_price) × order_size

slippage_bps = (slippage_dollars / order_size) × 10,000
```

### Step 5: Validation

```
IF slippage_bps > max_slippage_bps (100)
  → REJECT: "Slippage X bps exceeds limit 100 bps"

IF slippage_dollars > max_slippage_dollars ($5)
  → REJECT: "Slippage $X exceeds limit $5"

ELSE
  → ACCEPT trade
```

---

## Why Your Markets Have High Slippage

### Example: ETH $6,500 Market

**Market Data**:
- Best ask: $0.990
- Best bid: $0.010
- Spread: $0.980 (19,600 bps) ← **MASSIVE SPREAD!**
- Orderbook depth: 8 bids, 30 asks
- Order size: ~$10-50

**Calculation**:

1. **VWAP Simulation**:
   - Walk through 3-8 orderbook levels
   - VWAP ≈ $0.100 (for $10 order)

2. **Apply Buffers**:
   - Base: 10%
   - Thin book (>= 3 levels): **+10%** → 20% total
   - Wide spread (19,600 bps >> 500): **+20%** → **40% total buffer!**

3. **Buffered Price**:
   - buffered_price = $0.100 × 1.40 = $0.140

4. **Slippage**:
   - quoted_price (best ask) = $0.990
   - slippage = ($0.140 - $0.090) / $0.090 × 10,000
   - **slippage ≈ 5,555 bps (55.5%)**

5. **Result**:
   - 5,555 bps >> 100 bps limit
   - **REJECTED** ❌

---

## Why Spreads Are So Wide

Your markets show spreads of **~19,600 bps** (196%!). This happens because:

### Prediction Market Mechanics

In prediction markets:
- **YES token** trades at probability estimate (e.g., $0.09 = 9% chance)
- **NO token** trades at (1 - YES price) = $0.91

### CLOB Orderbook Artifacts

The orderbook shows:
- Best bid: $0.001 (maker buying at near-zero)
- Best ask: $0.999 (maker selling at near-certainty)

This creates a **fake spread** because:
1. Market makers place wide limit orders
2. Actual trades happen closer to mid-price
3. Spread calculation uses best bid/ask (not realistic fills)

---

## The Problem

Your **100 bps (1%) slippage limit** is **far too strict** for:

1. **Long-dated markets** (321 days) with low urgency
2. **Thin orderbooks** (< 10 levels) → 20% buffer
3. **Wide spreads** (19,600 bps) → +20% buffer
4. **Total buffer**: 40% safety margin built in

**Result**: Nearly ALL trades rejected despite having CLOB liquidity!

---

## Solutions

### Option 1: Increase Limits (Recommended)

**Conservative** (Allow best markets):
```json
"max_slippage_bps": 1500,  // 15%
"max_slippage_dollars": 20.0
```

**Moderate** (Allow most markets):
```json
"max_slippage_bps": 6000,  // 60%
"max_slippage_dollars": 50.0
```

**Aggressive** (Allow all markets):
```json
"max_slippage_bps": 12000,  // 120%
"max_slippage_dollars": 100.0
```

### Option 2: Reduce Safety Buffers

Modify `_apply_buffers()` logic:

```json
"depth_buffer_pct": 0.05,      // Reduce from 10% to 5%
"volatility_adjustment": false  // Disable +20% spread penalty
```

**Impact**:
- Thin book buffer: 10% (instead of 20%)
- No spread penalty
- **Total buffer**: 10% (instead of 40%)

### Option 3: Disable Slippage Checking

```json
"slippage_estimation": {
  "enabled": false
}
```

**Trade-off**: No protection, but all trades execute.

### Option 4: Use Market Orders with AMM

Instead of CLOB limit orders, use Polymarket's AMM:
- No slippage estimation needed
- Pay the quoted price
- Simpler execution

---

## Recommended Approach

**For your long-dated price-level markets:**

```json
{
  "max_slippage_bps": 6000,       // 60% (reasonable for thin books)
  "max_slippage_dollars": 50.0,   // Allow larger absolute slippage
  "depth_buffer_pct": 0.10,       // Keep 10% base buffer
  "volatility_adjustment": false,  // DISABLE spread penalty (it's too harsh)
  "volume_limit_pct": 0.05,       // Increase to 5% of volume
  "warn_threshold_bps": 3000      // Warn at 30%
}
```

**Why this works:**
- ✅ Keeps safety buffers for protection
- ✅ Removes overly conservative spread penalty (40% → 20%)
- ✅ Allows trades on markets with real CLOB liquidity
- ✅ Still rejects truly illiquid markets

---

## Bottom Line

Your slippage estimator is **working correctly** but is **too conservative** for:
- Long-dated markets (low trading urgency)
- Prediction markets (wide "fake" spreads)
- Thin but active orderbooks (3-10 levels is normal)

**Increase limits to 6,000 bps and disable volatility_adjustment** to start opening positions.
