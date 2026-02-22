# Setup Guide - Real Vietnamese Data Integration

## 🚀 Quick Setup (5 minutes)

### Step 1: Install Dependencies

Choose **ONE** of the following methods:

#### Method A: Using pip (Recommended)
```bash
cd "09 DEX Screening Strategies/Vietnam Value-Momentum ML Strategy"

pip install pandas numpy scikit-learn vnstock3

# Optional: For charts
pip install matplotlib
```

#### Method B: Using requirements.txt
```bash
cd "09 DEX Screening Strategies/Vietnam Value-Momentum ML Strategy"

pip install -r requirements.txt
```

#### Method C: Using install script (Mac/Linux)
```bash
cd "09 DEX Screening Strategies/Vietnam Value-Momentum ML Strategy"

./install.sh
```

### Step 2: Verify Installation

```bash
python3 test_real_data.py
```

This will run 5 tests:
1. ✅ Module imports
2. ✅ vnstock3 installation
3. ✅ Real data fetching
4. ✅ Strategy components
5. ✅ Mini backtest

**Expected output:**
```
🎉 ALL TESTS PASSED!
You're ready to run full backtests!
```

### Step 3: Run Your First Backtest

```bash
python3 standalone_strategy_real_data.py
```

This will:
- Load real HOSE stocks
- Download historical data from vnstock
- Train ML model
- Simulate quarterly rebalancing
- Generate performance report

**Time:** 5-10 minutes for full HOSE backtest

---

## 📋 Detailed Installation

### Prerequisites

- **Python**: 3.7 or higher
- **Internet**: For downloading data from vnstock
- **Disk space**: ~500 MB for data cache

Check Python version:
```bash
python3 --version
# Should show: Python 3.7.x or higher
```

### Package Details

| Package | Version | Purpose |
|---------|---------|---------|
| pandas | ≥1.3.0 | Data manipulation |
| numpy | ≥1.21.0 | Numerical computations |
| scikit-learn | ≥0.24.0 | Machine learning |
| vnstock3 | latest | Vietnamese stock data |
| matplotlib | ≥3.3.0 | Charts (optional) |

### Troubleshooting Installation

#### Issue: "No module named 'vnstock3'"

**Solution:**
```bash
pip install vnstock3

# If that fails:
pip install --upgrade pip
pip install vnstock3

# If still fails:
pip install git+https://github.com/thinh-vu/vnstock.git@main
```

#### Issue: "No module named 'sklearn'"

**Solution:**
```bash
pip install scikit-learn

# NOT: pip install sklearn (old package name)
```

#### Issue: Permission denied

**Solution:**
```bash
# Use --user flag
pip install --user pandas numpy scikit-learn vnstock3

# Or use sudo (not recommended)
sudo pip install pandas numpy scikit-learn vnstock3
```

#### Issue: "pip: command not found"

**Solution:**
```bash
# Try pip3 instead
pip3 install pandas numpy scikit-learn vnstock3

# Or use python -m pip
python3 -m pip install pandas numpy scikit-learn vnstock3
```

---

## 🔍 Verification

### Check Package Versions

```python
import pandas as pd
import numpy as np
import sklearn
import vnstock3

print(f"pandas: {pd.__version__}")
print(f"numpy: {np.__version__}")
print(f"scikit-learn: {sklearn.__version__}")
print(f"vnstock3: installed ✓")
```

### Test Data Connection

```python
from vnstock3 import Vnstock

vnstock = Vnstock()
stock = vnstock.stock(symbol='VNM', source='VCI')

# Get recent data
df = stock.quote.history(start='2024-10-01', end='2024-10-31')

print(f"Downloaded {len(df)} days of data for VNM")
print(f"Latest close: {df['close'].iloc[-1]:,.0f} VND")
```

**Expected output:**
```
Downloaded 22 days of data for VNM
Latest close: 85,500 VND
```

---

## 📁 File Structure

After setup, you should have:

```
Vietnam Value-Momentum ML Strategy/
├── README.md                          # Full documentation
├── SETUP.md                           # This file
├── QUICKSTART.md                      # Quick start guide
├── STRATEGY_DESIGN.md                 # Strategy methodology
│
├── requirements.txt                   # Package dependencies
├── install.sh                         # Installation script
│
├── data_provider.py                   # ⭐ Data integration
├── fundamental_screener.py            # Fundamental analysis
├── ml_predictor.py                    # ML predictions
├── portfolio_manager.py               # Portfolio construction
│
├── standalone_strategy_real_data.py   # ⭐ Main strategy (REAL DATA)
├── main.py                            # QuantConnect version
│
├── test_real_data.py                  # ⭐ Test script
├── example_usage.py                   # Usage examples
│
└── data_cache/                        # Created automatically
    └── (cached data files)
```

---

## 🎯 Next Steps

### For First-Time Users

1. **Read the Quick Start:**
   ```bash
   cat QUICKSTART.md
   ```

