# Condition ID Mapping - In Progress

## What's Happening

The **market_mapper.py** (existing tool) is now running to link 2M+ historical trades to their markets:

```bash
python3 src/utils/market_mapper.py --map-all
```

## Process

### Step 1: Fetch Market Data (Running Now)
- Querying Polymarket Gamma API for all markets
- Extracting token_id → condition_id mappings
- Storing in `data/alchemy_trades.db` (token_condition_map table)
- Progress: ~1,500+ markets fetched (updates every 500)
- Rate: ~100 markets/second

### Step 2: Update Trades (Next)
- Once all markets are fetched, will update `on_chain_trades` table
- Maps `maker_asset_id` (token_id) → `condition_id`
- Updates ~2M trades with their condition_ids

### Step 3: Verification
- Shows final coverage statistics
- Expected: 60-80% of trades mapped (some trades may be from delisted markets)

## Timeline

- **Step 1 (Market Fetch):** ~5-10 minutes (fetching 50,000+ markets)
- **Step 2 (Trade Update):** ~2-5 minutes (updating 2M trades)
- **Total:** ~10-15 minutes

## Monitoring Progress

```bash
# Watch real-time progress
tail -f logs/market_mapping.log

# Check stats after completion
python3 src/utils/market_mapper.py --stats
```

## What This Enables

Once complete, we'll have **2M+ historical trades linked to markets**, enabling:

### ✅ Historical Model Training
```bash
# Train models from historical data
python3 scripts/train_short_expiry.py
```

This will:
- Load 1,226 short-expiry markets
- Extract features from 2M+ on-chain trades
- Train GradientBoostingClassifier for each bucket
- Output: `data/models/short_expiry_{bucket}.pkl`

### ✅ Rich Training Dataset
- **Ultra-short (0-24h):** 797 markets → thousands of samples
- **Short (24-72h):** 231 markets → hundreds of samples
- **Medium (72-168h):** 198 markets → hundreds of samples

### ✅ ML Trading (Phase 2)
- Load trained models into bot
- Hybrid approach: ML predictions + rule-based fallback
- Probability-calibrated signals
- Bucket-specific strategies

## Current Status

**Started:** 2026-02-11 08:28:53
**Status:** Step 1 in progress (fetching markets)
**Progress:** 1,500+ markets fetched
**Estimated Completion:** ~08:40 (10-15 min total)

Check progress:
```bash
tail -f logs/market_mapping.log
```

## After Mapping Completes

### 1. Verify Coverage
```bash
python3 src/utils/market_mapper.py --stats
```

Expected output:
```
Total mappings: 100,000+
Total markets: 50,000+
Trade Mapping Coverage:
  Total trades: 2,025,299
  Mapped trades: 1,500,000+ (70-80%)
  Coverage: 70-80%
```

### 2. Train Models
```bash
python3 scripts/train_short_expiry.py
```

This should now work because trades have condition_ids!

### 3. Deploy Hybrid Bot
Once models are trained:
- Update `config_short_expiry.json` to enable ML
- Restart bot with ML predictions
- Monitor performance vs rule-based

---

**⏳ Mapping in progress... Check logs for updates!**
