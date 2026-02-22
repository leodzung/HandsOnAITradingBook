#!/usr/bin/env python3
"""
Check if recently closed markets have been resolved by querying Gamma API directly.
"""
import requests
import sqlite3
from datetime import datetime, timedelta

def check_resolved_status():
    """Check if Gamma API returns resolved markets."""
    
    # Get a recently closed market from our DB
    conn = sqlite3.connect('data/alchemy_trades.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT condition_id, question, end_date 
        FROM markets 
        WHERE end_date < '2026-02-15' AND end_date > '2026-02-01'
        LIMIT 1
    """)
    
    market = cursor.fetchone()
    conn.close()
    
    if not market:
        print("No recently closed markets found")
        return
    
    condition_id, question, end_date = market
    print(f"Checking market: {question}")
    print(f"Condition ID: {condition_id}")
    print(f"End date: {end_date}")
    
    # Query Gamma API for this specific market
    try:
        url = f"https://gamma-api.polymarket.com/markets/{condition_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ API Response:")
            print(f"  Active: {data.get('active')}")
            print(f"  Closed: {data.get('closed')}")
            print(f"  Resolved: {data.get('resolved')}")
            print(f"  Outcome: {data.get('resolvedOutcome', 'Not resolved yet')}")
            
            if data.get('resolved'):
                print(f"\n✅ Market IS resolved! Outcome: {data.get('resolvedOutcome')}")
            else:
                print(f"\n⏳ Market closed but not yet resolved")
                print(f"   This is normal - resolution can take hours/days after closing")
        else:
            print(f"API error: {response.status_code}")
            
    except Exception as e:
        print(f"Error querying API: {e}")

if __name__ == '__main__':
    check_resolved_status()
