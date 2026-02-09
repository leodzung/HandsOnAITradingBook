# Issues & Root Causes - Summary

**Date:** December 30, 2025
**Bots:** Event-Based Trader + Price-Level Trader

---

## **Issue #1: Signal Generator Bug** ✅ FIXED

### Symptom:
- Bot generated 112 BUY signals, 0 SELL signals
- All 10 positions betting YES on unlikely events

### Root Cause:
**Python array indexing error**

```python
# BROKEN CODE (models.py:434):
expected_return = probabilities[prediction] * current_price

# When prediction = -1 (DOWN):
# probabilities[-1] → accesses LAST element (index 2, class 1)
# Should access: probabilities[0] (class -1)
# Result: SELL signals calculated with wrong probability → never triggered
```

### Technical Explanation:
- Model classes: `[-1, 0, 1]` (DOWN, NEUTRAL, UP)
- Numpy array indices: `[0, 1, 2]`
- When `prediction = -1`, Python interprets `probabilities[-1]` as "last element" not "class -1"
- This gave SELL signals the probability of UP (class 1), not DOWN (class -1)
- SELL expected_return was wrong → never met threshold

### Fix:
```python
# FIXED CODE:
class_to_idx = {-1: 0, 0: 1, 1: 2}
pred_idx = class_to_idx.get(prediction, 1)
pred_prob = probabilities[pred_idx]
expected_return = pred_prob * current_price  # Now uses correct probability
```

**Status:** ✅ Fixed @ 10:00 PM

---

## **Issue #2: Model Bias (Synthetic Training Data)** ⚠️ NOT FIXED

### Symptom:
- Model predicts UP (class 1) 80%+ of the time
- Even negative sentiment → predicts UP
- Rarely predicts DOWN (class -1)

### Root Cause:
**Training labels based on sentiment, not actual market outcomes**

Training process (`train_on_real_data.py`):
```python
# How labels were created:
sentiment = row['sentiment_score']
credibility = row['source_credibility']
score = sentiment * credibility + random_noise

if score > 0.2: label = 1 (UP)
elif score < -0.2: label = -1 (DOWN)
else: label = 0 (NEUTRAL)
```

**Fundamental Flaws:**

1. **No connection to reality:**
   - Labels = f(sentiment), not f(actual price change)
   - Model learned "positive news → UP" not "price actually goes up"

2. **Ignores market prices:**
   - "Putin ousted?" at $0.50 = 50% implied probability
   - Real probability: ~1%
   - Market is 50X overpriced
   - Should predict DOWN → SELL
   - Instead: sees positive news → predicts UP → BUY

3. **Insufficient features:**
   - Only 8 features (sentiment, credibility, volume)
   - Missing: current market price, historical outcomes, price trends
   - Can't learn "market is wrong" patterns

4. **Distribution bias:**
   - Sentiment scores naturally skew positive (news is often optimistic)
   - More positive → more UP labels
   - Model learned to predict UP as default

### Why It's Wrong:
**Example:** "Will Putin be ousted in 2025?"
- Market price: $0.50 (50% probability)
- Real probability: ~1%
- Positive news about Russia → sentiment = +0.5
- Model: sentiment is positive → predict UP (1)
- Signal: BUY YES at $0.50
- **Correct:** Market is overpriced → predict DOWN (-1) → SELL (bet NO)
- **Result:** We bet YES on a 1% event at 50% price → guaranteed loss

### What Model Should Learn:
```
if market_price > model_probability + threshold:
    predict DOWN → SELL (market overpriced)
elif market_price < model_probability - threshold:
    predict UP → BUY (market underpriced)
else:
    predict NEUTRAL → HOLD (fair price)
```

### Solution:
**Must retrain on REAL outcome data:**
1. Collect 200+ resolved markets
2. Label: did price actually go up? (YES=1, NO=-1)
3. Add features: current_market_price, implied_probability
4. Model learns: "when is market wrong?" not "is news positive?"

**Status:** ⚠️ Needs 7-14 days data collection

---

## **Issue #3: Position Persistence Bug** ❌ CRITICAL

### Symptom:
- Original 10 positions: $245 deployed
- Bot restarted
- Opened 8 MORE positions: $181 deployed
- Total: 18 positions, but bot only knows about 8

### Root Cause:
**Position data stored in RAM only, not persisted to disk**

Architecture flaw:
```python
# trader.py:
class PolymarketTrader:
    def __init__(self):
        self.position_timers = {}  # In-memory dictionary
        self.risk_manager.active_positions = {}  # In-memory dictionary
        # NO save/load mechanism!

# On bot startup:
# ✅ Loads: data/paper_trading_balance.json (balance)
# ❌ Doesn't load: positions (no file exists!)
# Bot thinks: "I have 0 positions"
# Opens new positions without checking
```

