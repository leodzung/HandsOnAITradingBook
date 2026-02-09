# Polymarket Trading Flow - Complete Walkthrough

## Overview

Your trading bot runs in a continuous loop, executing one complete cycle every **5 minutes**. Here's exactly what happens in each cycle:

---

## 🔄 Main Trading Loop

```
START
  ↓
[Wait 5 minutes]
  ↓
[Execute Trading Cycle]
  ↓
REPEAT FOREVER
```

---

## 📊 Detailed Trading Cycle (10 Steps)

### **STEP 1: Fetch Markets** 📈
**File:** `polymarket_client.py` → `get_markets()`

```python
# Fetch 100 active markets from Polymarket API
markets = client.get_markets(limit=100, active=True)
# Returns: 100 raw markets
```

**What happens:**
- Calls Polymarket Gamma API: `https://gamma-api.polymarket.com/markets`
- Gets market data: question, volume, price, expiry, etc.

**Example market:**
```json
{
  "question": "Fed emergency rate cut in 2025?",
  "volume": 2504892.47,
  "bestBid": 0.08,
  "bestAsk": 0.09,
  "endDate": "2025-12-31T12:00:00Z"
}
```

---

### **STEP 2: Filter Markets** 🔍
**File:** `polymarket_client.py` → `MarketFilter`

```python
# Filter 1: Active only (not expired)
active_markets = MarketFilter.filter_active_only(markets)
# 100 → 100 markets

# Filter 2: High liquidity (volume > $1,000)
liquid_markets = MarketFilter.filter_by_liquidity(active_markets, min_volume=1000)
# 100 → 100 markets

# Filter 3: Time to expiry (2-720 hours = 0.08-30 days)
tradeable_markets = MarketFilter.filter_by_time_to_expiry(
    liquid_markets,
    min_hours=2,
    max_hours=720
)
# 100 → 99 markets ✅
```

**Why filter?**
- **Active:** Skip expired markets
- **Liquidity:** Ensure we can execute trades
- **Expiry:** Avoid markets closing too soon or too far away

**Result:** **99 tradeable markets** ready for analysis

---

### **STEP 3: Detect News Events** 📰
**File:** `event_detector.py` → `get_all_recent_events()`

```python
events = event_detector.get_all_recent_events(lookback_hours=1)
```

**News sources checked:**
1. **NewsAPI** - `https://newsapi.org/v2/everything`
   - Query: "news OR market OR election OR crypto OR bitcoin"
   - Last 1 hour

2. **RSS Feeds** (3 feeds):
   - Bloomberg: `https://feeds.bloomberg.com/markets/news.rss`
   - CoinDesk: `https://www.coindesk.com/arc/outboundfeeds/rss/`
   - Reuters: `https://www.reuters.com/rssFeed/topNews`

**Example event detected:**
```python
Event(
    title="Bitcoin Surges to $95K on Institutional Buying",
    source="Bloomberg",
    published_time=2025-12-27 19:45:00,
    keywords=["Bitcoin", "Surges", "Institutional", "Buying"]
)
```

**Typical result:** 1-5 events per cycle

---

### **STEP 4: Match Events to Markets** 🎯
**File:** `event_detector.py` → `match_events_to_markets()`

```python
matched = event_detector.find_relevant_events(markets, lookback_hours=1)
```

**Matching algorithm:**
1. Extract keywords from event title (capitalized words)
2. Extract keywords from market question
3. Calculate keyword overlap
4. Match if overlap ≥ 1 keyword

**Example match:**
```
Event: "Bitcoin Surges to $95K on Institutional Buying"
Keywords: ["Bitcoin", "Surges", "Institutional", "Buying"]

Market: "Bitcoin to reach $100K in 2025?"
Keywords: ["Bitcoin", "reach", "100K", "2025"]

Overlap: ["Bitcoin"] → 1 keyword match ✅
```

**Result:** Dictionary mapping `market_id` → `[matching_events]`

