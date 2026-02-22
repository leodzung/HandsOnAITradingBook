# Vietnam Value-Momentum ML Strategy

## Overview
A hybrid fundamental/value and AI/ML-driven strategy designed for mid-term (3-6 month) opportunities in the Vietnamese stock market. This strategy combines quantitative screening, machine learning predictions, and sector rotation to identify high-conviction positions.

## Investment Thesis
Vietnam's stock market offers opportunities through:
- **Structural Growth**: Rising middle class, FDI inflows, infrastructure development
- **Sector Cycles**: Distinct rotation patterns across banking, real estate, industrials, and consumer sectors
- **Inefficiencies**: Less efficient than developed markets, creating alpha opportunities for systematic approaches
- **Foreign Flows**: Increasing foreign participation creates momentum and sentiment signals

## Strategy Components

### 1. Universe Selection
**Primary Markets**:
- **HOSE** (Ho Chi Minh Stock Exchange) - Large caps, more liquid
- **HNX** (Hanoi Stock Exchange) - Mid caps

**Liquidity Filters**:
- Minimum average daily trading value: VND 10-20 billion (~$400-800K USD)
- Minimum market cap: VND 1 trillion (~$40M USD)
- Exclude stocks with trading suspensions or regulatory issues

**Sector Coverage**:
- Banking & Financial Services
- Real Estate & Construction
- Manufacturing & Industrials
- Consumer Goods & Retail
- Technology & Telecommunications
- Energy & Utilities

### 2. Fundamental Screening (Stage 1)

**Value Metrics**:
- **P/E Ratio**: < 15 or bottom 30% of sector
- **P/B Ratio**: < 2.5 or bottom 40% of sector
- **Dividend Yield**: > 2% (optional, for income tilt)

**Quality Metrics**:
- **ROE**: > 12% (Vietnamese market average ~10-12%)
- **ROA**: > 5%
- **Debt/Equity**: < 2.0 (conservative for Vietnamese corporate leverage)
- **Current Ratio**: > 1.2

**Growth Metrics**:
- **Revenue Growth**: > 10% YoY (trailing 12 months)
- **Earnings Growth**: Positive YoY growth or recovery trend
- **Earnings Consistency**: No negative surprises in last 2 quarters

**Scoring System**:
```
Fundamental Score = 0.4 * Value_Score + 0.3 * Quality_Score + 0.3 * Growth_Score
- Top 50% of universe passes to ML stage
```

### 3. ML Prediction Layer (Stage 2)

**Option A: Gaussian Classifier for Direction (Simpler)**
Based on Example 15 in the repo:
- **Features**:
  - Technical: 20/50/200 MA ratios, RSI, MACD, ATR
  - Fundamental: ROE trend, earnings surprise, P/E change
  - Sentiment: Foreign flow (buy/sell ratio), volume spike
  - Macro: VN-Index momentum, sector relative strength
- **Target**: 3-month forward return (positive/negative classification)
- **Training**: Rolling 2-year window, retrain quarterly
- **Output**: Probability of positive return in next 3-6 months

**Option B: Regime Detection + Trend Scanning (More Sophisticated)**
Combine Examples 01 and 02:
- **Regime Detection**: Identify market regime (trending/mean-reverting/volatile)
- **Trend Scanning**: For each stock, determine if trending up/down or range-bound
- **Adaptive Strategy**:
  - In trending-up regime → favor momentum stocks
  - In mean-reverting regime → favor undervalued stocks
  - In volatile regime → reduce exposure, favor defensive sectors

**ML Score**:
```
ML_Score = Prediction_Probability * Model_Confidence
- Top 30-40 stocks proceed to portfolio construction
```

### 4. Sector Rotation Logic

**Sector Momentum Tracking**:
- Calculate 1-month and 3-month sector returns
- Identify top 3 performing sectors
- Overweight stocks from top-performing sectors (max 35% per sector)

**Defensive Rules**:
- Minimum 3 sectors represented in portfolio
- Maximum 40% in any single sector
- Financials cap at 30% (typically largest weight in VN market)

### 5. Portfolio Construction

**Position Sizing**:
```python
Base_Weight = 1 / N_Stocks  # Equal weight baseline
Adjusted_Weight = Base_Weight * (0.5 + 0.5 * Combined_Score)

Combined_Score = 0.4 * Fundamental_Score + 0.4 * ML_Score + 0.2 * Sector_Momentum_Score

# Constraints:
- Min position: 1.5%
- Max position: 8%
- Target: 15-25 stocks
```

**Rebalancing**:
- **Frequency**: Quarterly (aligned with earnings seasons)
- **Trigger-based rebalancing**:
  - If stock drops > 25% from entry → review fundamentals, ML score
  - If sector weight deviates > 10% from target → rebalance
- **Tax efficiency**: Vietnam has 0.1% securities transaction tax - factor into costs

### 6. Risk Management

**Stop Loss**:
- Hard stop: -20% from entry (trailing stop)
- ML-adaptive stop (Example 08): Use volatility + drawdown recovery model
  - For high volatility stocks: wider stops (up to -25%)
  - For low volatility stocks: tighter stops (-15%)

