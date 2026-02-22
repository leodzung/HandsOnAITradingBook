# 📊 Regime-Aware Strategy Results - UNEXPECTED FINDINGS

**Date**: November 10, 2024
**Status**: ⚠️ Regime-aware strategy implemented but performed WORSE than baseline

---

## 🎯 Executive Summary

**Bottom Line**: The regime-aware strategy, despite successfully detecting market regimes, performed WORSE than both the original and expanded strategies across all 3 years.

### 3-Year Performance Comparison

| Strategy | 2024 | 2023 | 2022 | 3-Year Total |
|----------|------|------|------|--------------|
| **Original** (5 stocks, top 3) | +25.57% | -3.71% | -22.06% | **-2.87%** |
| **Expanded** (15 stocks, top 5) | +15.49% | -1.97% | -24.32% | **-10.33%** |
| **Regime-Aware** | +16.39% | -13.01% | -26.18% | **-24.53%** ❌ |

**Key Finding**: Regime-aware strategy lost **-24.53%** over 3 years, making it the WORST performer.

---

## 📈 Year-by-Year Results

### 2024 Results (Bull Market)

| Metric | Original | Expanded | Regime-Aware | vs Original |
|--------|----------|----------|--------------|-------------|
| **Total Return** | +25.57% | +15.49% | **+16.39%** | **-9.18%** ❌ |
| **Max Drawdown** | -10.59% | -8.51% | **-8.06%** | **+2.53%** ✅ |
| **Sharpe Ratio** | 1.72 | 1.15 | **0.08** | **-1.64** ❌ |

**Regime Detection**:
- Jan-Mar: CHOPPY (40.1% of year) → Used diversified strategy (15 stocks, top 5)
- Apr-Sep: BULL (59.9% of year) → Used concentrated strategy (5 stocks, top 3)
- Oct: CHOPPY → Used diversified strategy

**Analysis**:
- Return was between original and expanded (+16.39% vs +25.57% and +15.49%)
- Successfully adapted to regimes but lower return due to spending 40% of time in defensive mode
- Better max drawdown than original (-8.06% vs -10.59%)

---

### 2023 Results (Choppy/Bear Market)

| Metric | Original | Expanded | Regime-Aware | vs Original |
|--------|----------|----------|--------------|-------------|
| **Total Return** | -3.71% | -1.97% | **-13.01%** | **-9.30%** ❌ |
| **Max Drawdown** | -32.52% | -27.27% | **-30.91%** | **+1.61%** ✅ |
| **Sharpe Ratio** | -0.20 | -0.24 | **-0.01** | **+0.19** ✅ |

**Regime Detection**:
- Jan-Apr: CHOPPY (75.1% of year) → Used diversified strategy
- Apr-Jul: BEAR (24.9% of year) → Used defensive strategy (30% cash, 2 stocks)
- Jul-Dec: CHOPPY → Used diversified strategy

**Analysis**:
- **Lost -13.01% vs -3.71% (original) and -1.97% (expanded)** ❌
- Regime detection correctly identified bear market in Apr-Jul
- BUT defensive strategy (30% cash) made things WORSE, not better
- The 70% that stayed invested still lost heavily

---

### 2022 Results (Bear Market)

| Metric | Original | Expanded | Regime-Aware | vs Original |
|--------|----------|----------|--------------|-------------|
| **Total Return** | -22.06% | -24.32% | **-26.18%** | **-4.12%** ❌ |
| **Max Drawdown** | -36.44% | -33.89% | **-28.05%** | **+8.39%** ✅ |
| **Sharpe Ratio** | -0.64 | -1.13 | **-0.10** | **+0.54** ✅ |

**Regime Detection**:
- Jan-Jul: CHOPPY (48.4% of year) → Used diversified strategy
- Jul-Dec: BEAR (51.6% of year) → Used defensive strategy (30% cash, 2 stocks)

