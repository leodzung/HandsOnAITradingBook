#!/usr/bin/env python3
"""Main orchestrator for the E-Commerce Arbitrage System."""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from utils.config import get_config
from utils.database import DatabaseManager
from utils.notifications import NotificationManager
from integrations.amazon_api import AmazonDataClient
from integrations.keepa_api import KeepaClient
from analyzers.profit_calculator import ProfitCalculator
from scanners.amazon_scanner import AmazonScanner
from scanners.retail_scanner import RetailScanner


class ArbitrageOrchestrator:
    """Main orchestrator for the arbitrage system."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the arbitrage system.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config_manager = get_config(config_path)
        self.config = self.config_manager.config_dict

        # Initialize database
        db_url = self.config_manager.database_url
        self.db = DatabaseManager(db_url)

        # Initialize notification system
        self.notifier = NotificationManager(self.config.get("notifications", {}))

        # Initialize API clients
        self.amazon_client = self._init_amazon_client()
        self.keepa_client = self._init_keepa_client()

        # Initialize profit calculator
        profit_config = self.config.get("profit", {})
        self.calculator = ProfitCalculator(profit_config.get("costs", {}))

        # Initialize scanners
        self.scanners = self._init_scanners()

        print("✓ Arbitrage system initialized")

    def _init_amazon_client(self) -> AmazonDataClient:
        """Initialize Amazon API client."""
        sp_api_creds = self.config_manager.get_amazon_credentials()
        pa_api_creds = self.config.get("amazon", {}).get("pa_api", {})

        # Only pass credentials if they're configured
        sp_creds = sp_api_creds if sp_api_creds.get("client_id") else None
        pa_creds = pa_api_creds if pa_api_creds.get("access_key") else None

        return AmazonDataClient(sp_api_credentials=sp_creds, pa_api_credentials=pa_creds)

    def _init_keepa_client(self) -> KeepaClient:
        """Initialize Keepa API client."""
        api_key = self.config_manager.get_keepa_key()

        if api_key:
            rate_limit = self.config.get("keepa", {}).get("rate_limit", 120)
            return KeepaClient(api_key, rate_limit)

        return None

    def _init_scanners(self) -> Dict:
        """Initialize all scanners."""
        scanner_config = self.config.get("scanning", {})

        scanners = {
            "amazon": AmazonScanner(
                amazon_client=self.amazon_client,
                keepa_client=self.keepa_client,
                profit_calculator=self.calculator,
                config=self.config.get("profit", {}),
            ),
            "retail": RetailScanner(
                amazon_client=self.amazon_client,
                profit_calculator=self.calculator,
                config=self.config.get("profit", {}),
            ),
        }

        return scanners

    def run_scanner(self, scanner_name: str) -> List[Dict]:
        """Run a specific scanner.

        Args:
            scanner_name: Name of scanner to run

        Returns:
            List of deals found
        """
        print(f"\n🔍 Running {scanner_name} scanner...")

        deals = []

        try:
            if scanner_name == "amazon":
                # Run Amazon scanner
                scanner = self.scanners["amazon"]

                # Scan by watchlist if configured
                watchlist = self.config.get("amazon", {}).get("watchlist_asins", [])
                if watchlist:
                    print(f"  → Scanning {len(watchlist)} watchlist items...")
                    deals.extend(scanner.scan_price_errors(watchlist))

                # Scan lightning deals
                if self.keepa_client:
                    print("  → Scanning for price drops...")
                    deals.extend(scanner.scan_lightning_deals())

            elif scanner_name == "retail":
                # Run retail scanner
                scanner = self.scanners["retail"]
                retail_config = self.config.get("retail", {})

                # Scan Best Buy if enabled
                if retail_config.get("bestbuy", {}).get("enabled"):
                    api_key = retail_config.get("bestbuy", {}).get("api_key")
                    print("  → Scanning Best Buy...")
                    deals.extend(scanner.scan_bestbuy_deals(api_key))

                # Scan Walmart if enabled
                if retail_config.get("walmart", {}).get("enabled"):
                    api_key = retail_config.get("walmart", {}).get("api_key")
                    print("  → Scanning Walmart...")
                    deals.extend(scanner.scan_walmart_clearance(api_key))

            # Filter and save deals
            qualified_deals = self._filter_deals(deals)

            if qualified_deals:
                print(f"✓ Found {len(qualified_deals)} qualified deals")
                self._save_deals(qualified_deals)
                self._send_alerts(qualified_deals)
            else:
                print("  No qualified deals found")

            return qualified_deals

        except Exception as e:
            print(f"✗ Error running {scanner_name} scanner: {e}")
            return []

    def run_all_scanners(self) -> List[Dict]:
        """Run all enabled scanners.

        Returns:
            Combined list of all deals found
        """
        print("\n" + "=" * 60)
        print("Starting arbitrage scan...")
        print("=" * 60)

        enabled_scanners = self.config.get("scanning", {}).get(
            "enabled_scanners", ["amazon"]
        )

        all_deals = []

        for scanner_name in enabled_scanners:
            deals = self.run_scanner(scanner_name)
            all_deals.extend(deals)

        print("\n" + "=" * 60)
        print(f"Scan complete. Total deals found: {len(all_deals)}")
        print("=" * 60)

        return all_deals

    def _filter_deals(self, deals: List[Dict]) -> List[Dict]:
        """Apply filters to deals.

        Args:
            deals: List of raw deals

        Returns:
            Filtered list of deals
        """
        filters = self.config.get("filters", {})
        min_roi = self.config.get("profit", {}).get("min_roi", 30.0)

        qualified = []

        for deal in deals:
            # Check ROI threshold
            if deal.get("roi_percentage", 0) < min_roi:
                continue

            # Check sales rank
            max_rank = filters.get("max_sales_rank", {}).get("default", 50000)
            if deal.get("sales_rank", 0) > max_rank:
                continue

            # Check number of sellers
            max_sellers = filters.get("max_number_of_sellers", 10)
            if deal.get("num_sellers", 0) > max_sellers:
                continue

            # Check excluded categories
            excluded_categories = filters.get("excluded_categories", [])
            if deal.get("category", "") in excluded_categories:
                continue

            # Check excluded brands
            excluded_brands = filters.get("excluded_brands", [])
            if deal.get("brand", "") in excluded_brands:
                continue

            qualified.append(deal)

        return qualified

    def _save_deals(self, deals: List[Dict]):
        """Save deals to database.

        Args:
            deals: List of deals to save
        """
        for deal in deals:
            try:
                # Check if deal already exists
                existing = self.db.update_deal(
                    asin=deal["asin"], source=deal["source"], updates=deal
                )

                if not existing:
                    # Add new deal
                    self.db.add_deal(deal)

                # Add to price history
                self.db.add_price_history(
                    {
                        "asin": deal["asin"],
                        "price": deal["source_price"],
                        "source": deal["source"],
                    }
                )

            except Exception as e:
                print(f"Error saving deal {deal.get('asin')}: {e}")

    def _send_alerts(self, deals: List[Dict]):
        """Send alerts for high-value deals.

        Args:
            deals: List of deals
        """
        # Filter for high-value deals worthy of immediate alert
        email_config = self.config.get("notifications", {}).get("email", {})
        alert_min_roi = email_config.get("alert_min_roi", 50.0)

        high_value_deals = [d for d in deals if d.get("roi_percentage", 0) >= alert_min_roi]

        for deal in high_value_deals:
            self.notifier.send_deal_alert(deal)

    def show_deals(self, min_roi: float = 30.0, limit: int = 20):
        """Display top deals from database.

        Args:
            min_roi: Minimum ROI to display
            limit: Maximum number to show
        """
        deals = self.db.get_active_deals(min_roi=min_roi, limit=limit)

        if not deals:
            print("No deals found in database")
            return

        print(f"\n{'=' * 100}")
        print(f"Top {len(deals)} Deals (ROI >= {min_roi}%)")
        print(f"{'=' * 100}")

        for i, deal in enumerate(deals, 1):
            print(f"\n{i}. {deal.product_title[:60]}")
            print(f"   ASIN: {deal.asin} | Source: {deal.source}")
            print(
                f"   Price: ${deal.source_price:.2f} → ${deal.amazon_price:.2f} | "
                f"Profit: ${deal.estimated_profit:.2f} | ROI: {deal.roi_percentage:.1f}%"
            )
            print(
                f"   Rank: {deal.sales_rank or 'N/A'} | "
                f"Rating: {deal.average_rating or 'N/A'} ({deal.review_count or 0} reviews)"
            )
            print(f"   Found: {deal.first_seen.strftime('%Y-%m-%d %H:%M')}")

        print(f"\n{'=' * 100}")

    def send_daily_report(self):
        """Send daily digest report."""
        deals = self.db.get_active_deals(min_roi=30.0, limit=100)

        if deals:
            # Convert SQLAlchemy objects to dicts
            deal_dicts = []
            for deal in deals:
                deal_dicts.append(
                    {
                        "asin": deal.asin,
                        "product_title": deal.product_title,
                        "source": deal.source,
                        "source_price": deal.source_price,
                        "amazon_price": deal.amazon_price,
                        "estimated_profit": deal.estimated_profit,
                        "roi_percentage": deal.roi_percentage,
                    }
                )

            self.notifier.send_daily_digest(deal_dicts)
            print(f"✓ Daily digest sent ({len(deal_dicts)} deals)")
        else:
            print("No deals to report")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="E-Commerce Arbitrage System")

    parser.add_argument(
        "--config", default="config/config.yaml", help="Path to config file"
    )

    parser.add_argument("--scan-all", action="store_true", help="Run all scanners")

    parser.add_argument(
        "--scanner",
        choices=["amazon", "retail", "wholesale"],
        help="Run specific scanner",
    )

    parser.add_argument("--show-deals", action="store_true", help="Show top deals")

    parser.add_argument("--min-roi", type=float, default=30.0, help="Minimum ROI to show")

    parser.add_argument("--report", action="store_true", help="Send daily report")

    args = parser.parse_args()

    # Initialize system
    try:
        orchestrator = ArbitrageOrchestrator(config_path=args.config)
    except Exception as e:
        print(f"✗ Failed to initialize system: {e}")
        return 1

    # Execute requested action
    try:
        if args.scan_all:
            orchestrator.run_all_scanners()

        elif args.scanner:
            orchestrator.run_scanner(args.scanner)

        elif args.show_deals:
            orchestrator.show_deals(min_roi=args.min_roi)

        elif args.report:
            orchestrator.send_daily_report()

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
