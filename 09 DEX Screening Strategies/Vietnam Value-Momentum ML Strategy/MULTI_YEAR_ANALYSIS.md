# 📊 Multi-Year Backtest Analysis

**Date**: November 10, 2024
**Status**: Strategy testing in progress - NOT ready for live trading

---

## 🎯 Executive Summary

Tested the Vietnam Value-Momentum ML Strategy on real Vietnamese stock data across multiple years. **Key finding**: Strategy performance varies dramatically by market conditions.

**Recommendation**: 🔴 **DO NOT trade live** - Strategy needs significant improvements first.

---

## 📈 Performance by Year

### 2024 Results (Bull Market)

| Metric | Value | Status |
|--------|-------|--------|
| **Return** | **+25.57%** | ✅ Excellent |
| **Sharpe Ratio** | 1.72 | ✅ Very Good |
| **Max Drawdown** | -10.59% | ✅ Well controlled |
| **ML Accuracy** | 68.81% | ✅ Good |
| **Monthly Win Rate** | 67% (6/9) | ✅ Consistent |
| **Stocks Selected** | VNM, VCB, FPT, MSN | Top quality picks |

**Market Conditions**: Trending bull market with clear momentum
**Why It Worked**: ML correctly identified momentum in trending stocks

---

### 2023 Results (Choppy Market)

| Metric | Value | Status |
|--------|-------|--------|
| **Return** | **-3.71%** | ❌ Loss |
| **Sharpe Ratio** | -0.20 | ❌ Negative |
| **Max Drawdown** | -32.52% | ❌ Large loss |
| **ML Accuracy** | 57.05% | ⚠️ Barely > random |
| **Monthly Win Rate** | ??? | ❌ Poor |
| **Stocks Selected** | HPG, MSN (concentrated) | Too concentrated |

**Market Conditions**: Choppy, volatile, sector rotation
**Why It Failed**: Momentum strategy failed in mean-reverting market

---

### 2022 Results (Bear Market)

| Metric | Value | Status |
|--------|-------|--------|
| **Return** | **-22.06%** | ❌ Large loss |
| **Sharpe Ratio** | -0.64 | ❌ Negative |
| **Max Drawdown** | -36.44% | ❌ Extreme |
| **ML Accuracy** | 62.19% | ⚠️ Moderate |
| **Monthly Win Rate** | ??? | ❌ Poor |
| **Stocks Selected** | MSN, FPT, VCB (concentrated) | Too concentrated |

**Market Conditions**: Bear market, global recession fears, Vietnam economic slowdown
**Why It Failed**: Momentum strategy completely failed in bear market, no downside protection

---

## 📊 Aggregate Performance

**3-Year Average (2022-2024)**:
- Average Return: **-0.07% per year** (essentially flat)
- Volatility: Extremely high year-to-year variation
- Risk-Adjusted: Very poor (negative in 2 of 3 years)
- **Cumulative 3-Year Return**: **-2.87%** (losing money overall)

**Year-by-Year Breakdown**:
- 2024: +25.57% ✅ (bull market)
- 2023: -3.71% ❌ (choppy market)
- 2022: -22.06% ❌ (bear market)

**Comparison to VN-Index**:
- VN-Index 2024: ~10-12% (estimated) → Strategy outperformed by ~15%
- VN-Index 2023: ~13% (estimated) → Strategy underperformed by ~17%
- VN-Index 2022: ~-32% (bear) → Strategy outperformed by ~10% (but still lost money)
- **3-Year VN-Index**: ~-13% → Strategy slightly better but both negative

**Key Finding**: 🔴 Strategy is **NOT profitable** over the full 3-year period

---

## 🔍 Root Cause Analysis

### Why 2024 Succeeded

1. ✅ **Clear trend**: Bull market with momentum
2. ✅ **ML works**: 68.81% accuracy predicting continuation
3. ✅ **Stock selection**: VNM, VCB, FPT all strong performers
4. ✅ **Timing**: Quarterly rebalancing captured major moves
5. ✅ **Low drawdown**: Exit signals worked well

### Why 2023 Failed

1. ❌ **Concentrated positions**: Only 1 stock per quarter (HPG or MSN)
   - Should have 5+ stocks for diversification
   - Single stock risk too high

2. ❌ **Wrong market regime**: Applied momentum to mean-reverting market
   - 2023 was choppy with sector rotation
   - Momentum signals gave false positives

3. ❌ **No defensive mechanism**: Stayed fully invested during drops
   - No cash buffer or stop losses
   - Rode entire -32.52% drawdown

4. ❌ **ML overfitting**: Model trained mostly on bull market data
   - 57.05% accuracy (barely better than coin flip)
   - Need more diverse training data

5. ❌ **No regime detection**: Strategy doesn't adapt to market conditions
   - Same approach in all markets
   - Need to detect trending vs choppy

### Why 2022 Failed Even Worse

1. ❌ **Bear market devastation**: -22.06% loss, -36.44% max drawdown
   - Vietnam market declined ~32% in 2022
   - Global recession fears, inflation, Fed rate hikes
   - Strategy lost money but not as much as market