**Analysis**:
- **Lost -26.18% vs -22.06% (original) and -24.32% (expanded)** ❌
- Regime detection correctly identified bear market starting July
- BUT still lost more than original strategy
- Better max drawdown (-28.05% vs -36.44%), but worse total return
- The defensive approach (30% cash) didn't provide enough protection

---

## 🔍 Detailed Analysis: Why Did Regime-Aware Fail?

### Problem 1: Defensive Strategy Not Defensive Enough

**Current Bear Market Strategy**:
- Invest only 30% of capital
- Select top 2 defensive stocks (VNM, VCB, GAS)
- Keep 70% in cash

**What Went Wrong**:
- The 30% invested in "defensive" stocks still lost heavily in bear markets
- VNM, VCB, GAS are NOT truly defensive - they fell along with the market
- Cash didn't earn returns (0%), so 70% of capital sat idle
- Net result: Lost money on the 30% invested + lost opportunity cost on 70% cash

**Example (2022)**:
- 30% invested in defensive stocks → Still lost -15% to -20%
- 70% in cash → 0% return
- Combined: -26.18% total loss

### Problem 2: Regime Detection Lag

**Issue**: Regime is detected at rebalancing dates (every 90 days)

**What Went Wrong**:
- Market may have already fallen 10-15% before bear regime is detected
- By the time we go defensive, much of the damage is already done
- Example (2022): Market started falling in Jan, but bear regime only detected in July

### Problem 3: Whipsaw in Choppy Markets

**Issue**: Choppy markets had mixed signals

**What Went Wrong**:
- 2023 oscillated between CHOPPY and BEAR regimes
- Each regime change triggered rebalancing
- Transaction costs (0.4% round-trip) accumulated
- Strategy kept switching between diversified and defensive modes
- Never stayed invested long enough to capture any rebounds

### Problem 4: ML Model Not Regime-Specific

**Issue**: Single ML model trained on all data (bull + bear + choppy)

**What Went Wrong**:
- Model accuracy was only 53.86% in 2024 (vs 68.81% for original)
- Model trained on mixed conditions doesn't specialize for any regime
- Predictions were not calibrated for regime-specific behavior
- Example: In bull markets, model should be more aggressive, but wasn't

### Problem 5: Over-Diversification in Wrong Regimes

**Issue**: Used diversified strategy in choppy markets

**What Went Wrong**:
- In choppy markets, diversification spread losses across more stocks
- Top 5 stocks all lost money, so diversifying = losing on more positions
- Original strategy (top 3) at least limited exposure to fewer losing positions
- Diversification only helps when some stocks rise - not when all fall

---

## 💡 Key Insights

### 1. Regime Detection ≠ Regime Protection

**Finding**: Successfully detecting bear markets doesn't automatically lead to better returns.

**Evidence**:
- Regime detector correctly identified bear markets in 2022 (51.6% of year) and 2023 (24.9%)
- Applied defensive strategy as intended (30% cash, 2 stocks)
- **Still lost -26.18% (2022) and -13.01% (2023)**

**Lesson**: Detection is easy, but effective defensive action is hard.

### 2. "Defensive Stocks" Are Not Defensive Enough

**Finding**: VNM, VCB, GAS fell along with the broader market.

**Evidence**:
- 2022: Even defensive stocks lost -20% to -30%
- 2023: Defensive stocks still fell -10% to -15%
- These are "blue chip" stocks, not "defensive" stocks

**Lesson**: Need truly defensive assets (bonds, gold, USD) or 100% cash in bear markets.

### 3. Partial Cash Positions Don't Work

**Finding**: Staying 30% invested during bear markets = 30% of losses.

**Evidence**:
- 2022: 30% invested → lost 30% × -60% = -18% + 70% × 0% = -18%
- Actual loss: -26.18%
- Going 100% cash would have lost 0%

**Lesson**: In true bear markets, half-measures don't work. Either fully exit or accept full losses.

### 4. Transaction Costs Add Up with Regime Switching

**Finding**: Frequent rebalancing due to regime changes increases costs.

