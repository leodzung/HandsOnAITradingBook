# Signal Quality Analysis - January 5, 2026

## Executive Summary

**Problem:** Event-Based Trader generates consistent HOLD signals with low confidence (42-55%), resulting in zero trades since restart on Jan 4, 10:03 AM.

**Root Cause:** Overly broad keyword-based event-market matching creates weak, irrelevant signal pairs that the ML model correctly identifies as low-quality.

**Impact:** Bot is working correctly (not making bad trades) but missing potential opportunities due to noise in the matching pipeline.

---

## Detailed Findings

### 1. Event-Market Matching Issues 🚨

#### Current Matching Algorithm
Location: `event_detector.py:283-321`

```python
def match_events_to_markets(self, events, markets, min_keyword_overlap: int = 1):
    # Match if ANY 1+ keywords overlap between event and market
    for event in events:
        event_keywords = set([k.lower() for k in event.keywords])
        for market_id, m_keywords in market_keywords.items():
            overlap = len(event_keywords & m_keywords)
            if overlap >= min_keyword_overlap:  # Just 1 word!
                matches[market_id].append(event)
```

**Problem:** `min_keyword_overlap = 1` means a SINGLE shared word creates a match.

#### Examples of Bad Matches

**Example 1: Generic Video Title → NFL Markets**
- **Event:** "The China Show 1/5/2026 (Video)"
- **Matched Markets:**
  - "Will the Chargers win the AFC Championship?"
  - "Will the Broncos win the AFC Championship?"
  - "Will the Texans win the AFC Championship?"
  - ...and 10+ more NFL markets
- **Likely Shared Keyword:** "show", "championship", "2026", or similar generic terms
- **Relevance:** Zero - China geopolitical video has nothing to do with NFL

**Example 2: Stock Market Article → GDP Market**
- **Event:** "Wall Street Bulls Eye Milder Gains in 2026 After 3-Year Surge"
- **Matched Market:** "Negative GDP growth in 2025?"
- **Likely Shared Keywords:** "2026", "2025", "year", "growth"
- **Signal Confidence:** 42% (model correctly identifies weak relevance)
- **Relevance:** Low - article is about stock market optimism, not GDP contraction

**Example 3: Turkey Inflation → US GDP**
- **Event:** "Turkey's Inflation Slowed Further, Supporting 2026 Rate Cuts"
- **Matched Market:** "Negative GDP growth in 2025?"
- **Likely Shared Keywords:** "inflation", "growth", "2026", "2025"
- **Relevance:** Weak - Turkish monetary policy has limited direct impact on US GDP

### 2. Confidence Score Analysis 📊

#### How Confidence is Calculated
Location: `models.py:404-406`

```python
probabilities = self.model.predict_proba(features)[0]  # [P(DOWN), P(NEUTRAL), P(UP)]
confidence = np.max(probabilities)  # Take the highest
```

**Current Range:** 42-55% (very low)

**What This Means:**
- 50% confidence = model predicts all 3 outcomes equally likely (random)
- 42-55% = model is slightly better than random but very uncertain
- Target: 60%+ for trades (configured threshold)

**Example Probability Distributions:**
```
42% confidence: [0.42, 0.38, 0.20]  → Slight lean to DOWN, but uncertain
50% confidence: [0.50, 0.30, 0.20]  → Moderately confident in DOWN
55% confidence: [0.55, 0.30, 0.15]  → Reasonably confident in DOWN
```

### 3. Model Behavior ✅

**The model is working correctly!** It's assigning low confidence to weak event-market pairs, which is exactly what we want.

**Evidence:**
- Weak matches (China Show → NFL) get ~50% confidence
- Slightly better matches (Wall Street → GDP) get ~42-55%
- No false high-confidence signals on irrelevant news

**This indicates:**
1. The retrained model (40 samples) learned that most matched pairs are noise
2. The model needs strong, relevant event-market correlations to predict with confidence
3. The bottleneck is upstream (matching quality), not the model

### 4. Feature Tracking Issue 🔧

**Problem:** Tracked events in database have NULL sentiment scores.

```sql
SELECT sentiment_score, sentiment_magnitude
FROM tracked_events
WHERE completed = 1
LIMIT 5;

-- Result: All NULL
```

**Impact:**
- We have 604 resolved outcomes
- But missing the input features (sentiment, overlap, etc.)
- Cannot retrain model with this data

**Root Cause:** `price_tracker.py` isn't saving features when tracking events.

---

## Root Causes Identified

### 🎯 Primary Issue: Keyword Matching Too Broad

**Current:** 1 shared word = match
**Result:** Generic news matches unrelated markets
**Examples:**
- "show" → Championship markets
- "2026" → Any market mentioning a year

### 🎯 Secondary Issue: No Semantic Understanding

**Current:** Simple keyword overlap
**Missing:**
- Understanding that "China Show" is unrelated to NFL
- Understanding that "Wall Street gains" doesn't predict "GDP contraction"
- Context awareness of relevance

### 🎯 Tertiary Issue: Feature Tracking Incomplete

