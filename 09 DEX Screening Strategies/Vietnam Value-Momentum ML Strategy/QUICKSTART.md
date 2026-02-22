# Quick Start Guide - Real Vietnamese Data Integration

This guide will help you get up and running with **REAL Vietnamese stock market data** in under 10 minutes!

## 🚀 Quick Installation

### Step 1: Install Dependencies

```bash
# Navigate to strategy directory
cd "09 DEX Screening Strategies/Vietnam Value-Momentum ML Strategy"

# Install required packages
pip install pandas numpy scikit-learn vnstock3

# Optional: For charts
pip install matplotlib
```

### Step 2: Test Data Connection

```bash
# Test that vnstock is working
python data_provider.py
```

This will:
- ✅ Connect to vnstock
- ✅ Fetch real HOSE stock listing
- ✅ Download real price data for VNM, VCB, HPG
- ✅ Get real fundamental data

**Expected output:**
```
Testing Vietnam Data Provider
✅ vnstock initialized successfully
Found 350+ stocks on HOSE
✅ Successfully fetched: 3/3 stocks
VNM: Latest close: 85,500 VND
```

### Step 3: Run Your First Backtest

```bash
# Run backtest with real data (this may take 5-10 minutes)
python standalone_strategy_real_data.py
```

This will:
1. Load real HOSE stocks
2. Download 2 years of price history
3. Fetch fundamental data
4. Train ML model
5. Simulate trading quarterly rebalancing
6. Generate performance report

**Expected output:**
```
RUNNING BACKTEST WITH REAL DATA
Period: 2023-01-01 to 2024-10-31
✅ Loaded 350 stocks from HOSE
✅ Loaded historical data for 280 stocks
✅ Loaded fundamentals for 250 stocks
✅ Model trained successfully!
   Training accuracy: 58.5%

📊 Performance Summary:
   Total Return:        18.5%
   Annual Return:       10.2%
   Sharpe Ratio:         0.85
   Max Drawdown:       -12.3%

💰 Final Portfolio: 1,185,000,000 VND
```

---

## 📊 Data Sources Explained

### Option 1: vnstock (FREE - Recommended for Learning)

**Pros:**
- ✅ Free and open source
- ✅ Easy to set up (no API key needed)
- ✅ Recently updated (November 2024)
- ✅ Good data quality for HOSE/HNX
- ✅ Includes fundamental data

**Cons:**
- ⚠️ Rate limits on requests
- ⚠️ May have occasional data gaps
- ⚠️ Not recommended for high-frequency trading

**Good for:**
- Learning and backtesting
- Research and analysis
- Personal investing (not institutional)

### Option 2: FiinGroup API (PREMIUM - For Serious Trading)

**Pros:**
- ✅ Professional-grade data
- ✅ Complete fundamental coverage
- ✅ Reliable and fast
- ✅ Corporate actions included
- ✅ Customer support

**Cons:**
- 💰 Requires paid subscription (~$100-500/month)
- 🔑 Need to contact FiinGroup for API access

**Good for:**
- Professional traders
- Institutional use
- Live trading systems

**How to get started:**
1. Visit https://fiingroup.vn/ApiDataFeed
2. Contact sales for API key
3. Set API key in code:
```python
strategy = VietnamStockStrategyRealData(
    data_source='fiingroup',
    api_key='YOUR_API_KEY_HERE'
)
```

---

## 📝 Example Usage Patterns

### Pattern 1: Quick Test (3 stocks, 1 year)

```python
from standalone_strategy_real_data import VietnamStockStrategyRealData
from datetime import datetime

# Initialize
strategy = VietnamStockStrategyRealData(
    initial_capital=100_000_000,  # 100M VND
    target_stocks=3,
    data_source='vnstock'
)

# Run quick backtest
results = strategy.run_backtest(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 10, 31),
    universe=['VNM', 'VCB', 'HPG']  # Specific stocks
)
```

**Runtime:** ~1 minute

### Pattern 2: Full HOSE Backtest (All stocks, 2 years)

```python
strategy = VietnamStockStrategyRealData(
    initial_capital=1_000_000_000,  # 1B VND
    target_stocks=20,
    data_source='vnstock'
)

results = strategy.run_backtest(
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2024, 10, 31)
)

strategy.save_results(results, 'full_backtest.csv')
```