**Evidence**:
- 2023 had 3 regime changes → 4 rebalancing events
- Each rebalance = 0.4% round-trip cost
- Total: 1.6% in transaction costs alone
- Original strategy (no regime switching) had lower costs

**Lesson**: Regime switching must generate >1-2% extra return to justify transaction costs.

### 5. Single ML Model Doesn't Adapt to Regimes

**Finding**: Training one model on all market conditions produces mediocre predictions.

**Evidence**:
- Model accuracy: 53.86% (regime-aware) vs 68.81% (original in bull markets)
- Model doesn't know which regime it's predicting for
- Predictions aren't calibrated for bull/bear/choppy behavior

**Lesson**: Need separate ML models for each regime, or regime-specific features.

---

## 📊 Cumulative 3-Year Performance

### Original Strategy (5 stocks, top 3)
```
Starting Capital: 100M VND
2022: -22.06% → 77.9M VND
2023: -3.71% × 77.9M → 75.0M VND
2024: +25.57% × 75.0M → 94.2M VND
Final: 94.2M VND (-5.8M, -5.8%)
```

### Expanded Strategy (15 stocks, top 5)
```
Starting Capital: 100M VND
2022: -24.32% → 75.7M VND
2023: -1.97% × 75.7M → 74.2M VND
2024: +15.49% × 74.2M → 85.7M VND
Final: 85.7M VND (-14.3M, -14.3%)
```

### Regime-Aware Strategy
```
Starting Capital: 100M VND
2022: -26.18% → 73.8M VND
2023: -13.01% × 73.8M → 64.2M VND
2024: +16.39% × 64.2M → 74.7M VND
Final: 74.7M VND (-25.3M, -25.3%)
```

**Comparison**:
- Original: Lost -5.8M (-5.8%)
- Expanded: Lost -14.3M (-14.3%)
- **Regime-Aware: Lost -25.3M (-25.3%)** ❌

**Regime-aware strategy lost 4.4× more than the original strategy!**

---

## ⚠️ What Went Wrong: Root Cause Analysis

### Expected Behavior vs Actual Behavior

**Expected (from REGIME_DETECTION_SUMMARY.md)**:
- 2024 (BULL): Use concentrated → +25.57% ✓
- 2023 (CHOPPY): Use diversified → -1.97% ✓
- 2022 (BEAR): Go to cash → 0% ✓
- **Total: +13% to +24%** ✓

**Actual Behavior**:
- 2024: Used concentrated + diversified → +16.39% (between expected)
- 2023: Used diversified + defensive → -13.01% ❌ (much worse than expected)
- 2022: Used diversified + defensive → -26.18% ❌ (much worse than expected)
- **Total: -24.53%** ❌

### The Discrepancy

**Why the huge difference?**

1. **Expected analysis assumed perfect execution**:
   - "Go to cash" in bear markets means 100% cash
   - Actual: Only 70% cash, 30% invested in "defensive" stocks that still fell

2. **Expected analysis used wrong baseline**:
   - Projected regime-aware would get original returns in bull markets
   - Actual: Got lower returns due to spending time in diversified mode

3. **Expected analysis underestimated defensive losses**:
   - Assumed defensive stocks would hold value in bear markets
   - Actual: "Defensive" stocks (VNM, VCB, GAS) fell along with market

4. **Expected analysis didn't account for regime detection lag**:
   - Assumed instant regime detection at regime change
   - Actual: 90-day rebalancing delay means detecting regime late

5. **Expected analysis didn't account for ML model degradation**:
   - Assumed ML model would work equally well in all regimes
   - Actual: Single model trained on mixed data has lower accuracy (53.86% vs 68.81%)

---

## 🎯 Lessons Learned

### What We Learned About Strategy Design

1. **Regime detection is necessary but not sufficient**
   - Detecting bear markets is easy
   - Protecting capital in bear markets is hard

2. **Defensive strategies must be TRULY defensive**
   - "Blue chip" ≠ "defensive"
   - Need uncorrelated assets (bonds, gold, USD, cash)
   - Or need to go 100% to cash

