#!/usr/bin/env python3
"""
Detect resolved markets by analyzing outcome_prices.
If outcome_prices = ["0", "1"] or ["1", "0"], the market is resolved.
"""
import sqlite3
import json

def detect_resolved_markets():
    """Find markets that are effectively resolved based on outcome prices."""
    
    conn = sqlite3.connect('data/alchemy_trades.db')
    cursor = conn.cursor()
    
    # Get markets with outcome_prices
    cursor.execute("""
        SELECT condition_id, question, end_date, outcome_prices, active, resolved
        FROM markets
        WHERE outcome_prices IS NOT NULL
        AND end_date < '2026-02-21'
        ORDER BY end_date DESC
    """)
    
    resolved_count = 0
    ambiguous_count = 0
    samples = []
    
    for row in cursor.fetchall():
        condition_id, question, end_date, outcome_prices_str, active, resolved = row
        
        try:
            outcome_prices = json.loads(outcome_prices_str)
            
            # Check if resolved (one outcome = 1.0, other = 0.0)
            if len(outcome_prices) == 2:
                yes_price = float(outcome_prices[0])
                no_price = float(outcome_prices[1])
                
                # Market is resolved if one side is 0 or 1
                if (yes_price == 0.0 and no_price == 1.0) or (yes_price == 1.0 and no_price == 0.0):
                    resolved_count += 1
                    if len(samples) < 5:
                        outcome = "YES" if yes_price == 1.0 else "NO"
                        samples.append({
                            'question': question[:60],
                            'end_date': end_date,
                            'outcome': outcome,
                            'condition_id': condition_id
                        })
                elif yes_price > 0 and yes_price < 1 and no_price > 0 and no_price < 1:
                    ambiguous_count += 1
        except:
            pass
    
    conn.close()
    
    print("=== RESOLVED MARKETS DETECTED ===\n")
    print(f"Total markets checked: {resolved_count + ambiguous_count}")
    print(f"✅ Effectively RESOLVED (prices = 0 or 1): {resolved_count:,}")
    print(f"⏳ Still ambiguous (prices between 0-1): {ambiguous_count:,}")
    
    if resolved_count > 0:
        print(f"\n✅✅ GREAT NEWS: You have {resolved_count:,} resolved markets!")
        print("\nSample resolved markets:")
        for s in samples:
            print(f"  • {s['question']}...")
            print(f"    Outcome: {s['outcome']} | End: {s['end_date']}")
    
    return resolved_count

if __name__ == '__main__':
    count = detect_resolved_markets()
    
    if count > 0:
        print("\n" + "="*60)
        print("🎯 YOU CAN NOW CREATE REAL LABELS!")
        print("="*60)
        print("\nNext step:")
        print("  python3 create_labels_from_outcome_prices.py")