---

### **STEP 5: Extract Features** 🧬
**File:** `feature_extractor.py` → `create_training_sample()`

For each event-market pair, extract **8 features**:

```python
features = {
    'sentiment_score': 0.85,        # +1 = very positive, -1 = very negative
    'sentiment_magnitude': 2.0,     # Strength of sentiment
    'source_credibility': 1.0,      # Bloomberg=1.0, blog=0.5
    'title_length': 48,             # Number of characters
    'has_description': 1,           # Boolean (0 or 1)
    'keyword_overlap': 4,           # Number of matching keywords
    'market_volume': 2500000,       # Trading volume in $
    'market_volume_log': 14.73      # Log-scaled volume
}
```

**Sentiment analysis:**
```python
# Positive words: surge, gain, rise, win, success → +score
# Negative words: fall, drop, crash, loss, fail → -score

"Bitcoin surges to $95K" → sentiment = +0.85 (very positive)
"Markets crash on recession fears" → sentiment = -0.70 (very negative)
```

**Source credibility scores:**
- Bloomberg, Reuters, WSJ: **1.0** (highest)
- CNN, CNBC, CoinDesk: **0.8**
- Medium blogs: **0.5**
- Unknown sources: **0.3** (lowest)

---

### **STEP 6: Predict with ML Model** 🤖
**File:** `models.py` → `PriceMovementPredictor.predict()`

```python
# Load your trained model
model = PriceMovementPredictor()
model.load('real_data_model.pkl')

# Predict
features_array = [0.85, 2.0, 1.0, 48, 1, 4, 2500000, 14.73]
prediction = model.predict([features_array])[0]
confidence = model.predict_proba([features_array]).max()

# Output:
# prediction = 1 (UP)
# confidence = 0.78 (78%)
```

**How Random Forest predicts:**
```
100 decision trees each vote:
├─ Tree 1: UP ✓
├─ Tree 2: UP ✓
├─ Tree 3: NEUTRAL
├─ Tree 4: UP ✓
├─ ...
└─ Tree 100: UP ✓

Final votes: 78 UP, 15 NEUTRAL, 7 DOWN
→ Prediction: UP
→ Confidence: 78% (78 trees agreed)
```

**Prediction classes:**
- **UP (+1):** Price likely to increase
- **NEUTRAL (0):** Price likely unchanged
- **DOWN (-1):** Price likely to decrease

---

### **STEP 7: Generate Trading Signal** 💰
**File:** `models.py` → `TradingSignalGenerator.generate_signal()`

```python
def generate_signal(prediction, confidence, current_price):
    # Check confidence threshold
    if confidence < 0.65:
        return None  # HOLD - not confident enough

    # Generate signal based on prediction
    if prediction == 1 and current_price < 0.95:
        return {
            'action': 'BUY',
            'confidence': confidence,
            'expected_return': 0.05
        }
    elif prediction == -1 and current_price > 0.05:
        return {
            'action': 'SELL',
            'confidence': confidence,
            'expected_return': 0.05
        }
    else:
        return None  # HOLD
```

**Signal generation rules:**
1. **Confidence ≥ 65%** → Consider trading
2. **Confidence < 65%** → HOLD (too uncertain)
3. **Prediction = UP** AND **price < $0.95** → BUY
4. **Prediction = DOWN** AND **price > $0.05** → SELL
5. **Prediction = NEUTRAL** → HOLD

**Example signals:**

| Prediction | Confidence | Current Price | Signal | Reason |
|------------|-----------|---------------|--------|--------|
| UP | 78% | $0.55 | **BUY** ✅ | High confidence, room to grow |
| DOWN | 72% | $0.85 | **SELL** ✅ | High confidence, room to fall |
| UP | 52% | $0.45 | **HOLD** ⚠️ | Confidence too low |
| UP | 80% | $0.98 | **HOLD** ⚠️ | Price too high (limited upside) |

