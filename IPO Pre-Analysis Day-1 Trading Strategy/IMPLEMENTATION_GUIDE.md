# IPO Pre-Analysis Day-1 Trading - Implementation Guide

## Complete Step-by-Step Implementation

This guide walks you through implementing the full IPO trading strategy from data collection to live trading.

---

## Phase 1: Data Collection & Preparation

### Week 1-2: Build Historical IPO Dataset

**Objective:** Create a dataset of 300-500 historical IPOs (2015-2024) for model training.

#### Step 1.1: Collect IPO Calendar Data

**Free Sources:**
1. **Renaissance Capital IPO Center**
   - URL: https://www.renaissancecapital.com/IPO-Center/IPO-Calendar
   - Data: Ticker, company name, listing date, price range, final price, underwriters
   - Export: Manual copy-paste to CSV

2. **Nasdaq IPO Calendar**
   - URL: https://www.nasdaq.com/market-activity/ipos
   - Data: Similar to Renaissance Capital
   - Historical data available

3. **IPOScoop**
   - URL: https://www.iposcoop.com/
   - Data: IPO performance metrics, first-day returns
   - Historical archive available

**Action Items:**
- [ ] Download IPO listings for 2015-2024
- [ ] Create master CSV with: ticker, listing_date, offer_price, shares_offered, underwriter
- [ ] Save as `data/ipo_master_list.csv`

#### Step 1.2: Download S-1 Filings

For each IPO in your master list, download the final S-1/S-1A filing.

**Using SEC EDGAR:**
1. Go to: https://www.sec.gov/edgar/searchedgar/companysearch.html
2. Search by ticker
3. Find "S-1" or "S-1/A" filing dated ~1 week before IPO
4. Download HTML or PDF version

**Automated Approach:**
```python
import requests
from sec_edgar_downloader import Downloader

dl = Downloader("YourCompany", "your.email@example.com")

for ticker in ipo_list:
    try:
        dl.get("S-1", ticker, limit=1)
    except:
        print(f"Failed to download {ticker}")
```

**Action Items:**
- [ ] Download S-1 filings for all IPOs
- [ ] Store in `data/s1_filings/` folder
- [ ] Create index: `data/s1_index.csv` (ticker → file path)

#### Step 1.3: Extract Fundamental Data from S-1 Filings

**Key Sections to Parse:**

1. **Summary Financial Data Table** (usually page 10-15)
   - Revenue (last 3 years)
   - Gross profit
   - Operating income/loss
   - Net income/loss
   - Cash and equivalents
   - Total debt

2. **Business Description** (textual analysis)
   - Company age (founded year)
   - Number of employees
   - Customer concentration (% from top 5 customers)

3. **Use of Proceeds**
   - Growth vs. selling shareholders (binary classification)

**Parsing Approach:**

**Option A: Manual** (for small datasets <100 IPOs)
- Create Excel template with all fields
- Manually copy values from each S-1
- Time: ~15 min per IPO

**Option B: Semi-Automated** (recommended)
```python
import pdfplumber
import re

def extract_financials(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages[:30]:  # Check first 30 pages
            text += page.extract_text()

        # Use regex to find financial tables
        revenue_match = re.search(r'Revenue.*?(\d{1,3},\d{3},\d{3})', text)
        # ... more patterns

    return financials_dict
```

**Option C: AI-Powered** (advanced)
- Use OpenAI GPT-4 to extract tables from S-1
- Prompt: "Extract the summary financial data table from this S-1 filing"
- Parse JSON response

**Action Items:**
- [ ] Extract fundamental data for all IPOs
- [ ] Save to `data/ipo_fundamentals.csv`
- [ ] Validate: check for missing values, outliers

#### Step 1.4: Calculate Deal Characteristics

Most of this data is in the final S-1 amendment (filed 1 day before IPO).

**Key Metrics:**
```python
def calculate_deal_features(row):
    # Price vs. range
    range_midpoint = (row['range_low'] + row['range_high']) / 2
    price_vs_range = (row['offer_price'] - range_midpoint) / range_midpoint

    # Float %
    float_pct = row['shares_offered'] / row['shares_outstanding']

    # P/S ratio
    market_cap = row['offer_price'] * row['shares_outstanding']
    price_to_sales = market_cap / row['revenue']

    # Underwriter tier (1 = bulge bracket)
    bulge_bracket = ['Goldman Sachs', 'Morgan Stanley', 'JP Morgan',
                     'Bank of America', 'Citigroup']
    is_bulge = any(uw in row['underwriters'] for uw in bulge_bracket)

    return {
        'price_vs_range': price_vs_range,
        'float_pct': float_pct,
        'price_to_sales': price_to_sales,
        'underwriter_tier': int(is_bulge)
    }
```

