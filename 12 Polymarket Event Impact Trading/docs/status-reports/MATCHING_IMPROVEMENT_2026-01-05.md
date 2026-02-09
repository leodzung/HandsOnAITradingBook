# Matching Quality Improvement - January 5, 2026, 12:03 PM

## Change Implemented

**Modified:** `event_detector.py:285`  
**Change:** `min_keyword_overlap: int = 1` → `min_keyword_overlap: int = 3`  
**Bot Restarted:** 12:03 PM PST (PID 48442)

---

## Immediate Results

### Before (min_keyword_overlap = 1)
**Last cycle before change:** 3:02 AM
- **Events found:** 17
- **Markets matched:** 22
- **Match ratio:** 1.3 markets per event
- **Example bad match:** "The China Show" → 10+ NFL markets

### After (min_keyword_overlap = 3)
**First cycle after change:** 12:03 PM
- **Events found:** 23
- **Markets matched:** 2 ✅
- **Match ratio:** 0.09 markets per event
- **Reduction:** 91% fewer matches (22 → 2)

---

## Quality Assessment

### ✅ Success: Massive Noise Reduction

**91% reduction in matches** means we've eliminated most of the "China Show → NFL" type false positives.

### ⚠️ Remaining Issue: Homonym Matching

**Match Found:**
- **Event:** "UK Government Opens Consultation on Expanding Bills Market"
- **Market:** "Will the Bills win the AFC Championship?"
- **Problem:** "bills" (UK government treasury bills) ≠ "Bills" (Buffalo Bills NFL team)
- **Root Cause:** Case-insensitive keyword matching without context

**Shared Keywords (likely):**
- "bills" / "Bills"
- "market"
- "championship" (if in description)
- "win"
- "2025" or "december"

### Signal Quality

**Confidence scores:** 39-43% (still low)
- **Brazil inflation market:** 43% (UK bills → Brazil inflation is weak relevance)
- **Bills AFC Championship:** 39% (homonym false match)

**Model is still correctly identifying these as low-quality signals.**

---

## Next Steps

### Option 1: Add Case Sensitivity for Proper Nouns
**Problem:** "bills" (common noun) matches "Bills" (proper noun)  
**Solution:** Preserve case for capitalized words in matching  
**Complexity:** Medium (requires keyword extraction changes)

### Option 2: Add Stopword/Common Word Filtering
**Problem:** Generic words like "market", "will", "win" creating false matches  
**Solution:** Filter out top 100 most common English words from matching  
**Complexity:** Low (simple word list filter)

### Option 3: Increase Threshold to 4-5 Keywords
**Impact:** Further reduce matches, but risk missing valid ones  
**Trade-off:** Higher precision, lower recall

### Option 4: Implement Relevance Score Filter (Recommended)
**As documented in analysis:** Add `score_event_market_relevance() >= 0.3` filter  
**Expected impact:** Eliminate "bills/Bills" type homonym matches  
**Complexity:** Low (5-minute change)

---

## Recommendation

**Implement Option 4 next** (relevance score filter). This will:
1. Keep the 3-keyword minimum (good baseline)
2. Add semantic similarity check
3. Filter out homonym matches
4. Minimal code change

**Expected outcome after Option 4:**
- Matches: 2 → 1 or 0 (eliminate Bills homonym)
- Confidence: 39-43% → 45-60% (if we get good matches)
- Quality: High precision matches only

---

## Monitoring Plan

**Track for 24 hours:**
- Average matches per cycle
- Confidence score distribution
- Any BUY/SELL signals generated
- False positive rate (manual review)

**Success Criteria:**
- Match count: 0-5 per cycle (down from 22)
- Confidence: 50%+ average (up from 42-55%)
- At least 1 trade in 48 hours (if market conditions permit)

---

*Change implemented: January 5, 2026, 12:03 PM PST*  
*Status: MONITORING*  
*Next review: January 6, 2026, 12:00 PM PST*
