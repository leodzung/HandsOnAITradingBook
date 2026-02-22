"""
Debug: Check actual orderbook data for BTC > $68K market.
Compare what API returns vs what PriceFetcher sees.
"""
import sys
from pathlib import Path
import json
import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.polymarket_client import PolymarketClient
from core.price_fetcher import PriceFetcher

def test_btc68k_orderbook():
    """Debug BTC > $68K orderbook fetching."""

    # BTC > $68K condition ID from our earlier test
    condition_id = "0xd290ea4b4607f5b107e9988bd33dcd49edd5a1a275d2664fb869edc50af5f888"

    print("=" * 80)
    print("DEBUGGING: BTC > $68K Orderbook Price Discrepancy")
    print("=" * 80)
    print(f"\nCondition ID: {condition_id}")
    print(f"Web interface shows: YES = $0.86")
    print(f"Our system shows: YES = $0.99\n")

    client = PolymarketClient()
    price_fetcher = PriceFetcher(client)

    # Test 1: What does PriceFetcher return?
    print("=" * 80)
    print("TEST 1: PriceFetcher.get_entry_prices()")
    print("=" * 80)

    entry_prices = price_fetcher.get_entry_prices(condition_id)
    if entry_prices:
        print(f"YES price: {entry_prices.yes_price}")
        print(f"NO price: {entry_prices.no_price}")
        print(f"Source: {entry_prices.source if hasattr(entry_prices, 'source') else 'N/A'}")
    else:
        print("❌ No entry prices returned")

    # Test 2: Raw CLOB API orderbook
    print("\n" + "=" * 80)
    print("TEST 2: Raw CLOB API - /book endpoint")
    print("=" * 80)

    # The CLOB API book endpoint
    book_url = f"https://clob.polymarket.com/book"

    # Get orderbook for YES token (assuming token_id format)
    # First, get market info to find token IDs
    market_url = f"https://clob.polymarket.com/markets/{condition_id}"

    try:
        market_resp = requests.get(market_url, timeout=10)
        market_resp.raise_for_status()
        market_data = market_resp.json()

        print(f"\nMarket data from CLOB API:")
        print(json.dumps(market_data, indent=2)[:1000] + "...")

        # Extract token IDs
        tokens = market_data.get('tokens', [])
        if tokens:
            print(f"\nFound {len(tokens)} tokens:")
            for token in tokens:
                outcome = token.get('outcome')
                token_id = token.get('token_id')
                print(f"  - {outcome}: {token_id}")

    except Exception as e:
        print(f"Error fetching market data: {e}")

    # Test 3: Check what get_market_prices returns (the old method)
    print("\n" + "=" * 80)
    print("TEST 3: PolymarketClient.get_market_prices()")
    print("=" * 80)

    try:
        prices = client.get_market_prices(condition_id, side='BUY')
        print(f"YES price: {prices.get('yes_price')}")
        print(f"NO price: {prices.get('no_price')}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 4: Try to fetch orderbook directly for each token
    print("\n" + "=" * 80)
    print("TEST 4: Fetch orderbook for YES token directly")
    print("=" * 80)

    try:
        # Re-fetch market to get token IDs
        market_resp = requests.get(market_url, timeout=10)
        market_data = market_resp.json()
        tokens = market_data.get('tokens', [])

        yes_token = next((t for t in tokens if t.get('outcome') == 'Yes'), None)

        if yes_token:
            token_id = yes_token.get('token_id')
            print(f"\nYES Token ID: {token_id}")

            # Fetch orderbook
            book_params = {
                'token_id': token_id,
                'side': 'SELL'  # We want to BUY, so we look at SELL orders
            }

            book_resp = requests.get(book_url, params=book_params, timeout=10)
            book_resp.raise_for_status()
            book_data = book_resp.json()

            print(f"\nOrderbook response:")
            print(json.dumps(book_data, indent=2)[:2000])

            # Find best ask (lowest sell price)
            asks = book_data.get('asks', [])
            if asks:
                best_ask = asks[0]  # Should be sorted by price
                print(f"\n✅ Best ASK (price to BUY YES):")
                print(f"   Price: ${float(best_ask['price']):.3f}")
                print(f"   Size: {best_ask['size']}")
            else:
                print("\n❌ No asks in orderbook")

    except Exception as e:
        print(f"Error fetching orderbook: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_btc68k_orderbook()
