#!/usr/bin/env python3
"""
Create REAL training labels with proper threshold for resolved markets.
Markets are resolved when prices are <0.01 or >0.99 (not exactly 0/1).
"""
import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/alchemy_trades.db')

print("=== Creating REAL Training Labels (Fixed Threshold) ===\n")

query = """
SELECT 
    t.id,
    t.condition_id,
    t.block_timestamp,
    t.price as trade_price,
    m.question,
    m.end_date,
    m.outcome_prices,
    m.volume
FROM on_chain_trades t
JOIN markets m ON t.condition_id = m.condition_id
WHERE m.end_date >= '2025-08-01' 
AND m.end_date <= '2026-02-21'
AND m.outcome_prices IS NOT NULL
"""

df = pd.read_sql_query(query, conn)
conn.close()

print(f"✅ Loaded {len(df):,} trades from {df['condition_id'].nunique():,} markets")

def parse_and_label(row):
    try:
        prices = json.loads(row['outcome_prices'])
        if len(prices) < 2:
            return None, None
        
        yes_price = float(prices[0])
        no_price = float(prices[1])
        
        # RESOLVED if one side >99% or <1%
        if yes_price >= 0.99 or no_price <= 0.01:
            outcome = "YES"
        elif no_price >= 0.99 or yes_price <= 0.01:
            outcome = "NO"
        else:
            return None, None
        
        trader_bet_yes = row['trade_price'] > 0.5
        label = 1 if (outcome == "YES" and trader_bet_yes) or (outcome == "NO" and not trader_bet_yes) else -1
        
        return outcome, label
    except:
        return None, None

print("Parsing outcomes...")
df[['outcome', 'label']] = df.apply(lambda row: pd.Series(parse_and_label(row)), axis=1)
df_labeled = df[df['label'].notna()].copy()

print(f"\n{'='*70}")
print(f"✅✅ SUCCESS! REAL LABELED DATASET CREATED")
print(f"{'='*70}")
print(f"   Total trades: {len(df_labeled):,}")
print(f"   Resolved markets: {df_labeled['condition_id'].nunique():,}")
print(f"   Date range: {df_labeled['block_timestamp'].min()} → {df_labeled['block_timestamp'].max()}")

print(f"\n📊 Labels:")
counts = df_labeled['label'].value_counts()
print(f"   Correct (1):  {counts.get(1, 0):,}")
print(f"   Wrong (-1):   {counts.get(-1, 0):,}")

print(f"\n📋 Sample markets:")
for cid in df_labeled['condition_id'].unique()[:10]:
    m = df_labeled[df_labeled['condition_id'] == cid].iloc[0]
    print(f"  [{m['outcome']}] {m['question'][:60]}")

output = 'data/REAL_labeled_from_alchemy.csv'
df_labeled.to_csv(output, index=False)

print(f"\n✅ SAVED: {output}")
print(f"{'='*70}")
