# Price Level Bot - Immediate Stop Loss Issue Analysis

## Problem Summary

Three positions were opened and immediately closed within seconds/minutes, all hitting stop loss:

| Market | Side | Entry Price | Exit Price | PnL | Time |
|--------|------|-------------|------------|-----|------|
| GOLD $5,500 | YES | **0.999** | 0.6855 | -$6.38 | 08:17:17 |
| GOLD $5,700 | YES | **0.990** | 0.605 | -$9.36 | 08:17:19 |
| BTC $45k dip | NO | **0.99** | 0.58 | -$13.50 | 08:18:57 |

**Total loss: $29.24** (triggered circuit breaker)

---

## Root Cause

### Price Discrepancy Between Signal Generation and Execution

The bot is using **TWO DIFFERENT price sources**:

1. **Signal Generation**: Uses Gamma API `outcomePrices` (mid-market estimate)
2. **Trade Execution**: Uses CLOB API `best ask` (actual orderbook price)

### Example: GOLD $5,500 Market

**During Signal Generation:**
```
2026-02-13 08:17:17 - Market Price: YES=$0.685, NO=$0.315
2026-02-13 08:17:17 - ML Signal: BUY YES (edge: +24.04%, confidence: 92.59%)
2026-02-13 08:17:17 - Slippage: 4134 bps (acceptable, < 6000 bps limit)
```

**During Execution:**
```
2026-02-13 08:17:17 - [PAPER TRADE] BUY YES $20.34
2026-02-13 08:17:17 - YES Price: $0.999  ← 🚨 ACTUAL EXECUTION PRICE!
```

**What happened:**
- Expected entry: $0.685 (quoted price from Gamma API)
- Actual entry: **$0.999** (best ask from CLOB orderbook)
- **Difference: 45.8%!** ($0.314 higher than expected)

### Example: GOLD $5,700 Market

**During Signal Generation:**
```
2026-02-13 08:17:19 - Market Price: YES=$0.605, NO=$0.395
2026-02-13 08:17:19 - ML Signal: BUY YES (edge: +32.36%, confidence: 92.86%)
2026-02-13 08:17:19 - Slippage: 4840 bps (acceptable)
```

**During Execution:**
```
2026-02-13 08:17:19 - [PAPER TRADE] BUY YES $24.08
2026-02-13 08:17:19 - YES Price: $0.990  ← 🚨 ACTUAL EXECUTION PRICE!
```

**What happened:**
- Expected entry: $0.605
- Actual entry: **$0.990**
- **Difference: 63.6%!** ($0.385 higher than expected)

---

## Why This Happens

### 1. Gamma API Returns Mid-Market Prices

The `outcomePrices` from Gamma API are **estimates**, not guaranteed execution prices:
- They represent a mid-market average
- They're updated periodically (not real-time)
- They don't account for current orderbook depth

### 2. CLOB API Has Wide Spreads

The actual CLOB orderbook shows:
```
Market: GOLD $5,500
Gamma API quote: YES=$0.685
CLOB orderbook:
  - Best bid: $0.001 (makers buying at near-zero)
  - Best ask: $0.999 (makers selling at near-certainty)
  - Spread: 99,800 bps!
```

### 3. Slippage Estimator Calculates Correctly

The slippage estimator **DID estimate correctly**:
- For GOLD $5,500: Estimated slippage 4,134 bps ($8.408)
- This was calculated using the CLOB orderbook
- Expected execution: ~$0.685 + slippage = ~$0.713
- **BUT: The bot then executed at $0.999 anyway!**

---

## The Bug

### Where is the Execution Price Coming From?

The bot is likely doing this in `trader_price_levels.py`:

```python
# Signal generation uses Gamma API prices
market_price_yes = float(market['outcomePrices'][0])  # 0.685

# ...slippage check passes...

# 🚨 EXECUTION uses a DIFFERENT price source!
# Possibly fetching from CLOB orderbook:
execution_price = float(clob_orderbook['asks'][0]['price'])  # 0.999
```

**The slippage estimator is being bypassed during actual execution!**

---

## Why Stop Loss Triggered Immediately

With 20% stop loss threshold:

**GOLD $5,500 example:**
```
Entry price: $0.999 (from CLOB best ask)
Current price: $0.6855 (from Gamma API)
Loss: ($0.999 - $0.6855) / $0.999 = 31.4%
Stop loss threshold: 20%
Result: 31.4% > 20% → ❌ STOP LOSS TRIGGERED
```

**The positions aren't "immediately closing"** - they're closing because:
1. Entered at inflated CLOB best ask price (0.99-0.999)
2. Monitored using realistic Gamma mid-price (0.60-0.68)
3. Difference exceeds 20% stop loss
4. Closed within seconds

