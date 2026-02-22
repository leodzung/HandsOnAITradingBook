# News Sentiment Analysis - Quick Start Guide

## 5-Minute Setup

### Step 1: Install Dependencies

```bash
cd "09 DEX Screening Strategies"
pip install -r requirements_news_sentiment.txt
```

### Step 2: Run Demo (No API Keys Needed)

```bash
# Basic demo with mock data
python demo_news_sentiment.py

# Detailed analysis of specific token
python demo_news_sentiment.py --token BASEDOG
```

### Step 3: Get API Keys (Optional - for Production)

#### Free Tier (Recommended for Testing)
1. **CryptoPanic** - https://cryptopanic.com/developers/api/
   - Sign up for free account
   - Get API key (20 requests/min)
   - Cost: $0/month

2. **NewsAPI** - https://newsapi.org/register
   - Sign up for developer account
   - Get API key (1000 requests/day)
   - Cost: $0/month

3. **GitHub** - https://github.com/settings/tokens
   - Create personal access token
   - No special permissions needed (public repo access)
   - Cost: $0/month

#### Set Environment Variables

```bash
export CRYPTOPANIC_KEY="your_cryptopanic_key_here"
export NEWSAPI_KEY="your_newsapi_key_here"
export GITHUB_TOKEN="your_github_token_here"
```

Or create a `.env` file:
```
CRYPTOPANIC_KEY=your_cryptopanic_key_here
NEWSAPI_KEY=your_newsapi_key_here
GITHUB_TOKEN=your_github_token_here
```

### Step 4: Run with Live Data

```bash
# With API keys set
python demo_news_sentiment.py --live
```

---

## Usage Examples

### Example 1: Analyze Multiple Tokens

```python
from news_sentiment import NewsSentimentAnalyzer

# Initialize
analyzer = NewsSentimentAnalyzer(
    cryptopanic_key='YOUR_KEY',
    newsapi_key='YOUR_KEY',
    github_token='YOUR_TOKEN'
)

# Analyze token
metrics = analyzer.analyze_token(
    token_address='0x123...',
    token_symbol='TOKEN',
    social_links={
        'github': 'https://github.com/project/repo',
        'medium': '@project',
        'website': 'https://project.com'
    }
)

print(f"News Score: {metrics.total_score}/100")
print(f"Catalysts: {metrics.major_catalysts}")
```

### Example 2: Integration with Existing Strategy

```python
from strategy1_pool_scanner import PoolScannerStrategy
from news_sentiment import NewsSentimentAnalyzer

# Run pool scanner
scanner = PoolScannerStrategy(chains=['ethereum', 'base'])
scanner.run(max_cycles=1)
opportunities = scanner.get_ranked_opportunities()

# Add news sentiment
news_analyzer = NewsSentimentAnalyzer(...)

for opp in opportunities[:10]:  # Top 10
    news_metrics = news_analyzer.analyze_token(
        opp.token_address,
        opp.token_symbol,
        opp.social_links
    )

    # Combine scores
    base_score = opp.composite_score
    news_score = news_metrics.total_score
    final_score = (base_score * 0.7) + (news_score * 0.3)

    print(f"{opp.token_symbol}: {final_score:.1f} (base: {base_score:.1f}, news: {news_score:.1f})")
```

### Example 3: Get Detailed Report

```python
from news_sentiment import NewsSentimentAnalyzer, format_news_report

analyzer = NewsSentimentAnalyzer(...)
metrics = analyzer.analyze_token('0x123...', 'TOKEN')

# Print formatted report
print(format_news_report(metrics))
```

---

## Understanding the Scores

### Total Score (0-100)

| Score Range | Rating | Meaning |
|------------|--------|---------|
| 80-100 | EXCELLENT | Strong positive news, multiple catalysts |
| 65-79 | GOOD | Positive coverage, some catalysts |
| 50-64 | MODERATE | Limited news or mixed sentiment |
| 30-49 | LOW | Little coverage or negative news |
| 0-29 | VERY LOW | No news or very negative |

