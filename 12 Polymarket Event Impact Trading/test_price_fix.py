"""
Test the price endpoint fix.
Verify we now get $0.89 instead of $0.99 for BTC > $68K.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.polymarket_client import PolymarketClient
from core.price_fetcher import PriceFetcher

def test_price_fix():
    """Test that we now get correct prices."""

    condition_id = "0xd290ea4b4607f5b107e9988bd33dcd49edd5a1a275d2664fb869edc50af5f888"

    print("=" * 80)
    print("Testing Price Endpoint Fix")
    print("=" * 80)
    print(f"\nMarket: BTC > $68,000 on February 14")
    print(f"Condition ID: {condition_id}")
    print(f"\nExpected: ~$0.89 (what user sees on web interface)")
    print(f"Previous bug: $0.99 (stale /book data)\n")

    client = PolymarketClient()
    price_fetcher = PriceFetcher(client)

    # Test 1: Direct client method
    print("=" * 80)
    print("TEST 1: client.get_clob_prices() [FIXED]")
    print("=" * 80)

    prices = client.get_clob_prices(condition_id, side='BUY')
    print(f"\nEntry prices (ASK):")
    print(f"  YES: ${prices.get('yes'):.3f}" if prices.get('yes') else "  YES: None")
    print(f"  NO:  ${prices.get('no'):.3f}" if prices.get('no') else "  NO: None")

    if prices.get('yes'):
        if abs(prices.get('yes') - 0.89) < 0.05:
            print(f"\n  ✅ SUCCESS: Price is ~$0.89 (matches web interface!)")
        elif abs(prices.get('yes') - 0.99) < 0.05:
            print(f"\n  ❌ FAILED: Still showing $0.99 (fix didn't work)")
        else:
            print(f"\n  ⚠️  Unexpected price: ${prices.get('yes'):.3f}")

    # Test 2: PriceFetcher (used by bots)
    print("\n" + "=" * 80)
    print("TEST 2: PriceFetcher.get_entry_prices() [Used by bots]")
    print("=" * 80)

    entry_prices = price_fetcher.get_entry_prices(condition_id)
    if entry_prices:
        print(f"\nEntry prices:")
        print(f"  YES: ${entry_prices.yes_price:.3f}")
        print(f"  NO:  ${entry_prices.no_price:.3f}")

        if abs(entry_prices.yes_price - 0.89) < 0.05:
            print(f"\n  ✅ SUCCESS: Bots will now see correct price!")
        elif abs(entry_prices.yes_price - 0.99) < 0.05:
            print(f"\n  ❌ FAILED: Bots still see wrong price")

    # Test 3: Check if market is now tradeable
    print("\n" + "=" * 80)
    print("TEST 3: Would bots trade this market now?")
    print("=" * 80)

    max_entry_price = 0.90
    print(f"\nBot config: max_entry_price = ${max_entry_price}")

    if entry_prices:
        yes_tradeable = entry_prices.yes_price <= max_entry_price
        no_tradeable = entry_prices.no_price <= max_entry_price

        print(f"\nYES @ ${entry_prices.yes_price:.3f}: {'✅ TRADEABLE' if yes_tradeable else '❌ TOO EXPENSIVE'}")
        print(f"NO  @ ${entry_prices.no_price:.3f}: {'✅ TRADEABLE' if no_tradeable else '❌ TOO EXPENSIVE'}")

        if yes_tradeable or no_tradeable:
            print(f"\n🎉 SUCCESS: Market is now tradeable!")
            print(f"   Before fix: Rejected at $0.99")
            print(f"   After fix: Tradeable at ${entry_prices.yes_price:.3f}")
        else:
            print(f"\n⚠️  Market still not tradeable (both > ${max_entry_price})")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if prices.get('yes') and abs(prices.get('yes') - 0.89) < 0.05:
        print(f"\n✅ FIX SUCCESSFUL!")
        print(f"   - Reading correct price: ${prices.get('yes'):.3f}")
        print(f"   - Matches web interface: ~$0.89")
        print(f"   - Bots will now find tradeable markets")
        print(f"\nNext steps:")
        print(f"   1. Run your bots to test market discovery")
        print(f"   2. Check if Bitcoin Feb 14 markets are now found")
        print(f"   3. Verify other markets also show correct prices")
    else:
        print(f"\n❌ FIX MAY NOT BE WORKING")
        print(f"   Current price: ${prices.get('yes'):.3f}")
        print(f"   Expected: ~$0.89")
        print(f"   Please check the implementation")

if __name__ == "__main__":
    test_price_fix()
