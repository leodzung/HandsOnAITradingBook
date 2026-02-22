"""
Check recent trades to see if there was a $0.88 execution.
"""
import requests
import json
from datetime import datetime

def check_recent_trades():
    """Check recent trades for BTC > $68K market."""

    # YES token ID
    yes_token_id = "24168195061698673571636804603275958543405788116122493724133027478229770239133"

    print("=" * 80)
    print("Checking Recent Trades for BTC > $68K (YES token)")
    print("=" * 80)

    # Note: The /trades endpoint may require authentication
    # Let's try to get the orderbook timestamp to see when it was last updated

    book_url = "https://clob.polymarket.com/book"
    book_resp = requests.get(book_url, params={'token_id': yes_token_id}, timeout=10)
    book_data = book_resp.json()

    timestamp_ms = int(book_data.get('timestamp', 0))
    timestamp_sec = timestamp_ms / 1000
    orderbook_time = datetime.fromtimestamp(timestamp_sec)

    print(f"\nOrderbook timestamp: {orderbook_time} (your local time)")
    print(f"Current time: {datetime.now()}")

    time_diff_sec = (datetime.now() - orderbook_time).total_seconds()
    print(f"Orderbook age: {time_diff_sec:.1f} seconds")

    # Check if there are any asks near $0.88
    asks = book_data.get('asks', [])

    print(f"\nLooking for $0.88 in the orderbook:")
    found_88 = False
    for i, ask in enumerate(asks, 1):
        price = float(ask['price'])
        size = float(ask['size'])

        # Check if close to $0.88
        if abs(price - 0.88) < 0.02:  # Within 2 cents
            print(f"  {i}. ${price:.3f} × {size:,.2f} shares ← CLOSE TO $0.88")
            found_88 = True
        elif i <= 15:  # Show first 15
            print(f"  {i}. ${price:.3f} × {size:,.2f} shares")

    if not found_88:
        print(f"\n  ❌ No asks near $0.88 found in current orderbook")
        print(f"  Current best ask: ${float(asks[0]['price']):.3f}")
        print(f"\n  This suggests:")
        print(f"    - Market moved since your purchase")
        print(f"    - Best ask was $0.88 when you bought")
        print(f"    - Now it's ${float(asks[0]['price']):.3f}")
    else:
        print(f"\n  ✅ Found liquidity near $0.88")

    # Show bids too
    bids = book_data.get('bids', [])
    print(f"\nCurrent best BID: ${float(bids[0]['price']):.3f}")
    print(f"Current best ASK: ${float(asks[0]['price']):.3f}")
    print(f"Spread: ${float(asks[0]['price']) - float(bids[0]['price']):.3f}")

    # Analysis
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    best_ask_now = float(asks[0]['price'])
    user_execution = 0.88

    print(f"\nUser's market order execution: ${user_execution:.2f}")
    print(f"Current best ask: ${best_ask_now:.3f}")
    print(f"Difference: ${best_ask_now - user_execution:.3f}")

    if best_ask_now > user_execution + 0.05:
        print(f"\n❌ SIGNIFICANT DISCREPANCY!")
        print(f"\nPossible explanations:")
        print(f"  1. Market moved UP after your purchase (prices increased)")
        print(f"  2. You got a better fill through Polymarket's price improvement")
        print(f"  3. Web interface routes through different liquidity sources")
        print(f"  4. There was a brief moment when ask was $0.88")

        print(f"\nMost likely: Market moved. When you bought:")
        print(f"  - Best ask WAS $0.88 → you got filled")
        print(f"  - Now best ask IS $0.99 → market moved up $0.11")
    else:
        print(f"\n✅ Prices are similar (market hasn't moved much)")

if __name__ == "__main__":
    check_recent_trades()
