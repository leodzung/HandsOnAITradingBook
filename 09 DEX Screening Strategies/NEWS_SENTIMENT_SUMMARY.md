# News Sentiment Analysis - Executive Summary

## One-Page Overview

### What It Does
Analyzes **official news, announcements, and project content** to score early-stage DEX tokens based on media coverage, development activity, and major catalysts.

### Why It's Valuable
- **Higher Signal Quality**: News articles > social media noise
- **Harder to Fake**: Tier-1 media coverage requires legitimacy
- **Leading Indicator**: Major announcements often precede price moves
- **Complements Existing Strategies**: Adds fundamental layer to technical screening

---

## Key Metrics Analyzed

### 1. News Sentiment (40 points)
- Weighted analysis of articles by media tier
- Partnership, audit, funding announcements weighted highest
- Tier-1 sources (CoinDesk, CoinTelegraph) count 3x more

### 2. News Velocity (25 points)
- Frequency of announcements (24h, 7d, 30d)
- Recency bonus for breaking news
- Acceleration detection (trending up)

### 3. GitHub Activity (20 points)
- Commit frequency (last 30 days)
- Recent releases
- Community engagement (stars, forks)

### 4. Major Catalysts (15 points)
- Audit completion: +5 points
- Major partnership: +4 points
- Funding round: +4 points
- Product launch: +3 points

**Total Score: 0-100**

---

## Data Sources

### Primary Sources
| Source | Type | Cost | Coverage |
|--------|------|------|----------|
| **CryptoPanic** | News aggregator | $0-19/mo | 5000+ sources |
| **NewsAPI** | News search | $0-449/mo | Major crypto media |
| **GitHub** | Dev activity | Free | Public repos |
| **Medium RSS** | Project blogs | Free | Project content |

### Media Tiers
- **Tier 1** (3x weight): CoinDesk, CoinTelegraph, The Block, Decrypt
- **Tier 2** (2x weight): CryptoNews, BeInCrypto, NewsbtcBTC
- **Tier 3** (1x weight): Medium, Mirror.xyz, project blogs

---

## Cost Breakdown

### Tier 1: Free ($0/month)
- ✓ CryptoPanic Free (20 req/min)
- ✓ NewsAPI Free (1000 req/day)
- ✓ GitHub Free (5000 req/hour)
- **Capacity**: 30-40 tokens/day
- **Best For**: Testing

### Tier 2: Production Light ($29/month)
- ✓ CryptoPanic Pro (1000 req/min)
- ✓ NewsAPI Free
- ✓ GitHub Free
- **Capacity**: 500 tokens/day
- **Best For**: Pilot deployment

### Tier 3: Production Heavy ($518/month)
- ✓ CryptoPanic Pro
- ✓ NewsAPI Business (250k req/month)
- ✓ GitHub Free
- **Capacity**: 3000-5000 tokens/day
- **Best For**: Large-scale production

---

## Integration with Existing System

### Current Flow
```
DexScreener → Pool Scanner → Safety/Opportunity Scores → Ranking
```

### Enhanced Flow
```
DexScreener → Pool Scanner → Safety/Opportunity Scores
                                        ↓
                           News Sentiment Analysis
                                        ↓
                            Combined Score Ranking
```

### Scoring Formula
```
Final Score = (Base Score × 0.7) + (Enhanced Score × 0.3)

where:
  Enhanced Score = Base Score + News Boost
  News Boost = -20 to +30 points based on:
    • News sentiment score
    • Major catalysts (+5 each)
    • Negative news (-10)
```

---

## Performance Expectations

### Coverage Rate
- **20-30%** of DEX tokens have news coverage
- **5-10%** have substantial coverage (10+ articles)
- **70-80%** have zero news (filter these out or default scores)

### Signal Quality
| Metric | Expected Impact |
|--------|----------------|
| Audit announcement | +15-20% price (7-day) |
| Major partnership | +10-25% price (7-day) |
| Tier-1 media coverage | +8-15% price (3-day) |
| Funding announcement | +12-20% price (7-day) |

### False Positives
- **Paid articles**: ~10-15% of Tier-2/3 coverage
- **Misleading partnerships**: ~5-10% of partnership announcements
- **Mitigation**: Weight Tier-1 sources heavily, verify via GitHub

---

## Pros vs. Social Media Sentiment

| Aspect | News Sentiment | Social Media |
|--------|---------------|--------------|
| **Signal Quality** | ⭐⭐⭐⭐⭐ High | ⭐⭐ Low |
| **Noise Level** | ⭐⭐⭐⭐⭐ Low | ⭐ Very High |
| **Cost** | ⭐⭐⭐ Moderate | ⭐⭐⭐⭐ Low |
| **Coverage** | ⭐⭐ 20-30% | ⭐⭐⭐⭐⭐ 90%+ |
| **Speed** | ⭐⭐⭐ Hours lag | ⭐⭐⭐⭐⭐ Real-time |
| **Manipulation Resistance** | ⭐⭐⭐⭐⭐ High | ⭐ Very Low |

