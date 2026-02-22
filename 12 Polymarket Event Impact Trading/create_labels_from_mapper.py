#!/usr/bin/env python3
"""
Create training labels from on-chain trades + resolved markets.
Uses market_mapper to connect trades to resolved outcomes.
"""
import sqlite3
import pandas as pd
from datetime import datetime

def create_labeled_dataset():
    """Generate labeled training data from mapped trades and resolved markets."""
    
    # Connect to databases
    alchemy_db = sqlite3.connect('data/alchemy_trades.db')
    history_db = sqlite3.connect('data/polymarket_history.db')
    
    print("=== Creating Labeled Training Dataset ===\n")
    
    # Get resolved markets with outcomes
    print("Loading resolved markets...")
    resolved = pd.read_sql_query("""
        SELECT condition_id, question, resolved_outcome, outcome_prices
        FROM resolved_markets
        WHERE resolved_outcome IS NOT NULL
    """, history_db)
    print(f"✓ Loaded {len(resolved):,} resolved markets")
    
    # Get on-chain trades with condition_ids
    print("\nLoading on-chain trades...")
    trades = pd.read_sql_query("""
        SELECT 
            id, condition_id, block_timestamp, price,
            maker_amount_filled, taker_amount_filled
        FROM on_chain_trades
        WHERE condition_id IS NOT NULL
        ORDER BY block_timestamp
    """, alchemy_db)
    print(f"✓ Loaded {len(trades):,} trades with condition_ids")
    
    # Join trades with resolved outcomes
    print("\nMatching trades to resolved outcomes...")
    labeled = trades.merge(
        resolved[['condition_id', 'question', 'resolved_outcome']],
        on='condition_id',
        how='inner'
    )
    
    print(f"✓ Matched {len(labeled):,} trades to resolved markets")
    
    if len(labeled) == 0:
        print("\n❌ NO OVERLAP - Cannot create labels")
        print("   Run: ./update_mapper_for_labels.sh first")
        return None
    
    # Create labels based on resolved outcome
    def create_label(row):
        """
        Label logic:
        - If resolved_outcome == 'Yes' and price > 0.5: Correct (1)
        - If resolved_outcome == 'No' and price < 0.5: Correct (1)
        - Otherwise: Incorrect (-1)
        """
        if row['resolved_outcome'] == 'Yes':
            return 1 if row['price'] > 0.5 else -1
        elif row['resolved_outcome'] == 'No':
            return 1 if row['price'] < 0.5 else -1
        else:
            return 0  # Neutral
    
    labeled['label'] = labeled.apply(create_label, axis=1)
    
    # Save labeled dataset
    output_path = 'data/labeled_from_mapper.csv'
    labeled.to_csv(output_path, index=False)
    
    print(f"\n✅ Created labeled dataset: {output_path}")
    print(f"   Total samples: {len(labeled):,}")
    print(f"   Unique markets: {labeled['condition_id'].nunique():,}")
    print(f"   Date range: {labeled['block_timestamp'].min()} to {labeled['block_timestamp'].max()}")
    print(f"\n   Label distribution:")
    print(labeled['label'].value_counts().to_dict())
    
    alchemy_db.close()
    history_db.close()
    
    return labeled

if __name__ == '__main__':
    create_labeled_dataset()
