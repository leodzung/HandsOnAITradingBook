# ML Training Requirements for Short-Expiry Bot

**Date:** 2026-02-14
**Current Status:** Phase 1 (Rule-based trading)
**Next Phase:** Phase 2 (ML model integration)

---

## Current Data Collection Status

### Price Snapshots
```sql
SELECT COUNT(*) as total_snapshots,
       COUNT(DISTINCT market_id) as unique_markets,
       datetime(MIN(timestamp)) as first_snapshot,
       datetime(MAX(timestamp)) as last_snapshot,
       ROUND((julianday(MAX(timestamp)) - julianday(MIN(timestamp))) * 24, 2) as hours_of_data
FROM price_snapshots;
```

**Results:**
- **Total snapshots:** 214
- **Unique markets:** 56
- **Data duration:** 0.82 hours (~49 minutes)
- **Collection rate:** ~261 snapshots/hour
- **First snapshot:** 2026-02-15 05:00:23
- **Last snapshot:** 2026-02-15 05:49:33

### Trade History
```sql
SELECT COUNT(*) as total_trades,
       COUNT(CASE WHEN outcome = 'WIN' THEN 1 END) as wins,
       COUNT(CASE WHEN outcome = 'LOSS' THEN 1 END) as losses,
       COUNT(CASE WHEN outcome IS NULL THEN 1 END) as open
FROM positions;
```

**Current:** Still paper trading in Phase 1 (rule-based), minimal trade history.

---

## ML Model Requirements

### Model Type (Planned)
**Gradient Boosting Machine (GBM)** with walk-forward validation

**Why GBM?**
- Handles non-linear relationships well
- Robust to feature scaling
- Good for binary classification (WIN/LOSS)
- Interpretable feature importance

### Data Requirements

#### Minimum Dataset Size

For **reliable GBM training**, we need:

| Data Type | Minimum | Recommended | Current | Gap |
|-----------|---------|-------------|---------|-----|
| **Unique markets** | 100 | 300+ | 56 | Need 44+ more markets |
| **Price snapshots** | 5,000 | 20,000+ | 214 | Need 4,786+ more |
| **Completed trades** | 50 | 200+ | ~0 | Need 50+ trades |
| **Days of data** | 7 | 30+ | 0.03 | Need 7+ days |
| **Markets per bucket** | 30 | 100+ | 18/bucket | Need ~12+ per bucket |

#### Feature Coverage Requirements

**Time-based features** (require historical data):
- ✅ Days/hours/minutes to expiry - Available immediately
- ⏳ **Momentum features** - Need 24 hours of data per market
  - Price change 1h/4h/12h
  - Velocity, acceleration
  - Trend consistency
- ⏳ **Volume trends** - Need 7 days for reliable signals
  - 24h vs 7-day volume comparison
  - Liquidity trends

**Microstructure features** (available now):
- ✅ Spread, depth, imbalance - Available from orderbook

**Outcome labels** (requires completed trades):
- ❌ **Need markets to resolve** - 0 completed trades currently

---

## Data Collection Timeline

### Current Collection Rate

**Assumptions:**
- Bot scans every 5 minutes (300 seconds)
- Finds ~40-60 markets per scan
- Each market gets 1 snapshot per scan

**Rate:** ~261 snapshots/hour = ~6,264 snapshots/day

### Projected Timeline

#### Scenario 1: Minimum Viable Dataset

**Target:** 5,000 snapshots + 50 completed trades

| Metric | Target | Current | Days Needed |
|--------|--------|---------|-------------|
| Price snapshots | 5,000 | 214 | **1 day** (at current rate) |
| Unique markets | 100 | 56 | **3-5 days** (need market turnover) |
| Completed trades | 50 | 0 | **7-14 days** (markets need time to resolve) |

**Estimated time: 14 days**

#### Scenario 2: Recommended Dataset

**Target:** 20,000 snapshots + 200 completed trades

| Metric | Target | Current | Days Needed |
|--------|--------|---------|-------------|
| Price snapshots | 20,000 | 214 | **3-4 days** |
| Unique markets | 300 | 56 | **10-15 days** |
| Completed trades | 200 | 0 | **30-45 days** |

**Estimated time: 30-45 days**

---

## Feature Engineering Requirements

### 1. Price History Data (Momentum Features)

**Requirement:** 24 hours of continuous price snapshots per market

**Current status:**
- Markets tracked: 56
- Average snapshots per market: 214/56 = 3.8 snapshots
- Need: 24 hours × 12 samples/hour = 288 snapshots per market

**Gap:** Need 23+ more hours of data collection

### 2. Volume History (Volume Trends)

**Requirement:** 7 days of volume data per market

**Current status:**
- Volume data: Available from API (instant)
- Volume trends: Need 7 days to calculate

**Gap:** Need 7 days of data collection

### 3. Market Resolution Data (Labels)

**Requirement:** Markets must resolve to generate WIN/LOSS labels

**Current status:**
- Open positions: Paper trading phase
- Completed trades: 0

**Timeline:**
- Ultra-short (2-24h): Resolve in 1 day
- Short (1-3 days): Resolve in 1-3 days
- Medium (3-7 days): Resolve in 3-7 days

**Gap:** Need to wait for markets to resolve (7-14 days minimum)

---

## Recommended Action Plan

### Phase 1: Data Collection (Current - Next 30 days)

