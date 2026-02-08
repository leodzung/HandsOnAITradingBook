# Polymarket Event Impact Trading System

An AI-driven trading system for Polymarket prediction markets that detects breaking news/events and predicts their impact on market prices.

## Strategy Overview

**Strategy #2: Deep Learning Event Impact Forecasting**

This system implements a machine learning approach to trading Polymarket prediction markets:

1. **Event Detection** - Monitors news sources (RSS, NewsAPI, Twitter) for breaking events
2. **Event Matching** - Matches detected events to relevant Polymarket markets
3. **Feature Extraction** - Extracts features from:
   - Event sentiment and credibility
   - Market price history and volatility
   - Order book depth and spread
   - Volume patterns
4. **ML Prediction** - Predicts price movement direction (up/down/neutral)
5. **Trade Execution** - Executes trades with confidence-based position sizing
6. **Risk Management** - Enforces position limits and stop losses

## Why This Strategy?

- **Fast Execution Edge**: Acts on news within seconds-minutes
- **Scalable**: Works across all market categories (politics, crypto, sports)
- **Data-Driven**: Uses ML instead of manual predictions
- **Lower Risk**: Diversifies across many small trades vs. few large bets
- **Testable**: Can backtest on historical data

## Repository Structure

```
12 Polymarket Event Impact Trading/
├── deploy.sh                  # ⭐ Deployment script (use this!)
├── trader.py                  # Event-based trading bot
├── trader_price_levels.py     # Price-level trading bot
├── arbitrage_bot.py           # Cross-market arbitrage bot
├── polymarket_client.py       # Polymarket API integration
├── event_detector.py          # News/event detection system
├── feature_extractor.py       # Feature engineering pipeline
├── position_manager.py        # Position persistence & tracking
├── models.py                  # ML models for prediction
├── backtester.py              # Backtesting framework
├── config.json                # Event trader config
├── config_price_levels.json   # Price-level trader config
├── requirements.txt           # Python dependencies
├── research.ipynb             # Jupyter notebook for research
├── data/                      # Databases & state files
│   ├── positions.db           # Event trader positions
│   ├── positions_price_level.db  # Price-level positions
│   └── paper_trading_*.json   # Balance tracking
├── backups/                   # Log backups (created by deploy.sh)
├── trading.out                # Event trader logs
├── trading_price_levels.out   # Price-level trader logs
├── arbitrage.out              # Arbitrage bot logs
└── README.md                  # This file
```

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Create config file
python config.py
```

### 2. Configure API Keys

Edit `config.json` and add your API keys:

```json
{
  "polymarket_api_key": "YOUR_API_KEY",
  "news_api_key": "YOUR_NEWS_API_KEY",
  "paper_trading": true
}
```

**Required API Keys:**
- **Polymarket**: Contact Polymarket for API access
- **NewsAPI**: Get free key at https://newsapi.org (500 requests/day)

**Optional:**
- **Twitter API**: For social sentiment (requires approval)

### 3. Train Model

Open and run `research.ipynb`:

```bash
jupyter notebook research.ipynb
```

This notebook will:
- Generate synthetic training data (or use your real data)
- Train multiple ML models
- Run backtests
- Save the best model

### 4. Deployment (IMPORTANT)

**Always use the deployment script when starting or restarting bots:**

```bash
cd "12 Polymarket Event Impact Trading"

# Check current status
./deploy.sh status

# Deploy specific bot
./deploy.sh price-level    # or: ./deploy.sh pl
./deploy.sh event          # or: ./deploy.sh ev
./deploy.sh arbitrage      # or: ./deploy.sh arb
./deploy.sh both           # Deploy price-level + event traders
./deploy.sh all            # Deploy all three bots

