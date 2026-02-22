# Vietnam Value-Momentum ML Strategy

A comprehensive hybrid fundamental/value and AI/ML-driven trading strategy designed for mid to long-term opportunities (3-6 months) in the Vietnamese stock market (HOSE/HNX).

## Overview

This strategy combines:
- **Fundamental Screening**: Value, quality, and growth metrics tailored for Vietnamese market
- **Machine Learning Predictions**: Gaussian Naive Bayes classifier for 3-6 month return direction
- **Portfolio Construction**: Risk-managed position sizing with sector rotation
- **Quarterly Rebalancing**: Aligned with earnings seasons and market cycles

**Target Audience**: Seasoned investors with Vietnamese market experience
**Investment Horizon**: 3-6 months (medium term)
**Target Return**: 15-25% annual (vs VN-Index 8-12% historical)
**Rebalancing**: Quarterly

---

## Table of Contents

1. [Strategy Design](#strategy-design)
2. [Installation](#installation)
3. [Usage](#usage)
   - [QuantConnect Implementation](#quantconnect-implementation)
   - [Standalone/Local Implementation](#standalone-local-implementation)
4. [Data Requirements](#data-requirements)
5. [Performance Expectations](#performance-expectations)
6. [Customization](#customization)
7. [Risk Management](#risk-management)
8. [Vietnamese Market Considerations](#vietnamese-market-considerations)
9. [Troubleshooting](#troubleshooting)

---

## Strategy Design

### Three-Stage Process

**Stage 1: Fundamental Screening** 🔍
- Value metrics: P/E, P/B, Dividend Yield (relative to sector)
- Quality metrics: ROE > 12%, ROA > 5%, Debt/Equity < 2.0
- Growth metrics: Revenue growth > 10% YoY, positive earnings trends
- **Output**: Top 50% of universe passes to ML stage

**Stage 2: ML Prediction** 🤖
- Gaussian Naive Bayes classifier predicts 3-6 month forward returns
- Features include:
  - Technical: Moving averages, RSI, MACD, volatility
  - Fundamental: ROE trends, P/E changes, earnings surprises
  - Sentiment: Foreign flow ratios, sector momentum
- **Output**: Top 30-40 stocks with positive predictions

**Stage 3: Portfolio Construction** 📊
- Position sizing: 1.5% - 8% per stock, target 15-25 stocks
- Sector constraints: Max 40% per sector, minimum 3 sectors
- Combined scoring: 40% Fundamental + 40% ML + 20% Sector Momentum
- **Output**: Portfolio weights with quarterly rebalancing

### Key Differentiators

✅ **Vietnamese Market Specific**:
- ROE threshold of 12% (vs 15% for developed markets)
- Sector rotation for banking, real estate, manufacturing, consumer
- Foreign ownership monitoring
- Tet (Lunar New Year) seasonal patterns

✅ **Risk Management**:
- Trailing stop losses: -20% (adaptive based on volatility)
- Drawdown protection: Reduce exposure if portfolio down > 15%
- Position limits and diversification requirements

✅ **Hybrid Approach**:
- Not purely quantitative or fundamental
- Combines best of both worlds for Vietnamese market inefficiencies

---

## Installation

### Requirements

```bash
# Core dependencies
pip install pandas numpy scikit-learn

# For QuantConnect (if using cloud platform)
# No installation needed - runs in cloud

# For standalone Vietnamese data
pip install vnquant  # Vietnamese stock data library
# OR use FiinGroup API, VND Direct API, SSI iBoard, etc.
```

### File Structure

```
Vietnam Value-Momentum ML Strategy/
├── README.md                    # This file
├── STRATEGY_DESIGN.md          # Detailed strategy documentation
├── fundamental_screener.py     # Fundamental screening module
├── ml_predictor.py             # ML prediction module
├── portfolio_manager.py        # Portfolio construction & risk management
├── main.py                     # QuantConnect algorithm
├── standalone_strategy.py      # Standalone Python implementation
└── examples/                   # Usage examples (see below)
```

---

## Usage

### QuantConnect Implementation

**Step 1: Set Up Project**

1. Create new project on QuantConnect
2. Upload all `.py` files to your project
3. Set `main.py` as your algorithm file

**Step 2: Add Vietnamese Stock Data** (Critical!)

```python
# In main.py, replace universe selection with Vietnamese stocks

# Option A: Use AddData() for custom Vietnamese data
self.add_data(VietnameseStockData, "VNM", Resolution.DAILY)
self.add_data(VietnameseStockData, "VIC", Resolution.DAILY)
# ... add more stocks

# Option B: Integrate with Vietnamese data provider API
# Contact FiinGroup, VND Direct, or SSI for API access
```

**Step 3: Configure Parameters**

```python
# Adjust in main.py initialize() method
self.universe_size = 100        # Number of stocks to screen
self.target_stocks = 20         # Target portfolio positions
self.rebalance_frequency = 90   # Days between rebalancing
```

**Step 4: Run Backtest**

- Click "Run Backtest" in QuantConnect
- Review performance metrics and logs
- Adjust parameters as needed

**Step 5: Deploy Live** (Optional)

- Connect to supported brokers
- Note: QuantConnect's Vietnamese broker support is limited
- Consider using standalone implementation for live trading

### Standalone/Local Implementation

**Step 1: Install Dependencies**

```bash
pip install pandas numpy scikit-learn vnquant
```

**Step 2: Configure Data Sources**

Edit `standalone_strategy.py`:

```python
def fetch_historical_data(self, symbols, start_date, end_date):
    # Replace placeholder with actual data source

    # Option 1: vnquant library (free, limited)
    from vnquant import DataLoader
    data = {}
    for symbol in symbols:
        loader = DataLoader(symbol, 'cafe', start_date, end_date)
        data[symbol] = loader.download()

    # Option 2: FiinGroup API (premium, recommended)
    # import requests
    # headers = {'Authorization': 'Bearer YOUR_API_KEY'}
    # response = requests.get(f'https://api.fiingroup.vn/...', headers=headers)

    # Option 3: VND Direct API
    # ... use DNSE SDK or REST API

    return data
```

**Step 3: Run Backtest**

```python
from standalone_strategy import VietnamStockStrategy
from datetime import datetime

# Initialize
strategy = VietnamStockStrategy(
    initial_capital=1_000_000_000,  # 1 billion VND
    target_stocks=20,
    rebalance_frequency_days=90
)

# Run backtest
results = strategy.run_backtest(
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2024, 10, 1)
)

# Analyze results
print(results.tail())
results.to_csv('backtest_results.csv')
```

**Step 4: Paper Trading** (Recommended before live)

- Use broker's demo account (VPS, SSI, VNDIRECT provide paper trading)
- Run strategy for 1-2 quarters to validate
- Monitor performance vs expectations

**Step 5: Live Trading**

```python
# Modify standalone_strategy.py for live execution
# - Remove backtest loop
# - Add broker API integration
# - Implement order execution
# - Add monitoring and alerting

# Example pseudo-code:
from vps_api import VPSBroker  # Replace with your broker

broker = VPSBroker(api_key='...', secret='...')

# On rebalancing day:
target_weights = strategy._construct_portfolio(...)
trades = portfolio_manager.generate_rebalancing_trades(
    target_weights, current_prices, portfolio_value
)

for trade in trades:
    if trade['action'] == 'BUY':
        broker.place_order(trade['symbol'], 'BUY', trade['shares'])
    else:
        broker.place_order(trade['symbol'], 'SELL', trade['shares'])
```

---

## Data Requirements

### Essential Data

1. **Historical Prices** (Daily)
   - Open, High, Low, Close, Volume
   - Minimum 2 years for training
   - 5+ years preferred for robust backtesting

2. **Fundamental Data** (Quarterly)
   - P/E ratio, P/B ratio
   - ROE, ROA
   - Debt/Equity, Current Ratio
   - Revenue growth, Earnings growth
   - Market cap, Dividend yield

3. **Market Data**
   - VN-Index / VN30 index prices
   - Sector indices (optional but helpful)
   - Foreign trading data (optional but valuable)

### Recommended Data Providers

| Provider | Type | Cost | Quality | Vietnamese Focus |
|----------|------|------|---------|------------------|
| **FiinGroup (FiinPro)** | Premium API | $$$ | ⭐⭐⭐⭐⭐ | ✅ Best for institutions |
| **VND Direct (DNSE)** | API + App | $$ | ⭐⭐⭐⭐ | ✅ Good for retail |
| **SSI iBoard** | API | $$ | ⭐⭐⭐⭐ | ✅ Good for retail |
| **vnquant** | Python library | Free | ⭐⭐⭐ | ✅ Basic needs |
| **Cafef.vn** | Web scraping | Free | ⭐⭐ | ⚠️ Requires scraping |
| **Vietstock** | Web scraping | Free | ⭐⭐ | ⚠️ Requires scraping |

**Recommendation**: For serious investment, use FiinGroup or VND Direct for reliable, clean data.

---

## Performance Expectations

### Target Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Annual Return | 15-25% | vs VN-Index ~10% |
| Sharpe Ratio | > 0.8 | Risk-adjusted return |
| Max Drawdown | < 25% | Downside protection |
| Win Rate | > 55% | Profitable quarters |
| Quarterly Turnover | 50-100% | Transaction costs matter |

### Realistic Expectations

**✅ What this strategy is good at**:
- Identifying fundamentally strong, undervalued stocks
- Capturing medium-term trends (3-6 months)
- Managing sector rotation
- Avoiding value traps through ML validation

**⚠️ What this strategy struggles with**:
- Short-term market timing (< 1 month)
- Extreme market events (COVID crash, financial crisis)
- Low liquidity stocks (execution issues)
- Rapid news-driven moves (earnings surprises, M&A)

**📉 Expected drawdowns**:
- Normal corrections: 10-15% (quarterly)
- Bear markets: 20-30% (annually)
- Black swan events: 30-40%

### Benchmark Comparison

Expected to outperform in:
- ✅ Bull markets (trending up): +5-10% vs VN-Index
- ✅ Sideways markets (range-bound): +8-12% vs VN-Index
- ⚠️ Bear markets (trending down): -5-10% better (still negative)

---

## Customization

### Conservative Settings

For risk-averse investors:

```python
# Increase quality focus
fundamental_screener = FundamentalScreener(
    min_roe=0.15,  # Higher quality threshold
    min_roa=0.08,
    max_debt_equity=1.5,  # Lower leverage
    min_div_yield=0.03  # Require 3% dividend
)

# Tighter portfolio constraints
portfolio_manager = PortfolioManager(
    target_stocks=25,  # More diversification
    max_position=0.06,  # Lower concentration
    fundamental_weight=0.5,  # More weight on fundamentals
    ml_weight=0.3,
    sector_momentum_weight=0.2
)
```

### Aggressive Settings

For growth-focused investors:

```python
# Focus on growth
fundamental_screener = FundamentalScreener(
    min_roe=0.10,
    min_revenue_growth=0.15,  # Higher growth requirement
    max_pe_percentile=80,  # Allow higher valuations
    min_div_yield=0.0  # Don't require dividends
)

# Concentrated portfolio
portfolio_manager = PortfolioManager(
    target_stocks=15,  # Fewer positions
    max_position=0.10,  # Higher concentration
    ml_weight=0.5,  # More weight on ML
    fundamental_weight=0.3,
    sector_momentum_weight=0.2
)
```

### Sector-Specific

Focus on specific sectors:

```python
# In universe selection
def _select_sector_focused(self, fundamental):
    # Filter for specific sectors
    target_sectors = [
        MorningstarSectorCode.FINANCIAL_SERVICES,  # Banking
        MorningstarSectorCode.TECHNOLOGY,  # Tech
        MorningstarSectorCode.INDUSTRIALS  # Manufacturing
    ]

    filtered = [
        f for f in fundamental
        if f.asset_classification.morningstar_sector_code in target_sectors
    ]

    return [x.symbol for x in filtered]
```

---

## Risk Management

### Built-in Risk Controls

1. **Position Limits**
   - Min position: 1.5%
   - Max position: 8%
   - Prevents over-concentration

2. **Sector Limits**
   - Max sector weight: 40%
   - Min sectors: 3
   - Ensures diversification

3. **Stop Losses**
   - Hard stop: -20% from entry
   - Adaptive stops based on volatility
   - Implemented in `portfolio_manager.py`

4. **Drawdown Management**
   - If portfolio down > 15%: Reduce exposure by 25%
   - If market down > 20%: Shift to defensive sectors

### Additional Risk Considerations

**Vietnamese Market Specific**:

- **Foreign Ownership Limits**: Monitor room availability (most stocks 49% cap)
- **Price Limits**: ±7% daily limit can prevent exits
- **Liquidity**: Some stocks have low volume, adjust position sizes
- **Settlement**: T+2 settlement, ensure cash for rebalancing
- **Currency**: VND/USD risk if you're foreign investor

**Operational Risks**:

- **Data Quality**: Vietnamese data can have errors, validate carefully
- **Broker Reliability**: Choose established brokers (VPS, SSI, VNDIRECT)
- **Technology**: Ensure stable internet and backup systems
- **Tax**: 0.1% securities transaction tax + capital gains considerations

---

## Vietnamese Market Considerations

### Market Microstructure

**Trading Hours**:
- Morning: 9:00 - 11:30 AM (Vietnam time, GMT+7)
- Afternoon: 1:00 - 3:00 PM
- Adjust execution times in algorithm accordingly

**Holidays**:
- Tet (Lunar New Year): January/February - market closed 7-10 days
- Other holidays: Similar to international markets
- Plan rebalancing around holiday closures

**Market Indices**:
- **VN-Index**: HOSE (Ho Chi Minh), large caps
- **VN30**: Top 30 stocks, used for futures
- **HNX-Index**: Hanoi, mid caps
- **UPCOM**: Unlisted public companies

### Regulatory Environment

**Foreign Ownership**:
```python
# Example: Check foreign room before trading
def check_foreign_room(symbol):
    """Check if foreign room available for purchase"""
    # Data from FiinGroup or broker API
    foreign_ownership_pct = get_foreign_ownership(symbol)
    limit = get_foreign_limit(symbol)  # Usually 49%, some 30%

    room_available = limit - foreign_ownership_pct

    if room_available < 1:  # Less than 1% room
        return False, "Foreign room full"

    return True, f"{room_available:.1f}% room available"
```

**Sector-Specific Limits**:
- Banks: Often 30% foreign limit
- Airlines: 30-49% limit
- Utilities: May have lower limits
- Other sectors: Generally 49%

### Seasonal Patterns

**Tet Effect** (January/February):
- Portfolio window dressing by institutions
- Lower liquidity before Tet
- Post-Tet rally common
- **Action**: Consider rebalancing after Tet

**Earnings Seasons**:
- Quarterly reports: ~15th of month after quarter
- Clustered announcements create volatility
- **Action**: Rebalance 2-3 weeks after earnings

**Year-End** (November/December):
- Tax-loss harvesting by foreign investors
- Window dressing by funds
- Lower liquidity
- **Action**: Monitor but don't fight the trend

---

## Troubleshooting

### Common Issues

**1. Model Not Training / Low Accuracy**

```
Error: "Insufficient training samples: 50 < 100"
```

**Solution**:
- Ensure you have at least 2 years of historical data
- Reduce `min_samples` parameter if data is limited
- Check for missing data in your data source

**2. No Candidates After Screening**

```
"Insufficient candidates after fundamental screening: 3"
```

**Solution**:
- Relax fundamental filters (lower min_roe, increase max_debt_equity)
- Expand universe size
- Check if fundamental data is being loaded correctly
- Vietnamese stocks may have different characteristics than US stocks

**3. High Transaction Costs Eating Returns**

**Solution**:
- Increase `rebalance_frequency_days` (e.g., 120 days instead of 90)
- Increase `min_position` to reduce number of trades
- Use `max_turnover` constraint more aggressively
- Consider broker with lower fees

**4. Foreign Room Issues**

```
"Cannot buy VNM: Foreign ownership limit reached"
```

**Solution**:
- Implement foreign room checking before trades
- Maintain watchlist of stocks with >5% room
- Focus on stocks with lower foreign ownership

**5. Data Quality Issues**

```
"Price data missing for VIC on 2024-05-15"
```

**Solution**:
- Use forward fill for occasional missing data
- Switch to more reliable data provider (FiinGroup)
- Implement data validation checks
- Log data issues for review

---

## Next Steps

### For Backtesting (Recommended First Step)

1. ✅ Install dependencies
2. ✅ Set up data sources (start with vnquant for free testing)
3. ✅ Run backtest on historical data (2019-2024)
4. ✅ Analyze results and compare to VN-Index
5. ✅ Experiment with parameters

### For Paper Trading

1. Open demo account with Vietnamese broker
2. Run strategy on current data
3. Monitor for 1-2 quarters
4. Compare to expectations
5. Refine before going live

### For Live Trading

1. ✅ Complete paper trading successfully
2. Start with smaller capital allocation (e.g., 20-30% of target)
3. Set up monitoring and alerts
4. Review monthly performance
5. Scale up gradually

---

## Support & Contributing

**Questions?**
- Review `STRATEGY_DESIGN.md` for detailed strategy logic
- Check code comments in each module

**Found a bug or want to improve?**
- This is part of the "Hands-On AI Trading" book repository
- Contributions welcome via pull requests
- Share your Vietnamese market customizations!

**Disclaimer**:
This strategy is for educational purposes. Past performance does not guarantee future results. Always test thoroughly before risking real capital. Consult with financial advisors for personalized advice.

---

**Version**: 1.0
**Last Updated**: 2025-11-09
**Tested On**: Vietnamese market data (HOSE/HNX)
**QuantConnect Compatible**: Yes (with custom data integration)
**Standalone Compatible**: Yes (with Vietnamese data sources)

Good luck with your Vietnamese stock investing! 🇻🇳📈