**Week 1-2: Accumulate Price History**
- ✅ Bot is running and collecting snapshots
- ✅ Microservice is stable
- 🎯 **Goal:** 10,000+ snapshots across 100+ markets
- 🎯 **Milestone:** First markets resolve (ultra-short bucket)

**Week 3-4: Build Trade History**
- 🎯 **Goal:** 50+ completed trades
- 🎯 **Milestone:** Enough data for minimum viable model

**Week 5-8: Expand Dataset**
- 🎯 **Goal:** 200+ completed trades
- 🎯 **Goal:** 20,000+ snapshots across 300+ markets
- 🎯 **Milestone:** Ready for production ML model

### Phase 2: Model Training (After 30 days)

**Prerequisites:**
- ✅ 20,000+ price snapshots
- ✅ 300+ unique markets
- ✅ 200+ completed trades with outcomes
- ✅ 30 days of volume/liquidity trends

**Training Approach:**
1. **Split data by time** (not random)
   - Training: Days 1-21 (70%)
   - Validation: Days 22-25 (10%)
   - Test: Days 26-30 (20%)

2. **Walk-forward validation**
   - Train on period 1 → Test on period 2
   - Retrain on periods 1+2 → Test on period 3
   - Prevents lookahead bias

3. **Feature importance analysis**
   - Identify top predictive features
   - Remove redundant features
   - Improve model interpretability

4. **Hyperparameter tuning**
   - Learning rate, max depth, n_estimators
   - Use validation set for tuning
   - Cross-validate on time splits

### Phase 3: Model Deployment (After 45 days)

**Validation criteria before deployment:**
- ✅ Test accuracy > 55% (better than random)
- ✅ Sharpe ratio > 1.0 on test set
- ✅ Maximum drawdown < 20%
- ✅ Model doesn't overfit (train vs test gap < 5%)

**Deployment strategy:**
- Start with 10% of capital
- Monitor model predictions vs outcomes
- Gradually increase allocation if performing well

---

## Current Bottlenecks

### 1. Market Resolution Time
**Issue:** Markets need 1-7 days to resolve
**Impact:** Can't generate labels until markets close
**Solution:** Wait patiently, focus on data collection

### 2. Market Turnover
**Issue:** Same markets appear repeatedly
**Impact:** Need new markets for diversity
**Solution:**
- Scan more frequently
- Expand to non-crypto categories (Phase 3)
- Track more event types

### 3. Momentum Feature Gaps
**Issue:** Need 24h of history per market
**Impact:** Momentum features return 0.0 initially
**Solution:** Accumulate 24 hours of snapshots (automatic)

---

## Interim Steps (While Collecting Data)

### 1. Validate Rule-Based Strategy
**Now - Week 2:**
- Monitor Phase 1 (rule-based) performance
- Track win rate, profit factor, max drawdown
- Identify which rules work best
- Use this to inform ML feature selection

### 2. Feature Engineering Experiments
**Week 2-3:**
- Calculate features on collected data
- Analyze feature distributions
- Test feature correlations
- Identify predictive patterns

### 3. Simulate Training with Partial Data
**Week 3-4:**
- Train models on partial dataset
- Evaluate performance vs data size
- Identify if more data needed
- Refine feature engineering

---

## Data Quality Checklist

Before training, verify:

- [ ] Price snapshots cover full 24-hour cycle
- [ ] No gaps > 1 hour in time series
- [ ] All buckets have balanced representation
- [ ] Trade outcomes are correctly labeled
- [ ] Features have no missing values
- [ ] Outliers are handled appropriately
- [ ] Market variety (not just Bitcoin markets)
- [ ] Different expiry horizons represented

---

## Expected Model Performance

### Baseline (Random Guessing)
- Accuracy: ~50%
- Sharpe ratio: ~0
- Win rate: ~50%

### Minimum Viable Model (14 days data)
- Expected accuracy: 52-55%
- Expected Sharpe: 0.5-0.8
- Win rate: 53-56%

### Production Model (30+ days data)
- Target accuracy: 55-58%
- Target Sharpe: 1.0-1.5
- Win rate: 56-60%

**Note:** In prediction markets, even small edges (55% accuracy) can be highly profitable with proper position sizing.

---

## Summary

### Current Status
- ✅ Data collection active (49 minutes of data)
- ✅ Momentum features implemented
- ✅ Bot running in Phase 1 (rule-based)
- ⏳ Waiting for markets to resolve

### Timeline to ML Training

| Milestone | Data Needed | ETA |
|-----------|-------------|-----|
| **Minimum viable model** | 5k snapshots, 50 trades | **14 days** |
| **Recommended model** | 20k snapshots, 200 trades | **30-45 days** |
| **Production model** | 50k+ snapshots, 500+ trades | **60-90 days** |

### Next Actions

**Today:**
- ✅ Continue data collection (automatic)
- ✅ Monitor microservice stability
- ✅ Verify price tracking working

**This Week:**
- Monitor first trade completions
- Analyze rule-based strategy performance
- Plan feature engineering pipeline

**Weeks 2-4:**
- Build trade history database
- Experiment with feature engineering
- Test small-scale models on partial data

**Month 2+:**
- Train production ML model
- Deploy with walk-forward validation
- Transition to Phase 2

---

**Recommendation:** Continue data collection for **30 days minimum** before training a production ML model. Use the interim time to validate rule-based strategies and refine feature engineering.

---

**Author:** Claude Sonnet 4.5
**Date:** 2026-02-14
**Status:** Data Collection Phase