# Reset positions (use after code changes that affect position storage)
./deploy.sh reset          # Clear all positions, reset balances
./deploy.sh reset-and-deploy  # Reset + deploy both traders
```

**What the deploy script does:**
1. Backs up current logs to `backups/` directory
2. Gracefully stops the running process
3. Shows current database state (open positions, balance)
4. Starts new process with `nohup`
5. Verifies successful startup

**When to redeploy:**
- After ANY code change to `trader.py` or `trader_price_levels.py`
- After changes to config files (`config.json`, `config_price_levels.json`)
- After database resets or position clearing
- After changes to imported modules (`polymarket_client.py`, `position_manager.py`, etc.)

### 5. Paper Trading

Test the strategy without real money:

```bash
# Edit config.json: "paper_trading": true
./deploy.sh both
```

Monitor performance for 1-2 weeks before going live.

### 6. Live Trading

Once confident:

```bash
# Edit config.json: "paper_trading": false
./deploy.sh both
```

**WARNING**: Start with small position sizes!

## Configuration

Key parameters in `config.json`:

### Trading Parameters
- `min_confidence`: Minimum model confidence to trade (0.65 = 65%)
- `min_expected_return`: Minimum expected return to trade (0.03 = 3%)
- `max_position_size`: Maximum $ per trade (default: $100)
- `max_positions`: Maximum concurrent positions (default: 10)
- `hold_time_hours`: How long to hold positions (default: 24)

### Risk Management
- `max_daily_loss`: Maximum loss before stopping (default: $500)
- `paper_trading`: Set to `false` for real trading

### Market Filters (Applied at API Level for Efficiency)
- `min_market_volume`: Only trade markets with >$X volume (default: $1000)
- `min_liquidity`: Minimum market liquidity (price-level trader only, default: $500)
- `min_hours_to_expiry`: Avoid markets expiring too soon (event trader, default: 2 hours)
- `max_hours_to_expiry`: Avoid markets too far in future (event trader, default: 8760 hours = 365 days)
- `min_days_to_expiry`: Minimum days to expiry (price-level trader, default: 1 day)
- `max_days_to_expiry`: Maximum days to expiry (price-level trader, default: 365 days)

**Note**: As of 2026-02-08, the system can discover **27,523+ active markets** on Polymarket using enhanced API filtering.

## How It Works

### 1. Event Detection

The system monitors multiple news sources:

```python
# RSS Feeds (free, no API key)
- Bloomberg Markets
- CoinDesk
- Reuters

# NewsAPI (requires key)
- Searches for keywords
- Filters by credibility

# Twitter (optional)
- Track trending topics
- Sentiment analysis
```

### 2. Feature Extraction

For each event + market pair:

**Event Features:**
- Sentiment score (-1 to 1)
- Source credibility (0 to 1)
- Keyword overlap with market
- Time since published

**Market Features:**
- Current price
- Price volatility (1h, 24h)
- Volume trend
- Order book spread
- Bid-ask imbalance

### 3. ML Prediction

Models available:
- **Random Forest** (default) - Fast, interpretable
- **Gradient Boosting** - Higher accuracy
- **Logistic Regression** - Simple baseline
- **Ensemble** - Combines multiple models

Output: Prediction + Confidence
```
Prediction: 1 (up), 0 (neutral), -1 (down)
Confidence: 0.75 (75% certain)
```

### 4. Signal Generation

```python
if confidence > min_confidence:
    if prediction == UP and price < 0.95:
        signal = BUY
    elif prediction == DOWN and price > 0.05:
        signal = SELL
    else:
        signal = HOLD
```

### 5. Position Sizing

Uses confidence-based Kelly criterion:

```python
position_size = base_size * (confidence - 0.5) * 2
```

Higher confidence → Larger position

### 6. Risk Management

**Position Limits:**
- Max 10 concurrent positions (diversification)
- Max $100 per position (limit single-trade risk)

**Stop Loss:**
- Daily loss limit: $500
- Bot stops trading if hit

**Time-Based Exit:**
- Closes positions after 24 hours
- Avoids prolonged exposure

## Backtesting

The `backtester.py` module simulates historical trading:

```python
# Run backtest
backtester = Backtester(
    initial_capital=10000,
    position_size=100,
    hold_time_hours=24
)

results = backtester.run_backtest(signals_df, price_data)
```

**Metrics Calculated:**
- Win rate
- Profit factor
- Sharpe ratio
- Maximum drawdown
- Total return

## Performance Tracking

The system tracks all predictions:

```python
tracker = ModelPerformanceTracker()
tracker.record_prediction(
    prediction=1,
    actual=1,
    confidence=0.75,
    market_id='market_123'
)

stats = tracker.get_statistics()
# Returns: accuracy, accuracy by class, confidence distribution
```

## Example Workflow

1. **News breaks**: "Trump announces 2028 candidacy"
2. **Event detected**: NewsAPI picks it up within 30 seconds
3. **Market matched**: "Will Trump run in 2028?" (currently $0.35)
4. **Features extracted**:
   - Sentiment: +0.8 (positive)
   - Source: Bloomberg (credible)
   - Market volatility: Low
5. **Model predicts**: UP with 78% confidence
6. **Signal generated**: BUY at $0.35
7. **Trade executed**: $100 position (285 shares)
8. **Price moves**: $0.35 → $0.42 in 2 hours
9. **Position closed**: Sell at $0.42 for $20 profit

## Advanced Usage

### Using FinBERT for Sentiment

For better sentiment analysis:

```bash
pip install transformers torch
```

Edit `config.json`:
```json
{
  "use_transformers": true
}
```

### Custom Event Sources

Add custom RSS feeds in `config.json`:

```json
{
  "rss_feeds": [
    "https://your-custom-feed.com/rss",
    "https://another-source.com/feed"
  ]
}
```

### Multi-Model Ensemble

Train multiple models and combine:

```python
from models import EnsemblePredictor