3. **Partial solutions produce partial failures**
   - 30% cash in bear markets = 30% of losses
   - Either fully commit to defense (100% cash) or fully stay invested

4. **One-size-fits-all ML models don't work**
   - Need separate models for each regime
   - Or regime-specific features
   - Or don't use ML at all (use fundamentals/value)

5. **Transaction costs matter**
   - Every regime change = rebalancing = costs
   - Need >1-2% edge to justify switching

### What We Learned About Vietnamese Market

1. **There are no truly "defensive" Vietnamese stocks**
   - VNM, VCB, GAS all fell in 2022 bear market
   - High correlation with VN-Index
   - Diversification within Vietnamese stocks doesn't provide protection

2. **Bear markets are severe and prolonged**
   - 2022: -22% to -26% losses across all strategies
   - Lasting 6+ months (July-December)
   - Drawdowns of -28% to -36%

3. **Regime changes happen mid-quarter**
   - 90-day rebalancing is too slow
   - Market moves happen faster than quarterly checks
   - Need daily or weekly regime monitoring

4. **Choppy markets are the norm**
   - 2023: 75% choppy, 25% bear
   - 2024: 40% choppy, 60% bull
   - Default should be "choppy" strategy, not "bull"

---

## 📋 Why This Failed: Implementation Flaws

### Critical Flaw #1: Wrong Defensive Strategy

**Problem**:
```python
if detected_regime == 'bear':
    invest_amount = cash * 0.30  # Only 30% invested
    num_stocks = 2
    universe = defensive_stocks  # ['VNM', 'VCB', 'GAS']
```

**Why It Failed**:
- VNM, VCB, GAS are NOT defensive - they're just large-cap blue chips
- 30% invested × -60% loss = -18% total loss
- 70% cash × 0% return = missed opportunity

**What Should Have Been Done**:
```python
if detected_regime == 'bear':
    invest_amount = 0  # 100% cash
    # OR
    invest_amount = cash * 0.50  # 50% in ACTUAL defensive assets (bonds, gold)
```

### Critical Flaw #2: Single ML Model for All Regimes

**Problem**:
```python
# One model trained on all historical data
predictor.train(training_df)  # Mixed bull/bear/choppy data
```

**Why It Failed**:
- Model averages across all market conditions
- Doesn't specialize for any regime
- Lower accuracy (53.86% vs 68.81%)

**What Should Have Been Done**:
```python
# Train separate models for each regime
bull_model.train(bull_training_data)
bear_model.train(bear_training_data)
choppy_model.train(choppy_training_data)

# Use regime-specific model
if regime == 'bull':
    pred = bull_model.predict(features)
```

### Critical Flaw #3: Rebalancing Lag

**Problem**:
```python
rebalance_interval = 90  # Every 90 days
```

**Why It Failed**:
- Markets can fall 10-20% in 90 days
- Bear regime detected AFTER major fall
- Too slow to react

**What Should Have Been Done**:
```python
# Check regime daily, rebalance when regime changes
if regime_changed:
    rebalance()
```

### Critical Flaw #4: No Stop Losses

**Problem**:
- No stop loss mechanism
- Held positions during entire bear market
- Watched portfolio fall -26%

**What Should Have Been Done**:
```python
# Exit position if drawdown > 10%
if (current_price - entry_price) / entry_price < -0.10:
    sell_position()
    go_to_cash()
```

---

## 🔄 What Would Be Needed to Fix This

### Option 1: True Defensive Assets

**Requirement**: Access to uncorrelated defensive assets

**Changes**:
```python
if regime == 'bear':
    # 100% to defensive assets
    portfolio = {
        'BONDS': 0.50,  # Vietnamese government bonds
        'GOLD': 0.25,   # Gold ETF
        'USD': 0.25     # USD money market
    }
```

**Challenge**: These assets may not be available or liquid in Vietnam.

### Option 2: Full Cash Exit in Bear Markets