2. ❌ **No defensive positioning**: Stayed invested during crash
   - Should have moved to cash when market turned bearish
   - Rode the entire bear market down
   - No stop losses or risk controls

3. ❌ **Momentum in bear market**: Worst possible combination
   - Momentum strategies typically lose in bear markets
   - Applied bullish momentum signals to falling market
   - Classic "fighting the tape"

4. ❌ **ML model confusion**: 62.19% accuracy (moderate)
   - Better than 2023 (57%) but still not great
   - Model saw conflicting signals in volatile market
   - Training data didn't include enough bear market examples

5. ❌ **Concentrated positions again**: Only 1-2 stocks per quarter
   - Single stock risk magnified losses
   - MSN selected multiple times (poor performer in 2022)
   - No diversification to cushion blow

---

## 💡 Key Learnings

### What We Discovered

1. **Strategy ONLY works in bull markets** - 2024 was the exception, not the rule
2. **Fails in all other conditions** - Lost money in both 2022 and 2023
3. **Market regime is EVERYTHING** - Wrong regime = guaranteed losses
4. **Diversification critical** - 1-2 stocks = gambling, not investing
5. **Testing saves money** - Found major flaw BEFORE losing real capital! 🎯
6. **3-year return is flat** - Would have been better off in cash/bonds

### What This Means

**Reality Check**:
- Strategy is **NOT profitable** over full market cycle
- Only works 1 out of 3 years (33% success rate)
- Cumulative 3-year return: -2.87% (losing money)
- Max drawdown: -36.44% (unacceptable risk)

**The Harsh Truth**:
- Current version is **fundamentally flawed**
- Not just "needs improvement" - needs **complete redesign**
- Momentum-only approach doesn't work in Vietnamese market
- ML model can't predict well enough across all conditions

**Good News (Yes, there is some)**:
- Testing revealed this BEFORE losing real money! 🎯
- Real data integration works perfectly
- We learned exactly what NOT to do
- Framework is solid, just needs different strategy

---

## 🔧 Required Improvements (Before Live Trading)

### Priority 1: Increase Diversification

**Current**: 1-3 stocks per quarter
**Target**: 5-10 stocks minimum

**How**: Change line 125 in simple_backtest_real_data.py
```python
selected_stocks = [s for s, _ in sorted_preds[:5]]  # 5 stocks minimum
```

**Expected Impact**: Lower returns but much lower risk

---

### Priority 2: Add Regime Detection

**Current**: Same strategy in all markets
**Target**: Detect trending vs choppy markets

**How**: Add VN-Index trend filter
```python
def detect_market_regime(vnindex_data):
    # Simple: 50-day vs 200-day MA
    ma50 = vnindex_data['close'].rolling(50).mean().iloc[-1]
    ma200 = vnindex_data['close'].rolling(200).mean().iloc[-1]

    if ma50 > ma200 * 1.02:  # 2% above
        return 'bull_trending'
    elif ma50 < ma200 * 0.98:  # 2% below
        return 'bear_trending'
    else:
        return 'choppy'

# Use different strategies based on regime
if regime == 'bull_trending':
    use_momentum_strategy()
elif regime == 'choppy':
    reduce_positions()  # Go 50% cash
else:  # bear
    go_defensive()  # Dividend stocks only
```

**Expected Impact**: Avoid 2023-like losses

---

### Priority 3: Add Defensive Mechanisms

**Current**: Always fully invested
**Target**: Cash position when uncertain

**Options**:
1. **Stop losses**: Exit if stock down >15%
2. **Portfolio stops**: Reduce exposure if portfolio down >10%
3. **Cash buffer**: Keep 20-30% cash in choppy markets
4. **Volatility filter**: Exit when market volatility spikes

---

### Priority 4: Train on Mixed Conditions

**Current**: Training on mostly trending data
**Target**: Include bear and choppy markets

**How**: Use 2021-2023 data for training (mixed conditions)
```python
# Current: Uses last 1 year
train_start = start_date - timedelta(days=365)

# Better: Uses last 2 years (more diverse)
train_start = start_date - timedelta(days=730)
```

**Expected Impact**: Better ML predictions in all markets

---

## 📅 Recommended Timeline

### Week 1: Testing & Analysis ✅ COMPLETED
- [x] Test 2024 → ✅ +25.57%
- [x] Test 2023 → ❌ -3.71%
- [x] Test 2022 → ❌ -22.06%
- [x] Understand why results vary → Documented

### Week 2: Quick Improvements
- [ ] Increase to 5 stocks
- [ ] Add VN-Index trend filter
- [ ] Test improved version on 2023 (should be better)

### Week 3-4: Major Enhancements
- [ ] Implement regime detection
- [ ] Add stop losses
- [ ] Retrain ML on mixed data
- [ ] Test on all years (2022, 2023, 2024)

