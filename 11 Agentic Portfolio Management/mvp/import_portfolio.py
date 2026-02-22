#!/usr/bin/env python3
"""
Import Portfolio from Robinhood to Alpaca Paper Trading

Usage:
    1. CSV Import:    python import_portfolio.py portfolio.csv
    2. Manual Input:  python import_portfolio.py --manual
    3. JSON Input:    python import_portfolio.py portfolio.json

CSV Format (Robinhood export or custom):
    Symbol,Quantity,Average Cost
    AAPL,50,150.25
    NVDA,25,450.00

JSON Format:
    [
        {"symbol": "AAPL", "quantity": 50, "avg_cost": 150.25},
        {"symbol": "NVDA", "quantity": 25, "avg_cost": 450.00}
    ]
"""

import os
import sys
import csv
import json
import time
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Alpaca imports (alpaca-trade-api v3.0)
try:
    import alpaca_trade_api as tradeapi
except ImportError:
    print("Error: alpaca-trade-api not installed. Run: pip install alpaca-trade-api")
    sys.exit(1)


class PortfolioImporter:
    """Import portfolio positions into Alpaca paper trading"""

    def __init__(self):
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

        if not api_key or not secret_key:
            raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env")

        self.api = tradeapi.REST(api_key, secret_key, base_url, api_version='v2')
        self.account = self.api.get_account()

        print(f"\n{'='*60}")
        print("ALPACA PAPER TRADING - PORTFOLIO IMPORTER")
        print(f"{'='*60}")
        print(f"Account: {self.account.account_number}")
        print(f"Cash: ${float(self.account.cash):,.2f}")
        print(f"Portfolio Value: ${float(self.account.portfolio_value):,.2f}")
        print(f"{'='*60}\n")

    def get_current_positions(self):
        """Get current Alpaca positions"""
        positions = self.api.list_positions()
        return {p.symbol: {
            'qty': float(p.qty),
            'market_value': float(p.market_value),
            'avg_entry': float(p.avg_entry_price)
        } for p in positions}

    def close_all_positions(self):
        """Close all existing positions"""
        positions = self.api.list_positions()
        if not positions:
            print("No existing positions to close.")
            return

        print(f"\nClosing {len(positions)} existing positions...")
        for pos in positions:
            try:
                self.api.close_position(pos.symbol)
                print(f"  ✓ Closed {pos.symbol} ({pos.qty} shares)")
            except Exception as e:
                print(f"  ✗ Failed to close {pos.symbol}: {e}")

        # Wait for orders to settle
        print("Waiting for orders to settle...")
        time.sleep(3)

    def cancel_all_orders(self):
        """Cancel all open orders"""
        orders = self.api.list_orders(status='open')
        if not orders:
            print("No open orders to cancel.")
            return

        print(f"\nCancelling {len(orders)} open orders...")
        self.api.cancel_all_orders()
        time.sleep(2)

    def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is tradeable on Alpaca"""
        try:
            asset = self.api.get_asset(symbol)
            return asset.tradable and asset.status == 'active'
        except:
            return False

    def place_order(self, symbol: str, quantity: float, side: str = 'buy'):
        """Place a market order"""
        try:
            # Round to whole shares (Alpaca doesn't support fractional in paper trading)
            qty = int(round(abs(quantity)))
            if qty == 0:
                print(f"  ⚠ Skipping {symbol}: quantity rounds to 0")
                return None

            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type='market',
                time_in_force='day'
            )
            return order
        except Exception as e:
            print(f"  ✗ Order failed for {symbol}: {e}")
            return None

    def import_from_csv(self, filepath: str) -> list:
        """Parse portfolio from CSV file"""
        positions = []

        with open(filepath, 'r') as f:
            # Try to detect the CSV format
            sample = f.read(2048)
            f.seek(0)

            # Check for common delimiters
            if '\t' in sample:
                reader = csv.DictReader(f, delimiter='\t')
            else:
                reader = csv.DictReader(f)

            # Normalize column names
            for row in reader:
                # Handle various CSV formats
                symbol = None
                quantity = None
                avg_cost = None

                # Try different column name variations
                for key, value in row.items():
                    key_lower = key.lower().strip()

                    if key_lower in ['symbol', 'ticker', 'instrument', 'stock']:
                        symbol = value.strip().upper()
                    elif key_lower in ['quantity', 'qty', 'shares', 'amount']:
                        try:
                            quantity = float(value.replace(',', ''))
                        except:
                            pass
                    elif key_lower in ['average cost', 'avg cost', 'avg_cost', 'cost basis', 'price']:
                        try:
                            avg_cost = float(value.replace('$', '').replace(',', ''))
                        except:
                            pass

                if symbol and quantity:
                    positions.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'avg_cost': avg_cost or 0
                    })

        return positions

    def import_from_json(self, filepath: str) -> list:
        """Parse portfolio from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)

        positions = []
        for item in data:
            positions.append({
                'symbol': item.get('symbol', '').upper(),
                'quantity': float(item.get('quantity', item.get('qty', 0))),
                'avg_cost': float(item.get('avg_cost', item.get('average_cost', 0)))
            })

        return positions

    def manual_input(self) -> list:
        """Get positions via manual input"""
        print("\nEnter positions (one per line, format: SYMBOL QUANTITY)")
        print("Example: AAPL 50")
        print("Enter 'done' when finished.\n")

        positions = []
        while True:
            try:
                line = input("> ").strip()
                if line.lower() == 'done':
                    break

                parts = line.split()
                if len(parts) >= 2:
                    symbol = parts[0].upper()
                    quantity = float(parts[1])
                    avg_cost = float(parts[2]) if len(parts) > 2 else 0

                    positions.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'avg_cost': avg_cost
                    })
                    print(f"  Added: {symbol} x {quantity}")
                else:
                    print("  Invalid format. Use: SYMBOL QUANTITY [AVG_COST]")
            except EOFError:
                break
            except ValueError as e:
                print(f"  Error: {e}")

        return positions

    def import_portfolio(self, positions: list, reset: bool = True, skip_confirm: bool = False):
        """Import positions into Alpaca"""
        if not positions:
            print("No positions to import.")
            return

        print(f"\n{'='*60}")
        print(f"IMPORTING {len(positions)} POSITIONS")
        print(f"{'='*60}\n")

        # Show what will be imported
        print("Positions to import:")
        total_value = 0
        valid_positions = []

        for pos in positions:
            symbol = pos['symbol']
            qty = pos['quantity']

            # Skip zero quantities
            if qty == 0:
                continue

            # Validate symbol
            if not self.validate_symbol(symbol):
                print(f"  ⚠ {symbol}: Not tradeable on Alpaca, skipping")
                continue

            # Estimate value
            est_value = qty * pos.get('avg_cost', 100)
            total_value += abs(est_value)

            valid_positions.append(pos)
            side = "LONG" if qty > 0 else "SHORT"
            print(f"  • {symbol}: {abs(qty)} shares ({side})")

        print(f"\nEstimated total value: ${total_value:,.2f}")
        print(f"Available cash: ${float(self.account.cash):,.2f}")

        if total_value > float(self.account.cash) * 0.95:
            print("\n⚠️  WARNING: Portfolio value may exceed available cash!")
            print("   Some orders may fail or be partially filled.")

        # Confirm
        if skip_confirm:
            print("\n--yes flag provided, proceeding with import...")
        else:
            confirm = input("\nProceed with import? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print("Import cancelled.")
                return

        # Reset existing positions if requested
        if reset:
            self.cancel_all_orders()
            self.close_all_positions()

            # Refresh account
            self.account = self.api.get_account()
            print(f"\nCash after closing positions: ${float(self.account.cash):,.2f}")

        # Place orders
        print(f"\n{'='*60}")
        print("PLACING ORDERS")
        print(f"{'='*60}\n")

        successful = 0
        failed = 0

        for pos in valid_positions:
            symbol = pos['symbol']
            qty = pos['quantity']

            # Determine order side
            if qty > 0:
                side = 'buy'
            else:
                side = 'sell'
                qty = abs(qty)

            print(f"  {side.upper()} {qty} shares of {symbol}...", end=" ")

            order = self.place_order(symbol, qty, side)

            if order:
                print(f"✓ Order {order.id[:8]}...")
                successful += 1
            else:
                print("✗ Failed")
                failed += 1

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        # Summary
        print(f"\n{'='*60}")
        print("IMPORT COMPLETE")
        print(f"{'='*60}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")

        # Wait and show final portfolio
        print("\nWaiting for orders to fill...")
        time.sleep(5)

        self.show_portfolio()

    def show_portfolio(self):
        """Display current Alpaca portfolio"""
        self.account = self.api.get_account()
        positions = self.api.list_positions()

        print(f"\n{'='*60}")
        print("CURRENT ALPACA PORTFOLIO")
        print(f"{'='*60}")
        print(f"Cash: ${float(self.account.cash):,.2f}")
        print(f"Portfolio Value: ${float(self.account.portfolio_value):,.2f}")
        print(f"\nPositions ({len(positions)}):")

        if positions:
            for pos in positions:
                pl = float(pos.unrealized_pl)
                pl_pct = float(pos.unrealized_plpc) * 100
                pl_sign = "+" if pl >= 0 else ""
                print(f"  {pos.symbol:6} | {float(pos.qty):8.2f} shares | "
                      f"${float(pos.market_value):>10,.2f} | "
                      f"{pl_sign}${pl:,.2f} ({pl_sign}{pl_pct:.1f}%)")
        else:
            print("  No positions")

        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Import portfolio from Robinhood to Alpaca Paper Trading',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python import_portfolio.py portfolio.csv          # Import from CSV
  python import_portfolio.py portfolio.json         # Import from JSON
  python import_portfolio.py --manual               # Manual input
  python import_portfolio.py --show                 # Show current portfolio
  python import_portfolio.py --reset                # Close all positions
        """
    )

    parser.add_argument('file', nargs='?', help='CSV or JSON file with positions')
    parser.add_argument('--manual', '-m', action='store_true', help='Manual position input')
    parser.add_argument('--show', '-s', action='store_true', help='Show current portfolio')
    parser.add_argument('--reset', '-r', action='store_true', help='Close all positions')
    parser.add_argument('--no-reset', action='store_true', help='Keep existing positions (add to them)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    try:
        importer = PortfolioImporter()

        if args.show:
            importer.show_portfolio()
            return

        if args.reset:
            confirm = input("Close ALL positions? (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                importer.cancel_all_orders()
                importer.close_all_positions()
                importer.show_portfolio()
            return

        # Get positions from source
        positions = []

        if args.manual:
            positions = importer.manual_input()
        elif args.file:
            if not os.path.exists(args.file):
                print(f"Error: File not found: {args.file}")
                sys.exit(1)

            if args.file.endswith('.json'):
                positions = importer.import_from_json(args.file)
            else:
                positions = importer.import_from_csv(args.file)

            print(f"Loaded {len(positions)} positions from {args.file}")
        else:
            parser.print_help()
            print("\n💡 Quick start:")
            print("   1. Create a CSV file with your positions")
            print("   2. Run: python import_portfolio.py your_portfolio.csv")
            return

        # Import positions
        if positions:
            importer.import_portfolio(positions, reset=not args.no_reset, skip_confirm=args.yes)

    except KeyboardInterrupt:
        print("\n\nCancelled.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
