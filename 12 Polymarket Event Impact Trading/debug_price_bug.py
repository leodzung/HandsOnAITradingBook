"""
Debug the price discrepancy bug.
User bought YES at $0.88, but we showed $0.99.
"""
import requests
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.polymarket_client import PolymarketClient
from core.price_fetcher import PriceFetcher

def debug_btc68k_prices():
    """Debug why we're reading wrong prices."""

    condition_id = "0xd290ea4b4607f5b107e9988bd33dcd49edd5a1a275d2664fb869edc50af5f888"

    print("=" * 80)
    print("DEBUGGING: Why did we read $0.99 when actual price was $0.88?")
    print("=" * 80)
    print(f"\nCondition ID: {condition_id}")
    print(f"User bought YES at: $0.88")
    print(f"Our system showed: $0.99")
    print(f"Discrepancy: $0.11 (12.5% error!)\n")

    client = PolymarketClient()
    price_fetcher = PriceFetcher(client)

    # Step 1: Get market info from CLOB
    print("=" * 80)
    print("STEP 1: Get token IDs from CLOB market")
    print("=" * 80)

    market_url = f"https://clob.polymarket.com/markets/{condition_id}"
    market_resp = requests.get(market_url, timeout=10)
    market_data = market_resp.json()

    tokens = market_data.get('tokens', [])
    print(f"\nTokens from CLOB market:")
    for token in tokens:
        print(f"  {token.get('outcome')}: {token.get('token_id')}")

    yes_token = next((t for t in tokens if t.get('outcome') == 'Yes'), None)
    no_token = next((t for t in tokens if t.get('outcome') == 'No'), None)

    yes_token_id = yes_token.get('token_id')
    no_token_id = no_token.get('token_id')

    # Step 2: Get raw orderbook for YES token
    print("\n" + "=" * 80)
    print("STEP 2: Get raw orderbook for YES token")
    print("=" * 80)

    book_url = "https://clob.polymarket.com/book"
    yes_book_resp = requests.get(book_url, params={'token_id': yes_token_id}, timeout=10)
    yes_book = yes_book_resp.json()

    print(f"\nYES token orderbook:")
    print(f"  Timestamp: {yes_book.get('timestamp')}")
    print(f"  Hash: {yes_book.get('hash')}")

    # Show top 10 asks
    asks = yes_book.get('asks', [])
    print(f"\n  Top 10 ASKs (prices to BUY YES):")
    for i, ask in enumerate(asks[:10], 1):
        price = float(ask['price'])
        size = float(ask['size'])
        print(f"    {i}. ${price:.3f} × {size:,.2f} shares")

    if asks:
        best_ask = float(asks[0]['price'])
        print(f"\n  ✅ Best ASK (cheapest to buy YES): ${best_ask:.3f}")
    else:
        print(f"\n  ❌ No asks in orderbook!")
        best_ask = None

    # Step 3: What does our get_token_ids return?
    print("\n" + "=" * 80)
    print("STEP 3: What does client.get_token_ids() return?")
    print("=" * 80)

    token_ids = client.get_token_ids(condition_id)
    print(f"\nget_token_ids() returned:")
    print(f"  yes_token_id: {token_ids.get('yes_token_id')}")
    print(f"  no_token_id: {token_ids.get('no_token_id')}")

    # Check if they match
    if token_ids.get('yes_token_id') == yes_token_id:
        print(f"\n  ✅ YES token ID matches!")
    else:
        print(f"\n  ❌ YES token ID MISMATCH!")
        print(f"     Expected: {yes_token_id}")
        print(f"     Got: {token_ids.get('yes_token_id')}")

    # Step 4: What does get_clob_prices return?
    print("\n" + "=" * 80)
    print("STEP 4: What does client.get_clob_prices() return?")
    print("=" * 80)

    clob_prices = client.get_clob_prices(condition_id, side='BUY')
    print(f"\nget_clob_prices(side='BUY') returned:")
    print(f"  YES: ${clob_prices.get('yes')}")
    print(f"  NO: ${clob_prices.get('no')}")

    if clob_prices.get('yes') != best_ask:
        print(f"\n  ❌ PRICE MISMATCH!")
        print(f"     Raw orderbook best ask: ${best_ask:.3f}")
        print(f"     get_clob_prices() returned: ${clob_prices.get('yes')}")
        print(f"     Difference: ${abs(clob_prices.get('yes') - best_ask):.3f}")
    else:
        print(f"\n  ✅ Prices match!")

    # Step 5: What does PriceFetcher return?
    print("\n" + "=" * 80)
    print("STEP 5: What does PriceFetcher.get_entry_prices() return?")
    print("=" * 80)

    entry_prices = price_fetcher.get_entry_prices(condition_id)
    if entry_prices:
        print(f"\nget_entry_prices() returned:")
        print(f"  YES: ${entry_prices.yes_price:.3f}")
        print(f"  NO: ${entry_prices.no_price:.3f}")

        if entry_prices.yes_price != best_ask:
            print(f"\n  ❌ PRICE MISMATCH!")
            print(f"     Raw orderbook best ask: ${best_ask:.3f}")
            print(f"     PriceFetcher returned: ${entry_prices.yes_price:.3f}")
            print(f"     Difference: ${abs(entry_prices.yes_price - best_ask):.3f}")
        else:
            print(f"\n  ✅ Prices match!")
    else:
        print(f"\n  ❌ Could not fetch prices!")

    # Step 6: Check NO token orderbook too
    print("\n" + "=" * 80)
    print("STEP 6: Check NO token orderbook")
    print("=" * 80)

    no_book_resp = requests.get(book_url, params={'token_id': no_token_id}, timeout=10)
    no_book = no_book_resp.json()

    no_asks = no_book.get('asks', [])
    print(f"\nNO token - Top 5 ASKs:")
    for i, ask in enumerate(no_asks[:5], 1):
        price = float(ask['price'])
        size = float(ask['size'])
        print(f"  {i}. ${price:.3f} × {size:,.2f} shares")

    if no_asks:
        no_best_ask = float(no_asks[0]['price'])
        print(f"\nNO best ASK: ${no_best_ask:.3f}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY & DIAGNOSIS")
    print("=" * 80)

    print(f"\nUser's execution: Bought YES at $0.88")
    print(f"Raw CLOB orderbook: Best ASK is ${best_ask:.3f}")
    print(f"Our system showed: ${clob_prices.get('yes')}")

    if best_ask and clob_prices.get('yes'):
        diff = clob_prices.get('yes') - best_ask
        if abs(diff) > 0.01:
            print(f"\n❌ BUG CONFIRMED: We're reading ${diff:.3f} higher than actual!")
            print(f"\nPossible causes:")
            print(f"  1. Orderbook caching/staleness")
            print(f"  2. Reading wrong token/side")
            print(f"  3. API returning wrong data")
            print(f"  4. Timing issue (orderbook changed)")
        else:
            print(f"\n✅ Prices are correct NOW (within 1 cent)")
            print(f"\nMost likely:")
            print(f"  - Orderbook was different when user tested earlier")
            print(f"  - Market moved between our test and user's purchase")

if __name__ == "__main__":
    debug_btc68k_prices()