**Action Items:**
- [ ] Add deal characteristics to dataset
- [ ] Save updated `data/ipo_fundamentals.csv`

#### Step 1.5: Collect Market Conditions Data

Use QuantConnect or Yahoo Finance to get historical market data.

**Required Data:**
- VIX (daily close) on IPO listing date
- SPY return (30-day prior to IPO)
- Sector ETF return (QQQ, XLF, XLE, etc.)
- Recent IPO performance (avg return of IPOs in prior 30 days)

**Using QuantConnect:**
```python
qb = QuantBook()

for ipo in ipo_list:
    listing_date = ipo['listing_date']

    # Get VIX
    vix = qb.add_index("VIX")
    vix_history = qb.history(vix, listing_date - timedelta(1), listing_date, Resolution.DAILY)
    ipo['vix'] = vix_history['close'].iloc[-1]

    # Get SPY return (30 days)
    spy = qb.add_equity("SPY")
    spy_history = qb.history(spy, listing_date - timedelta(30), listing_date, Resolution.DAILY)
    ipo['spy_return_30d'] = spy_history['close'].pct_change(30).iloc[-1]
```

**Action Items:**
- [ ] Collect market data for all IPO dates
- [ ] Add to `data/ipo_market_conditions.csv`

#### Step 1.6: Collect Sentiment Data

**News Sentiment (FinBERT):**

1. Get pre-IPO news articles (Google News, AlphaSense)
2. Run through FinBERT for sentiment scoring

```python
from transformers import BertTokenizer, TFBertForSequenceClassification
import tensorflow as tf

tokenizer = BertTokenizer.from_pretrained('ProsusAI/finbert')
model = TFBertForSequenceClassification.from_pretrained('ProsusAI/finbert')

def get_sentiment(article_text):
    inputs = tokenizer(article_text, return_tensors='tf', padding=True,
                      truncation=True, max_length=512)
    outputs = model(inputs)
    probs = tf.nn.softmax(outputs.logits, axis=-1).numpy()[0]

    # FinBERT classes: [negative, neutral, positive]
    sentiment_score = probs[2] - probs[0]  # -1 to +1 scale
    return sentiment_score

# For each IPO, get news from 30 days before listing
for ipo in ipo_list:
    news_articles = get_news(ipo['ticker'], days_before=30)
    sentiments = [get_sentiment(article) for article in news_articles]

    ipo['finbert_score'] = np.mean(sentiments)
    ipo['news_volume'] = len(news_articles)
```

**Google Trends:**
```python
from pytrends.request import TrendReq

pytrends = TrendReq()
pytrends.build_payload([ipo['company_name']],
                       timeframe=f'{start_date} {end_date}')
trends = pytrends.interest_over_time()
ipo['google_trends'] = trends.mean()
```

**Action Items:**
- [ ] Collect news articles for each IPO (30 days pre-listing)
- [ ] Run FinBERT sentiment analysis
- [ ] Get Google Trends data
- [ ] Save to `data/ipo_sentiment.csv`

#### Step 1.7: Collect Target Variable (IPO Performance)

Get actual price data for each IPO from listing day through Day 30.

**Using QuantConnect:**
```python
for ipo in ipo_list:
    ticker = ipo['ticker']
    listing_date = ipo['listing_date']

    # Get price data for 30 days post-IPO
    equity = qb.add_equity(ticker)
    history = qb.history(equity, listing_date, listing_date + timedelta(30),
                        Resolution.DAILY)

    if not history.empty:
        first_close = history['close'].iloc[0]
        day30_close = history['close'].iloc[-1] if len(history) >= 30 else None

        if day30_close:
            return_30d = (day30_close - first_close) / first_close
            ipo['return_30d'] = return_30d
            ipo['success'] = 1 if return_30d > 0.10 else 0  # >10% = success
```

**Action Items:**
- [ ] Collect 30-day returns for all IPOs
- [ ] Calculate binary target: 1 if return > 10%, else 0
- [ ] Save to `data/ipo_performance.csv`

#### Step 1.8: Merge All Data

Combine all datasets into one master training file.