**Runtime:** ~10-15 minutes

### Pattern 3: Custom Stock Selection

```python
# Define your own universe
tech_consumer_stocks = [
    'FPT', 'CMG', 'VNM', 'MSN', 'MWG',
    'PNJ', 'SAB', 'VJC', 'VRE', 'VIC'
]

strategy = VietnamStockStrategyRealData(
    initial_capital=500_000_000,
    target_stocks=5,
    data_source='vnstock'
)

results = strategy.run_backtest(
    start_date=datetime(2023, 6, 1),
    end_date=datetime(2024, 10, 31),
    universe=tech_consumer_stocks
)
```

**Runtime:** ~2-3 minutes

### Pattern 4: Conservative Settings

```python
# More risk-averse parameters
strategy = VietnamStockStrategyRealData(
    initial_capital=1_000_000_000,
    target_stocks=25,  # More diversification
    rebalance_frequency_days=180,  # Less frequent trading
    transaction_cost=0.005  # Higher cost buffer
)

# Update screener for higher quality
strategy.fundamental_screener.min_roe = 0.15  # Higher quality
strategy.fundamental_screener.min_div_yield = 0.03  # Require dividends

results = strategy.run_backtest(
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2024, 10, 31)
)
```

---

## 🔧 Troubleshooting

### Issue 1: "vnstock not installed"

```bash
# Solution: Install vnstock3
pip install vnstock3

# If that fails, try:
pip install --upgrade pip
pip install vnstock3
```

### Issue 2: "Failed to fetch listing from vnstock"

This can happen due to:
- Network issues
- vnstock API changes
- Rate limiting

**Solution:**
```python
# The data provider will automatically fallback to default stocks
# Or specify your own universe:
strategy.run_backtest(
    ...,
    universe=['VNM', 'VCB', 'HPG', 'VIC', 'FPT', 'MSN']
)
```

### Issue 3: "Insufficient training samples"

This happens when:
- Not enough historical data
- Too many stocks with missing data

**Solutions:**
1. Use longer backtest period:
```python
start_date = datetime(2022, 1, 1)  # 3 years instead of 2
```

2. Use fewer, more liquid stocks:
```python
universe = ['VNM', 'VCB', 'VIC', 'HPG', 'FPT']  # Blue chips
```

3. Lower minimum samples:
```python
strategy.ml_predictor.min_samples = 50  # Default is 100
```

### Issue 4: Slow performance

**Solutions:**
1. Enable caching (already enabled by default)
2. Reduce universe size:
```python
# Instead of all HOSE stocks (~350), use top 50
strategy.load_universe('HOSE', min_market_cap=10_000_000_000_000)
```

3. Use shorter backtest period
4. Reduce rebalancing frequency

### Issue 5: Data quality issues

Some stocks may have missing/bad data. The strategy handles this gracefully:
- Stocks with insufficient data are automatically skipped
- Missing fundamental values use defaults
- Price gaps are handled in feature calculation

To see which stocks were skipped:
```python
# Check loaded vs passed screening
print(f"Loaded data: {len(strategy.historical_data)} stocks")
print(f"Has fundamentals: {len(strategy.fundamentals_data)} stocks")
```

---

## 🎯 Next Steps After Your First Backtest

### 1. Analyze Results

```bash
# Open the CSV file
open backtest_results.csv

# Or in Python:
import pandas as pd
results = pd.read_csv('vietnam_backtest_real_data.csv')
print(results[['date', 'portfolio_value', 'return']].tail(20))
```

### 2. Experiment with Parameters

Try different configurations:

```python
# More aggressive
strategy = VietnamStockStrategyRealData(
    target_stocks=15,  # More concentrated
    rebalance_frequency_days=60  # More frequent
)
strategy.fundamental_screener.min_roe = 0.10  # Lower bar
strategy.portfolio_manager.fundamental_weight = 0.3  # Less fundamental
strategy.portfolio_manager.ml_weight = 0.5  # More ML

# Run backtest and compare results
```

### 3. Validate on Different Time Periods

