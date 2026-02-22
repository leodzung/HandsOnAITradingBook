# DEX Screening Strategies for Early Token Discovery

Three distinct agents for finding early-stage token opportunities on decentralized exchanges (DEXs) across Ethereum, BSC, and Solana.

## Overview

This module contains three specialized strategies for discovering tokens before they go mainstream, each with different approaches, risk profiles, and ideal use cases.

### Strategy 1: New Liquidity Pool Scanner
**Focus:** First-mover advantage on brand new token launches

- Monitors newly created liquidity pools across multiple DEXs
- Filters based on initial liquidity, contract verification, and safety checks
- Ideal for aggressive traders who want to catch tokens before they trend
- **Risk Level:** Medium
- **Best For:** Getting the earliest possible entries

### Strategy 2: Smart Money Tracker
**Focus:** Copy trading proven whale wallets

- Tracks successful traders who consistently find gems
- Monitors their transactions and copies their buys
- Leverages the research of proven winners
- **Risk Level:** Medium-Low
- **Best For:** Reducing research burden with social proof

### Strategy 3: Honeypot Detector + Anomaly Scanner
**Focus:** Maximum safety through deep analysis

- Multi-layered scam detection (honeypots, rug pulls, tax traps)
- Statistical anomaly detection for unusual patterns
- Thorough contract and holder analysis
- **Risk Level:** Low
- **Best For:** Conservative traders prioritizing capital preservation

## Installation

### Requirements

```bash
pip install web3 numpy requests
```

### Optional (for production use):
- Etherscan/BSCScan API keys
- DexScreener API access
- Moralis or Alchemy API keys
- The Graph endpoints

## Usage

### Quick Start - Run All Strategies and Compare

```python
from strategy_ranker import main

# Run all 3 strategies for 2 cycles and generate comparison report
main()
```

### Individual Strategy Usage

#### Strategy 1: Pool Scanner

```python
from strategy1_pool_scanner import PoolScannerStrategy

strategy = PoolScannerStrategy(
    chains=['ethereum', 'bsc'],
    min_liquidity_usd=20000,
    max_pool_age_hours=48,
    min_safety_score=65,
    min_opportunity_score=55,
    scan_interval_seconds=300  # 5 minutes
)

# Run indefinitely
strategy.run()

# Or run for specific duration/cycles
strategy.run(duration_hours=2)
strategy.run(max_cycles=10)
```

#### Strategy 2: Smart Money Tracker

```python
from strategy2_smart_money import SmartMoneyTracker

strategy = SmartMoneyTracker(
    chains=['ethereum', 'bsc'],
    min_whale_reputation=75,
    min_trade_size_usd=10000,
    max_trade_age_minutes=30,
    min_safety_score=60,
    scan_interval_seconds=180  # 3 minutes
)

strategy.run(max_cycles=20)
```

#### Strategy 3: Anomaly Detector

```python
from strategy3_anomaly_detector import AnomalyDetectorStrategy

strategy = AnomalyDetectorStrategy(
    chains=['ethereum', 'bsc'],
    max_token_age_hours=72,
    min_safety_score=75,
    max_scam_indicators=1,
    enable_deep_scan=True
)

strategy.run(duration_hours=24)
```

## Architecture

### Core Components

1. **dex_utils.py** - Shared utilities
   - `DEXDataFetcher` - Fetches on-chain data from multiple sources
   - `RiskAnalyzer` - Calculates safety and opportunity scores
   - Data structures: `Token`, `LiquidityPool`, `TokenMetrics`

2. **strategy1_pool_scanner.py** - Pool scanning strategy
   - `PoolScannerStrategy` - Main strategy class
   - `PoolOpportunity` - Scored pool opportunity

3. **strategy2_smart_money.py** - Whale tracking strategy
   - `SmartMoneyTracker` - Main strategy class
   - `WhaleWallet` - Tracked whale data
   - `CopyTradeOpportunity` - Copy trade opportunity

4. **strategy3_anomaly_detector.py** - Anomaly detection strategy
   - `AnomalyDetectorStrategy` - Main strategy class
   - `ScamIndicators` - Detected scam patterns
   - `AnomalyScore` - Statistical anomaly scores

5. **strategy_ranker.py** - Comparison framework
   - `StrategyRanker` - Ranks and compares strategies
   - `StrategyMetrics` - Performance metrics
   - `StrategyRanking` - Final rankings

## Scoring Methodology

### Safety Score (0-100)
- Contract verification (+20)
- Honeypot check (+30)
- Tax levels (+15)
- Holder distribution (+20)
- Liquidity locks (+15)
- Minimum liquidity (+10)

### Opportunity Score (0-100)
- Price momentum (+35)
- Volume/liquidity ratio (+25)
- Holder growth (+10)
- Early entry bonus (+20)
- Holder concentration (+10)

### Composite Score
Weighted average of safety and opportunity:
- Strategy 1: 60% Safety, 40% Opportunity
- Strategy 2: 40% Whale Reputation, 35% Safety, 25% Opportunity
- Strategy 3: 60% Safety, 40% Anomaly Appeal

## Production Setup

### Required API Keys

Set up the following in your environment or config:

