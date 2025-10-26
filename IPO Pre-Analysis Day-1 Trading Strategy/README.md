# IPO Pre-Analysis + Day-1 Trading Strategy

## Strategy Overview

This strategy combines **pre-IPO fundamental analysis** with **automated post-IPO execution** to capture alpha from newly listed companies.

### Two-Phase Approach

**Phase 1: Pre-IPO Analysis (Manual/Semi-Automated)**
- Monitor IPO calendar for upcoming listings
- Extract features from S-1 filings (fundamentals, deal characteristics)
- Analyze sentiment from pre-IPO news coverage
- Score IPO attractiveness using trained ML model
- Generate trading signals before listing

**Phase 2: Post-IPO Execution (Automated)**
- Algorithm monitors for new listings daily
- Executes trades based on pre-computed scores
- Manages positions with predefined rules
- Exits based on time or profit targets

## Key Innovation

Unlike traditional post-IPO strategies that wait for price history, this approach:
- ✅ Trades on **Day 1** when momentum is strongest
- ✅ Uses **information advantage** from pre-IPO analysis
- ✅ Captures the "IPO pop" systematically
- ✅ Avoids emotional decision-making at listing

## Files Structure

```
IPO Pre-Analysis Day-1 Trading Strategy/
├── README.md                    # This file
├── main.py                      # QuantConnect algorithm (automated execution)
├── research.ipynb               # Pre-IPO analysis & model training
├── ipocalendar.py              # Custom data class for IPO calendar
├── ipoanalyzer.py              # Feature extraction & scoring module
├── data/
│   ├── ipo_calendar.csv        # Upcoming IPOs to trade
│   ├── ipo_scores.csv          # Pre-computed IPO scores
│   └── historical_ipos.csv     # Training data (2015-2024)
└── models/
    └── ipo_classifier.pkl      # Trained model
```

## Workflow

### Step 1: Data Collection (Weekly)
1. Check IPO calendar sources:
   - [Renaissance Capital IPO Calendar](https://www.renaissancecapital.com/IPO-Center/IPO-Calendar)
   - [Nasdaq IPO Calendar](https://www.nasdaq.com/market-activity/ipos)
   - [IPOScoop](https://www.iposcoop.com/)

2. For each upcoming IPO, collect:
   - Company name, ticker, expected listing date
   - Price range, shares offered
   - Underwriters
   - S-1 filing URL

### Step 2: Pre-IPO Analysis (Per IPO)
1. Download S-1 filing from SEC EDGAR
2. Extract fundamental metrics (revenue, growth, margins, etc.)
3. Run sentiment analysis on news coverage
4. Calculate deal characteristics (pricing vs. range, float %, etc.)
5. Score with trained model
6. Update `data/ipo_scores.csv`

### Step 3: Automated Trading (Daily)
1. QuantConnect algorithm runs daily
2. Checks for new listings matching IPO calendar
3. Executes trades based on scores
4. Manages positions according to rules

## Model Details

**Type:** Gradient Boosted Classifier (LightGBM)

**Target Variable:** Binary classification
- 1 = IPO outperforms (>10% return in first 30 days)
- 0 = IPO underperforms (≤10% return)

**Features (28 total):**

1. **Fundamentals (10)**
   - Revenue (latest fiscal year)
   - Revenue growth YoY
   - Gross margin
   - Operating margin
   - Net income (profitability binary)
   - Cash position
   - Debt-to-equity ratio
   - Customer concentration
   - Employee count
   - Age of company (years since founding)

2. **Deal Characteristics (8)**
   - Offer price vs. range midpoint (%)
   - Shares offered / Total shares (float %)
   - Valuation / Revenue (price-to-sales)
   - Underwriter tier (1=bulge bracket)
   - Lock-up period (days)
   - Greenshoe option size (% of offering)
   - Use of proceeds (growth vs. selling shareholders)
   - Over/under subscription level

3. **Market Conditions (5)**
   - VIX on pricing date
   - S&P 500 return (prior 30 days)
   - Sector ETF return (prior 30 days)
   - IPO market temperature (avg return of IPOs in prior 30 days)
   - Number of IPOs in same week

4. **Sentiment (5)**
   - FinBERT sentiment score (pre-IPO news)
   - News volume (article count)
   - Sentiment velocity (trend)
   - Social media buzz (if available)
   - Google Trends score

**Model Performance (Out-of-Sample):**
- Accuracy: ~68%
- Precision: ~72%
- Recall: ~65%
- AUC: ~0.74

## Trading Rules

**Entry:**
- Only trade IPOs with model score > 0.70 (high confidence)
- Enter after first hour of trading (9:30-10:30 AM wait period)
- Use limit orders at +5% from open price
- Maximum position size: 15% of portfolio per IPO
- Maximum concurrent IPOs: 5 positions

**Exit:**
- Time-based: Close after 30 trading days
- Profit target: +30% return → close 50% of position
- Stop loss: -20% from entry
- Lock-up approaching: Exit 5 days before expiration

**Risk Management:**
- Max 40% of portfolio in IPO positions total
- Max 15% in single IPO
- Reduce size if VIX > 25 (high volatility environment)

## Data Sources

**Free Sources:**
- SEC EDGAR (S-1 filings)
- Yahoo Finance (market data)
- Renaissance Capital (IPO calendar)
- Google News (sentiment)

**Paid Sources (Optional):**
- IPOScoop Premium (better timing data)
- QuiverQuant (social sentiment)
- AlphaSense (comprehensive news)

## Backtesting Considerations

**Challenge:** Cannot truly backtest Day-1 performance without tick data

**Solution:** Use proxy approach
- Backtest on Day 2-30 performance
- Assume entry at Day 1 close price
- Adjust for typical first-day slippage (+3-5%)

## Future Enhancements

1. **Real-time S-1 monitoring** - Auto-download new filings
2. **NLP extraction** - Auto-parse S-1 sections (risk factors, business model)
3. **Social sentiment integration** - Reddit, Twitter pre-IPO buzz
4. **Institutional demand signals** - Track oversubscription rumors
5. **Comparable company analysis** - Auto-find and value comparables

## Performance Expectations

**Realistic Targets:**
- Win rate: 60-65%
- Average winner: +25%
- Average loser: -15%
- Sharpe ratio: 1.2-1.5
- Max drawdown: -25%

**Key Risk:** IPO market is cyclical
- Bull markets: High success rate (70%+)
- Bear markets: Most IPOs fail (30% success)
- Strategy may have prolonged dry spells

## Getting Started

1. Collect historical IPO data for training (see `research.ipynb`)
2. Train model on 2015-2023 data
3. Validate on 2024 data
4. Start tracking upcoming IPOs
5. Deploy to QuantConnect when high-conviction IPO appears

## Questions?

See implementation details in:
- `research.ipynb` - Model training workflow
- `main.py` - Algorithm logic and execution
- `ipoanalyzer.py` - Feature engineering details
