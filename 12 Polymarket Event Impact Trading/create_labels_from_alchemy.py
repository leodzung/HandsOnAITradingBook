#!/usr/bin/env python3
"""
Create REAL training labels from resolved markets in alchemy_trades.db.
"""
import sqlite3
import pandas as pd
import json

def create_real_labels():
    conn = sqlite3.connect('data/alchemy_trades.db')
    
    print("=== Creating REAL Training Labels ===\n")
    
    # Get markets with trades that have ended and have clear outcomes
    # outcome_prices = ["0", "1"] or ["1", "0"] indicates resolution
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
        m.outcome_prices
    FROM on_chain_trades t
    JOIN markets m ON t.condition_id = m.condition_id
    WHERE m.end_date >= '2025-08-01' 
    AND m.end_date <= '2026-02-21'
    AND m.outcome_prices IS NOT NULL
    AND (m.outcome_prices LIKE '%\"0\", \"1\"%' OR m.outcome_prices LIKE '%\"1\", \"0\"%')
    """
    
    df = pd.read_sql_query(query, conn)
    
    print(f"✅ Loaded {len(df):,} trades from resolved markets")
    print(f"✅ Unique markets: {df['condition_id'].nunique():,}")
    
    if len(df) == 0:
        print("\n❌ No trades found for resolved markets")
        conn.close()
        return
    
    # Parse outcome_prices and create labels
    def create_label(row):
        try:
            prices = json.loads(row['outcome_prices'])
            yes_price = float(prices[0])
            no_price = float(prices[1])
            
            # Determine resolved outcome
            if yes_price >= 0.99 and no_price <= 0.01:
                resolved_outcome = "YES"
            elif no_price >= 0.99 and yes_price <= 0.01:
                resolved_outcome = "NO"
            else:
                return None  # Not clearly resolved
            
            # Create label based on whether trade was correct
            # If trade_price > 0.5, trader bet YES
            # If trade_price < 0.5, trader bet NO
            trader_bet_yes = row['trade_price'] > 0.5
            
            if resolved_outcome == "YES":
                return 1 if trader_bet_yes else -1
            else:  # NO
                return 1 if not trader_bet_yes else -1
                
        except Exception as e:
            return None
    
    df['label'] = df.apply(create_label, axis=1)
    df_labeled = df[df['label'].notna()].copy()
    
    print(f"\n✅ Created labels for {len(df_labeled):,} trades")
    print(f"   Unique markets: {df_labeled['condition_id'].nunique():,}")
    print(f"   Date range: {df_labeled['block_timestamp'].min()} to {df_labeled['block_timestamp'].max()}")
    
    print(f"\n📊 Label distribution:")
    print(df_labeled['label'].value_counts().to_dict())
    
    # Show sample markets
    print(f"\n📋 Sample resolved markets:")
    for cid in df_labeled['condition_id'].unique()[:5]:
        market = df_labeled[df_labeled['condition_id'] == cid].iloc[0]
        print(f"  • {market['question']}")
        print(f"    Outcome: {market['outcome_prices']}")
        print(f"    Trades: {len(df_labeled[df_labeled['condition_id'] == cid]):,}")
    
    # Save
    output_path = 'data/labeled_from_alchemy.csv'
    df_labeled.to_csv(output_path, index=False)
    
    print(f"\n{'='*70}")
    print(f"✅✅ REAL LABELED DATASET CREATED: {output_path}")
    print(f"{'='*70}")
    
    conn.close()
    return df_labeled

if __name__ == '__main__':
    create_real_labels()