---

### **STEP 8: Risk Management Check** 🛡️
**File:** `trader.py` → `RiskManager.can_trade()`

```python
# Check 1: Position limits
if current_positions >= max_positions:
    return False  # Already at max (10 positions)

# Check 2: Position size
if position_size > max_position_size:
    return False  # Position too large (max $100)

# Check 3: Daily loss limit
if daily_loss >= max_daily_loss:
    return False  # Hit daily loss limit ($500)

return True  # All checks passed ✅
```

**Risk parameters:**
- **Max positions:** 10 concurrent trades
- **Max position size:** $100 per trade
- **Max daily loss:** $500 total
- **Hold time:** 24 hours (auto-close)

**Why risk management?**
- Prevents over-leveraging
- Limits maximum loss
- Forces diversification
- Protects capital

---

### **STEP 9: Execute Trade** 📝
**File:** `trader.py` → `execute_trade()`

**Paper Trading Mode** (current default):
```python
if paper_trading:
    # Log trade (no real money)
    logger.info(f"[PAPER] BUY $100 at $0.55")

    # Track paper position
    position = {
        'entry_time': datetime.now(),
        'entry_price': 0.55,
        'side': 'BUY',
        'size': 100
    }

    # No actual order placed ✅
```

**Live Trading Mode:**
```python
else:
    # Place real order on Polymarket
    order = client.place_order(
        token_id='0xabc...',
        side='BUY',
        price=0.55,
        size=181.82,  # $100 / $0.55 = 181.82 shares
        order_type='GTC'
    )

    # Wait for order to fill
    # Update portfolio
```

**Trade logging:**
```
2025-12-27 19:45:23 - trader - INFO - [PAPER] BUY $100 at $0.55
2025-12-27 19:45:23 - trader - INFO - Position opened: market_id=0xabc...
```

---

### **STEP 10: Position Management** ⏱️
**File:** `trader.py` → `manage_positions()`

```python
# Check all open positions
for position in open_positions:
    time_held = (now - position['entry_time']).hours

    # Close if held for 24 hours
    if time_held >= 24:
        close_position(position)
```

**Position lifecycle:**
```
T+0h:  BUY $100 @ $0.55
T+12h: Check price (still monitoring)
T+24h: CLOSE position @ $0.62
       → P&L = ($0.62 - $0.55) × 181.82 = +$12.73 ✅
```

**Why 24-hour hold?**
- News impact typically occurs within 24h
- Prevents overtrading
- Reduces slippage costs
- Simplifies backtesting

---

### **STEP 11: Performance Tracking** 📊
**File:** `trader.py` → `log_performance()`

**Metrics tracked:**
```python
performance_stats = {
    'total_trades': 47,
    'winning_trades': 29,
    'losing_trades': 18,
    'win_rate': 0.617,          # 61.7%
    'total_pnl': 234.50,        # $234.50
    'avg_return': 0.053,        # 5.3% per trade
    'sharpe_ratio': 1.42,
    'max_drawdown': -78.20,     # Worst loss streak
    'prediction_accuracy': 0.65 # 65% correct predictions
}
```

**Logged every cycle:**
```
2025-12-27 19:50:23 - trader - INFO - Performance Stats:
  Total trades: 47
  Win rate: 61.7%
  Total P&L: $234.50
  Accuracy (24h): 68.4%
```

---

## 📈 Complete Cycle Example

Let's trace one complete cycle:

### **19:45:00 - Cycle Starts**

**Step 1-2:** Fetch and filter markets
```
100 markets → 99 tradeable markets
```

**Step 3:** Detect news
```
NewsAPI finds: "Fed Hints at Rate Cuts in 2025"
Source: Reuters
Time: 19:43:00 (2 minutes ago)
```

**Step 4:** Match to markets
```
Event keywords: ["Fed", "Hints", "Rate", "Cuts", "2025"]
Market: "Fed emergency rate cut in 2025?"
Match: ["Fed", "Rate", "Cuts", "2025"] → 4 keywords ✅
```