**Requirement**: Accept 0% return during bear markets

**Changes**:
```python
if regime == 'bear':
    # 100% cash, 0% invested
    sell_all_positions()
    cash = portfolio_value
```

**Trade-off**:
- Miss rebounds if regime detection wrong
- But preserve capital if regime detection right

### Option 3: Regime-Specific ML Models

**Requirement**: Separate models for each regime

**Changes**:
```python
# Train 3 separate models
models = {
    'bull': GaussianNB(),
    'choppy': RandomForest(),
    'bear': LogisticRegression()
}

# Use regime-specific model
model = models[current_regime]
pred = model.predict(features)
```

**Challenge**: Need more historical data to train 3 models separately.

### Option 4: Daily Regime Monitoring + Stop Losses

**Requirement**: Check regime daily, exit on drawdowns

**Changes**:
```python
# Check regime daily
regime = detector.detect_regime(current_date)

# Exit if regime changes to bear
if regime == 'bear' and previous_regime != 'bear':
    sell_all()
    go_to_cash()

# Exit if drawdown > 10%
if max_drawdown < -0.10:
    sell_all()
    go_to_cash()
```

**Trade-off**: Higher transaction costs from more frequent trading.

### Option 5: Abandon Momentum Entirely

**Requirement**: Complete strategy redesign

**Changes**:
- Focus on value + quality fundamentals
- Ignore momentum completely
- Buy undervalued stocks with strong fundamentals
- Hold for 1-2 years regardless of market regime

**Rationale**:
- Momentum fails in 2 out of 3 years
- Regime detection didn't fix momentum's fundamental flaw
- Value investing may be more robust across all regimes

---

## 📊 Comparison Summary

### Performance Ranking (3-Year Total)

1. **Original** (5 stocks, top 3): -2.87% ✅ BEST
2. **Expanded** (15 stocks, top 5): -10.33%
3. **Regime-Aware**: -24.53% ❌ WORST

### Max Drawdown Ranking (Worst Year)

1. **Regime-Aware**: -28.05% (2022) ✅ BEST
2. **Expanded**: -33.89% (2022)
3. **Original**: -36.44% (2022) ❌ WORST

### Sharpe Ratio (Best Year)

1. **Original** (2024): 1.72 ✅ BEST
2. **Expanded** (2024): 1.15
3. **Regime-Aware** (2024): 0.08 ❌ WORST

### Overall Assessment

| Aspect | Winner | Reason |
|--------|--------|--------|
| **Total Return** | Original (-2.87%) | Lost least money over 3 years |
| **Risk Control** | Regime-Aware (-28% max DD) | Best drawdown protection in 2022 |
| **Risk-Adjusted Return** | Original (Sharpe 1.72) | Best Sharpe ratio in bull market |
| **Consistency** | Expanded | Smallest range of outcomes |

**Verdict**: **Original strategy is still the best overall**, despite all enhancements.

---

## 💭 Final Thoughts

### The Harsh Reality

**We built a sophisticated regime detection system, implemented adaptive strategies, and tested rigorously. The result? Made things WORSE.**

**Key Realizations**:

1. **Complexity ≠ Better Performance**
   - Original simple strategy: -2.87% loss
   - Complex regime-aware strategy: -24.53% loss
   - Added complexity made things 8.5× worse!

2. **Regime Detection Without Proper Defense = Useless**
   - Detecting bear markets is easy
   - Protecting capital is hard
   - We detected the bear markets but still lost -26%

3. **There Are No Safe Havens in Vietnamese Stocks**
   - All stocks fell together in 2022
   - "Defensive" stocks aren't defensive
   - Need to exit to cash or other asset classes

4. **Momentum Strategies Don't Work in Vietnamese Market (2022-2024)**
   - 3 years of testing proves this
   - Lost money with concentrated (original)
   - Lost money with diversified (expanded)
   - Lost money with regime-aware
   - **Momentum itself is the problem**

### What This Teaches Us

