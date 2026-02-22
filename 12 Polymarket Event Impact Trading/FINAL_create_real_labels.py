#!/usr/bin/env python3
"""
Create REAL training labels - handles string prices correctly.
"""
import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/alchemy_trades.db')

print("=== Creating REAL Training Labels ===\n")

# Get trades from markets in our date range
query = """
SELECT 
    t.id as trade_id,
    t.condition_id,
    t.block_timestamp,
    t.price as trade_price,
    m.question,
    m.end_date,
    m.outcome_prices
FROM on_chain_trades t
JOIN markets m ON t.condition_id = m.condition_id
WHERE m.end_date >= '2025-08-01' 
AND m.end_date <= '2026-02-21'
AND m.outcome_prices IS NOT NULL
"""

print("Loading trades...")
df = pd.read_sql_query(query, conn)
conn.close()

print(f"✅ Loaded {len(df):,} trades from {df['condition_id'].nunique():,} markets")

# Parse outcome prices (handle BOTH strings and numbers)
def parse_and_label(row):
    try:
        prices = json.loads(row['outcome_prices'])
        if len(prices) < 2:
            return None, None
        
        # Convert to float (handles both "0" strings and 0.0 numbers)
        yes_price = float(prices[0])
        no_price = float(prices[1])
        
        # Check if resolved - EXACT match for 0/1
        if (yes_price == 0.0 and no_price == 1.0):
            outcome = "NO"
        elif (yes_price == 1.0 and no_price == 0.0):
            outcome = "YES"
        # Also check very close to 0/1 (>99% certain)
        elif yes_price >= 0.99 and no_price <= 0.01:
            outcome = "YES"
        elif no_price >= 0.99 and yes_price <= 0.01:
            outcome = "NO"
        else:
            return None, None  # Not resolved
        
        # Create label: 1 if trader was correct, -1 if wrong
        trader_bet_yes = row['trade_price'] > 0.5
        
        if outcome == "YES":
            label = 1 if trader_bet_yes else -1
        else:  # NO
            label = 1 if not trader_bet_yes else -1
        
        return outcome, label
        
    except Exception as e:
        return None, None

print("\nParsing outcomes...")
df[['resolved_outcome', 'label']] = df.apply(
    lambda row: pd.Series(parse_and_label(row)), axis=1
)

df_labeled = df[df['label'].notna()].copy()

print(f"\n{'='*70}")
if len(df_labeled) > 0:
    print(f"✅✅ SUCCESS! Found {len(df_labeled):,} trades from RESOLVED markets")
    print(f"   Unique resolved markets: {df_labeled['condition_id'].nunique():,}")
    print(f"   Date range: {df_labeled['block_timestamp'].min()} to {df_labeled['block_timestamp'].max()}")
    
    print(f"\n📊 Label distribution:")
    label_counts = df_labeled['label'].value_counts().to_dict()
    print(f"   Correct predictions (1):  {label_counts.get(1, 0):,}")
    print(f"   Wrong predictions (-1):   {label_counts.get(-1, 0):,}")
    
    print(f"\n📋 Sample resolved markets:")
    for cid in df_labeled['condition_id'].unique()[:15]:
        market = df_labeled[df_labeled['condition_id'] == cid].iloc[0]
        trade_count = len(df_labeled[df_labeled['condition_id'] == cid])
        print(f"  • [{market['resolved_outcome']}] {market['question'][:55]}")
        print(f"     {trade_count:,} trades | End: {market['end_date']}")
    
    output = 'data/REAL_labeled_training_data.csv'
    df_labeled.to_csv(output, index=False)
    
    print(f"\n{'='*70}")
    print(f"✅ SAVED: {output}")
    print(f"{'='*70}")
    print("\n🎯 YOU NOW HAVE REAL LABELS FROM REAL RESOLVED MARKETS!")
    print("   Next: Train your ML models with this dataset")
else:
    print("⏳ No resolved markets found")
    print(f"   Markets checked: {df['condition_id'].nunique():,}")
    print("   These markets have ended but outcomes not yet settled to 0/1")
print(f"{'='*70}")