```python
import pandas as pd

# Load all datasets
master = pd.read_csv('data/ipo_master_list.csv')
fundamentals = pd.read_csv('data/ipo_fundamentals.csv')
market = pd.read_csv('data/ipo_market_conditions.csv')
sentiment = pd.read_csv('data/ipo_sentiment.csv')
performance = pd.read_csv('data/ipo_performance.csv')

# Merge on ticker
df = master.merge(fundamentals, on='ticker')
df = df.merge(market, on='ticker')
df = df.merge(sentiment, on='ticker')
df = df.merge(performance, on='ticker')

# Drop rows with missing target
df = df.dropna(subset=['success'])

# Save final training dataset
df.to_csv('data/historical_ipos.csv', index=False)

print(f"Final dataset: {len(df)} IPOs with {len(df.columns)} features")
```

**Action Items:**
- [ ] Merge all datasets
- [ ] Handle missing values
- [ ] Save as `data/historical_ipos.csv`
- [ ] Validate dataset quality

---

## Phase 2: Model Training

### Week 3: Train and Validate Model

Follow the `research.ipynb` notebook to:

1. **Load data** → `data/historical_ipos.csv`
2. **Train model** → LightGBM classifier
3. **Validate** → 80/20 split, check AUC > 0.70
4. **Save model** → Object Store as `ipo_classifier_model`

**Action Items:**
- [ ] Run `research.ipynb` end-to-end
- [ ] Achieve validation AUC > 0.70
- [ ] Save model to Object Store
- [ ] Document feature importances

---

## Phase 3: Weekly IPO Scoring

### Ongoing: Score Upcoming IPOs

**Every Monday:**

#### Step 3.1: Get IPO Calendar (Next 30 Days)

Check these sources:
- Renaissance Capital: https://www.renaissancecapital.com/IPO-Center/IPO-Calendar
- Nasdaq: https://www.nasdaq.com/market-activity/ipos
- IPOScoop: https://www.iposcoop.com/

**Create CSV:**
```csv
ticker,company_name,expected_date,price_range_low,price_range_high,sector
NEWCO,New Company Inc,2025-01-15,20,24,Technology
```

#### Step 3.2: Download S-1 for Each Upcoming IPO

- Search SEC EDGAR for ticker
- Download latest S-1 or S-1/A filing
- Save to `data/s1_filings/upcoming/`

#### Step 3.3: Extract Features

Use `ipoanalyzer.py` to extract all 28 features:

```python
from ipoanalyzer import IPOFeatureExtractor, IPOScorer

extractor = IPOFeatureExtractor()

# Manually fill in data from S-1
ipo_data = {
    'fundamentals': {
        'revenue': 800_000_000,
        'revenue_growth_yoy': 0.65,
        # ... all 10 fundamental features
    },
    'deal': {
        'offer_price': 22,  # When announced
        'range_low': 20,
        'range_high': 24,
        # ... all 8 deal features
    },
    'market': extractor.calculate_market_features_live(...),
    'sentiment': {
        # Run FinBERT on recent news
        'finbert_score': 0.45,
        # ...
    }
}

# Extract feature vector
features = extractor.extract_all_features(ipo_data)
```

#### Step 3.4: Score with Model

```python
scorer = IPOScorer()
scorer.load_model('models/ipo_classifier.pkl')

score = scorer.score_ipo(ipo_data)
print(f"IPO Score: {score:.3f}")
```

#### Step 3.5: Update IPO Calendar CSV

```python
upcoming_ipos.append({
    'date': '2025-01-15',
    'ticker': 'NEWCO',
    'company_name': 'New Company Inc',
    'score': score,
    'offer_price': 22,
    'shares_offered': 15_000_000,
    'sector': 'Technology'
})

df = pd.DataFrame(upcoming_ipos)
df.to_csv('data/ipo_calendar.csv', index=False)
```

#### Step 3.6: Upload to QuantConnect

```python
qb = QuantBook()
csv_content = df.to_csv(index=False)
qb.object_store.save('ipo_calendar', csv_content)
```

**Action Items (Weekly):**
- [ ] Monday: Get IPO calendar for next 30 days
- [ ] Tuesday: Download S-1 filings
- [ ] Wednesday: Extract features and score IPOs
- [ ] Thursday: Update `ipo_calendar.csv`
- [ ] Friday: Upload to Object Store

---

## Phase 4: Deploy & Monitor

### Week 4: Deploy to QuantConnect

#### Step 4.1: Upload Files