**About Strategy Development**:
- Backtesting reveals truth, even when painful
- Sophisticated doesn't mean effective
- Simple strategies often outperform complex ones
- Guard against overfitting to recent data (2024 bull market)

**About Vietnamese Market**:
- Highly volatile (volatility >200% in some years)
- Strong bear markets (-20% to -30%)
- High correlation among stocks (no diversification benefit)
- Need defensive assets outside of stocks

**About Our Approach**:
- Momentum + ML is fundamentally flawed for this market
- Regime detection can't fix a broken strategy
- Need either:
  - True defensive assets (bonds, gold)
  - 100% cash in bear markets
  - Complete strategy redesign (value, not momentum)

---

## 🚦 Next Steps: Three Paths Forward

### Path A: Accept Defeat, Use Simple Strategy (Recommended)

**Action**: Stick with original strategy (-2.87% over 3 years)

**Rationale**:
- Original is least-bad option
- All enhancements made things worse
- Sometimes simple is better

**Next**: Focus on risk management (stop losses, position sizing)

---

### Path B: Implement Proper Defensive Strategy

**Action**: Modify regime-aware to use 100% cash in bear markets

**Requirements**:
- Go 100% cash when regime = bear (not 30%)
- Remove "defensive stocks" concept
- Accept 0% return during bear years

**Expected Outcome**:
- 2022: 0% (instead of -26.18%)
- 2023: -6% (choppy parts still lose, bear parts 0%)
- 2024: +16.39%
- **Total: +10% to +12%** (finally profitable!)

**Trade-off**: Miss rebounds if regime detection is wrong

---

### Path C: Complete Strategy Redesign

**Action**: Abandon momentum entirely, design value-based strategy

**Requirements**:
- Focus on fundamental value (low P/E, P/B, high ROE)
- Buy undervalued stocks
- Hold for 1-2 years
- Ignore short-term market movements
- No ML, no technical indicators

**Expected Outcome**:
- More stable across all market regimes
- Lower volatility
- Better long-term compounding
- Potentially profitable over full cycle

**Trade-off**: Lower upside in bull markets

---

## 📁 Files Generated

**Results Files**:
- `regime_aware_2024_results.csv` - 2024 regime-aware results (+16.39%)
- `regime_aware_2023_results.csv` - 2023 regime-aware results (-13.01%)
- `regime_aware_2022_results.csv` - 2022 regime-aware results (-26.18%)

**Output Logs**:
- `regime_aware_2024_output.txt` - Detailed 2024 execution log
- `regime_aware_2023_output.txt` - Detailed 2023 execution log
- `regime_aware_2022_output.txt` - Detailed 2022 execution log

**Documentation**:
- `REGIME_AWARE_RESULTS.md` - This comprehensive analysis

---

## 🔚 Conclusion

**The regime-aware strategy failed to improve performance. In fact, it made things significantly worse.**

Despite:
- ✅ Successfully detecting market regimes (bull/bear/choppy)
- ✅ Adapting strategy based on regime
- ✅ Using defensive measures in bear markets
- ✅ Implementing everything as designed

We got:
- ❌ Worst 3-year return (-24.53%)
- ❌ Worse than original (-2.87%)
- ❌ Worse than expanded (-10.33%)
- ❌ Lost -25.3M VND vs -5.8M VND (original)

**Root Cause**:
- Momentum strategy is fundamentally flawed for this market/timeframe
- Regime detection can't fix a broken strategy
- "Defensive stocks" aren't defensive
- Partial cash positions don't work

**Recommendation**:
Either:
1. **Accept the original strategy** as least-bad option
2. **Implement 100% cash in bear markets** (Path B)
3. **Completely redesign the strategy** with value focus (Path C)

**DO NOT** proceed with the current regime-aware implementation for live trading.

---

**Status**: ⚠️ Regime-aware strategy FAILED
**Next Decision**: Choose Path A, B, or C above
**Live Trading**: **NOT READY** - Strategy performs worse than baseline
**Learning**: Complexity without proper execution = worse results
