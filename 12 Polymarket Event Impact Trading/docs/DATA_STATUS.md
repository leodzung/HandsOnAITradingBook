# Data Status and Training Requirements

**Last Updated:** 2026-02-11

## Overview

This document clarifies what historical data is available and what's needed for training the short-expiry trading models.

## Current Data Inventory

### ✅ Available Data

#### 1. Alchemy On-Chain Trades (`data/alchemy_trades.db`)
- **Total Trades:** 2,076,257 on-chain trades
- **Markets:** 1,070 unique condition_ids
- **Time Range:** Up to 2026-02-08
- **Market Duration:** 90+ days (long-duration markets only)
- **Examples:** Presidential elections, Fed rate decisions, major political events

#### 2. Token-Condition Mapping (`data/token_mapping.db`)
- **Total Mappings:** 99,957 token-to-condition mappings
- **Markets:** 50,000+ markets with metadata
- **Resolved Markets:** 49,703 markets with outcome data
- **Coverage:** Maps Polymarket API markets to on-chain condition_ids

#### 3. Linked Trainable Data (Alchemy ∩ Mapping)
```
Markets with BOTH trades AND outcomes: 1,049 markets
Duration breakdown:
  - 0-7 days (SHORT EXPIRY):  0 markets ❌
  - 7-30 days:                0 markets
  - 30-90 days:               0 markets
  - 90+ days:                 1,049 markets ✅
```

**Status:** ✅ Data linkage works, ❌ but NO short-expiry markets in alchemy database

### ❌ Missing Data

#### Short-Expiry Historical Trades
- **What's Missing:** On-chain trades for markets with 0-7 day duration
- **Why:** Alchemy collector was configured for high-volume, long-duration markets only
- **Impact:** Cannot train short-expiry models from historical data

#### Short-Expiry Market Outcomes
- **What's Missing:** Resolved outcomes for short-expiry markets with trade history
- **Why:** Markets in token_mapping.db without corresponding alchemy trades
- **Count:** ~20,000 short-expiry resolved markets exist, but no price history

## Training Requirements by Bot

### Short-Expiry Bot (`trader_short_expiry.py`)

**Requires:**
- Markets with 0-7 day duration
- Historical price data (trades) during market lifetime
- Resolved outcomes (YES/NO)
- Minimum 100-200 markets for training

**Current Status:**
```
❌ Historical data: 0 markets available
✅ Live data collection: In progress (10 open positions)
⏳ ETA for training: 7-10 days (need 100-150 closed positions)
```

**Recommendation:** Wait for live data collection

### Price-Level Bot (`trader_price_levels.py`)

**Requires:**
- Any duration markets
- Price movement history
- Entry/exit outcomes

**Current Status:**
```
✅ Could train on 1,049 long-duration markets
⚠️  But: Different market dynamics than target short-expiry markets
```

**Recommendation:** Wait for live data collection for best results

### Event-Based Bot (`trader.py`)

**Requires:**
- News/event data
- Market reactions
- Sentiment features

**Current Status:**
```
✅ Training data exists: data/real_training_dataset.csv
✅ Model ready: Can train now
```

## Data Collection Strategy

### Current Approach: Live Collection ✅

**Bot:** `trader_short_expiry.py` running in paper trading mode

**Collection Rate:**
- ~10-15 positions opened per day (ultra_short bucket)
- Positions close within 24-48 hours
- Features automatically extracted and stored in `positions_short_expiry.db`

**Timeline:**
```
Day 1-3:   30-45 closed positions
Day 4-7:   60-105 closed positions
Day 8-10:  100-150 closed positions ✅ READY FOR TRAINING
```

**Monitor Progress:**
```bash
sqlite3 data/positions_short_expiry.db \
  "SELECT status, COUNT(*) FROM positions GROUP BY status;"
```

### Alternative: Historical Collection ⏸️ (Not Recommended)

Would require:
1. Identifying historical short-expiry markets
2. Reconfiguring alchemy collector for low-volume markets
3. Downloading historical on-chain trades
4. Weeks of API calls and processing

**Why Not Recommended:**
- Time-consuming (weeks vs. days for live collection)
- Historical data may not reflect current market conditions
- Live data has same features the bot actually uses
- Live data provides ground truth for actual tradeable markets

## Database Schema Reference

### alchemy_trades.db
```sql
on_chain_trades (
    condition_id TEXT,      -- Links to token_mapping
    block_timestamp TEXT,
    price REAL,
    maker_amount_filled REAL,
    taker_amount_filled REAL
)
```

### token_mapping.db
```sql
markets (
    condition_id TEXT PRIMARY KEY,
    question TEXT,
    end_date TEXT,
    created_at TEXT,
    outcome_prices TEXT,    -- JSON: ["0.0", "1.0"] = YES won
    resolved INTEGER
)
```

### positions_short_expiry.db
```sql
positions (
    market_id TEXT,
    outcome TEXT,           -- YES or NO
    entry_price REAL,
    exit_price REAL,
    bucket TEXT,            -- ultra_short, short, medium
    hours_to_expiry_at_entry REAL,
    signal_reason TEXT,
    features_json TEXT,     -- All extracted features
    status TEXT             -- open or closed
)
```

## Action Items

### Now
- [x] Understand data limitations
- [x] Keep short-expiry bot running to collect data
- [ ] Monitor daily position closures

### After 100+ Closed Positions
- [ ] Run training on live collected data
- [ ] Validate model performance
- [ ] Integrate model predictions into trader

### Optional Future Work
- [ ] Configure alchemy collector for short-expiry markets
- [ ] Backfill historical short-expiry data
- [ ] Build hybrid training dataset

## FAQ

**Q: Why can't we use the 1,049 markets we have?**
A: They're all 90+ day markets. Short-expiry markets (0-7 days) have completely different dynamics:
- Time decay dominates pricing
- Volatility patterns differ
- Information arrival is different
- Models trained on long markets won't transfer well

**Q: Can we just wait a few more days?**
A: Yes! The bot is collecting the exact data we need. In 7-10 days you'll have better training data than any historical collection could provide.

**Q: What about the market mapper - didn't that fix this?**
A: The market mapper successfully linked markets to trades. The issue is that the alchemy database simply doesn't contain short-expiry market trades. It's a data scope issue, not a technical issue.

**Q: Should we train on what we have?**
A: No. Training on 90+ day markets for a short-expiry bot would be like training a sprinter by having them run marathons. Wait for the right data.

## Check Data Status

Run this script anytime to check current data availability:

```bash
python3 scripts/check_data_status.py
```

This will show:
- Available training data by market duration
- Current live data collection progress
- Estimated days until training ready
- Data quality metrics