### What Happened:
**Timeline:**
1. **1:38 PM** - Bot opens 10 positions ($245)
   - Stored in `self.position_timers` (RAM)
   - Risk manager: `active_positions = 10`

2. **10:00 PM** - I stop bot to fix signal generator
   - RAM cleared
   - Positions lost

3. **10:02 PM** - Bot restarts
   - `self.position_timers = {}` (empty!)
   - `active_positions = 0`
   - Balance loads: $755 ✅
   - Positions load: Nothing ❌

4. **10:03 PM** - Bot sees new events
   - "I have 0/10 positions, I can open more!"
   - Opens 8 new positions
   - Now: 18 total (10 orphaned + 8 tracked)

### Technical Details:
**What IS persisted:**
```python
# data/paper_trading_balance.json
{
  "balance": 573.57,  # ✅ Survives restart
  "last_updated": "2025-12-30T22:03:01"
}
```

**What is NOT persisted:**
```python
# self.position_timers (RAM only)
{
  "market_123": {
    "entry_time": datetime(...),
    "entry_price": 0.50,
    "side": "BUY",
    "size": 22.84
  },
  # Lost on restart! ❌
}
```

### Current State:
- **Balance:** $573.57 (accurate)
- **Original 10:** Orphaned, can't manage them
- **New 8:** Bot tracking these
- **Risk:** 42.6% deployed vs 24% intended (2X over limit)
- **On next restart:** Would lose track of the 8, open more...

### Why This Is Bad:
1. **Can't close positions:** Lost entry times/prices
2. **Exceeded limits:** 18 positions vs 10 max
3. **Higher risk:** 2X intended exposure
4. **Compounding:** Each restart creates more orphans
5. **Production killer:** Can't safely restart in live trading

### Solution:
**Implement position persistence database:**

```python
# Create positions.db
import sqlite3

def save_position(market_id, entry_time, entry_price, side, size):
    conn = sqlite3.connect('data/positions.db')
    conn.execute('''
        INSERT OR REPLACE INTO positions
        VALUES (?, ?, ?, ?, ?, 'OPEN')
    ''', (market_id, entry_time, entry_price, side, size))
    conn.commit()

def load_positions():
    conn = sqlite3.connect('data/positions.db')
    positions = conn.execute(
        'SELECT * FROM positions WHERE status = "OPEN"'
    ).fetchall()
    # Restore self.position_timers
    return positions
```

**Status:** ❌ Not implemented - bot currently stopped

---

## **Root Cause Summary**

| Issue | Root Cause Category | Severity | Fixed? |
|-------|-------------------|----------|--------|
| Signal Generator | **Implementation Bug** - Array indexing | High | ✅ Yes |
| Model Bias | **Architecture Flaw** - Wrong training approach | Critical | ❌ No |
| Position Persistence | **Architecture Flaw** - No state management | Critical | ❌ No |

---

## **Common Themes**

All three issues stem from:

### 1. **Insufficient Testing**
- Never tested signal distribution before deploying
- Never tested restart behavior
- Never validated on real outcomes
- Jumped to deployment too quickly

### 2. **Architecture Shortcuts**
- Used in-memory storage for production data
- Trained on synthetic labels (laziness)
- No validation/test sets
- No persistence layer

### 3. **Missing Domain Knowledge**
- Didn't understand Python indexing edge cases
- Didn't realize sentiment ≠ price movement
- Didn't think about restart scenarios
- Didn't validate against market prices

---

## **Why Paper Trading Saved Us**

If this were REAL money:
- **Issue #1:** Lost $150-200 betting on unlikely events (15-20%)
- **Issue #2:** Same losses compounding
- **Issue #3:** Lost track of $426 in positions, possibly can't close them

**Total potential loss:** $200-400 (20-40% of capital)

But since paper trading:
- $0 real money lost ✅
- Found 3 critical bugs ✅
- Can fix before risking capital ✅
- **Exactly what paper trading is for!**

---

## **The Path Forward**

### Must Fix (Blocking):
1. ✅ Signal generator bug - DONE
2. ❌ Position persistence - 2-3 hours work
3. ❌ Model retraining - 7-14 days data + 2 days work

### Should Fix (Important):
4. Add market price features
5. Implement proper backtesting
6. Add monitoring/alerting
7. Comprehensive error handling

### Nice to Have:
8. Dashboard
9. Multiple strategies
10. Advanced risk management

**Timeline to live:** 4-6 weeks following full roadmap

---

**The good news:** These are all fixable. The infrastructure works, we just found the holes before putting real money in them. 🎓