### Component Breakdown

- **Sentiment Score (0-40)**: Weighted sentiment of news articles
- **Velocity Score (0-25)**: Frequency and recency of news
- **GitHub Score (0-20)**: Development activity
- **Catalyst Score (0-15)**: Major announcements (audits, partnerships, funding)

### Major Catalysts

- **audit**: Security audit completion
- **partnership**: Major partnership announcement
- **funding**: Funding round raised
- **product_launch**: Product/mainnet launch

---

## Cost Comparison

### Free Tier (Testing)
- **Monthly Cost**: $0
- **Capacity**: ~30-40 tokens/day
- **APIs**: CryptoPanic Free + NewsAPI Free + GitHub Free
- **Best For**: Initial testing and validation

### Production Light ($29/month)
- **Monthly Cost**: $29
- **Capacity**: ~500 tokens/day
- **APIs**: CryptoPanic Pro ($19) + NewsAPI Free + GitHub Free
- **Best For**: Small-scale production

### Production Heavy ($518/month)
- **Monthly Cost**: $518
- **Capacity**: ~3000-5000 tokens/day
- **APIs**: CryptoPanic Pro ($19) + NewsAPI Business ($449) + GitHub Free
- **Best For**: Large-scale production

---

## Optimization Tips

### 1. Use Caching
```python
# Cache news results for 6 hours to reduce API calls
import redis
redis_client = redis.Redis()

def get_news_cached(token_symbol):
    cache_key = f"news:{token_symbol}"
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    news = analyzer.analyze_token(...)
    redis_client.setex(cache_key, 21600, json.dumps(news))  # 6 hours

    return news
```

### 2. Batch Processing
```python
# Process tokens in batches
tokens_to_analyze = [...]

for i in range(0, len(tokens_to_analyze), 10):
    batch = tokens_to_analyze[i:i+10]

    for token in batch:
        analyze_token(token)

    time.sleep(60)  # Rate limiting
```

### 3. Selective Analysis
```python
# Only analyze high-potential tokens
if base_score > 70:
    news_metrics = analyzer.analyze_token(...)
else:
    print(f"Skipping {token} (low base score)")
```

---

## Common Issues

### Issue: No News Found
**Cause**: Very new token, not yet covered by media
**Solution**: This is expected for 70-80% of early DEX tokens. Focus on tokens with coverage.

### Issue: API Rate Limits
**Cause**: Exceeding free tier limits
**Solution**:
1. Add caching (reduces calls by 80%)
2. Upgrade to paid tier
3. Spread analysis over longer time period

### Issue: GitHub Analysis Fails
**Cause**: No GitHub repository or private repo
**Solution**: Expected for many tokens. Score will be 0 for GitHub component.

---

## Next Steps

1. **Week 1**: Run demos, test with free tier
2. **Week 2**: Integrate with existing strategies
3. **Week 3**: Collect data, measure predictive power
4. **Week 4**: Optimize based on results
5. **Month 2+**: Scale to production

---

## Support & Documentation

- **Full Strategy**: See `NEWS_SENTIMENT_STRATEGY.md` for complete details
- **Code**: See `news_sentiment.py` for implementation
- **Demo**: See `demo_news_sentiment.py` for examples

---

## Advanced: Adding FinBERT (Better Sentiment)

For production, replace keyword-based sentiment with FinBERT:

```bash
pip install transformers torch
```

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class FinBERTAnalyzer:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")

    def analyze(self, text):
        inputs = self.tokenizer(text, return_tensors="pt", max_length=512, truncation=True)

        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

        labels = ['positive', 'negative', 'neutral']
        scores = predictions[0].tolist()

        return {
            'label': labels[scores.index(max(scores))],
            'score': max(scores) * 2 - 1  # Convert to -1 to 1 range
        }
```

---

**Ready to start? Run `python demo_news_sentiment.py` now!**
