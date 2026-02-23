#!/usr/bin/env python3
"""
Create CORRECT training labels using actual outcome_index from trades.

FIXES: Previous script incorrectly assumed trade_price > 0.5 = bought YES.
NOW: Uses maker_asset_id → outcome_index mapping to determine actual outcome traded.
"""
import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/alchemy_trades.db')

print("=== Creating CORRECT Training Labels ===\n")

# Join trades with token mapping to get ACTUAL outcome traded
query = """
SELECT
    t.id as trade_id,
    t.condition_id,
    t.block_timestamp,
    t.price as trade_price,
    t.maker_asset_id,
    tcm.outcome_index,
    m.question,
    m.end_date,
    m.outcome_prices
FROM on_chain_trades t
JOIN token_condition_map tcm ON CAST(t.maker_asset_id AS TEXT) = CAST(tcm.token_id AS TEXT)
JOIN markets m ON t.condition_id = m.condition_id
WHERE m.end_date >= '2025-08-01'
  AND m.end_date <= '2026-02-21'
  AND m.outcome_prices IS NOT NULL
  AND t.price IS NOT NULL
  AND t.price > 0
  AND t.price < 1
"""

print("Loading trades with outcome mapping...")
df = pd.read_sql_query(query, conn)
conn.close()

print(f"✅ Loaded {len(df):,} trades from {df['condition_id'].nunique():,} markets")

# Parse outcome prices and create CORRECT labels
def parse_and_label(row):
    try:
        prices = json.loads(row['outcome_prices'])
        if len(prices) < 2:
            return None, None

        yes_price = float(prices[0])
        no_price = float(prices[1])

        # Check if resolved
        if (yes_price == 0.0 and no_price == 1.0):
            market_outcome = "NO"  # NO won
            winning_outcome_index = 1
        elif (yes_price == 1.0 and no_price == 0.0):
            market_outcome = "YES"  # YES won
            winning_outcome_index = 0
        elif yes_price >= 0.99 and no_price <= 0.01:
            market_outcome = "YES"
            winning_outcome_index = 0
        elif no_price >= 0.99 and yes_price <= 0.01:
            market_outcome = "NO"
            winning_outcome_index = 1
        else:
            return None, None  # Not resolved

        # CORRECT label logic: Check if trader bought the winning outcome
        trader_outcome_index = row['outcome_index']  # 0=YES, 1=NO

        if trader_outcome_index == winning_outcome_index:
            label = 1.0  # Trader bought the winner
        else:
            label = -1.0  # Trader bought the loser

        return market_outcome, label

    except Exception as e:
        print(f"Error parsing row: {e}")
        return None, None

print("\nParsing outcomes...")
df[['resolved_outcome', 'label']] = df.apply(
    lambda row: pd.Series(parse_and_label(row)), axis=1
)

df_labeled = df[df['label'].notna()].copy()

# Add outcome name for clarity
df_labeled['trader_bought'] = df_labeled['outcome_index'].map({0: 'YES', 1: 'NO'})

print(f"\n{'='*70}")
if len(df_labeled) > 0:
    print(f"✅✅ SUCCESS! Found {len(df_labeled):,} trades from RESOLVED markets")
    print(f"   Unique resolved markets: {df_labeled['condition_id'].nunique():,}")
    print(f"   Date range: {df_labeled['block_timestamp'].min()} to {df_labeled['block_timestamp'].max()}")

    print(f"\n📊 Label distribution:")
    label_counts = df_labeled['label'].value_counts().to_dict()
    print(f"   Winning trades (1):  {label_counts.get(1.0, 0):,} ({label_counts.get(1.0, 0)/len(df_labeled)*100:.1f}%)")
    print(f"   Losing trades (-1):  {label_counts.get(-1.0, 0):,} ({label_counts.get(-1.0, 0)/len(df_labeled)*100:.1f}%)")

    print(f"\n🔍 Validation sample (first 5 winners):")
    winners = df_labeled[df_labeled['label'] == 1.0].head(5)
    for _, row in winners.iterrows():
        print(f"  Bought {row['trader_bought']} at ${row['trade_price']:.3f}, Market resolved {row['resolved_outcome']} → WIN ✓")

    print(f"\n🔍 Validation sample (first 5 losers):")
    losers = df_labeled[df_labeled['label'] == -1.0].head(5)
    for _, row in losers.iterrows():
        print(f"  Bought {row['trader_bought']} at ${row['trade_price']:.3f}, Market resolved {row['resolved_outcome']} → LOSS ✗")

    # Save with cleaner column set
    output_cols = ['trade_id', 'condition_id', 'block_timestamp', 'trade_price',
                   'trader_bought', 'resolved_outcome', 'question', 'end_date',
                   'outcome_prices', 'label']

    output = 'data/REAL_labeled_from_alchemy.csv'
    df_labeled[output_cols].to_csv(output, index=False)

    # Also create hours_to_expiry for convenience
    df_final = pd.read_csv(output)
    df_final['block_timestamp'] = pd.to_datetime(df_final['block_timestamp'])
    df_final['end_date'] = pd.to_datetime(df_final['end_date'])
    df_final['hours_to_expiry'] = (df_final['end_date'] - df_final['block_timestamp']).dt.total_seconds() / 3600
    df_final.to_csv(output, index=False)

    print(f"\n{'='*70}")
    print(f"✅ SAVED: {output}")
    print(f"{'='*70}")
    print("\n🎯 LABELS ARE NOW CORRECT!")
    print("   Previous bug: Assumed price > 0.5 = bought YES (WRONG)")
    print("   Fixed: Uses actual outcome_index from maker_asset_id (CORRECT)")
else:
    print("⏳ No resolved markets found")
print(f"{'='*70}")
