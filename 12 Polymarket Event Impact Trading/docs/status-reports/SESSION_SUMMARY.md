# Polymarket Event Impact Trading - Session Summary

## Date: January 17, 2026

## Problem Solved: Model YES Bias

### Original Issue
- Model generated 0 SELL signals out of 259 evaluations (100% BUY YES bias)
- Root cause: Training data had unrealistic feature ranges
  - Training: strike_distance_pct -24% to +14%
  - Real markets: strike_distance_pct 58%+ (e.g., BTC at $95k, strike at $150k)
  - Training: days_to_expiry 15-23 days
  - Real markets: days_to_expiry 73-348 days

### Solution Implemented
1. **Downloaded real historical crypto prices** from CoinGecko API (366 days BTC + 366 ETH)
2. **Created `generate_real_training_data.py`** - generates balanced training data from actual price movements
3. **Generated 1,000 balanced samples** with 50/50 YES/NO split and realistic feature ranges:
   - Strike distances: 5% to 200%
   - Days to expiry: 30 to 180 days
4. **Retrained model** with calibration (CalibratedClassifierCV, isotonic method)

### Results
- **Model Performance**: 92.67% accuracy, 95.87% ROC-AUC
- **Backtest**: 78.2% win rate, +$39,052 P&L on 500 simulated trades
- **Signal Balance**: 49.8% YES, 50.2% NO predictions (fixed!)

## Files Created/Modified

### New Files
- `generate_real_training_data.py` - Real data generator using CoinGecko prices
- `backtest_price_level_model.py` - Historical backtesting framework
- `collect_polymarket_history.py` - Polymarket API data collector
- `data/real_training_data.csv` - 1,000 balanced training samples
- `data/historical_prices_real.csv` - 732 daily prices (BTC + ETH)
- `data/polymarket_history.db` - SQLite with 1,859 resolved markets
- `data/polymarket_resolved.csv` - 61 price-level markets
- `data/polymarket_crypto_resolved.csv` - 36 true crypto price-level markets

### Modified Files
- `data/price_level_model.pkl` - Retrained, calibrated model
- `data/price_level_model_OLD_BIASED.pkl` - Backup of old biased model

## Polymarket Historical Data Findings

### Data Availability
- Collected 1,859 resolved markets total
- Only 36 true crypto price-level markets (all from 2021-2022)

### Why Only 2021-2022 Data?
1. Current crypto markets (e.g., "BTC $150k by March 2026") haven't expired yet
2. 2023-2024 resolved markets were mostly political (US elections)
3. Polymarket had more short-term crypto markets in 2021 that have now resolved

## Current System State

### Trading Bot
- Paper trading mode with $10.72 balance
- 4 open BTC positions (all $150k strike markets)
- Model now producing balanced BUY/SELL signals

### Key Components
- `trading_price_levels.py` - Main trading bot
- `price_level_features.py` - Feature extraction (37 features)
- `market_parser.py` - Polymarket market parsing
- `external_data.py` - Spot price data from CoinGecko
- `conditional_resolution.py` - Handles 50-50 resolution rules
- `position_manager.py` - Position tracking

## API Endpoints Used

### Polymarket
- Gamma API: `https://gamma-api.polymarket.com/markets`
- CLOB API: `https://clob.polymarket.com/book`

### Price Data
- CoinGecko: `https://api.coingecko.com/api/v3/coins/{id}/market_chart`

## Potential Future Work
1. Validate model against 36 real resolved markets from 2021-2022
2. Set up ongoing tracking of active markets for future validation
3. Expand to other assets (SOL, etc.)
4. Add transaction cost modeling to backtest
