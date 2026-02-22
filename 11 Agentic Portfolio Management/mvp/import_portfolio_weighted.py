#!/usr/bin/env python3
"""
Weight-Based Portfolio Import with Cost Basis Tracking

This script imports a portfolio by matching percentage weights rather than
exact share counts. It also tracks cost basis for P&L calculations.

Features:
- Calculates portfolio weights from source (Robinhood CSV)
- Allocates available cash proportionally based on weights
- Uses notional (dollar-based) orders for precise allocation
- Tracks cost basis in a separate JSON file for P&L analysis
- Handles positions too small to trade (< $1)

Usage:
    python import_portfolio_weighted.py robinhood_portfolio.csv
    python import_portfolio_weighted.py robinhood_portfolio.csv --yes
    python import_portfolio_weighted.py --show-cost-basis
"""

import os
import sys
import csv
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    import alpaca_trade_api as tradeapi
except ImportError:
    print("Error: alpaca-trade-api not installed. Run: pip install alpaca-trade-api")
    sys.exit(1)


class WeightedPortfolioImporter:
    """Import portfolio using weight-based allocation with cost basis tracking"""

    COST_BASIS_FILE = "cost_basis.json"
    MIN_ORDER_VALUE = 1.0  # Minimum dollar value for an order

    def __init__(self):
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

        if not api_key or not secret_key:
            raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env")

        self.api = tradeapi.REST(api_key, secret_key, base_url, api_version='v2')
        self.account = self.api.get_account()

        print(f"\n{'='*70}")
        print("WEIGHTED PORTFOLIO IMPORTER - WITH COST BASIS TRACKING")
        print(f"{'='*70}")
        print(f"Account: {self.account.account_number}")
        print(f"Cash: ${float(self.account.cash):,.2f}")
        print(f"Portfolio Value: ${float(self.account.portfolio_value):,.2f}")
        print(f"{'='*70}\n")

    def load_cost_basis(self) -> dict:
        """Load existing cost basis data"""
        if os.path.exists(self.COST_BASIS_FILE):
            with open(self.COST_BASIS_FILE, 'r') as f:
                return json.load(f)
        return {"positions": {}, "last_updated": None, "source": None}

    def save_cost_basis(self, data: dict):
        """Save cost basis data to file"""
        data["last_updated"] = datetime.now().isoformat()
        with open(self.COST_BASIS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nCost basis saved to {self.COST_BASIS_FILE}")

    def parse_csv(self, filepath: str) -> list:
        """Parse portfolio from CSV file"""
        positions = []

        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                symbol = None
                quantity = None
                avg_cost = None

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

                if symbol and quantity and quantity > 0:
                    positions.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'avg_cost': avg_cost or 0,
                        'value': quantity * (avg_cost or 0)
                    })

        return positions

    def calculate_weights(self, positions: list) -> list:
        """Calculate portfolio weights for each position"""
        total_value = sum(p['value'] for p in positions)

        if total_value == 0:
            print("Error: Total portfolio value is 0")
            return []

        for pos in positions:
            pos['weight'] = pos['value'] / total_value
            pos['weight_pct'] = pos['weight'] * 100

        # Sort by weight descending
        positions.sort(key=lambda x: x['weight'], reverse=True)

        return positions

    def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is tradeable on Alpaca"""
        try:
            asset = self.api.get_asset(symbol)
            return asset.tradable and asset.status == 'active'
        except:
            return False

    def get_current_price(self, symbol: str) -> float:
        """Get current/last price for a symbol"""
        try:
            # Try to get latest trade
            trade = self.api.get_latest_trade(symbol)
            return float(trade.price)
        except:
            try:
                # Fallback to last quote
                quote = self.api.get_latest_quote(symbol)
                return float(quote.ask_price + quote.bid_price) / 2
            except:
                return 0

    def place_notional_order(self, symbol: str, notional: float) -> dict:
        """Place a notional (dollar-based) order"""
        try:
            order = self.api.submit_order(
                symbol=symbol,
                notional=round(notional, 2),
                side='buy',
                type='market',
                time_in_force='day'
            )
            return {"success": True, "order": order}
        except Exception as e:
            # If notional fails, try qty-based order
            error_msg = str(e)
            if "notional" in error_msg.lower() or "fractionable" in error_msg.lower():
                return self.place_qty_order(symbol, notional)
            return {"success": False, "error": str(e)}

    def place_qty_order(self, symbol: str, notional: float) -> dict:
        """Place a quantity-based order (fallback for non-fractionable stocks)"""
        try:
            price = self.get_current_price(symbol)
            if price <= 0:
                return {"success": False, "error": "Could not get price"}

            qty = int(notional / price)
            if qty <= 0:
                return {"success": False, "error": f"Qty rounds to 0 (${notional:.2f} / ${price:.2f})"}

            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side='buy',
                type='market',
                time_in_force='day'
            )
            return {"success": True, "order": order, "qty": qty}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancel_all_orders(self):
        """Cancel all open orders"""
        orders = self.api.list_orders(status='open')
        if orders:
            print(f"Cancelling {len(orders)} open orders...")
            self.api.cancel_all_orders()
            time.sleep(2)

    def close_all_positions(self):
        """Close all existing positions"""
        positions = self.api.list_positions()
        if not positions:
            print("No existing positions to close.")
            return

        print(f"Closing {len(positions)} existing positions...")
        for pos in positions:
            try:
                self.api.close_position(pos.symbol)
                print(f"  Closed {pos.symbol}")
            except Exception as e:
                print(f"  Failed to close {pos.symbol}: {e}")

        time.sleep(3)

    def import_portfolio(self, positions: list, skip_confirm: bool = False):
        """Import portfolio using weight-based allocation"""
        if not positions:
            print("No positions to import.")
            return

        # Calculate weights
        positions = self.calculate_weights(positions)
        total_source_value = sum(p['value'] for p in positions)

        # Get available cash
        self.account = self.api.get_account()
        available_cash = float(self.account.cash)

        print(f"{'='*70}")
        print("PORTFOLIO WEIGHT ANALYSIS")
        print(f"{'='*70}")
        print(f"Source portfolio value: ${total_source_value:,.2f}")
        print(f"Available Alpaca cash:  ${available_cash:,.2f}")
        print(f"Scale factor: {available_cash/total_source_value:.2%}")
        print()

        # Validate symbols and calculate target allocations
        print("Position Weights (Top 20):")
        print(f"{'Symbol':<8} {'Weight':>8} {'Source $':>12} {'Target $':>12} {'Status':<15}")
        print("-" * 60)

        valid_positions = []
        skipped_value = 0

        for i, pos in enumerate(positions):
            symbol = pos['symbol']
            weight = pos['weight']
            source_value = pos['value']
            target_value = weight * available_cash

            # Validate symbol
            if not self.validate_symbol(symbol):
                status = "Not tradeable"
                skipped_value += target_value
                if i < 20:
                    print(f"{symbol:<8} {weight:>7.2%} ${source_value:>10,.2f} ${target_value:>10,.2f} {status:<15}")
                continue

            # Skip tiny positions
            if target_value < self.MIN_ORDER_VALUE:
                status = "Too small"
                skipped_value += target_value
                if i < 20:
                    print(f"{symbol:<8} {weight:>7.2%} ${source_value:>10,.2f} ${target_value:>10,.2f} {status:<15}")
                continue

            pos['target_value'] = target_value
            valid_positions.append(pos)
            status = "Ready"

            if i < 20:
                print(f"{symbol:<8} {weight:>7.2%} ${source_value:>10,.2f} ${target_value:>10,.2f} {status:<15}")

        if len(positions) > 20:
            print(f"... and {len(positions) - 20} more positions")

        print()
        print(f"Valid positions: {len(valid_positions)}")
        print(f"Total to allocate: ${sum(p['target_value'] for p in valid_positions):,.2f}")
        print(f"Skipped value: ${skipped_value:,.2f}")

        # Confirm
        if not skip_confirm:
            confirm = input("\nProceed with import? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print("Import cancelled.")
                return
        else:
            print("\n--yes flag provided, proceeding...")

        # Reset existing positions
        self.cancel_all_orders()
        self.close_all_positions()

        # Refresh account
        time.sleep(2)
        self.account = self.api.get_account()
        available_cash = float(self.account.cash)
        print(f"\nCash after reset: ${available_cash:,.2f}")

        # Recalculate target values with actual cash
        total_weight = sum(p['weight'] for p in valid_positions)
        for pos in valid_positions:
            pos['target_value'] = (pos['weight'] / total_weight) * available_cash * 0.995  # 0.5% buffer

        # Place orders
        print(f"\n{'='*70}")
        print("PLACING ORDERS")
        print(f"{'='*70}\n")

        successful = 0
        failed = 0
        cost_basis_data = {
            "positions": {},
            "source_file": "robinhood_portfolio.csv",
            "import_date": datetime.now().isoformat(),
            "source_total_value": total_source_value,
            "alpaca_allocated": available_cash
        }

        for pos in valid_positions:
            symbol = pos['symbol']
            target_value = pos['target_value']

            print(f"  {symbol:6} | ${target_value:>10,.2f} | ", end="")

            result = self.place_notional_order(symbol, target_value)

            if result["success"]:
                order = result["order"]
                print(f"Order {order.id[:8]}...")
                successful += 1

                # Store cost basis
                cost_basis_data["positions"][symbol] = {
                    "original_qty": pos['quantity'],
                    "original_avg_cost": pos['avg_cost'],
                    "original_value": pos['value'],
                    "weight": pos['weight'],
                    "target_value": target_value,
                    "order_id": order.id,
                    "order_type": "notional" if hasattr(order, 'notional') else "qty"
                }
            else:
                print(f"FAILED: {result['error']}")
                failed += 1

            time.sleep(0.3)  # Rate limiting

        # Save cost basis
        self.save_cost_basis(cost_basis_data)

        # Summary
        print(f"\n{'='*70}")
        print("IMPORT COMPLETE")
        print(f"{'='*70}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Cost basis saved to: {self.COST_BASIS_FILE}")

        # Show market status
        clock = self.api.get_clock()
        if not clock.is_open:
            print(f"\n  Market is CLOSED. Orders will fill at: {clock.next_open}")

    def show_cost_basis(self):
        """Display cost basis information with P&L"""
        data = self.load_cost_basis()

        if not data.get("positions"):
            print("No cost basis data found. Import a portfolio first.")
            return

        print(f"\n{'='*70}")
        print("COST BASIS & P/L TRACKING")
        print(f"{'='*70}")
        print(f"Source: {data.get('source_file', 'Unknown')}")
        print(f"Import Date: {data.get('import_date', 'Unknown')}")
        print(f"Source Value: ${data.get('source_total_value', 0):,.2f}")
        print()

        # Get current positions
        current_positions = {p.symbol: p for p in self.api.list_positions()}

        print(f"{'Symbol':<8} {'Orig Cost':>10} {'Curr Price':>10} {'P/L':>12} {'P/L %':>8}")
        print("-" * 55)

        total_cost = 0
        total_current = 0

        for symbol, basis in data["positions"].items():
            orig_cost = basis.get("original_avg_cost", 0)

            if symbol in current_positions:
                pos = current_positions[symbol]
                curr_price = float(pos.current_price)
                curr_value = float(pos.market_value)
                qty = float(pos.qty)

                # Calculate P/L based on original cost basis
                cost_value = qty * orig_cost
                pl = curr_value - cost_value
                pl_pct = (pl / cost_value * 100) if cost_value > 0 else 0

                total_cost += cost_value
                total_current += curr_value

                pl_sign = "+" if pl >= 0 else ""
                print(f"{symbol:<8} ${orig_cost:>9.2f} ${curr_price:>9.2f} {pl_sign}${pl:>10,.2f} {pl_sign}{pl_pct:>6.1f}%")
            else:
                print(f"{symbol:<8} ${orig_cost:>9.2f} {'N/A':>10} {'Pending':>12}")

        print("-" * 55)
        if total_cost > 0:
            total_pl = total_current - total_cost
            total_pl_pct = (total_pl / total_cost) * 100
            pl_sign = "+" if total_pl >= 0 else ""
            print(f"{'TOTAL':<8} ${total_cost:>9,.0f} ${total_current:>9,.0f} {pl_sign}${total_pl:>10,.2f} {pl_sign}{total_pl_pct:>6.1f}%")

    def show_portfolio(self):
        """Display current Alpaca portfolio"""
        self.account = self.api.get_account()
        positions = self.api.list_positions()

        print(f"\n{'='*70}")
        print("CURRENT ALPACA PORTFOLIO")
        print(f"{'='*70}")
        print(f"Cash: ${float(self.account.cash):,.2f}")
        print(f"Portfolio Value: ${float(self.account.portfolio_value):,.2f}")
        print(f"\nPositions ({len(positions)}):")

        if positions:
            # Sort by market value
            positions = sorted(positions, key=lambda p: float(p.market_value), reverse=True)

            for pos in positions:
                pl = float(pos.unrealized_pl)
                pl_pct = float(pos.unrealized_plpc) * 100
                pl_sign = "+" if pl >= 0 else ""
                print(f"  {pos.symbol:6} | {float(pos.qty):>8.2f} shares | "
                      f"${float(pos.market_value):>10,.2f} | "
                      f"{pl_sign}${pl:,.2f} ({pl_sign}{pl_pct:.1f}%)")
        else:
            print("  No positions (orders may be pending)")

        print(f"{'='*70}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Weight-based portfolio import with cost basis tracking',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('file', nargs='?', help='CSV file with positions')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    parser.add_argument('--show', '-s', action='store_true', help='Show current portfolio')
    parser.add_argument('--cost-basis', '-c', action='store_true', help='Show cost basis & P/L')

    args = parser.parse_args()

    try:
        importer = WeightedPortfolioImporter()

        if args.show:
            importer.show_portfolio()
            return

        if args.cost_basis:
            importer.show_cost_basis()
            return

        if args.file:
            if not os.path.exists(args.file):
                print(f"Error: File not found: {args.file}")
                sys.exit(1)

            positions = importer.parse_csv(args.file)
            print(f"Loaded {len(positions)} positions from {args.file}")

            importer.import_portfolio(positions, skip_confirm=args.yes)
        else:
            parser.print_help()
            print("\nExamples:")
            print("  python import_portfolio_weighted.py portfolio.csv")
            print("  python import_portfolio_weighted.py portfolio.csv --yes")
            print("  python import_portfolio_weighted.py --cost-basis")

    except KeyboardInterrupt:
        print("\n\nCancelled.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
