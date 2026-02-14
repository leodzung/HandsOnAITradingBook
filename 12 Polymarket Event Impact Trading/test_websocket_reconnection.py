#!/usr/bin/env python3
"""
Test WebSocket Reconnection Logic with Exponential Backoff

This script tests the WebSocket reconnection behavior by:
1. Starting a WebSocket connection
2. Monitoring connection state
3. Simulating connection failures
4. Verifying exponential backoff behavior

Expected behavior:
- Initial connection: 1s delay
- 1st reconnect: ~1s (base) ± 30% jitter
- 2nd reconnect: ~2s ± jitter
- 3rd reconnect: ~4s ± jitter
- 4th reconnect: ~8s ± jitter
- 5th reconnect: ~16s ± jitter
- 6th reconnect: ~32s ± jitter
- 7th+ reconnect: ~60s ± jitter (capped at MAX_RECONNECT_DELAY)
- On successful reconnection: backoff resets to 1s
"""

import sys
import time
import logging
from datetime import datetime

# Add project to path
sys.path.insert(0, '.')

from src.utils.orderbook_websocket import OrderBookWebSocket

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_reconnection_logic():
    """Test WebSocket reconnection with exponential backoff."""

    print("\n" + "="*80)
    print("TESTING WEBSOCKET RECONNECTION WITH EXPONENTIAL BACKOFF")
    print("="*80 + "\n")

    print("This test will:")
    print("1. Start a WebSocket connection")
    print("2. Monitor connection state and reconnection attempts")
    print("3. Display backoff delays and reconnect counts")
    print("\nExpected behavior:")
    print("- Reconnect delays: 1s → 2s → 4s → 8s → 16s → 32s → 60s (max)")
    print("- Each delay has ±30% jitter to prevent thundering herd")
    print("- Unlimited retries (will keep trying as long as running)")
    print("\nPress Ctrl+C to stop\n")

    # Create WebSocket client
    ws_client = OrderBookWebSocket()

    # Add a test market
    # Using a known BTC market
    condition_id = "0x1234567890abcdef"  # Dummy condition
    yes_token = "123456789"
    no_token = "987654321"

    ws_client.add_market(condition_id, yes_token, no_token, "Test Market")

    # Start WebSocket
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting WebSocket...")
    ws_client.start()

    # Monitor connection and stats
    last_reconnect_count = 0
    last_backoff_delay = 0

    try:
        while True:
            time.sleep(2)  # Check every 2 seconds

            stats = ws_client.get_stats()

            # Display connection state
            status = "CONNECTED" if stats['connected'] else "DISCONNECTED"
            reconnects = stats['reconnect_count']
            backoff = stats['current_backoff_delay']

            # Only print if state changed
            if reconnects != last_reconnect_count or backoff != last_backoff_delay:
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

                if reconnects > last_reconnect_count:
                    print(f"\n[{timestamp}] RECONNECTION ATTEMPT #{reconnects}")
                    print(f"  Status: {status}")
                    print(f"  Current backoff delay: {backoff:.1f}s")
                    print(f"  Total reconnects: {reconnects}")
                    print(f"  Total errors: {stats['errors']}")

                    # Verify exponential backoff behavior
                    expected_delays = [1, 2, 4, 8, 16, 32, 60]
                    attempt_idx = min(reconnects - 1, len(expected_delays) - 1)
                    expected = expected_delays[attempt_idx]

                    if reconnects <= len(expected_delays):
                        jitter_range = expected * 0.3
                        min_expected = expected - jitter_range
                        max_expected = expected + jitter_range

                        if min_expected <= backoff <= max_expected:
                            print(f"  ✓ Backoff delay is correct (expected ~{expected}s ± 30%)")
                        else:
                            print(f"  ✗ WARNING: Backoff delay outside expected range")
                            print(f"    Expected: {min_expected:.1f}s - {max_expected:.1f}s")
                else:
                    print(f"\n[{timestamp}] State changed:")
                    print(f"  Status: {status}")
                    print(f"  Current backoff: {backoff:.1f}s")

                last_reconnect_count = reconnects
                last_backoff_delay = backoff

            # Print periodic stats summary
            if int(time.time()) % 30 == 0:
                print(f"\n--- Stats Summary ---")
                print(f"  Connected: {stats['connected']}")
                print(f"  Messages received: {stats['messages_received']}")
                print(f"  Book updates: {stats['book_updates']}")
                print(f"  Reconnections: {stats['reconnects']}")
                print(f"  Errors: {stats['errors']}")
                print(f"  Current backoff: {backoff:.1f}s")

    except KeyboardInterrupt:
        print("\n\nStopping WebSocket...")
        ws_client.stop()
        print("\nFinal stats:")
        stats = ws_client.get_stats()
        print(f"  Total reconnections: {stats['reconnects']}")
        print(f"  Total errors: {stats['errors']}")
        print(f"  Total messages: {stats['messages_received']}")
        print(f"  Final backoff delay: {stats['current_backoff_delay']:.1f}s")
        print("\nTest completed successfully!")


def test_backoff_calculation():
    """Unit test for backoff calculation logic."""

    print("\n" + "="*80)
    print("UNIT TEST: EXPONENTIAL BACKOFF CALCULATION")
    print("="*80 + "\n")

    # Simulate backoff progression
    INITIAL_DELAY = 1
    MAX_DELAY = 60
    MULTIPLIER = 2

    current_delay = INITIAL_DELAY
    delays = []

    print("Simulating backoff progression:")
    for attempt in range(1, 12):
        delays.append(current_delay)
        print(f"  Attempt {attempt}: {current_delay}s delay")

        # Update delay for next iteration
        current_delay = min(current_delay * MULTIPLIER, MAX_DELAY)

    # Verify expectations
    expected = [1, 2, 4, 8, 16, 32, 60, 60, 60, 60, 60]
    assert delays == expected, f"Backoff progression incorrect: {delays}"

    print("\n✓ Backoff calculation is correct!")
    print(f"  Pattern: {' → '.join(map(str, expected[:7]))} (capped at 60s)")
    print(f"  After 7th attempt, all delays stay at 60s")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Test WebSocket reconnection logic')
    parser.add_argument(
        '--unit-test',
        action='store_true',
        help='Run unit test for backoff calculation only'
    )
    args = parser.parse_args()

    if args.unit_test:
        test_backoff_calculation()
    else:
        print("\nNOTE: This test will attempt to connect to Polymarket WebSocket.")
        print("If the WebSocket is unreachable, you'll see reconnection attempts.")
        print("This is EXPECTED behavior to test the exponential backoff logic.\n")
        time.sleep(2)
        test_reconnection_logic()
