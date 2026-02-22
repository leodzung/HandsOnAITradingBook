# 📊 Expanded Universe Comparison - Before vs After

**Date**: November 10, 2024
**Test**: Impact of expanding universe from 5 to 15 stocks & selecting top 5 instead of top 3

---

## 🎯 Changes Made

### Configuration Changes

| Parameter | Original | Expanded | Change |
|-----------|----------|----------|--------|
| **Universe Size** | 5 stocks | 15 stocks | +200% |
| **Stocks Selected** | Top 3 | Top 5 | +67% |
| **Position Size** | 33.3% each | 20% each | More diversified |

### Universe Expansion Details

**Original Universe (5 stocks)**:
- VNM (Vinamilk - Dairy)
- VCB (Vietcombank - Banking)
- HPG (Hoa Phat - Steel)
- FPT (FPT Corp - Technology)
- MSN (Masan - Consumer)

**Expanded Universe (15 stocks)**:
- All 5 original stocks PLUS:
- GAS (PetroVietnam Gas - Energy)
- PLX (Petrolimex - Energy/Retail)
- SAB (Sabeco - Beverages)
- POW (PV Power - Utilities)
- BID (BIDV - Banking)
- VHM (Vinhomes - Real Estate)
- VIC (Vingroup - Conglomerate)
- MWG (Mobile World - Retail)
- TCB (Techcombank - Banking)
- CTG (VietinBank - Banking)

**Sector Diversity**:
- Original: 5 sectors
- Expanded: 8 sectors (added Energy, Utilities, Real Estate)

---

## 📊 Complete Results Comparison

### 2024 Results (Bull Market)

| Metric | Original (5 stocks, top 3) | Expanded (15 stocks, top 5) | Change |
|--------|---------------------------|----------------------------|--------|
| **Return** | **+25.57%** | **+15.49%** | **-10.08%** ❌ |
| **Sharpe Ratio** | 1.72 | 1.15 | -0.57 ❌ |
| **Max Drawdown** | -10.59% | -8.51% | +2.08% ✅ |
| **ML Accuracy** | 68.81% | 56.20% | -12.61% ❌ |
| **Volatility** | 15.65% | 13.03% | -2.62% ✅ |

**Analysis**: Lower returns but better risk control

---

### 2023 Results (Choppy Market)

| Metric | Original (5 stocks, top 3) | Expanded (15 stocks, top 5) | Change |
|--------|---------------------------|----------------------------|--------|
| **Return** | **-3.71%** | **-1.97%** | **+1.74%** ✅ |
| **Sharpe Ratio** | -0.20 | -0.24 | -0.04 ~ |
| **Max Drawdown** | -32.52% | -27.27% | +5.25% ✅ |
| **ML Accuracy** | 57.05% | 57.91% | +0.86% ✅ |
| **Volatility** | ~18% | 20.80% | +2.80% ❌ |

**Analysis**: SIGNIFICANT improvement - smaller loss and better drawdown

---

### 2022 Results (Bear Market)

| Metric | Original (5 stocks, top 3) | Expanded (15 stocks, top 5) | Change |
|--------|---------------------------|----------------------------|--------|
| **Return** | **-22.06%** | **-24.32%** | **-2.26%** ❌ |
| **Sharpe Ratio** | -0.64 | -1.13 | -0.49 ❌ |
| **Max Drawdown** | -36.44% | -33.89% | +2.55% ✅ |
| **ML Accuracy** | 62.19% | 59.73% | -2.46% ❌ |
| **Volatility** | 38.21% | 23.54% | -14.67% ✅ |

**Analysis**: Slightly worse return but better max drawdown and lower volatility

---

## 📈 3-Year Aggregate Performance

### Original Configuration (5 stocks, top 3)

| Metric | Value |
|--------|-------|
| **Average Annual Return** | -0.07% |
| **Cumulative 3-Year Return** | -2.87% |
| **Best Year** | +25.57% (2024) |
| **Worst Year** | -22.06% (2022) |
| **Range** | 47.63% |
| **Max Drawdown (worst)** | -36.44% |

### Expanded Configuration (15 stocks, top 5)

| Metric | Value | vs Original |
|--------|-------|-------------|
| **Average Annual Return** | **-3.60%** | ❌ Worse (-3.53%) |
| **Cumulative 3-Year Return** | **-10.33%** | ❌ Worse (-7.46%) |
| **Best Year** | +15.49% (2024) | Lower upside |
| **Worst Year** | -24.32% (2022) | Worse loss |
| **Range** | 39.81% | ✅ Less volatile |
| **Max Drawdown (worst)** | -33.89% | ✅ Better (+2.55%) |

