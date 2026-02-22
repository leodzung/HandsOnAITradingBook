#!/usr/bin/env python3
"""
Check overlap between on-chain trades and ACTUALLY resolved markets.
Uses alchemy_trades.db (not polymarket_history.db).
"""
import sqlite3
import json

def check_overlap():
    conn = sqlite3.connect('data/alchemy_trades.db')
    cursor = conn.cursor()
    
    print("=== CHECKING REAL OVERLAP ===\n")
    
    # Get resolved markets (outcome_prices = ["0","1"] or ["1","0"])
    cursor.execute("""
        SELECT condition_id, question, end_date, outcome_prices
        FROM markets
        WHERE end_date >= '2025-08-01' 
        AND end_date <= '2026-02-21'
        AND outcome_prices IS NOT NULL
    """)
    
    resolved_markets = {}
    for row in cursor.fetchall():
        cid, question, end_date, prices_str = row
        try:
            prices = json.loads(prices_str)
            if len(prices) >= 2:
                # Check if effectively resolved (one side very high, other very low)
                p0 = float(prices[0])
                p1 = float(prices[1])
                
                # Market is resolved if prices are extreme (0/1 or very close)
                if (p0 <= 0.01 and p1 >= 0.99) or (p0 >= 0.99 and p1 <= 0.01):
                    outcome = "YES" if p0 >= 0.99 else "NO"
                    resolved_markets[cid] = {
                        'question': question,
                        'end_date': end_date,
                        'outcome': outcome,
                        'prices': prices
                    }
        except:
            pass
    
    print(f"✅ Resolved markets found: {len(resolved_markets):,}")
    
    # Get trades with condition_ids
    cursor.execute("""
        SELECT DISTINCT condition_id 
        FROM on_chain_trades 
        WHERE condition_id IS NOT NULL
    """)
    
    trade_condition_ids = set(row[0] for row in cursor.fetchall())
    print(f"✅ On-chain trades with condition_ids: {len(trade_condition_ids):,}")
    
    # Check overlap
    overlap = trade_condition_ids & set(resolved_markets.keys())
    
    print(f"\n{'='*70}")
    print(f"🎯 OVERLAP: {len(overlap):,} markets with BOTH trades AND outcomes!")
    print(f"{'='*70}\n")
    
    if overlap:
        # Count total trades
        placeholders = ','.join(['?' for _ in overlap])
        cursor.execute(f"""
            SELECT COUNT(*) FROM on_chain_trades 
            WHERE condition_id IN ({placeholders})
        """, list(overlap))
        
        total_trades = cursor.fetchone()[0]
        
        print(f"✅✅ SUCCESS! You can create REAL labels for:")
        print(f"   - {len(overlap):,} unique markets")
        print(f"   - {total_trades:,} individual trades")
        print(f"   - Date range: Aug 2025 - Feb 2026")
        
        print(f"\nSample resolved markets:")
        for cid in list(overlap)[:10]:
            m = resolved_markets[cid]
            print(f"  • {m['question'][:60]}")
            print(f"    Outcome: {m['outcome']} | Prices: {m['prices']}")
        
        print(f"\n{'='*70}")
        print("🚀 NEXT STEP: python3 create_labels_from_alchemy.py")
        print(f"{'='*70}")
        
    else:
        print("❌ No overlap found")
    
    conn.close()
    return len(overlap)

if __name__ == '__main__':
    check_overlap()