1. Create new project in QuantConnect
2. Upload these files:
   - `main.py`
   - `ipocalendar.py`
   - `ipoanalyzer.py`

#### Step 4.2: Configure Parameters

In QuantConnect UI, set parameters:
```
score_threshold = 0.70
max_positions = 5
max_position_size = 0.15
holding_period = 30
profit_target = 0.30
stop_loss = -0.20
```

#### Step 4.3: Backtest

Run backtest for 2024:
- Start date: 2024-01-01
- End date: 2024-12-31
- Initial capital: $100,000

**Validate:**
- Total return > 15%
- Sharpe ratio > 1.0
- Max drawdown < 30%
- Win rate > 55%

#### Step 4.4: Paper Trading

Switch to paper trading mode:
- Monitor for 1 month
- Verify orders execute correctly
- Check position sizing logic

#### Step 4.5: Go Live

When confident:
- Switch to live trading
- Start with 25% of intended capital
- Scale up over 3 months

**Action Items:**
- [ ] Deploy to QuantConnect
- [ ] Run backtest and validate
- [ ] Paper trade for 1 month
- [ ] Go live with partial capital

---

## Phase 5: Maintenance

### Monthly: Model Retraining

Every 3 months:
1. Collect new IPO data from past quarter
2. Add to training dataset
3. Retrain model
4. Validate on out-of-sample data
5. Update model in Object Store if improved

### Weekly: IPO Scoring

See Phase 3 above.

### Daily: Monitor Performance

Check:
- Open positions
- Upcoming exits
- Recent IPO calendar changes

---

## Troubleshooting

### Issue: Model AUC < 0.70

**Solutions:**
- Collect more historical data (target 500+ IPOs)
- Feature engineering: add more sentiment sources
- Try different models: XGBoost, Neural Network
- Ensemble: combine multiple models

### Issue: No IPOs Listing This Week

**Normal!** IPO market is cyclical:
- Bull markets: 5-10 IPOs/week
- Bear markets: 0-2 IPOs/week
- Be patient, wait for high-quality opportunities

### Issue: First-Day Price Gaps

IPOs often gap up/down at open:
- Solution: Wait 1 hour after open (already in algorithm)
- Use limit orders with 2-5% buffer
- Accept slippage as cost of strategy

### Issue: Can't Find S-1 Filing

Some companies file under different tickers:
- Check parent company name
- Search by CIK number
- Contact investor relations

---

## Resources

**IPO Calendars:**
- Renaissance Capital: https://www.renaissancecapital.com/
- Nasdaq: https://www.nasdaq.com/market-activity/ipos
- IPOScoop: https://www.iposcoop.com/

**SEC Filings:**
- EDGAR: https://www.sec.gov/edgar

**Data APIs:**
- Alpha Vantage (free tier): https://www.alphavantage.co/
- IEX Cloud: https://iexcloud.io/
- Polygon.io: https://polygon.io/

**ML Libraries:**
- LightGBM: https://lightgbm.readthedocs.io/
- FinBERT: https://huggingface.co/ProsusAI/finbert
- scikit-learn: https://scikit-learn.org/

**QuantConnect:**
- Docs: https://www.quantconnect.com/docs/
- Forum: https://www.quantconnect.com/forum/

---

## Timeline Summary

| Week | Phase | Tasks | Time Required |
|------|-------|-------|---------------|
| 1-2 | Data Collection | Collect historical IPO data | 20-30 hours |
| 3 | Model Training | Train and validate model | 5-10 hours |
| 4 | Deployment | Deploy to QuantConnect | 5 hours |
| Ongoing | Weekly Scoring | Score upcoming IPOs | 2-3 hours/week |
| Quarterly | Maintenance | Retrain model | 3-5 hours/quarter |

**Total Initial Investment:** 30-45 hours
**Weekly Maintenance:** 2-3 hours

---

## Expected Results

**Conservative Estimates:**
- Win rate: 55-60%
- Average winner: +20-25%
- Average loser: -12-15%
- Annual return: 20-30%
- Sharpe ratio: 1.2-1.5
- Max drawdown: 20-30%

**Risk Factors:**
- IPO market cycles (dry spells)
- Model degradation over time
- Market regime changes
- Execution slippage

**Success Factors:**
- Data quality (accurate S-1 extraction)
- Disciplined execution (don't overtrade)
- Risk management (respect stop losses)
- Continuous improvement (retrain quarterly)

Good luck!