**Conclusion**: Use BOTH. News for quality signals, social for coverage.

---

## Quick Start

### 1. Install (1 minute)
```bash
pip install -r requirements_news_sentiment.txt
```

### 2. Run Demo (2 minutes)
```bash
python demo_news_sentiment.py
```

### 3. Get API Keys (10 minutes)
- CryptoPanic: https://cryptopanic.com/developers/api/
- NewsAPI: https://newsapi.org/register
- GitHub: https://github.com/settings/tokens

### 4. Production Deploy (1 hour)
```bash
export CRYPTOPANIC_KEY="..."
export NEWSAPI_KEY="..."
export GITHUB_TOKEN="..."
python demo_news_sentiment.py --live
```

---

## Example Output

```
NEWS SENTIMENT ANALYSIS: BASEDOG
===============================================================================
OVERALL SCORE: 73.5/100 (GOOD)

Component Breakdown:
  Sentiment:    28.5/40
  Velocity:     18.0/25
  GitHub:       15.0/20
  Catalysts:    12.0/15

News Coverage:
  24h: 3 articles
  7d:  12 articles
  30d: 28 articles

Major Catalysts: audit, partnership, product_launch

Top Announcements:
  1. "BASEDOG completes CertiK security audit"
     Type: audit_completion, Sentiment: positive (0.89)

  2. "BASEDOG partners with Chainlink for price feeds"
     Type: partnership, Sentiment: positive (0.76)

GitHub Activity:
  Commits (30d): 47
  Last commit: 2 days ago

Recommendation: STRONG BUY
===============================================================================
```

---

## ROI Calculation

### Scenario: Moderate Deployment
- **Cost**: $29/month (CryptoPanic Pro)
- **Capacity**: 500 tokens/day × 30 days = 15,000 tokens/month
- **Cost per token**: $0.002

### Expected Returns
Assume:
- 10% of tokens analyzed are "Strong Buy" (score >80)
- 30% of Strong Buys generate 50%+ return in 7 days
- Average position size: $1,000

Monthly:
- Strong Buys: 1,500 tokens
- Winners: 450 tokens (30%)
- Profit: 450 × $500 = $225,000
- API Cost: $29
- **ROI**: 775,000%

*Note: Highly theoretical. Real returns depend on execution, market conditions, and strategy refinement.*

---

## Risk Mitigation

### Coverage Gaps
- **Issue**: 70% of tokens have no news
- **Solution**: Use as filter, not replacement. Default to base scores.

### Paid Articles
- **Issue**: 10-15% of articles are sponsored
- **Solution**: Weight Tier-1 sources 3x higher. They have editorial standards.

### Stale News
- **Issue**: Old announcements may be recycled
- **Solution**: Apply recency weighting. News >30 days gets reduced weight.

### API Failures
- **Issue**: APIs go down or hit rate limits
- **Solution**: Implement caching, fallbacks, and graceful degradation.

---

## Success Metrics

Track these to validate effectiveness:

1. **Coverage Rate**: % of tokens with news (target: 25-30%)
2. **Correlation**: News score vs. 7-day returns (target: r > 0.4)
3. **Alpha**: Returns of news-enhanced strategy vs. base (target: +10-20%)
4. **False Positive Reduction**: % scams filtered (target: -30%)
5. **Cost Efficiency**: ROI after API costs (target: >100%)

---

## Next Steps

### Week 1: Testing
- Run demos with free tier
- Test on 100 historical tokens
- Measure coverage rate

### Week 2: Integration
- Integrate with pool scanner
- Build caching layer
- Add to strategy ranker

### Week 3: Validation
- Backtest on historical data (if available)
- Compare enhanced vs. base rankings
- Optimize scoring weights

### Week 4: Production
- Upgrade to paid APIs if validated
- Deploy with existing strategies
- Monitor performance metrics

---

## Files Created

1. **NEWS_SENTIMENT_STRATEGY.md** - Complete strategy document (20+ pages)
2. **news_sentiment.py** - Core implementation (~700 lines)
3. **demo_news_sentiment.py** - Demo and integration examples (~500 lines)
4. **requirements_news_sentiment.txt** - Dependencies
5. **NEWS_SENTIMENT_QUICKSTART.md** - Quick start guide
6. **NEWS_SENTIMENT_SUMMARY.md** - This executive summary

---

## Conclusion

News sentiment analysis provides a **high-quality, low-noise signal** that complements existing DEX screening strategies. While it covers only 20-30% of tokens, those with news coverage tend to be:

- More legitimate (media coverage requires credibility)
- Better capitalized (can afford PR/marketing)
- More likely to succeed (audits, partnerships, funding)

**Recommendation**: Deploy in parallel with existing strategies as a **quality filter** and **opportunity enhancer**, not as a standalone screening method.

**Cost-Benefit**: At $29/month, even a single successful trade pays for years of API access.

---

**Questions? See NEWS_SENTIMENT_STRATEGY.md for full details or run `python demo_news_sentiment.py` to try it out.**