```python
api_keys = {
    'etherscan': 'YOUR_ETHERSCAN_KEY',
    'bscscan': 'YOUR_BSCSCAN_KEY',
    'dexscreener': 'YOUR_DEXSCREENER_KEY',
    'moralis': 'YOUR_MORALIS_KEY',
    'alchemy': 'YOUR_ALCHEMY_KEY'
}

fetcher = DEXDataFetcher(api_keys=api_keys)
```

### Data Sources

The strategies can be integrated with:

1. **DexScreener API** - Real-time DEX data
2. **The Graph** - Historical on-chain queries
3. **Web3 RPC** - Direct blockchain interaction
4. **Honeypot.is** - Scam detection
5. **Token Sniffer** - Security scoring
6. **Nansen/Arkham** - Whale wallet data

### Production Implementation

For production use, implement these methods in `dex_utils.py`:

```python
def get_new_pools(self, chain, min_liquidity, max_age_hours):
    # Call DexScreener or The Graph
    url = f"https://api.dexscreener.com/latest/dex/search/?q={chain}"
    response = requests.get(url)
    # Parse and filter results
    return pools

def get_token_metrics(self, token_address, chain):
    # Aggregate data from multiple sources
    # - Contract verification (Etherscan)
    # - Holder distribution (blockchain query)
    # - Liquidity data (DEX APIs)
    # - Price data (DexScreener)
    return metrics
```

## Risk Management

### Recommended Approach

1. **Parallel Execution** - Run all 3 strategies simultaneously
2. **Cross-validation** - Tokens found by multiple strategies are higher confidence
3. **Position Sizing** - Allocate capital based on composite scores and risk tolerance

### Capital Allocation by Risk Profile

**Conservative (Capital Preservation)**
- 50% Strategy 3 (Anomaly Detector)
- 30% Strategy 2 (Smart Money)
- 20% Strategy 1 (Pool Scanner)

**Moderate (Balanced)**
- 40% Strategy 2 (Smart Money)
- 35% Strategy 3 (Anomaly Detector)
- 25% Strategy 1 (Pool Scanner)

**Aggressive (Maximum Returns)**
- 45% Strategy 1 (Pool Scanner)
- 35% Strategy 2 (Smart Money)
- 20% Strategy 3 (Anomaly Detector)

### Entry Timing

- **Strategy 1:** Enter immediately on high scores (>80)
- **Strategy 2:** Enter within 5-10 minutes of whale trade
- **Strategy 3:** Enter after full due diligence (1-24 hours)

## Performance Metrics

The ranking framework evaluates strategies on:

1. **Opportunity Quality (30%)** - Average composite scores
2. **Safety (25%)** - Average safety scores and risk levels
3. **Volume (20%)** - Number of opportunities found
4. **Efficiency (25%)** - Hit rate (opportunities / scanned)

## Example Output

```
###############################################################################
# STRATEGY 3: ANOMALY DETECTOR - SUMMARY
###############################################################################

Total Opportunities: 47
Total Tokens Scanned: 312
Pass Rate: 15.1%

🏆 TOP 10 OPPORTUNITIES:
===============================================================================

#1 NEWGEM (ETHEREUM)
   Risk Level: LOW
   Composite Score: 87.3/100
   Safety: 91.2 | Anomaly Appeal: 79.8
   Scam Indicators: 0/1 allowed
   Liquidity: $127,450
   24h Volume: $89,320
   Contract: 0x1234...5678
```

## Advanced Features

### Custom Filters

Add custom filtering logic:

```python
def custom_filter(opportunity):
    # Only tokens with >$50k liquidity
    if opportunity.metrics.liquidity_usd < 50000:
        return False

    # Only if price is up in last hour
    if opportunity.metrics.price_change_1h < 0:
        return False

    return True

# Apply filter
filtered_opps = [o for o in opportunities if custom_filter(o)]
```

### Webhook Notifications

Send alerts to Discord/Telegram:

```python
def send_alert(opportunity):
    message = f"🚨 New Opportunity: {opportunity.token_symbol}\n"
    message += f"Score: {opportunity.composite_score:.1f}/100\n"
    message += f"Contract: {opportunity.token_address}"

    # Send to Discord/Telegram
    requests.post(webhook_url, json={'content': message})
```

### Database Integration

Store opportunities for backtesting:

```python
import sqlite3

def save_opportunity(opportunity, strategy_number):
    conn = sqlite3.connect('dex_opportunities.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO opportunities VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        opportunity.token_address,
        strategy_number,
        opportunity.composite_score,
        opportunity.safety_score,
        int(time.time()),
        opportunity.chain
    ))

    conn.commit()
```

## Testing

Run the demo mode to test without real API calls:

```bash
python strategy_ranker.py
```

This runs all strategies for 2 cycles with mock data.

## Disclaimer

**USE AT YOUR OWN RISK**

- These strategies are for educational purposes
- Crypto trading is extremely high risk
- Early-stage tokens can go to zero
- Always do your own research (DYOR)
- Never invest more than you can afford to lose
- Past performance does not guarantee future results

## Support

For issues or questions:
1. Check the code comments for implementation details
2. Review the strategy summaries for methodology
3. Adjust parameters based on your risk tolerance

## License

Part of "Hands-On AI Trading with Python, QuantConnect, and AWS"