2. **Run tests:**
   ```bash
   python3 test_real_data.py
   ```

3. **Run mini backtest** (3 stocks, fast):
   ```python
   from standalone_strategy_real_data import VietnamStockStrategyRealData
   from datetime import datetime

   strategy = VietnamStockStrategyRealData(
       initial_capital=100_000_000,
       target_stocks=3
   )

   results = strategy.run_backtest(
       datetime(2024, 6, 1),
       datetime(2024, 10, 31),
       universe=['VNM', 'VCB', 'HPG']
   )
   ```

4. **Analyze results:**
   ```bash
   open vietnam_backtest_real_data.csv
   ```

### For Advanced Users

1. **Review strategy design:**
   ```bash
   cat STRATEGY_DESIGN.md
   ```

2. **Customize parameters:**
   - Edit `standalone_strategy_real_data.py`
   - Adjust screening thresholds in `fundamental_screener.py`
   - Modify ML features in `ml_predictor.py`

3. **Integrate with broker:**
   - Study broker API documentation
   - Implement order execution in strategy
   - Add monitoring and alerts

---

## 🌐 Data Sources

### vnstock (Free - Currently Using)

**Coverage:**
- ✅ HOSE stocks (350+)
- ✅ HNX stocks (400+)
- ✅ Historical prices (OHLCV)
- ✅ Company fundamentals
- ✅ Financial ratios
- ✅ Market indices (VN-Index, VN30, etc.)

**Limitations:**
- ⚠️ Rate limits (avoid making 100s of requests/minute)
- ⚠️ Occasional data gaps
- ⚠️ May be delayed 15 minutes (not real-time)

**Good for:**
- Learning and backtesting
- Research and analysis
- Personal investing

### FiinGroup API (Premium - Optional Upgrade)

**To setup:**
1. Visit https://fiingroup.vn/ApiDataFeed
2. Contact sales: sales@fiingroup.vn
3. Get API credentials
4. Update code:
   ```python
   strategy = VietnamStockStrategyRealData(
       data_source='fiingroup',
       api_key='YOUR_API_KEY'
   )
   ```

**Benefits:**
- ✅ Professional-grade data
- ✅ Real-time or minimal delay
- ✅ Complete corporate actions
- ✅ No rate limits
- ✅ Customer support

**Cost:** ~$100-500/month (contact for quote)

---

## 📞 Support

### Common Issues

| Issue | Solution |
|-------|----------|
| vnstock not installed | `pip install vnstock3` |
| No data returned | Check internet connection, try again in 1 minute |
| Slow backtest | Normal for 300+ stocks, use fewer stocks or enable caching |
| Permission errors | Use `pip install --user` or virtual environment |

### Getting Help

**Data issues:**
- vnstock GitHub: https://github.com/thinh-vu/vnstock
- Create issue if data fetching consistently fails

**Strategy questions:**
- Review `STRATEGY_DESIGN.md`
- Check `example_usage.py`
- Read code comments

**Vietnamese market:**
- HOSE: https://www.hsx.vn
- HNX: https://www.hnx.vn
- SSI Research: https://www.ssi.com.vn

---

## ✅ Setup Checklist

Before first backtest:
- [ ] Python 3.7+ installed
- [ ] All packages installed (`pip install -r requirements.txt`)
- [ ] Test script passes (`python3 test_real_data.py`)
- [ ] Can fetch real data (check data_provider.py test output)
- [ ] Understand strategy methodology (read STRATEGY_DESIGN.md)

After first backtest:
- [ ] Results generated successfully
- [ ] CSV file created with portfolio values
- [ ] Performance metrics calculated
- [ ] Compared to VN-Index benchmark
- [ ] Understand which stocks were selected

Ready for customization:
- [ ] Know how to adjust screening parameters
- [ ] Can modify ML features
- [ ] Understand portfolio construction logic
- [ ] Can interpret backtest results

---

## 🎓 Learning Path

### Week 1: Setup & Understanding
- [ ] Complete setup
- [ ] Run test script
- [ ] Run mini backtest (3 stocks)
- [ ] Read STRATEGY_DESIGN.md
- [ ] Review selected stocks

### Week 2: Experimentation
- [ ] Run full HOSE backtest
- [ ] Try different time periods
- [ ] Adjust parameters (conservative vs aggressive)
- [ ] Compare to VN-Index benchmark
- [ ] Analyze why certain stocks selected

### Week 3: Customization
- [ ] Modify fundamental filters
- [ ] Experiment with ML features
- [ ] Test different rebalancing frequencies
- [ ] Create sector-focused versions
- [ ] Document your findings

### Week 4: Validation
- [ ] Walk-forward testing on multiple periods
- [ ] Compare different parameter sets
- [ ] Analyze drawdowns and risk metrics
- [ ] Prepare for paper trading

---

**You're all set! Start with the test script to verify everything works:**

```bash
python3 test_real_data.py
```

**Good luck with your Vietnamese stock investing! 🇻🇳📈**