---

## 🔍 Detailed Analysis

### What Improved with Expansion ✅

1. **2023 Performance** (Biggest Win!)
   - Loss reduced from -3.71% to -1.97% (+1.74%)
   - Max drawdown improved from -32.52% to -27.27% (+5.25%)
   - Shows diversification helps in choppy markets

2. **Risk Metrics**
   - Max drawdown across 3 years improved (2024 & 2022)
   - Lower volatility in most years
   - More consistent position sizing (20% vs 33%)

3. **Better in Difficult Markets**
   - Choppy 2023: Significantly better
   - Both versions still lost money, but expanded lost less

### What Got Worse with Expansion ❌

1. **2024 Bull Market Performance**
   - Return dropped from +25.57% to +15.49% (-10.08%)
   - Sharpe ratio fell from 1.72 to 1.15
   - Concentrated bets on winners worked better in bull market

2. **2022 Bear Market**
   - Return worsened from -22.06% to -24.32% (-2.26%)
   - Sharpe ratio fell from -0.64 to -1.13
   - Diversification didn't help in crash

3. **Overall Returns**
   - 3-year cumulative return worse (-10.33% vs -2.87%)
   - Average annual return worse (-3.60% vs -0.07%)
   - **Still losing money in both cases!**

### ML Accuracy Insights

| Year | Original Accuracy | Expanded Accuracy | Note |
|------|------------------|------------------|------|
| 2024 | 68.81% | 56.20% | More stocks → harder to predict |
| 2023 | 57.05% | 57.91% | Slight improvement |
| 2022 | 62.19% | 59.73% | Slight decline |

**Finding**: ML model struggled with larger universe - more noise, harder to identify clear winners

---

## 💡 Key Insights

### The Diversification Trade-off

**Benefits**:
- ✅ Smaller losses in choppy markets (2023: +1.74%)
- ✅ Better max drawdown control (-33.89% vs -36.44%)
- ✅ Lower volatility overall
- ✅ More sector exposure

**Costs**:
- ❌ Lower upside in bull markets (2024: -10.08%)
- ❌ Still loses money overall (-10.33% vs -2.87%)
- ❌ ML model less accurate with more choices
- ❌ Can't concentrate on best opportunities

### The Concentration Paradox

**Original (Concentrated)**:
- High highs (+25.57% in 2024)
- Low lows (-22.06% in 2022)
- Overall: Nearly flat (-2.87% over 3 years)

**Expanded (Diversified)**:
- Lower highs (+15.49% in 2024)
- Similar lows (-24.32% in 2022)
- Overall: More negative (-10.33% over 3 years)

**Conclusion**: **Neither configuration is profitable!**

---

## 📊 Visual Summary

```
3-Year Cumulative Returns

Original (5 stocks, top 3):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2022: -22.06% 📉📉📉
2023: -3.71%  📉
2024: +25.57% 📈📈
Final: -2.87% (lost money)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Expanded (15 stocks, top 5):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2022: -24.32% 📉📉📉
2023: -1.97%  📉
2024: +15.49% 📈
Final: -10.33% (lost MORE money)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verdict: Expanded universe is WORSE overall
```

---

## ⚖️ Which Configuration is Better?

### Original (5 stocks, top 3) Wins:
- ✅ Better 3-year cumulative return (-2.87% vs -10.33%)
- ✅ Much better in bull markets (+25.57% vs +15.49%)
- ✅ Higher ML accuracy in good conditions (68.81%)
- ✅ Can concentrate on best opportunities

### Expanded (15 stocks, top 5) Wins:
- ✅ Better in choppy markets (-1.97% vs -3.71%)
- ✅ Better max drawdown control (-33.89% vs -36.44%)
- ✅ Lower volatility overall
- ✅ More sector diversification

### **OVERALL VERDICT**: 🟡 **Original is LESS BAD, but both FAIL**

**Why Original Wins**:
- Lost -2.87% vs -10.33% (7.46% better)
- Higher upside potential
- Both lose money, but original loses less

**But Reality**:
- **BOTH configurations are NOT profitable**
- **BOTH fail to beat risk-free rates (bank deposits ~5%)**
- **Diversification didn't save the strategy**

---

## 🎯 Recommendation

### Short Answer: **Neither - Don't trade either version!**

Both configurations lose money over a full market cycle. Expanding the universe helped reduce losses in choppy markets, but made overall performance WORSE.

### If You Must Choose (for educational purposes):

**Choose Original IF**:
- You believe next 1-2 years will be a bull market
- You can handle -36% max drawdown
- You want higher upside potential
- You're willing to accept higher concentration risk

