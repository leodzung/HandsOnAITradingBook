#!/usr/bin/env python3
"""
Create CORRECT training labels using:
1. Token-condition mapping (determines which outcome was traded)
2. Resolved market outcomes from polymarket_history.db
"""
import sqlite3
import pandas as pd
import json

print("="*70)
print("CREATING CORRECT TRAINING LABELS")
print("="*70)

# Step 1: Load token mapping
print("\n1. Loading token-condition mapping...")
conn_alchemy = sqlite3.connect('data/alchemy_trades.db')

df_map = pd.read_sql_query("""
    SELECT token_id, condition_id, outcome_index
    FROM token_condition_map
""", conn_alchemy)

token_to_outcome = {}
for _, row in df_map.iterrows():
    token_to_outcome[str(row['token_id'])] = int(row['outcome_index'])

print(f"✅ Loaded {len(token_to_outcome):,} token mappings")

# Step 2: Load resolved markets from polymarket_history
print("\n2. Loading resolved markets from polymarket_history...")
conn_history = sqlite3.connect('data/polymarket_history.db')

df_resolved = pd.read_sql_query("""
    SELECT
        condition_id,
        question,
        end_date,
        resolved_outcome,
        outcome_prices
    FROM resolved_markets
    WHERE end_date >= '2025-08-01'
      AND end_date <= '2026-02-21'
      AND resolved_outcome IN ('Yes', 'No')
""", conn_history)
conn_history.close()

print(f"✅ Loaded {len(df_resolved):,} resolved markets")

# Create lookup dict: condition_id -> resolved_outcome_index
resolved_outcome_map = {}
for _, row in df_resolved.iterrows():
    # Yes = outcome_index 0, No = outcome_index 1
    if row['resolved_outcome'] == 'Yes':
        resolved_outcome_map[row['condition_id']] = 0
    else:
        resolved_outcome_map[row['condition_id']] = 1

print(f"✅ Created outcome lookup for {len(resolved_outcome_map):,} markets")

# Step 3: Load trades
print("\n3. Loading trades...")
df_trades = pd.read_sql_query("""
    SELECT
        t.id as trade_id,
        t.condition_id,
        t.block_timestamp,
        t.price as trade_price,
        t.maker_asset_id
    FROM on_chain_trades t
    WHERE t.condition_id IS NOT NULL
      AND t.price IS NOT NULL
      AND t.price > 0
      AND t.price < 1
""", conn_alchemy)

print(f"✅ Loaded {len(df_trades):,} trades")

# Step 4: Map trades to outcomes
print("\n4. Mapping trades to outcomes...")
df_trades['trader_outcome_index'] = df_trades['maker_asset_id'].astype(str).map(token_to_outcome)
df_trades['market_outcome_index'] = df_trades['condition_id'].map(resolved_outcome_map)

# Filter to trades we have mappings for
df_labeled = df_trades[
    df_trades['trader_outcome_index'].notna() &
    df_trades['market_outcome_index'].notna()
].copy()

print(f"✅ Mapped {len(df_labeled):,} trades with both trader + market outcomes")

# Step 5: Create labels
print("\n5. Creating labels...")
df_labeled['label'] = (
    (df_labeled['trader_outcome_index'] == df_labeled['market_outcome_index'])
    .astype(int) * 2 - 1  # Convert True/False to 1.0/-1.0
).astype(float)

df_labeled['trader_bought'] = df_labeled['trader_outcome_index'].map({0: 'YES', 1: 'NO'})
df_labeled['resolved_outcome'] = df_labeled['market_outcome_index'].map({0: 'YES', 1: 'NO'})

# Add market details
market_details = {}
for _, row in df_resolved.iterrows():
    market_details[row['condition_id']] = {
        'question': row['question'],
        'end_date': row['end_date'],
        'outcome_prices': row['outcome_prices']
    }

df_labeled['question'] = df_labeled['condition_id'].map(lambda x: market_details.get(x, {}).get('question', ''))
df_labeled['end_date'] = df_labeled['condition_id'].map(lambda x: market_details.get(x, {}).get('end_date', ''))
df_labeled['outcome_prices'] = df_labeled['condition_id'].map(lambda x: market_details.get(x, {}).get('outcome_prices', ''))

# Calculate hours to expiry
df_labeled['block_timestamp'] = pd.to_datetime(df_labeled['block_timestamp'])
df_labeled['end_date'] = pd.to_datetime(df_labeled['end_date'])
df_labeled['hours_to_expiry'] = (df_labeled['end_date'] - df_labeled['block_timestamp']).dt.total_seconds() / 3600

# Step 6: Validation
print(f"\n{'='*70}")
print("✅✅ SUCCESS! CORRECT LABELED DATASET")
print(f"{'='*70}")
print(f"   Total trades: {len(df_labeled):,}")
print(f"   Unique markets: {df_labeled['condition_id'].nunique():,}")
print(f"   Date range: {df_labeled['block_timestamp'].min()} to {df_labeled['block_timestamp'].max()}")

print(f"\n📊 Label distribution:")
label_counts = df_labeled['label'].value_counts().to_dict()
winners = label_counts.get(1.0, 0)
losers = label_counts.get(-1.0, 0)
print(f"   Winners (1.0):  {winners:,} ({winners/len(df_labeled)*100:.1f}%)")
print(f"   Losers (-1.0):  {losers:,} ({losers/len(df_labeled)*100:.1f}%)")

print(f"\n🔍 Validation (5 winners):")
winners = df_labeled[df_labeled['label'] == 1.0].sample(min(5, len(df_labeled[df_labeled['label'] == 1.0])))
for _, row in winners.iterrows():
    print(f"  ✓ Bought {row['trader_bought']} at ${row['trade_price']:.3f}, market resolved {row['resolved_outcome']}")

print(f"\n🔍 Validation (5 losers):")
losers = df_labeled[df_labeled['label'] == -1.0].sample(min(5, len(df_labeled[df_labeled['label'] == -1.0])))
for _, row in losers.iterrows():
    print(f"  ✗ Bought {row['trader_bought']} at ${row['trade_price']:.3f}, market resolved {row['resolved_outcome']}")

# Step 7: Save
output_cols = ['trade_id', 'condition_id', 'block_timestamp', 'trade_price',
               'trader_bought', 'resolved_outcome', 'question', 'end_date',
               'outcome_prices', 'hours_to_expiry', 'label']

output = 'data/REAL_labeled_from_alchemy.csv'
df_labeled[output_cols].to_csv(output, index=False)

print(f"\n{'='*70}")
print(f"✅ SAVED: {output}")
print(f"✅ Labels created using CORRECT logic (token_condition_map)")
print(f"{'='*70}")

conn_alchemy.close()