---

## Evidence from Logs

### 1. Slippage Estimation Used Gamma API Price

```
Market Price: YES=$0.685
Slippage: 4134 bps ($8.408), depth: 1 levels
```

The slippage calculator expected:
- Base price: $0.685
- Slippage: $0.028 (4.1% of $0.685)
- Expected execution: ~$0.713

### 2. Execution Used CLOB Best Ask

```
YES Price: $0.999
```

This is the CLOB orderbook best ask, not the Gamma API quote!

### 3. Price Monitoring Used Gamma API

When checking positions, the bot fetches current market data from Gamma API:
- Shows realistic prices (0.60-0.68)
- Compares to inflated entry prices (0.99-0.999)
- Triggers stop loss

---

## Root Cause Hypothesis

### Likely Code Flow

1. **Signal Generation** (`trader_price_levels.py`):
   ```python
   # Fetch market from Gamma API
   market = client.get_market(market_id)
   market_price = float(market['outcomePrices'][0])  # 0.685

   # Generate signal using Gamma price
   signal = generate_signal(market_price)  # BUY YES

   # Estimate slippage using Gamma price as baseline
   slippage_result = estimator.estimate(market, size)  # PASS
   ```

2. **Trade Execution** (PROBLEM HERE):
   ```python
   # 🚨 BUG: Fetches CLOB orderbook for execution
   orderbook = client.get_orderbook(token_id)
   execution_price = orderbook['asks'][0]['price']  # 0.999!

   # Opens position at CLOB best ask, not Gamma quote
   position = open_position(execution_price=0.999)
   ```

3. **Position Monitoring**:
   ```python
   # Fetches current market from Gamma API
   current_market = client.get_market(market_id)
   current_price = float(current_market['outcomePrices'][0])  # 0.685

   # Calculates loss using Gamma price
   loss_pct = (execution_price - current_price) / execution_price
   # loss_pct = (0.999 - 0.685) / 0.999 = 31.4%

   if loss_pct > stop_loss_pct:  # 31.4% > 20%
       close_position()  # STOP LOSS!
   ```

---

## The Fix

### Option 1: Use Gamma API Price for Execution (Recommended)

**Pros:**
- Consistent pricing across signal generation and execution
- Simpler logic
- Slippage estimation becomes more accurate

**Cons:**
- Actual execution may differ from paper trading assumptions

```python
# Use the same price source throughout
market_price = float(market['outcomePrices'][outcome_index])

# Slippage estimation uses this price
slippage_result = estimator.estimate(market, size)

# Execution also uses this price
position = open_position(entry_price=market_price)
```

### Option 2: Use CLOB Price for All Operations

**Pros:**
- More realistic execution modeling
- Matches actual CLOB trading

**Cons:**
- Need to fetch orderbook for every operation
- Signal generation becomes orderbook-dependent

```python
# Fetch orderbook
orderbook = client.get_orderbook(token_id)
execution_price = orderbook['asks'][0]['price']

# Use CLOB price for signal generation
signal = generate_signal(execution_price)

# Use CLOB price for slippage estimation
slippage_result = estimator.estimate(market, size, clob_price=execution_price)

# Use CLOB price for execution
position = open_position(entry_price=execution_price)

# Use CLOB price for monitoring
current_orderbook = client.get_orderbook(token_id)
current_price = current_orderbook['asks'][0]['price']
```

### Option 3: Adjust Slippage-Adjusted Price

**Use the slippage estimator's buffered price as the execution price:**

```python
# Estimate slippage
slippage_result = estimator.estimate(market, side='BUY', size=size)

# Use the BUFFERED price as execution price
execution_price = slippage_result['buffered_price']  # Not best ask!

# This price already includes slippage buffer
position = open_position(entry_price=execution_price)
```

---

## Immediate Action Required

1. **Identify the exact code** where execution price is set
2. **Ensure consistency** between signal generation, slippage estimation, and execution
3. **Use ONE price source** throughout the trade lifecycle
4. **Test with** small position sizes first

---

## Next Steps

1. Read `trader_price_levels.py` execution logic
2. Find where `YES Price: $0.999` comes from
3. Verify if it's using CLOB best ask instead of Gamma quote
4. Fix to use consistent pricing
5. Backtest with historical data to validate fix

---

## Questions to Investigate

1. Where does the bot get the execution price in paper trading mode?
2. Is there a method called `_get_execution_price()` or similar?
3. Does the bot call `get_orderbook()` before executing trades?
4. Is the slippage estimator's recommended price being ignored?

Let me investigate the code to find the exact source of this bug.
