# Improvement Checklist - Polymarket Trading System

## Completed ✅

### 2026-02-14: Short Expiry Bot Price History Fix
- ✅ Added PriceTracker integration to short expiry bot
- ✅ Pass price_history to feature extractor (enables momentum signals)
- ✅ Use PriceFetcher for all price tracking (real-time CLOB data)
- ✅ Relaxed price range filters (0.02-0.98 instead of 0.05-0.95)
- ✅ Disabled arbitrage rule (never triggers in current market conditions)
- ✅ Updated memory: ALWAYS use PriceFetcher for ANY price data

---

## Future Enhancements 🔮

### Price Tracking

#### **Separate YES/NO Price Tracking** (Priority: Medium)
**Current State:**
- Only tracking YES price as market probability proxy
- Works for momentum signals but loses NO-side information

**Future Improvement:**
- Track both YES and NO prices separately
- Use `{market_id}_YES` and `{market_id}_NO` as separate tracking IDs
- Benefits:
  - Better momentum detection for both sides
  - Can detect YES/NO divergence (unusual spread behavior)
  - More accurate for markets where NO is the liquid side

**Implementation Notes:**
```python
# Future approach:
self.price_tracker.track_price(f"{market_id}_YES", entry_prices.yes_price)
self.price_tracker.track_price(f"{market_id}_NO", entry_prices.no_price)

# Feature extraction would need to handle both:
price_history_yes = self.price_tracker.get_price_history(f"{market_id}_YES", hours=24)
price_history_no = self.price_tracker.get_price_history(f"{market_id}_NO", hours=24)
```

**Effort:** ~2 hours (PriceTracker changes + feature extractor updates)

---

### Signal Generation

#### **ML Model Integration** (Priority: High)
**Status:** Planned (Phase 2)
- GBM model with walk-forward validation
- Train on historical short-expiry market outcomes
- Features: time decay, momentum, microstructure, volatility

#### **Cross-Market Correlation Signals** (Priority: Medium)
**Status:** Planned (Phase 3)
- Detect when related markets diverge (e.g., "BTC >$70k" vs "BTC >$72k")
- Correlation-based mean reversion signals

---

### Risk Management

#### **Dynamic Position Sizing** (Priority: Medium)
**Current:** Fixed position sizes by bucket (ultra_short: $50, short: $75, medium: $100)
**Future:** Kelly Criterion or volatility-adjusted sizing

#### **Trailing Stop Loss** (Priority: Low)
**Current:** Fixed stop-loss percentages
**Future:** Trail profitable positions to lock in gains

---

### Market Discovery

#### **Ultra-Short Bucket Opportunities** (Priority: High)
**Current:** Ultra-short bucket (0-24h) finds 0 markets
**Issue:** All markets rejected by quality filters
**Solution:**
- Investigate why all ultra-short markets fail filters
- May need separate filter thresholds for ultra-short

---

### Performance Monitoring

#### **Trade Analytics Dashboard** (Priority: Medium)
- Win rate by bucket, signal type, time-to-expiry
- Slippage analysis (actual vs estimated)
- Market selection quality metrics

#### **Backtesting Framework** (Priority: High)
- Simulate historical performance using price_tracking.db
- Validate signal logic before deploying

---

## Backlog 📝

- [ ] Multi-exchange arbitrage (Polymarket vs prediction market competitors)
- [ ] News sentiment integration (crypto news → short-expiry crypto markets)
- [ ] Market maker detection (avoid toxic flow)
- [ ] Gas fee optimization (if switching to real trading)

---

## Notes

**Last Updated:** 2026-02-14
**Active Bots:** Event-based, Price-level, Short-expiry
**Paper Trading Balance:** Event=$1000, Price-level=$500, Short-expiry=$470
