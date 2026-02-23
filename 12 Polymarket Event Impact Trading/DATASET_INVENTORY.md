# Polymarket Trading System - Dataset Inventory

**Last Updated:** February 23, 2026

This document provides a comprehensive overview of all datasets used in the Polymarket trading system, including data sources, processing pipelines, and usage patterns.

---

## Table of Contents

1. [Primary Data Sources](#primary-data-sources)
2. [Reference & Mapping Tables](#reference--mapping-tables)
3. [Training Datasets](#training-datasets)
4. [Derived & Feature Datasets](#derived--feature-datasets)
5. [System State & Persistence](#system-state--persistence)
6. [Data Pipeline Overview](#data-pipeline-overview)
7. [Storage Summary](#storage-summary)

---

## Primary Data Sources

These are raw data collected from external APIs and blockchain sources.

| Dataset | Database/File | Records | Size | Update Frequency | Description | Current Use | Future Use |
|---------|--------------|---------|------|------------------|-------------|-------------|------------|
| **On-Chain Trades** | `alchemy_trades.db` → `on_chain_trades` | 9.4M | 3.5 GB | Continuous (every 5 min) | Raw blockchain trades from Polygon via Alchemy API. Contains: `maker_asset_id`, `price`, `size`, `block_timestamp`. Source of truth for actual trading activity. | Label creation (determine trader outcome), volume analysis, liquidity metrics | Order flow analysis, market microstructure studies, whale detection |
| **GDELT News Events** | `gdelt_news.db` → `news_events` | 7.7M | 19 GB | Continuous (every 60 sec) | Global news events from GDELT Project. Filtered for crypto-related keywords (Bitcoin, Ethereum, crypto, blockchain, etc.). Contains: `title`, `url`, `timestamp`, `tone`, `themes`. | Event-based trading triggers (keyword + embedding matching) | Sentiment analysis, event impact measurement, news-driven alpha generation |
| **Resolved Markets** | `polymarket_history.db` → `resolved_markets` | 150,858 | ~100 MB | Weekly refresh | Historical Polymarket markets with final outcomes (YES/NO resolution). Date range: Aug 2025 - Feb 2026. Contains: `condition_id`, `question`, `resolved_outcome`, `outcome_prices`, `volume`. | **CRITICAL**: Training label creation - provides ground truth for which outcome won | Outcome prediction models, market resolution probability, resolution time analysis |
| **Market Snapshots** | `market_snapshots.db` → `decision_snapshots` | 23,400 | 41 MB | Every 15 min (when bot decides) | Real-time market state snapshots captured when trading bots make decisions. Contains: orderbook, prices, volume, features, decision (enter/exit), actual outcome. | Training data for ML models (features + labels), backtesting validation | Real-time model performance tracking, A/B testing framework |
| **Active Markets** | `alchemy_trades.db` → `markets` | 50,000 | Included in 3.5 GB | On-demand refresh | Current Polymarket markets metadata. Contains: `condition_id`, `question`, `end_date`, `category`, `volume`, `liquidity`, `outcome_prices` (live). | Market discovery, expiry filtering, volume analysis | Market categorization, trend detection, market lifecycle analysis |

---

## Reference & Mapping Tables

These tables enable joining and mapping between different data sources.

| Dataset | Database/File | Records | Size | Update Frequency | Description | Current Use | Future Use |
|---------|--------------|---------|------|------------------|-------------|-------------|------------|
| **Token-Condition Map** | `alchemy_trades.db` → `token_condition_map` | 199,914 | ~20 MB | Daily (2 AM cron) | Maps blockchain token IDs to Polymarket market condition IDs and outcomes. Each market has 2 tokens: `outcome_index=0` (YES), `outcome_index=1` (NO). Critical for determining which side of a bet was taken. | **CRITICAL**: Label creation - maps `maker_asset_id` from trades to actual outcome purchased | Token tracking, market identification, cross-chain analysis |
| **Embedding Cache** | `data/embedding_cache/embeddings.json` | ~50K | ~500 MB | On-demand | Pre-computed e5-large-v2 vector embeddings for news events and market questions. Used for semantic matching between news and markets. | Event-market matching (hybrid keyword + embedding similarity) | Semantic search, market clustering, duplicate detection |
| **Price Snapshots** | `polymarket_history.db` → `price_snapshots` | 0 (currently) | N/A | Planned: every 15 min | Time-series price data for active markets. Intended for historical price analysis. | Not yet used | Price momentum features, volatility estimation, orderbook dynamics |

---

## Training Datasets

These datasets are specifically prepared for ML model training.

| Dataset | File/Source | Records | Size | Creation Method | Description | Current Use | Model Type |
|---------|-------------|---------|------|----------------|-------------|-------------|------------|
| **Labeled Trades** | `data/REAL_labeled_from_alchemy.csv` | 1.22M | 257 MB | `create_labels_final_correct.py` | On-chain trades with **CORRECT** labels indicating win/loss. Joins: `on_chain_trades` + `token_condition_map` + `resolved_markets`. Labels: 1.0 (trader bought winning outcome), -1.0 (trader bought losing outcome). | **PRIMARY TRAINING DATA** for all 3 ML models | Event bot, Price-level bot, Short-expiry bot |
| **Market Snapshots** | `market_snapshots.db` → `decision_snapshots` | 23,400 | 41 MB | Real-time capture during bot operation | Captures: orderbook features (spread, depth, imbalance), volume metrics, time-to-expiry, price, decision made, actual outcome. Enriched with realized PnL. | Training data for decision validation, feature importance analysis | Reinforcement learning (planned) |
| **Feature-Engineered Training Data** | Generated in-memory | Varies | N/A | `FeatureExtractor` classes | Combines: orderbook features, volume metrics, time features, price momentum, news sentiment. Different feature sets for each bot (event, price-level, short-expiry). | Model training input (X features) | All ML models |

---

## Derived & Feature Datasets

These datasets are computed from primary sources for specific analytical purposes.

| Dataset | Storage | Description | Computation Source | Current Use | Future Use |
|---------|---------|-------------|-------------------|-------------|------------|
| **Orderbook Features** | In-memory | Spread, depth (bid/ask), imbalance, mid-price. Extracted from live orderbook or synthetic (from /price endpoint). | `common_features.py` → `OrderbookFeatures` | **ALL 3 BOTS**: Real-time trading decisions, model features | Liquidity risk assessment, slippage prediction |
| **Volume Features** | In-memory | 24h volume, 7d volume, volume trend, liquidity score. Derived from market metadata. | `common_features.py` → `VolumeFeatures` | **ALL 3 BOTS**: Market quality filtering, model features | Market maker presence detection, wash trading detection |
| **Time Features** | In-memory | Days/hours to expiry, time-of-day patterns, day-of-week effects. | `common_features.py` → `TimeFeatures` | **ALL 3 BOTS**: Urgency scoring, model features | Event timing analysis, optimal entry/exit timing |
| **News-Market Matches** | In-memory | Semantic similarity scores between news events and markets. Combines keyword matching + e5-large-v2 embeddings. | `event_tracker.py` → `EventTracker` | **EVENT BOT**: Trigger identification, confidence scoring | Event impact prediction, news alpha decay |
| **Price Tracking** | `price_tracking.db` | Historical price data for open positions. Tracks entry/exit prices for PnL calculation. | `PriceTracker` class | Position monitoring, stop-loss/take-profit triggers | Trade analytics, performance attribution |

---

## System State & Persistence

These datasets maintain system state across restarts.

| Dataset | Database/File | Records | Description | Why Persistent | Current Use |
|---------|--------------|---------|-------------|----------------|-------------|
| **Open Positions (Event Bot)** | `data/positions.db` → `positions` | ~10-50 | Tracks all open trading positions for event-based trader. Contains: `market_id`, `side`, `entry_price`, `size`, `stop_loss`, `take_profit`. | Survives bot restarts - critical for risk management | Position management, PnL tracking, stop-loss/take-profit execution |
| **Open Positions (Price-Level Bot)** | `data/positions_price_level.db` | ~5-20 | Same as above but for price-level trader. Separate DB prevents cross-contamination. | Survives bot restarts | Position management (price-level trader) |
| **Open Positions (Short-Expiry Bot)** | `data/positions_short_expiry.db` | ~20-100 | Same as above but for short-expiry trader (more active, more positions). | Survives bot restarts | Position management (short-expiry trader) |
| **Paper Trading Balance (Event)** | `data/paper_trading_balance.json` | 1 record | Tracks paper trading account balance ($1000 initial). Updates with each trade. | Simulates real account - prevents overspending | Paper trading mode (production uses real API balance) |
| **Paper Trading Balance (Price-Level)** | `data/paper_trading_balance_price_level.json` | 1 record | Separate $500 balance for price-level bot. | Separate balance tracking | Paper trading mode (price-level) |
| **Paper Trading Balance (Short-Expiry)** | `data/paper_trading_balance_short_expiry.json` | 1 record | Separate balance for short-expiry bot. | Separate balance tracking | Paper trading mode (short-expiry) |

---

## Data Pipeline Overview

### Collection Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL DATA SOURCES                        │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         │                    │                    │
    Alchemy API         GDELT Project      Polymarket API
    (Blockchain)        (News Events)      (Market Data)
         │                    │                    │
         ↓                    ↓                    ↓
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │   Alchemy    │    │    GDELT     │    │  Polymarket  │
  │  Collector   │    │  Collector   │    │   History    │
  │              │    │              │    │  Collector   │
  └──────────────┘    └──────────────┘    └──────────────┘
         │                    │                    │
         ↓                    ↓                    ↓
  alchemy_trades.db     gdelt_news.db    polymarket_history.db
  (9.4M trades)         (7.7M events)    (150K resolved)
```

### Label Creation Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    LABEL CREATION PIPELINE                       │
└─────────────────────────────────────────────────────────────────┘

alchemy_trades.db                polymarket_history.db
│                                │
├─ on_chain_trades               ├─ resolved_markets
│  (maker_asset_id, price)       │  (condition_id, resolved_outcome)
│                                │
├─ token_condition_map           │
│  (token_id → condition_id)     │
│  (token_id → outcome_index)    │
│                                │
└────────┬───────────────────────┘
         │
         ↓
┌────────────────────────────────────────────┐
│   create_labels_final_correct.py           │
│                                            │
│   1. Map maker_asset_id → outcome_index   │
│   2. Map condition_id → resolved_outcome  │
│   3. Compare: trader_bought == winner?    │
│   4. Label: 1.0 (win) or -1.0 (loss)     │
└────────────────────────────────────────────┘
         │
         ↓
  REAL_labeled_from_alchemy.csv
  (1.22M labeled trades)
         │
         ↓
┌────────────────────────────────────────────┐
│         ML MODEL TRAINING                  │
│                                            │
│   • Event Bot Model                        │
│   • Price-Level Bot Model                  │
│   • Short-Expiry Bot Model                 │
└────────────────────────────────────────────┘
```

### Trading Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                      TRADING PIPELINE                            │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────┐
    │  GDELT News │
    │   Events    │
    └──────┬──────┘
           │
           ↓
    ┌─────────────┐         ┌─────────────┐
    │   Event     │         │  Polymarket │
    │  Matching   │ ←────── │    API      │
    │             │         │  (Markets)  │
    └──────┬──────┘         └─────────────┘
           │
           ↓
    ┌─────────────┐
    │ ML Model    │
    │ Prediction  │
    └──────┬──────┘
           │
           ↓
    ┌─────────────┐
    │   Trade     │ ←────── OrderbookManager
    │  Executor   │         (Real-time prices)
    └──────┬──────┘
           │
           ↓
    ┌─────────────┐
    │  Position   │ ────→ positions.db
    │  Manager    │
    └─────────────┘
           │
           ↓
    ┌─────────────┐
    │  Snapshot   │ ────→ market_snapshots.db
    │  Recorder   │
    └─────────────┘
```

---

## Storage Summary

### By Database

| Database | Size | Tables | Records | Primary Use | Backup Required |
|----------|------|--------|---------|-------------|-----------------|
| `alchemy_trades.db` | 3.5 GB | 3 | 9.4M trades, 50K markets, 200K mappings | **PRIMARY**: Trading, label creation | ✅ CRITICAL |
| `gdelt_news.db` | 19 GB | 1 | 7.7M events | Event detection | ✅ Important |
| `polymarket_history.db` | 100 MB | 3 | 150K resolved, 0 snapshots, 0 trades | **PRIMARY**: Label creation | ✅ CRITICAL |
| `market_snapshots.db` | 41 MB | 1 | 23K snapshots | Model training, backtesting | ✅ Important |
| `positions.db` | <1 MB | 1 | ~50 positions | Position state | ✅ Important |
| `positions_price_level.db` | <1 MB | 1 | ~20 positions | Position state | ✅ Important |
| `positions_short_expiry.db` | <1 MB | 1 | ~100 positions | Position state | ✅ Important |
| `price_tracking.db` | <1 MB | 1 | Variable | Price history | Optional |

**Total Storage:** ~22.7 GB

### By Data Type

| Category | Size | Backup Priority |
|----------|------|-----------------|
| **Raw Trading Data** | 3.5 GB | 🔴 CRITICAL |
| **News Events** | 19 GB | 🟡 Important (re-collectable) |
| **Resolved Markets** | 100 MB | 🔴 CRITICAL (hard to re-collect) |
| **Training Data** | 257 MB (CSV) + 41 MB (snapshots) | 🟡 Important (regenerable) |
| **System State** | ~3 MB | 🟠 Important (active positions) |
| **Cache/Temp** | ~500 MB (embeddings) | 🟢 Optional (regenerable) |

---

## Data Usage Matrix

### By Trading Bot

| Bot | Primary Datasets | Feature Datasets | Training Data | Output |
|-----|-----------------|------------------|---------------|--------|
| **Event Bot** | `gdelt_news.db`, `alchemy_trades.db` (markets) | News-market matches, orderbook features, time features | `REAL_labeled_from_alchemy.csv` (filtered) | `positions.db`, `market_snapshots.db` |
| **Price-Level Bot** | `alchemy_trades.db` (markets, trades) | Orderbook features, volume features, time features | `REAL_labeled_from_alchemy.csv` (filtered) | `positions_price_level.db`, `market_snapshots.db` |
| **Short-Expiry Bot** | `alchemy_trades.db` (markets, trades) | Orderbook features, volume features, time features (< 48h) | `REAL_labeled_from_alchemy.csv` (filtered) | `positions_short_expiry.db`, `market_snapshots.db` |

### By Analysis Type

| Analysis | Input Datasets | Output | Frequency |
|----------|---------------|--------|-----------|
| **Label Creation** | `on_chain_trades`, `token_condition_map`, `resolved_markets` | `REAL_labeled_from_alchemy.csv` | Monthly (or when new resolved markets available) |
| **Model Training** | `REAL_labeled_from_alchemy.csv`, `market_snapshots.db` | Trained models (`*.pkl`) | Weekly (or after label refresh) |
| **Backtesting** | `market_snapshots.db`, `REAL_labeled_from_alchemy.csv` | Performance metrics, equity curves | On-demand |
| **Parameter Optimization** | `REAL_labeled_from_alchemy.csv` | Optimal parameter sets | Weekly |
| **Performance Analysis** | `market_snapshots.db`, `positions.db` | PnL reports, trade analytics | Daily |

---

## Data Collection Schedule

### Continuous (Always Running)

- ✅ **Alchemy Collector** - Every 5 minutes
- ✅ **GDELT Collector** - Every 60 seconds
- ✅ **OrderbookManager** - Real-time WebSocket (with REST fallback)
- ✅ **Trading Bots** - Continuous (check markets every 30-60 seconds)

### Scheduled (Cron Jobs)

- **Market Mapper Update** - Daily at 2 AM
  - Updates `token_condition_map` with new markets
  - Backfills `condition_id` for unmapped trades

- **Polymarket History Refresh** - Weekly (Sunday 3 AM)
  - Collects newly resolved markets from past 7 days
  - Updates `resolved_markets` table

- **Label Regeneration** - Monthly (1st @ 4 AM)
  - Creates new `REAL_labeled_from_alchemy.csv` with latest resolved outcomes
  - Triggers model retraining

- **Health Monitoring** - Every 5 minutes
  - Checks collector processes, data freshness
  - Sends Telegram alerts on failures

### On-Demand

- **Snapshot Recording** - When bot makes trading decision
- **Model Training** - After label refresh or parameter changes
- **Backtesting** - During development/validation

---

## Data Quality Checks

### Automated Checks

| Check | Frequency | Alert Threshold | Action |
|-------|-----------|-----------------|--------|
| **Data Staleness** | Every 5 min | > 1 hour | Telegram alert, restart collector |
| **Database Growth** | Every 5 min | 0% growth over 24h | Telegram alert, investigate |
| **Label Distribution** | After label creation | Not 45-55% balance | Review label logic, check resolved markets |
| **Mapping Coverage** | Daily | < 95% trades mapped | Update token_condition_map |
| **Duplicate Detection** | On write | N/A | Skip duplicates (INSERT OR IGNORE) |

### Manual Validation

- **Label Spot Checks** - After each label creation (validate 10-20 random samples)
- **Model Performance** - Weekly (check accuracy, ROC-AUC on validation set)
- **Trade Execution** - Daily (verify paper trading vs expected)

---

## Data Retention Policy

### Permanent Storage

- ✅ **On-Chain Trades** - Permanent (historical analysis)
- ✅ **Resolved Markets** - Permanent (ground truth)
- ✅ **Labeled Training Data** - Keep all versions (versioned by date)
- ✅ **Market Snapshots** - Permanent (backtesting, research)

### Rolling Window

- **GDELT News** - Keep last 90 days (older data rarely used)
- **Active Markets** - Refresh on-demand (stale data replaced)
- **Price Tracking** - Keep last 30 days (older data archived)

### Temporary/Cache

- **Embedding Cache** - Regenerate as needed (invalidate if model changes)
- **In-Memory Features** - Ephemeral (computed on-demand)

---

## Planned Datasets

These datasets are planned for future implementation:

| Dataset | Purpose | Timeline | Source |
|---------|---------|----------|--------|
| **Time-Series Price Data** | Price momentum features, volatility | Q2 2026 | Polymarket API (15-min snapshots) |
| **Order Flow Imbalance** | Detect informed trading | Q2 2026 | Alchemy on-chain data |
| **Social Media Sentiment** | Twitter/X mentions for crypto events | Q3 2026 | Twitter API / Scraping |
| **Whale Tracking** | Large trader identification | Q3 2026 | Alchemy on-chain data |
| **Cross-Market Correlations** | Related market price movements | Q3 2026 | Polymarket API (multi-market analysis) |
| **News Impact Decay** | How long news affects prices | Q3 2026 | GDELT + market_snapshots |

---

## Appendix: Data Access Patterns

### High-Frequency (< 1 second)

- **OrderbookManager** - Real-time WebSocket orderbook
- **PriceFetcher** - Entry/exit price queries

### Medium-Frequency (1-60 seconds)

- **Market Discovery** - Find tradeable markets
- **Event Matching** - Match news to markets
- **Position Monitoring** - Check stop-loss/take-profit

### Low-Frequency (minutes to hours)

- **Data Collection** - Alchemy (5 min), GDELT (60 sec)
- **Feature Extraction** - On-demand for ML prediction
- **Snapshot Recording** - When decisions made

### Batch (daily/weekly/monthly)

- **Label Creation** - Monthly or on-demand
- **Model Training** - Weekly or after label refresh
- **Market Mapper** - Daily updates
- **History Refresh** - Weekly (resolved markets)

---

## Quick Reference: File Locations

```
12 Polymarket Event Impact Trading/
├── data/
│   ├── alchemy_trades.db           # 3.5 GB - On-chain trades
│   ├── gdelt_news.db               # 19 GB - News events
│   ├── polymarket_history.db       # 100 MB - Resolved markets
│   ├── market_snapshots.db         # 41 MB - Decision snapshots
│   ├── positions.db                # <1 MB - Event bot positions
│   ├── positions_price_level.db    # <1 MB - Price-level positions
│   ├── positions_short_expiry.db   # <1 MB - Short-expiry positions
│   ├── price_tracking.db           # <1 MB - Price history
│   ├── REAL_labeled_from_alchemy.csv  # 257 MB - Training labels
│   ├── paper_trading_balance.json  # Event bot balance
│   ├── paper_trading_balance_price_level.json
│   ├── paper_trading_balance_short_expiry.json
│   └── embedding_cache/
│       └── embeddings.json         # ~500 MB - e5-large-v2 vectors
├── src/
│   ├── collectors/
│   │   ├── alchemy_collector.py
│   │   ├── gdelt_collector.py
│   │   └── collect_polymarket_history.py
│   └── ml/
│       └── train_all_models.py
└── create_labels_final_correct.py  # Label creation (correct logic)
```

---

**Last Updated:** February 23, 2026
**Version:** 1.0
**Status:** Production Ready ✅