```python
# Test in different market conditions
bear_market = (datetime(2022, 1, 1), datetime(2022, 12, 31))
bull_market = (datetime(2023, 1, 1), datetime(2023, 12, 31))
recent = (datetime(2024, 1, 1), datetime(2024, 10, 31))

for period_name, (start, end) in [('Bear', bear_market), ('Bull', bull_market), ('Recent', recent)]:
    print(f"\n{period_name} Market:")
    results = strategy.run_backtest(start, end)
```

### 4. Compare to Benchmark

```python
from data_provider import VietnamDataProvider

# Get VN-Index data
provider = VietnamDataProvider(data_source='vnstock')
vnindex = provider.get_market_index('VNINDEX', start_date='2023-01-01', end_date='2024-10-31')

# Calculate VN-Index return
vnindex_return = (vnindex['close'].iloc[-1] / vnindex['close'].iloc[0] - 1) * 100
print(f"VN-Index return: {vnindex_return:.2f}%")
print(f"Strategy return: {results['return'].iloc[-1]:.2f}%")
print(f"Outperformance: {results['return'].iloc[-1] - vnindex_return:.2f}%")
```

### 5. Start Paper Trading

Once you're satisfied with backtest results:

1. Open a paper trading account with a Vietnamese broker
2. Run the strategy live (but without real money)
3. Track performance for 1-2 quarters
4. Compare paper trading to backtest expectations

---

## 📚 Learning Resources

### Understanding the Strategy
- Read `STRATEGY_DESIGN.md` for full methodology
- Review `fundamental_screener.py` to see screening logic
- Examine `ml_predictor.py` to understand ML features

### Vietnamese Market Knowledge
- Learn about HOSE/HNX exchanges
- Understand foreign ownership limits (49% cap)
- Study sector dynamics (banking, real estate, industrials)
- Follow Tet (Lunar New Year) seasonal patterns

### Data Analysis
- Use `example_usage.py` for standalone component testing
- Modify parameters and observe effects
- Analyze which stocks are selected and why

---

## ⚡ Pro Tips

1. **Start Small**: Test with 5-10 stocks first, then expand
2. **Use Cache**: Data provider caches automatically - second runs are much faster
3. **Check Data Quality**: Not all Vietnamese stocks have complete data
4. **Monitor Costs**: 0.4% round-trip cost adds up with frequent trading
5. **Seasonal Patterns**: Avoid rebalancing right before Tet holiday
6. **Liquidity First**: Focus on top 50-100 most liquid stocks initially
7. **Version Control**: Save your parameter variations and results

---

## 🤝 Getting Help

**Issues with data:**
- vnstock GitHub: https://github.com/thinh-vu/vnstock
- Create an issue if data fetching fails

**Issues with strategy:**
- Review code comments in each module
- Check `STRATEGY_DESIGN.md` for methodology details
- Try the examples in `example_usage.py`

**Vietnamese market questions:**
- https://www.hsx.vn (HOSE exchange)
- https://www.hnx.vn (HNX exchange)
- https://www.ssi.com.vn (SSI broker research)

---

## ✅ Checklist

Before running your first backtest:
- [ ] Installed: `pip install pandas numpy scikit-learn vnstock3`
- [ ] Tested data connection: `python data_provider.py`
- [ ] Reviewed Vietnamese stock symbols (VNM, VCB, HPG, etc.)
- [ ] Understood backtest will take 5-15 minutes for full HOSE
- [ ] Prepared to analyze results in CSV file

After your first backtest:
- [ ] Reviewed performance metrics (return, Sharpe, drawdown)
- [ ] Compared to VN-Index benchmark
- [ ] Identified top selected stocks
- [ ] Understood why certain stocks were chosen
- [ ] Experimented with parameter variations

Ready to go live:
- [ ] Completed multiple backtests on different periods
- [ ] Results meet expectations (> 10% annual return, < 25% drawdown)
- [ ] Tested with paper trading for 1-2 quarters
- [ ] Comfortable with Vietnamese market dynamics
- [ ] Chosen broker and set up API integration

---

**Good luck with your Vietnamese stock investing journey! 🇻🇳📈**

*Remember: Past performance doesn't guarantee future results. Always test thoroughly before risking real capital.*
