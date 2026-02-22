"""Amazon scanner for finding deals on Amazon to resell."""

from typing import Dict, List, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.amazon_api import AmazonDataClient
from integrations.keepa_api import KeepaClient
from analyzers.profit_calculator import ProfitCalculator, ProductCategory


class AmazonScanner:
    """Scans Amazon for deals using various strategies."""

    def __init__(
        self,
        amazon_client: AmazonDataClient,
        keepa_client: Optional[KeepaClient] = None,
        profit_calculator: Optional[ProfitCalculator] = None,
        config: Optional[Dict] = None,
    ):
        """Initialize Amazon scanner.

        Args:
            amazon_client: Amazon API client
            keepa_client: Keepa API client (optional but recommended)
            profit_calculator: Profit calculator instance
            config: Configuration dictionary
        """
        self.amazon = amazon_client
        self.keepa = keepa_client
        self.calculator = profit_calculator or ProfitCalculator()
        self.config = config or {}

        # Scanner settings
        self.min_roi = self.config.get("min_roi", 30.0)
        self.min_price_drop = self.config.get("min_price_drop_percent", 20.0)
        self.max_price = self.config.get("max_source_price", 200.0)

    def scan_lightning_deals(self) -> List[Dict]:
        """Scan Amazon Lightning Deals and Today's Deals.

        Returns:
            List of potential deals
        """
        deals = []

        # Note: This would require scraping or access to Amazon's deal pages
        # Amazon doesn't provide a public API for Lightning Deals
        # In production, you might use:
        # 1. Keepa's deal finder
        # 2. Web scraping (respect robots.txt)
        # 3. Third-party deal aggregator APIs

        if self.keepa:
            # Use Keepa to find deals
            keepa_deals = self.keepa.find_deals(
                price_drop_percent=self.min_price_drop, max_current_price=self.max_price
            )

            for deal in keepa_deals:
                analyzed_deal = self.analyze_deal(deal)
                if analyzed_deal:
                    deals.append(analyzed_deal)

        return deals

    def scan_clearance_items(self, category: str = None) -> List[Dict]:
        """Scan for clearance items in specific categories.

        Args:
            category: Amazon category to scan

        Returns:
            List of clearance deals
        """
        deals = []

        # Placeholder for clearance scanning logic
        # In production, this would search for keywords like:
        # - "clearance"
        # - "closeout"
        # - Large price drops detected by Keepa

        return deals

    def scan_price_errors(self, watchlist: List[str]) -> List[Dict]:
        """Scan watchlist for price errors or significant drops.

        Args:
            watchlist: List of ASINs to monitor

        Returns:
            List of price error deals
        """
        deals = []

        for asin in watchlist:
            try:
                # Get current price
                pricing = self.amazon.get_price_and_availability(asin)

                if not pricing or not pricing.get("available"):
                    continue

                current_price = pricing.get("price", 0)

                if current_price == 0 or current_price > self.max_price:
                    continue

                # Check against historical data
                if self.keepa:
                    stats = self.keepa.get_price_statistics(asin)

                    if stats:
                        price_drop = stats.get("price_drop_from_avg", 0)

                        # Check for significant price drop
                        if price_drop >= self.min_price_drop:
                            deal_data = {
                                "asin": asin,
                                "source": "amazon",
                                "source_price": current_price,
                                "avg_price_30d": stats.get("avg_30d", 0),
                                "price_drop_percent": price_drop,
                            }

                            analyzed_deal = self.analyze_deal(deal_data)
                            if analyzed_deal:
                                deals.append(analyzed_deal)

            except Exception as e:
                print(f"Error scanning {asin}: {e}")
                continue

        return deals

    def analyze_deal(self, deal_data: Dict) -> Optional[Dict]:
        """Analyze a potential deal for profitability.

        Args:
            deal_data: Raw deal data

        Returns:
            Analyzed deal dictionary or None if not profitable
        """
        try:
            asin = deal_data.get("asin")
            source_price = deal_data.get("source_price", 0)

            if not asin or source_price == 0:
                return None

            # Get comprehensive product data
            if self.keepa:
                product = self.keepa.get_product(asin)
            else:
                product = self.amazon.get_product_data(asin)

            if not product:
                return None

            # Determine selling price (could be different marketplace)
            # For Amazon-to-Amazon, we'd sell at a higher price or different marketplace
            # Assume we can sell at average 30-day price or current highest price
            selling_price = max(
                product.get("avg_price_30d", 0), product.get("current_new_price", 0) * 1.1
            )

            if selling_price <= source_price:
                return None  # No profit potential

            # Calculate profit
            category = self._determine_category(product.get("category", ""))
            metrics = self.calculator.calculate_profit(
                source_price=source_price,
                amazon_price=selling_price,
                category=category,
                weight_oz=16,  # Default estimate
            )

            # Check if profitable
            if not self.calculator.is_profitable(
                metrics, min_roi=self.min_roi, min_profit=5.0
            ):
                return None

            # Assemble complete deal data
            complete_deal = {
                "asin": asin,
                "product_title": product.get("title", ""),
                "brand": product.get("brand", ""),
                "category": product.get("category", ""),
                "source": "amazon",
                "source_price": source_price,
                "amazon_price": selling_price,
                "estimated_profit": metrics.net_profit,
                "roi_percentage": metrics.roi_percentage,
                "profit_margin": metrics.profit_margin,
                "amazon_referral_fee": metrics.referral_fee,
                "amazon_fba_fee": metrics.fba_fee,
                "total_fees": metrics.total_fees,
                "sales_rank": product.get("current_sales_rank", 0),
                "review_count": product.get("review_count", 0),
                "average_rating": product.get("rating", 0),
                "num_sellers": deal_data.get("num_sellers", 0),
                "price_drop_percent": deal_data.get("price_drop_percent", 0),
                "first_seen": datetime.utcnow(),
            }

            return complete_deal

        except Exception as e:
            print(f"Error analyzing deal: {e}")
            return None

    def _determine_category(self, category_name: str) -> ProductCategory:
        """Map category name to ProductCategory enum.

        Args:
            category_name: Category name string

        Returns:
            ProductCategory enum value
        """
        category_lower = category_name.lower()

        if "electronic" in category_lower:
            return ProductCategory.ELECTRONICS
        elif "computer" in category_lower:
            return ProductCategory.COMPUTERS
        elif "camera" in category_lower or "photo" in category_lower:
            return ProductCategory.CAMERAS
        elif "toy" in category_lower or "game" in category_lower:
            return ProductCategory.TOYS_GAMES
        elif "book" in category_lower:
            return ProductCategory.BOOKS
        elif "home" in category_lower or "kitchen" in category_lower:
            return ProductCategory.HOME_KITCHEN
        elif "sport" in category_lower:
            return ProductCategory.SPORTS_OUTDOORS
        elif "tool" in category_lower:
            return ProductCategory.TOOLS
        elif "automotive" in category_lower or "auto" in category_lower:
            return ProductCategory.AUTOMOTIVE
        elif "music" in category_lower or "instrument" in category_lower:
            return ProductCategory.MUSICAL_INSTRUMENTS
        else:
            return ProductCategory.DEFAULT

    def scan_new_releases(self, category: str = None) -> List[Dict]:
        """Scan new releases for early opportunities.

        Args:
            category: Category to scan

        Returns:
            List of new release deals
        """
        # Placeholder for new releases scanning
        return []

    def scan_by_asins(self, asins: List[str]) -> List[Dict]:
        """Scan specific list of ASINs.

        Args:
            asins: List of ASINs to check

        Returns:
            List of deals found
        """
        deals = []

        for asin in asins:
            try:
                # Get current price
                pricing = self.amazon.get_price_and_availability(asin)

                if pricing and pricing.get("available"):
                    deal_data = {
                        "asin": asin,
                        "source_price": pricing.get("price", 0),
                        "num_sellers": pricing.get("num_sellers", 0),
                    }

                    analyzed_deal = self.analyze_deal(deal_data)
                    if analyzed_deal:
                        deals.append(analyzed_deal)

            except Exception as e:
                print(f"Error scanning ASIN {asin}: {e}")
                continue

        return deals
