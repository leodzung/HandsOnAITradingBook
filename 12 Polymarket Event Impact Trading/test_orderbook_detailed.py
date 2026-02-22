"""
Check both sides of the orderbook in detail.
"""
import requests
import json

def check_orderbook():
    """Check BTC > $68K orderbook in detail."""

    condition_id = "0xd290ea4b4607f5b107e9988bd33dcd49edd5a1a275d2664fb869edc50af5f888"

    print("=" * 80)
    print("BTC > $68K Orderbook Analysis")
    print("=" * 80)

    # Get market info
    market_url = f"https://clob.polymarket.com/markets/{condition_id}"
    market_resp = requests.get(market_url, timeout=10)
    market_data = market_resp.json()

    tokens = market_data.get('tokens', [])
    yes_token = next((t for t in tokens if t.get('outcome') == 'Yes'), None)
    no_token = next((t for t in tokens if t.get('outcome') == 'No'), None)

    print(f"\nYES Token ID: {yes_token.get('token_id')}")
    print(f"NO Token ID: {no_token.get('token_id')}")

    # Get YES orderbook
    print("\n" + "=" * 80)
    print("YES TOKEN ORDERBOOK")
    print("=" * 80)

    book_url = "https://clob.polymarket.com/book"
    yes_book = requests.get(book_url, params={'token_id': yes_token.get('token_id')}, timeout=10)
    yes_data = yes_book.json()

    print("\n--- BIDS (People wanting to BUY YES from us - we SELL to them) ---")
    bids = yes_data.get('bids', [])[:10]
    for i, bid in enumerate(bids, 1):
        print(f"{i}. Price: ${float(bid['price']):.3f}, Size: {float(bid['size']):,.2f}")

    print("\n--- ASKS (People SELLING YES to us - we BUY from them) ---")
    asks = yes_data.get('asks', [])[:10]
    if asks:
        for i, ask in enumerate(asks, 1):
            print(f"{i}. Price: ${float(ask['price']):.3f}, Size: {float(ask['size']):,.2f}")
        print(f"\n✅ Best ASK (cheapest price to BUY YES): ${float(asks[0]['price']):.3f}")
    else:
        print("❌ No ASKs available")

    # Get NO orderbook
    print("\n" + "=" * 80)
    print("NO TOKEN ORDERBOOK")
    print("=" * 80)

    no_book = requests.get(book_url, params={'token_id': no_token.get('token_id')}, timeout=10)
    no_data = no_book.json()

    print("\n--- BIDS (People wanting to BUY NO from us - we SELL to them) ---")
    bids = no_data.get('bids', [])[:10]
    for i, bid in enumerate(bids, 1):
        print(f"{i}. Price: ${float(bid['price']):.3f}, Size: {float(bid['size']):,.2f}")

    print("\n--- ASKS (People SELLING NO to us - we BUY from them) ---")
    asks = no_data.get('asks', [])[:10]
    if asks:
        for i, ask in enumerate(asks, 1):
            print(f"{i}. Price: ${float(ask['price']):.3f}, Size: {float(ask['size']):,.2f}")
        print(f"\n✅ Best ASK (cheapest price to BUY NO): ${float(asks[0]['price']):.3f}")
    else:
        print("❌ No ASKs available")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    yes_best_ask = float(asks[0]['price']) if yes_data.get('asks') else None
    no_best_ask = float(asks[0]['price']) if no_data.get('asks') else None

    print(f"\nTo BUY (Entry Prices):")
    print(f"  YES: ${yes_best_ask:.3f} (best ask)" if yes_best_ask else "  YES: No liquidity")
    print(f"  NO:  ${no_best_ask:.3f} (best ask)" if no_best_ask else "  NO: No liquidity")

    yes_best_bid = float(bids[0]['price']) if yes_data.get('bids') else None
    no_best_bid = float(bids[0]['price']) if no_data.get('bids') else None

    print(f"\nTo SELL (Exit Prices):")
    print(f"  YES: ${yes_best_bid:.3f} (best bid)" if yes_best_bid else "  YES: No liquidity")
    print(f"  NO:  ${no_best_bid:.3f} (best bid)" if no_best_bid else "  NO: No liquidity")

    if yes_best_ask and yes_best_bid:
        yes_spread = ((yes_best_ask - yes_best_bid) / yes_best_ask) * 100
        print(f"\nYES Spread: {yes_spread:.2f}%")

    if no_best_ask and no_best_bid:
        no_spread = ((no_best_ask - no_best_bid) / no_best_ask) * 100
        print(f"NO Spread: {no_spread:.2f}%")

if __name__ == "__main__":
    check_orderbook()
