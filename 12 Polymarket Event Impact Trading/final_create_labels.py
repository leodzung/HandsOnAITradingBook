#!/usr/bin/env python3
"""
Create REAL training labels from 1.2M+ trades with resolved outcomes.
"""
import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/alchemy_trades.db')

print("=== Creating REAL Training Labels ===\n")

# Get ALL trades with markets in our date range
query = """
SELECT 
    t.id as trade_id,
    t.condition_id,
    t.block_timestamp,
    t.price as trade_price,
    t.maker_amount_filled,
    t.taker_amount_filled,
    m.question,
    m.end_date,
    m.outcome_prices,
    m.volume,
    m.liquidity
FROM on_chain_trades t
JOIN markets m ON t.condition_id = m.condition_id
WHERE m.end_date >= '2025-08-01' 
AND m.end_date <= '2026-02-21'
AND m.outcome_prices IS NOT NULL
LIMIT 100000
"""

print("Loading trades (first 100K)...")
df = pd.read_sql_query(query, conn)
conn.close()

print(f"✅ Loaded {len(df):,} trades")
print(f"✅ Unique markets: {df['condition_id'].nunique():,}")

# Parse outcome prices and filter for resolved markets
def parse_and_label(row):
    try:
        prices = json.loads(row['outcome_prices'])
        if len(prices) < 2:
            return None, None
            
        yes_price = float(prices[0])
        no_price = float(prices[1])
        
        # Check if resolved (prices at extremes)
        if yes_price >= 0.95 and no_price <= 0.05:
            outcome = "YES"
        elif no_price >= 0.95 and yes_price <= 0.05:
            outcome = "NO"  
        elif yes_price == 0.0 and no_price == 1.0:
            outcome = "NO"
        elif yes_price == 1.0 and no_price == 0.0:
            outcome = "YES"
        else:
            return None, None  # Not clearly resolved
        
        # Create label
        trader_bet_yes = row['trade_price'] > 0.5
        
        if outcome == "YES":
            label = 1 if trader_bet_yes else -1
        else:
            label = 1 if not trader_bet_yes else -1
            
        return outcome, label
        
    except:
        return None, None

print("\nParsing outcomes and creating labels...")
df[['resolved_outcome', 'label']] = df.apply(
    lambda row: pd.Series(parse_and_label(row)), axis=1
)

df_labeled = df[df['label'].notna()].copy()

print(f"\n✅ RESOLVED markets with trades: {len(df_labeled):,} trades")
print(f"   Unique resolved markets: {df_labeled['condition_id'].nunique():,}")

if len(df_labeled) > 0:
    print(f"\n📊 Label distribution:")
    print(df_labeled['label'].value_counts().to_dict())
    
    print(f"\n📋 Sample resolved markets:")
    for cid in df_labeled['condition_id'].unique()[:10]:
        market = df_labeled[df_labeled['condition_id'] == cid].iloc[0]
        print(f"  • {market['question'][:70]}")
        print(f"    Outcome: {market['resolved_outcome']} | Trades: {len(df_labeled[df_labeled['condition_id'] == cid]):,}")
    
    output = 'data/REAL_labeled_training_data.csv'
    df_labeled.to_csv(output, index=False)
    
    print(f"\n{'='*70}")
    print(f"✅✅ SUCCESS! REAL LABELED DATASET: {output}")
    print(f"   {len(df_labeled):,} trades from {df_labeled['condition_id'].nunique():,} resolved markets")
    print(f"{'='*70}")
else:
    print("\n⏳ Markets have ended but not yet resolved (prices still ambiguous)")
    print("   Wait a few more days for official resolution")