**Current:** Tracking outcomes but not input features
**Impact:** Cannot analyze which feature patterns lead to accurate predictions

---

## Metrics & Statistics

### Event Discovery (Last 24 Hours)
- **Events found per cycle:** 0-17 (highly variable)
- **Markets matched:** 22-29
- **Average matches per event:** ~1.5-3 markets

### Signal Generation (Since Restart)
- **Total signals generated:** ~200+
- **BUY signals:** 0 (all below 60% threshold)
- **SELL signals:** 0 (all below 60% threshold)
- **HOLD signals:** 100% (42-55% confidence)
- **Trades executed:** 0

### Confidence Distribution
```
40-45%: ████████████████ (most common)
45-50%: ████████████
50-55%: ████████
55-60%: ██
60%+:   (none)
```

---

## Recommendations (Prioritized)

### ⚡ Immediate: Tighten Matching Criteria

**Change:** Increase `min_keyword_overlap` from 1 to 3

```python
# In event_detector.py:285
def match_events_to_markets(self, events, markets,
                           min_keyword_overlap: int = 3):  # Was 1
```

**Expected Impact:**
- Fewer but higher-quality matches
- Reduce noise from generic words
- Increase average confidence by 5-10%

**Risk:** May reduce match count significantly (need monitoring)

---

### 🎯 Short-Term: Add Relevance Scoring

**Change:** Use existing `score_event_market_relevance()` method to filter weak matches

```python
# In trader.py, after matching
for market_id, events in matches.items():
    for event in events:
        relevance = matcher.score_event_market_relevance(event, market)
        if relevance < 0.3:  # Filter out weak matches
            continue
        # Process signal...
```

**Expected Impact:**
- Filter out "China Show" → NFL type matches
- Improve signal quality without changing core matching

---

### 📊 Medium-Term: Fix Feature Tracking

**Change:** Modify `price_tracker.py` to save features when tracking

**Location:** `price_tracker.py:track_event()`

**Add:**
```python
def track_event(self, event, market, features: Dict):
    # Save features to database
    cursor.execute('''
        INSERT INTO tracked_events (
            ...,
            sentiment_score,
            sentiment_magnitude,
            source_credibility,
            ...
        ) VALUES (?, ?, ?, ...)
    ''', (..., features['sentiment_score'], features['sentiment_magnitude'], ...))
```

**Expected Impact:**
- Enable retraining on 604+ resolved outcomes
- Identify which features predict well
- Improve model over time

---

### 🔬 Long-Term: Semantic Event-Market Matching

**Change:** Use transformer embeddings for relevance

**Approach:**
1. Encode event text with sentence-transformers
2. Encode market question with same model
3. Use cosine similarity for matching
4. Set threshold (e.g., 0.6) for match

**Expected Impact:**
- Understand "China Show" is unrelated to NFL
- Match based on meaning, not just keywords
- Major quality improvement

---

## Action Plan

### Phase 1: Quick Wins (This Week)
1. ✅ **Document findings** (this file)
2. ⚠️ **Increase keyword overlap to 3** (2-minute change)
3. ⚠️ **Add relevance score filter ≥0.3** (5-minute change)
4. ⚠️ **Restart bot and monitor** (observe confidence changes)

### Phase 2: Data Collection (Next Week)
1. ⚠️ **Fix feature tracking** (30-minute change)
2. ⚠️ **Let bot run 7 days** (collect features with outcomes)
3. ⚠️ **Retrain on real data** (100+ samples expected)

### Phase 3: Advanced Matching (Week 3+)
1. ⚠️ **Implement semantic matching** (2-hour change)
2. ⚠️ **A/B test keyword vs semantic** (compare quality)
3. ⚠️ **Fine-tune thresholds** (optimize for precision)

---

## Expected Outcomes

### After Phase 1 (Keyword Overlap = 3)
- **Match count:** 22 markets → 8-12 markets (50-60% reduction)
- **Match quality:** Significant improvement
- **Confidence:** 42-55% → 50-65% (estimated)
- **Trade frequency:** 0 → 1-3 per week (conservative estimate)

### After Phase 2 (Real Data Retraining)
- **Model accuracy:** 50% → 65-75% (based on real outcomes)
- **Confidence calibration:** Better aligned with actual win rate
- **Trade frequency:** 1-3 per week → 3-5 per week

### After Phase 3 (Semantic Matching)
- **Match quality:** High precision (minimal false matches)
- **Confidence:** 60-80% for most signals
- **Trade frequency:** 5-10 per week
- **Win rate:** 60-70% (target)

---

## Conclusion

**The bot is healthy and working correctly.** Low confidence scores reflect poor input quality (overly broad matching), not model failure.

**The model is doing its job:** Filtering out weak signals to avoid bad trades.

**The fix is upstream:** Improve event-market matching quality to feed the model better signals.

**Next step:** Implement Phase 1 changes (5-minute fix) and observe impact over 2-3 days.

---

*Analysis completed: January 5, 2026, 3:30 AM*
*Analyst: Claude Sonnet 4.5*
*Status: READY FOR IMPLEMENTATION*