**Step 5:** Extract features
```python
{
    'sentiment_score': -0.20,        # Slightly negative ("emergency")
    'sentiment_magnitude': 1.5,
    'source_credibility': 1.0,       # Reuters = highly credible
    'title_length': 32,
    'has_description': 1,
    'keyword_overlap': 4,            # Strong match
    'market_volume': 2504892,        # High volume
    'market_volume_log': 14.73
}
```

**Step 6:** Predict
```
Model prediction: UP (1)
Confidence: 71%
Reasoning: High credibility + good keyword match + high volume
```

**Step 7:** Generate signal
```
Signal: BUY
Reason: Confidence 71% > 65% threshold
Current price: $0.08
Expected move: $0.08 → $0.12 (+50%)
```

**Step 8:** Risk check
```
✓ Current positions: 3 / 10
✓ Position size: $100 < $100 max
✓ Daily loss: -$23 < $500 max
→ All checks passed
```

**Step 9:** Execute
```
[PAPER] BUY $100 @ $0.08
→ 1,250 shares purchased (paper)
Entry logged at 19:45:23
```

**Step 10:** Monitor
```
Position will be closed at: 2025-12-28 19:45:23 (T+24h)
```

### **19:46:00 - Cycle Complete**
```
Next cycle in: 4 minutes
```

---

## 🎯 Key Decision Points

### **When to Trade?**
```
Trade if ALL conditions met:
  ✓ Event matched to market (keyword overlap ≥ 1)
  ✓ Model confidence ≥ 65%
  ✓ Prediction is UP or DOWN (not NEUTRAL)
  ✓ Price has room to move (not at 0.05 or 0.95)
  ✓ Risk checks pass (position limits, daily loss)
```

### **When to Hold?**
```
Hold if ANY condition fails:
  ✗ No events detected
  ✗ No event-market matches
  ✗ Model confidence < 65%
  ✗ Prediction is NEUTRAL
  ✗ Price too high/low (limited upside)
  ✗ At position limits
  ✗ Hit daily loss limit
```

### **When to Close?**
```
Close position when:
  • Time held ≥ 24 hours (auto-close)
  • Market expires/resolves
  • Daily loss limit hit (emergency close all)
```

---

## 💡 Trading Strategy Summary

**Your bot implements:**
1. **Event-driven strategy:** React to news within 1 hour
2. **ML-based prediction:** Use 8 features to predict price movement
3. **Confidence filtering:** Only trade when confidence ≥ 65%
4. **Risk management:** Limit positions, size, and losses
5. **Fixed hold time:** Close all positions after 24 hours
6. **Paper trading first:** Test without real money

**Current performance:**
- Model accuracy: 65% cross-validation
- Confidence threshold: 65%
- Expected trade frequency: 1-5 per day
- Position size: $100 per trade
- Hold time: 24 hours

---

## 🔄 Continuous Improvement

**After each trade:**
1. Log actual outcome (price movement)
2. Track prediction accuracy
3. Collect data for retraining
4. Adjust model monthly

**After 100+ trades:**
- Retrain model on real outcomes
- Optimize hyperparameters
- Add new features
- Improve accuracy to 70%+

---

## 🚀 Running the Trading Bot

**Start paper trading:**
```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"
python3 trader.py
```

**Monitor in real-time:**
```bash
tail -f trader.log
```

**Stop trading:**
```bash
Ctrl+C
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `trader.py` | Main trading loop |
| `polymarket_client.py` | API client + market filters |
| `event_detector.py` | News detection (NewsAPI, RSS) |
| `feature_extractor.py` | Feature engineering |
| `models.py` | ML model + signal generation |
| `real_data_model.pkl` | Trained Random Forest model |
| `config.json` | Configuration parameters |

---

**Your trading system is now fully explained and operational!** 🎉