ensemble = EnsemblePredictor(
    model_types=['random_forest', 'gradient_boost', 'logistic']
)
ensemble.train(X_train, y_train)
```

## Troubleshooting

**Problem**: No events detected
- Check API keys in `config.json`
- Verify RSS feeds are accessible
- Increase `event_lookback_hours`

**Problem**: Model accuracy too low
- Collect more training data
- Try different model types
- Adjust feature engineering
- Increase `min_confidence` threshold

**Problem**: No trades executed
- Lower `min_confidence` (but not below 0.60)
- Lower `min_expected_return`
- Check market filters (volume, expiry)

**Problem**: Daily loss limit hit
- Reduce `max_position_size`
- Increase `min_confidence`
- Review losing trades in performance tracker

## On-Chain Trade Collection & Mapping

The system collects on-chain trades from Polymarket's smart contract and maps them to market condition IDs.

### Two-Step Process

**Step 1: Collect Trades**
```bash
# Incremental update (recommended for cron jobs)
python3 alchemy_collector.py --incremental

# Or backfill historical data
python3 alchemy_collector.py --backfill-days 30
```

**Step 2: Map Token IDs to Condition IDs**
```bash
# Update mappings and populate condition_ids
python3 market_mapper.py --map-all
```

### Why Two Steps?

- **Token IDs** (used on-chain): `"123456789"`
- **Condition IDs** (used in Polymarket API): `"0xabc...xyz"`

The mapper connects these by querying Polymarket's Gamma API.

### Automated Collection

**Option 1: Use the helper script**
```bash
./collect_and_map.sh --incremental
```

**Option 2: Use cron**
```cron
# Collect and map every hour
0 * * * * cd /path/to/project && python3 alchemy_collector.py --incremental && python3 market_mapper.py --map-all >> cron_output.log 2>&1
```

**Option 3: Use training_pipeline.py**
```python
from training_pipeline import TrainingDataPipeline
pipeline = TrainingDataPipeline()
pipeline.run_full_pipeline()  # Handles both steps automatically
```

### Checking Mapping Status

```bash
python3 market_mapper.py --stats

# Or query directly
sqlite3 data/alchemy_trades.db "
SELECT
  COUNT(*) as total_trades,
  COUNT(DISTINCT condition_id) as unique_markets,
  COUNT(CASE WHEN condition_id IS NOT NULL THEN 1 END) as mapped_trades,
  ROUND(100.0 * COUNT(CASE WHEN condition_id IS NOT NULL THEN 1 END) / COUNT(*), 1) as coverage_pct
FROM on_chain_trades;
"
```

Expected coverage: **90-98%** (some old/test markets may not map)

## Extending the System

### Strategy #1: Multi-Agent System

Add specialized agents for different data sources:

```python
# Create agents
news_agent = NewsAnalysisAgent()
social_agent = SocialSentimentAgent()
poll_agent = PollingDataAgent()

# Meta-agent combines predictions
meta_agent = MetaAgent([news_agent, social_agent, poll_agent])
final_prediction = meta_agent.predict()
```

### Strategy #3: RL Market Maker

Add reinforcement learning for market making:

```python
from rl_market_maker import RLAgent

agent = RLAgent(
    state_space=market_features,
    action_space=['quote_spread', 'position_size']
)
agent.train()
```

## Safety & Disclaimer

**⚠️ Important Warnings:**

1. **Start Small**: Begin with $10-50 positions
2. **Paper Trade First**: Run paper trading for 1-2 weeks
3. **Monitor Closely**: Check performance daily
4. **Risk Only What You Can Afford to Lose**
5. **No Guarantees**: Past performance ≠ future results

**Regulatory Compliance:**
- Check local laws regarding prediction markets
- Polymarket may have geographic restrictions
- Keep records for tax purposes

## Performance Expectations

**Realistic Targets (after tuning):**
- Win Rate: 55-60%
- Sharpe Ratio: 1.0-1.5
- Max Drawdown: 10-20%
- Monthly Return: 3-8%

**Note**: Performance varies based on:
- Market conditions
- Model quality
- Data sources
- Risk parameters

## Resources

**Polymarket:**
- Docs: https://docs.polymarket.com
- API: Contact Polymarket team

**News APIs:**
- NewsAPI: https://newsapi.org
- Twitter API: https://developer.twitter.com

**ML/Finance:**
- FinBERT: https://huggingface.co/ProsusAI/finbert
- Scikit-learn: https://scikit-learn.org

## Contributing

This is part of the "Hands-On AI Trading" book repository. Improvements welcome!

Ideas for contribution:
- Better sentiment models
- More data sources
- Improved backtesting
- Portfolio optimization
- Risk management enhancements

## License

See main repository LICENSE

## Support

For questions:
1. Check the research notebook (`research.ipynb`)
2. Review configuration options
3. Check logs in `trader.log`
4. Open an issue in the main repo

---

**Built with:** Python, scikit-learn, pandas, NumPy

**Author:** Hands-On AI Trading Book

**Version:** 1.0.0
