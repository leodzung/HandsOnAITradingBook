"""
Detailed analysis of why Bitcoin Feb 14 markets are being filtered out.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.polymarket_client import PolymarketClient
from core.price_fetcher import PriceFetcher

def test_detailed_prices():
    """Get detailed price info for all Bitcoin Feb 14 markets."""

    print("=" * 80)
    print("DETAILED ANALYSIS: Bitcoin Feb 14 Market Prices & Spreads")
    print("=" * 80)

    # Initialize client and price fetcher
    client = PolymarketClient()
    price_fetcher = PriceFetcher(client)

    # Get Bitcoin Feb 14 event
    slug = "bitcoin-above-on-february-14"
    markets = client.get_markets_from_event(slug, exclude_closed=True)

    print(f"\nFound {len(markets)} active markets from event '{slug}'")
    print(f"\nQuality filter thresholds:")
    print(f"  - Price range: 0.05 - 0.95")
    print(f"  - Max spread: 10.0%")
    print(f"  - Max entry price: 0.90")
    print("\n" + "=" * 80)

    for i, market in enumerate(markets, 1):
        question = market.get('question', 'N/A')
        condition_id = market.get('conditionId')
        volume = market.get('volume', 0)

        try:
            volume_float = float(volume)
            volume_str = f"${volume_float:,.0f}"
        except:
            volume_str = str(volume)

        print(f"\n{i}. {question}")
        print(f"   Condition ID: {condition_id}")
        print(f"   Volume: {volume_str}")

        # Get entry prices (ASK)
        entry_prices = price_fetcher.get_entry_prices(condition_id)
        yes_entry = entry_prices.yes_price if entry_prices else None
        no_entry = entry_prices.no_price if entry_prices else None

        # Get exit prices (BID)
        exit_prices = price_fetcher.get_exit_prices(condition_id)
        yes_exit = exit_prices.yes_price if exit_prices else None
        no_exit = exit_prices.no_price if exit_prices else None

        print(f"\n   Entry Prices (ASK):")
        print(f"     YES: {yes_entry}")
        print(f"     NO:  {no_entry}")

        print(f"\n   Exit Prices (BID):")
        print(f"     YES: {yes_exit}")
        print(f"     NO:  {no_exit}")

        # Calculate spreads
        if yes_entry is not None and yes_exit is not None and yes_entry > 0:
            yes_spread_pct = ((yes_entry - yes_exit) / yes_entry) * 100
            print(f"\n   YES Spread: {yes_spread_pct:.2f}%")
        else:
            yes_spread_pct = None
            print(f"\n   YES Spread: Cannot calculate")

        if no_entry is not None and no_exit is not None and no_entry > 0:
            no_spread_pct = ((no_entry - no_exit) / no_entry) * 100
            print(f"   NO Spread:  {no_spread_pct:.2f}%")
        else:
            no_spread_pct = None
            print(f"   NO Spread:  Cannot calculate")

        # Check filter reasons
        print(f"\n   Filter Analysis:")
        failures = []

        # Price range check
        if yes_entry is not None:
            if yes_entry < 0.05 or yes_entry > 0.95:
                failures.append(f"YES price out of range ({yes_entry:.3f})")
        if no_entry is not None:
            if no_entry < 0.05 or no_entry > 0.95:
                failures.append(f"NO price out of range ({no_entry:.3f})")

        # Max entry price check
        if yes_entry is not None and yes_entry > 0.90:
            failures.append(f"YES > max entry price ({yes_entry:.3f} > 0.90)")
        if no_entry is not None and no_entry > 0.90:
            failures.append(f"NO > max entry price ({no_entry:.3f} > 0.90)")

        # Spread check
        if yes_spread_pct is not None and yes_spread_pct > 10.0:
            failures.append(f"YES spread too wide ({yes_spread_pct:.2f}% > 10%)")
        if no_spread_pct is not None and no_spread_pct > 10.0:
            failures.append(f"NO spread too wide ({no_spread_pct:.2f}% > 10%)")

        # No prices
        if yes_entry is None and no_entry is None:
            failures.append("No entry prices available")

        if failures:
            print(f"     ❌ REJECTED:")
            for reason in failures:
                print(f"        - {reason}")
        else:
            print(f"     ✅ PASSES all filters")

        print(f"\n{'─' * 80}")

if __name__ == "__main__":
    test_detailed_prices()