**Position Sizing Risk**:
- Portfolio volatility target: 18-22% annualized (VN-Index ~20-25%)
- Use inverse volatility weighting option for more conservative approach

**Drawdown Management**:
- If portfolio drawdown > 15% → reduce gross exposure by 25%
- If VN-Index drawdown > 20% (market correction) → shift to defensive sectors

**Hedging** (Optional for larger accounts):
- VN30 Index futures for systematic hedging
- Increase cash allocation during high volatility regimes

### 7. Performance Monitoring

**Benchmark**:
- VN-Index (primary)
- VN30 (large-cap benchmark)

**Target Metrics**:
- **Annual Return**: 15-25% (vs VN-Index 8-12% historical)
- **Sharpe Ratio**: > 0.8
- **Max Drawdown**: < 25%
- **Win Rate**: > 55%
- **Turnover**: 50-100% per quarter (3-6 month holds)

**Key Analytics**:
- Sector attribution analysis
- Factor exposure analysis (value, momentum, quality)
- ML model accuracy tracking
- Transaction cost analysis

## Implementation Considerations

### Data Requirements

**For QuantConnect Implementation**:
- Check if Vietnamese stock data available (HOSE/HNX tickers)
- May need custom data integration via `AddData()` API
- Fundamental data: Consider using FiinGroup, VND Direct, or SSI iBoard APIs

**For Local/Hybrid Implementation**:
- **Broker APIs**: VPS, SSI, VNDIRECT
- **Data Providers**:
  - FiinGroup (FiinPro) - Premium fundamental & technical data
  - VND Direct (DNSE API) - Market data
  - Cafef.vn / Vietstock - Free fundamental data (requires scraping)
- **News/Sentiment**: Vietnamese news sources, social media sentiment

### Technical Stack

**QuantConnect Version**:
```python
from AlgorithmImports import *
# Use QuantConnect's Equity, History, Universe Selection
# Implement custom fundamental data if needed
```

**Local/Hybrid Version**:
```python
import pandas as pd
import numpy as np
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import StandardScaler
import vnquant  # Vietnamese stock data library (if using)
# Or use broker APIs directly
```

### Backtesting Approach

**Historical Period**:
- Minimum 5 years (2019-2024) to capture full market cycle
- Include COVID crash (2020), recovery (2021), and correction (2022-2023)

**Walk-Forward Optimization**:
- Train on 2 years rolling window
- Test on next quarter
- Retrain every quarter

**Transaction Costs**:
- Brokerage: 0.15-0.35% per trade
- Securities tax: 0.1%
- Slippage: 0.1-0.3% (depends on liquidity)
- **Total**: ~0.4-0.8% round-trip

## Vietnamese Market-Specific Considerations

### Market Microstructure
- **Trading Hours**: 9:00-11:30 AM, 1:00-3:00 PM (Vietnam time, GMT+7)
- **Price Limits**: ±7% daily limit (±10% for less liquid stocks)
- **Settlement**: T+2

### Regulatory Environment
- **Foreign Ownership Limits**:
  - Most stocks: 49% foreign ownership cap
  - Some banks/strategic sectors: lower limits (20-30%)
  - Monitor Room (foreign ownership %) to avoid being locked out
- **Listing Requirements**: Different tiers affect liquidity
- **Index Rebalancing**: VN30 rebalances quarterly (can create opportunities)

### Seasonal Patterns
- **Tet (Lunar New Year)**: January/February - portfolio adjustment window, lower liquidity
- **Earnings Season**: Quarterly reports clustered around 15th of following month
- **Year-End**: Portfolio window dressing by institutions (November-December)

### Macro Factors to Monitor
- **USD/VND Exchange Rate**: Impacts foreign flows, exporters vs importers
- **Fed Policy**: Affects foreign capital flows into Vietnam
- **China Growth**: Vietnam's largest trading partner, supply chain dependencies
- **FDI Announcements**: Major driver of sector performance
- **Credit Growth Targets**: State Bank of Vietnam sets annual targets, impacts banks

## Next Steps for Implementation

1. **Data Sourcing**: Identify and set up data pipeline (QuantConnect vs local APIs)
2. **Backtest MVP**: Start with simplified version:
   - Fundamental screening only
   - Simple momentum overlay
   - Quarterly rebalancing
3. **Add ML Layer**: Implement Gaussian Classifier or regime detection
4. **Optimize**: Walk-forward optimization of parameters
5. **Paper Trade**: 1-2 quarters of paper trading to validate
6. **Live Deployment**: Start with smaller capital allocation, scale up

## Customization Options

**More Conservative**:
- Increase quality score weight (0.5 instead of 0.3)
- Focus on dividend-paying stocks
- Tighter stop losses
- More sector diversification

**More Aggressive**:
- Higher momentum weight
- Concentrated portfolio (10-15 stocks)
- Leverage sector rotation more heavily
- Add growth stock filters (reduce value tilt)

**Income-Focused**:
- Add dividend yield as primary filter (> 4%)
- Focus on utilities, banks, consumer staples
- Lower turnover strategy

---

**Version**: 1.0
**Last Updated**: 2025-11-09
**Target Investor**: Seasoned investors with Vietnamese market experience
**Holding Period**: 3-6 months
**Rebalancing**: Quarterly
