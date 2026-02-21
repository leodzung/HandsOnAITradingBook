#!/usr/bin/env python3
"""
Create REAL labels - FIXED double-JSON encoding bug.
"""
import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/alchemy_trades.db')

print("=== Creating REAL Training Labels (FIXED) ===\n")

query = """
SELECT 
    t.id,
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

df = pd.read_sql_query(query, conn)
conn.close()

print(f"✅ Loaded {len(df):,} trades from {df['condition_id'].nunique():,} markets\n")

def parse_and_label(row):
    try:
        # DOUBLE parse - outcome_prices is double-encoded!
        first_parse = json.loads(row['outcome_prices'])
        
        # Check if we need second parse (if it's still a string)
        if isinstance(first_parse, str):
            prices = json.loads(first_parse)
        else:
            prices = first_parse
        
        if len(prices) < 2:
            return None, None
        
        yes_price = float(prices[0])
        no_price = float(prices[1])
        
        # Resolved if extreme prices
        if (yes_price >= 0.99 and no_price <= 0.01) or yes_price == 1.0:
            outcome = "YES"
        elif (no_price >= 0.99 and yes_price <= 0.01) or no_price == 1.0:
            outcome = "NO"
        else:
            return None, None
        
        trader_bet_yes = row['trade_price'] > 0.5
        label = 1 if (outcome == "YES" and trader_bet_yes) or (outcome == "NO" and not trader_bet_yes) else -1
        
        return outcome, label
    except Exception as e:
        return None, None

print("Parsing outcomes...")
df[['outcome', 'label']] = df.apply(lambda row: pd.Series(parse_and_label(row)), axis=1)
df_labeled = df[df['label'].notna()].copy()

print(f"\n{'='*70}")
if len(df_labeled) > 0:
    print(f"✅✅ SUCCESS! REAL LABELED DATASET")
    print(f"{'='*70}")
    print(f"   Trades: {len(df_labeled):,}")
    print(f"   Markets: {df_labeled['condition_id'].nunique():,}")
    print(f"   Date: {df_labeled['block_timestamp'].min()} → {df_labeled['block_timestamp'].max()}")
    
    print(f"\n📊 Labels:")
    print(df_labeled['label'].value_counts().to_dict())
    
    print(f"\n📋 Samples:")
    for cid in df_labeled['condition_id'].unique()[:15]:
        m = df_labeled[df_labeled['condition_id'] == cid].iloc[0]
        ct = len(df_labeled[df_labeled['condition_id'] == cid])
        print(f"  [{m['outcome']}] {m['question'][:55]} ({ct:,} trades)")
    
    output = 'data/REAL_labeled_from_alchemy.csv'
    df_labeled.to_csv(output, index=False)
    print(f"\n✅ SAVED: {output}")
else:
    print("❌ No resolved markets found")
print(f"{'='*70}")