**Choose Expanded IF**:
- You expect choppy/volatile markets
- You prioritize risk control over returns
- You want lower drawdown (-34% vs -36%)
- You value sector diversification

### But The Real Lesson:

**Diversification alone doesn't fix a fundamentally flawed strategy!**

- Original: Lost -2.87% over 3 years
- Expanded: Lost -10.33% over 3 years
- Bank deposit: Would have gained +15.76% at 5% APY

**The problem isn't diversification - it's the momentum-only approach that fails in non-trending markets!**

---

## 🔄 What We Learned

### What Diversification Did:
1. ✅ Reduced volatility
2. ✅ Improved max drawdown slightly
3. ✅ Helped in choppy markets (2023)
4. ❌ Reduced returns in bull markets (2024)
5. ❌ Didn't help in bear markets (2022)
6. ❌ Made overall 3-year return WORSE

### What Diversification Couldn't Fix:
1. ❌ Fundamental flaw: momentum-only strategy
2. ❌ No market regime detection
3. ❌ No defensive mechanisms
4. ❌ ML model can't predict well enough across all conditions
5. ❌ Strategy still loses money overall

---

## 📋 Next Steps

Since **BOTH configurations fail**, you need to:

### Option 1: Add Market Regime Detection (Recommended)
```python
def get_market_regime(vnindex_data):
    ma50 = vnindex_data['close'].rolling(50).mean().iloc[-1]
    ma200 = vnindex_data['close'].rolling(200).mean().iloc[-1]

    if ma50 > ma200 * 1.02:
        return 'bull'  # Use original (concentrated)
    elif ma50 < ma200 * 0.98:
        return 'bear'  # Go to cash or defensive
    else:
        return 'choppy'  # Use expanded (diversified)
```

Apply different strategies based on market regime:
- **Bull**: Use original (5 stocks, top 3) for higher upside
- **Choppy**: Use expanded (15 stocks, top 5) for better risk control
- **Bear**: Go to cash or defensive stocks (dividends, low debt)

### Option 2: Complete Redesign
- Focus on value + quality fundamentals
- Use momentum only as confirming signal
- Add defensive mechanisms (stop losses, cash positions)
- Train ML on longer history (2-3 years)

### Option 3: Different Strategy Entirely
- Dividend aristocrats
- Mean reversion
- Sector rotation
- Market-neutral pairs

---

## 📁 Files Generated

**Results Files**:
- `expanded_2024_results.csv` - 2024 expanded universe results
- `expanded_2023_results.csv` - 2023 expanded universe results
- `expanded_2022_results.csv` - 2022 expanded universe results

**Original Files** (for comparison):
- `simple_backtest_results.csv` - Original 2024 results
- `backtest_2023_results.csv` - Original 2023 results
- `backtest_2022_results.csv` - Original 2022 results

**Analysis**:
- `EXPANDED_UNIVERSE_COMPARISON.md` - This file

---

## 💬 Final Thoughts

### The Harsh Truth:

**Expanding the universe made things WORSE, not better.**

- Original: -2.87% over 3 years
- Expanded: -10.33% over 3 years
- **Difference: -7.46% (expansion performed worse)**

### Why This Happened:

1. **In bull markets** (2024): Concentration pays off
   - Picking 3 best stocks >> picking 5 good stocks
   - Original captured +25.57%, expanded only +15.49%

2. **In bear markets** (2022): Both crash
   - Diversification didn't provide enough protection
   - Both lost ~23-24%

3. **In choppy markets** (2023): Diversification helps, but not enough
   - Expanded lost -1.97% vs original -3.71%
   - But this gain (+1.74%) doesn't offset losses in other metrics

### The Real Problem:

**The strategy doesn't work because**:
- ✗ Momentum fails in non-trending markets (67% of the time)
- ✗ No regime detection to avoid bad markets
- ✗ No defensive mechanisms
- ✗ ML model not robust enough

### The Real Solution:

**Don't fiddle with universe size - fix the fundamental approach!**

You need:
1. Market regime detection (bull/bear/choppy)
2. Different strategies for different regimes
3. Defensive mechanisms (cash, stop losses)
4. Better ML training (longer history, mixed conditions)

**Or**: Abandon momentum-only approach entirely and try value/quality focus with momentum as enhancer.

---

**Status**: ⚠️ Expansion tested - Made performance WORSE
**Verdict**: Original configuration is less bad, but BOTH fail
**Next**: Add regime detection or redesign strategy
**Live Trading**: Still NOT ready - would lose more money with expansion