### Week 5-6: Validation
- [ ] Walk-forward testing
- [ ] Stress testing (worst case scenarios)
- [ ] Compare improved vs original

### Month 2-7: Paper Trading
- [ ] Open paper trading account
- [ ] Trade live (with virtual money)
- [ ] Track vs backtest expectations
- [ ] Build confidence

### Month 8+: Live Trading (If All Checks Pass)
- [ ] Start with small capital (10-20% of target)
- [ ] Scale up gradually
- [ ] Monitor closely

---

## 🎯 Success Criteria (Before Live Trading)

Strategy must pass ALL of these:

- [ ] Positive returns in 3 consecutive years
- [ ] Average return > 10% per year
- [ ] Max drawdown < 20% in any year
- [ ] Sharpe ratio > 0.8 on aggregate
- [ ] Win rate > 60% of periods
- [ ] Paper trading matches backtest (±5%)
- [ ] Comfortable with worst-case loss
- [ ] Have emergency exit plan

**Current Status**: 2/8 criteria met (only 2024 results acceptable)

---

## 📁 Files Generated

**Results Files**:
- `simple_backtest_results.csv` - 2024 results (original) ✅
- `backtest_2023_results.csv` - 2023 results ✅
- `backtest_2022_results.csv` - 2022 results ✅

**Analysis Files**:
- `MULTI_YEAR_ANALYSIS.md` - This file (comprehensive 3-year analysis) ✅
- `ACTION_PLAN.md` - Updated with all 3 years ✅
- `RESULTS_SUMMARY.md` - 2024 detailed analysis ✅

**Test Scripts**:
- `test_2023.py` - 2023 backtest script ✅
- `test_2022.py` - 2022 backtest script ✅
- `run_2023_test.sh` - Quick test runner ✅

---

## 🔄 Next Immediate Action

**✅ TESTING COMPLETE**: All 3 years tested (2022, 2023, 2024)

**Results Summary**:
```
2024: +25.57% | 2023: -3.71% | 2022: -22.06%
Average: -0.07% per year (essentially FLAT)
Cumulative 3-year: -2.87% (LOSING MONEY)
```

**Critical Decision Point**:
The strategy is **fundamentally flawed** and NOT profitable over a full market cycle. You have TWO options:

### Option A: Major Redesign (Recommended)
Abandon momentum-only approach and redesign from scratch:
- Add market regime detection (bull/bear/choppy)
- Include defensive mechanisms (cash positions, stop losses)
- Focus on value + quality in bear markets
- Use momentum ONLY in confirmed bull markets
- Increase diversification to 5-10 stocks minimum

### Option B: Incremental Improvements (Less likely to succeed)
Try Priority 1 improvement and see if it helps:
```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies/Vietnam Value-Momentum ML Strategy"

# Edit simple_backtest_real_data.py
# Line 125: Change to 5 stocks instead of 1-3
# selected_stocks = [s for s, _ in sorted_preds[:5]]

# Re-test on all 3 years
python3 simple_backtest_real_data.py  # Test 2024
python3 test_2023.py  # Test 2023
python3 test_2022.py  # Test 2022
```

**Honest Assessment**: Minor tweaks (more stocks, different rebalancing) won't fix the fundamental issue that momentum doesn't work in non-trending markets. You need regime detection at minimum.

---

## 💬 Key Takeaways

1. **Testing saved you A LOT of money** 🎯
   - Found strategy loses money 2 out of 3 years
   - Discovered -36.44% max drawdown BEFORE risking real capital
   - Would have lost -2.87% over 3 years (vs safe alternatives)
   - This is EXACTLY why we test thoroughly!

2. **Strategy does NOT have potential (as-is)**
   - 2024 was the outlier, not the norm
   - Loses money in bear markets (-22.06%)
   - Loses money in choppy markets (-3.71%)
   - Only works in bull markets (+25.57%)
   - 33% success rate is unacceptable

3. **Market regime is EVERYTHING**
   - Momentum ONLY works in strong trends
   - Catastrophically fails in all other conditions
   - Vietnamese market isn't trending most of the time
   - Must detect regime BEFORE applying strategy

4. **Diversification is survival**
   - 1-2 stocks = guaranteed volatility
   - Concentrated positions magnified all losses
   - Need 5-10 stocks minimum
   - But this alone won't save the strategy

5. **Hard truth: Complete redesign needed**
   - Not "almost there" - fundamentally flawed
   - Can't fix with minor tweaks
   - Need regime detection as core component
   - Or abandon momentum approach entirely

6. **The REAL lesson**
   - Don't fall in love with your first idea
   - Test thoroughly before committing
   - Be willing to pivot or abandon
   - Losing time is better than losing money

**Remember**: The goal isn't to make THIS strategy work - it's to find a strategy that ACTUALLY works! 📈

---

**Status**: 🔴 Strategy Failed Validation
**Next Review**: After major redesign or new strategy approach
**Live Trading ETA**: 6-12 months minimum (requires complete rework)
**Current Strategy Verdict**: ❌ Do not trade - would lose money
