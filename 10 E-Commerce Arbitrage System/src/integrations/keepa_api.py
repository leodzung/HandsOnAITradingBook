"""Keepa API integration for Amazon price tracking and deals."""

from typing import Dict, List, Optional
import time
from datetime import datetime, timedelta


class KeepaClient:
    """Client for Keepa API."""

    def __init__(self, api_key: str, rate_limit: int = 120):
        """Initialize Keepa client.

        Args:
            api_key: Keepa API key
            rate_limit: Maximum requests per minute
        """
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.tokens_remaining = rate_limit
        self.last_request_time = None

        # Try to import keepa
        try:
            import keepa

            self.keepa = keepa
            self.api = keepa.Keepa(api_key)
        except ImportError:
            print("Warning: keepa package not installed. Install with: pip install keepa")
            self.keepa = None
            self.api = None

    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit."""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < 60 / self.rate_limit:
                time.sleep(60 / self.rate_limit - elapsed)

        self.last_request_time = time.time()

    def get_product(self, asin: str, domain: str = "US") -> Optional[Dict]:
        """Get product data including price history.

        Args:
            asin: Amazon ASIN
            domain: Amazon domain (US, UK, DE, etc.)

        Returns:
            Product data dictionary or None
        """
        if not self.api:
            return None

        try:
            self._wait_for_rate_limit()
            products = self.api.query(asin, domain=domain)

            if products and len(products) > 0:
                product = products[0]
                return self._parse_product_data(product)

            return None
        except Exception as e:
            print(f"Error fetching Keepa data for {asin}: {e}")
            return None

    def _parse_product_data(self, product: Dict) -> Dict:
        """Parse Keepa product data into standard format.

        Args:
            product: Raw Keepa product data

        Returns:
            Parsed product data
        """
        try:
            # Extract current prices
            current_amazon = product.get("data", {}).get("AMAZON", [])
            current_new = product.get("data", {}).get("NEW", [])
            current_sales_rank = product.get("data", {}).get("SALES", [])

            # Get latest values
            amazon_price = current_amazon[-1] if current_amazon else 0
            new_price = current_new[-1] if current_new else 0
            sales_rank = current_sales_rank[-1] if current_sales_rank else 0

            # Convert Keepa prices (stored as integers, divide by 100)
            if amazon_price > 0:
                amazon_price = amazon_price / 100
            if new_price > 0:
                new_price = new_price / 100

            # Calculate statistics
            stats = product.get("stats", {})

            parsed_data = {
                "asin": product.get("asin"),
                "title": product.get("title"),
                "brand": product.get("brand"),
                "category": product.get("categoryTree", [{}])[0].get("name", ""),
                "current_amazon_price": amazon_price,
                "current_new_price": new_price,
                "current_sales_rank": sales_rank,
                "avg_price_30d": stats.get("avg30", [0])[0] / 100 if stats.get("avg30") else 0,
                "avg_price_90d": stats.get("avg90", [0])[0] / 100 if stats.get("avg90") else 0,
                "avg_price_180d": stats.get("avg180", [0])[0] / 100 if stats.get("avg180") else 0,
                "lowest_price_30d": stats.get("min30", [0])[0] / 100 if stats.get("min30") else 0,
                "highest_price_30d": stats.get("max30", [0])[0] / 100 if stats.get("max30") else 0,
                "avg_sales_rank_30d": stats.get("avg30", [])[-1] if stats.get("avg30") and len(stats.get("avg30")) > 1 else 0,
                "review_count": product.get("reviewCount", 0),
                "rating": product.get("rating", 0) / 10 if product.get("rating") else 0,
                "price_history": self._extract_price_history(product),
                "sales_rank_history": self._extract_rank_history(product),
            }

            return parsed_data
        except Exception as e:
            print(f"Error parsing Keepa data: {e}")
            return {}

    def _extract_price_history(self, product: Dict, days: int = 90) -> List[Dict]:
        """Extract price history from Keepa data.

        Args:
            product: Keepa product data
            days: Number of days of history

        Returns:
            List of price history points
        """
        history = []
        try:
            data = product.get("data", {})
            csv = product.get("csv", [])

            # Keepa stores time as minutes since Keepa epoch (21 Dec 2018 00:00:00 GMT)
            keepa_epoch = datetime(2018, 12, 21, 0, 0, 0)
            cutoff_date = datetime.now() - timedelta(days=days)

            # Extract Amazon price history
            amazon_prices = data.get("AMAZON", [])
            if amazon_prices:
                for i in range(0, len(amazon_prices), 2):
                    if i + 1 < len(amazon_prices):
                        time_minutes = amazon_prices[i]
                        price = amazon_prices[i + 1]

                        if price > 0:  # -1 means no data
                            timestamp = keepa_epoch + timedelta(minutes=time_minutes)
                            if timestamp >= cutoff_date:
                                history.append(
                                    {
                                        "timestamp": timestamp.isoformat(),
                                        "price": price / 100,
                                        "source": "amazon",
                                    }
                                )

            return history
        except Exception as e:
            print(f"Error extracting price history: {e}")
            return []

    def _extract_rank_history(self, product: Dict, days: int = 90) -> List[Dict]:
        """Extract sales rank history.

        Args:
            product: Keepa product data
            days: Number of days of history

        Returns:
            List of sales rank points
        """
        history = []
        try:
            data = product.get("data", {})
            keepa_epoch = datetime(2018, 12, 21, 0, 0, 0)
            cutoff_date = datetime.now() - timedelta(days=days)

            sales_ranks = data.get("SALES", [])
            if sales_ranks:
                for i in range(0, len(sales_ranks), 2):
                    if i + 1 < len(sales_ranks):
                        time_minutes = sales_ranks[i]
                        rank = sales_ranks[i + 1]

                        if rank > 0:
                            timestamp = keepa_epoch + timedelta(minutes=time_minutes)
                            if timestamp >= cutoff_date:
                                history.append(
                                    {"timestamp": timestamp.isoformat(), "rank": rank}
                                )

            return history
        except Exception as e:
            print(f"Error extracting rank history: {e}")
            return []

    def find_deals(
        self,
        category: str = None,
        price_drop_percent: float = 30.0,
        max_current_price: float = 100.0,
        min_rating: float = 4.0,
    ) -> List[Dict]:
        """Find current deals based on criteria.

        Args:
            category: Amazon category to search
            price_drop_percent: Minimum price drop percentage
            max_current_price: Maximum current price
            min_rating: Minimum product rating

        Returns:
            List of deal dictionaries
        """
        # Note: Keepa has a deals API endpoint
        # This is a placeholder for actual implementation
        deals = []

        try:
            if self.api:
                # Use Keepa's deal finder
                # This requires the appropriate Keepa subscription tier
                pass

        except Exception as e:
            print(f"Error finding deals: {e}")

        return deals

    def get_price_statistics(self, asin: str) -> Optional[Dict]:
        """Get price statistics for an ASIN.

        Args:
            asin: Amazon ASIN

        Returns:
            Price statistics dictionary
        """
        product = self.get_product(asin)

        if not product:
            return None

        return {
            "asin": asin,
            "current_price": product.get("current_new_price", 0),
            "avg_30d": product.get("avg_price_30d", 0),
            "avg_90d": product.get("avg_price_90d", 0),
            "lowest_30d": product.get("lowest_price_30d", 0),
            "highest_30d": product.get("highest_price_30d", 0),
            "price_drop_from_avg": (
                (product.get("avg_price_30d", 0) - product.get("current_new_price", 0))
                / product.get("avg_price_30d", 1)
                * 100
            ),
        }

    def calculate_price_volatility(self, price_history: List[Dict]) -> float:
        """Calculate price volatility from history.

        Args:
            price_history: List of price points

        Returns:
            Volatility score (standard deviation / mean)
        """
        if len(price_history) < 2:
            return 0.0

        prices = [p["price"] for p in price_history if p["price"] > 0]

        if not prices:
            return 0.0

        mean_price = sum(prices) / len(prices)
        variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
        std_dev = variance**0.5

        # Return coefficient of variation (CV)
        if mean_price > 0:
            return (std_dev / mean_price) * 100
        return 0.0

    def is_deal(
        self, asin: str, current_price: float, threshold_percent: float = 20.0
    ) -> bool:
        """Check if current price is a deal compared to history.

        Args:
            asin: Amazon ASIN
            current_price: Current price to evaluate
            threshold_percent: Minimum discount percentage

        Returns:
            True if price is a deal
        """
        stats = self.get_price_statistics(asin)

        if not stats:
            return False

        avg_price = stats.get("avg_price_30d", 0)

        if avg_price == 0:
            return False

        discount_percent = ((avg_price - current_price) / avg_price) * 100

        return discount_percent >= threshold_percent
