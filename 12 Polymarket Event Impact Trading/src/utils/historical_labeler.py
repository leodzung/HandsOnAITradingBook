#!/usr/bin/env python3
"""
Historical Label Generator
Creates training labels for both event-driven and price-level trading bots.

Based on IMDEA paper methodology for labeling historical prediction market data.
"""

import json
import sqlite3
import logging
import requests
import time
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CoinGeckoClient:
    """Simple client for CoinGecko API to fetch historical spot prices."""

    BASE_URL = "https://api.coingecko.com/api/v3"

    # Asset symbol to CoinGecko ID mapping
    ASSET_IDS = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'SOL': 'solana',
        'MATIC': 'matic-network',
        'AVAX': 'avalanche-2',
        'DOGE': 'dogecoin',
        'XRP': 'ripple',
        'ADA': 'cardano',
        'DOT': 'polkadot',
        'LINK': 'chainlink'
    }

    def __init__(self, rate_limit_per_min: float = 10.0):
        """
        Initialize CoinGecko client.

        Args:
            rate_limit_per_min: Maximum requests per minute (free tier: 10-30)
        """
        self.rate_limit_per_min = rate_limit_per_min
        self.min_request_interval = 60.0 / rate_limit_per_min
        self.last_request_time = 0
        self.session = requests.Session()

        # Cache for spot prices
        self._price_cache: Dict[str, Dict[str, float]] = {}

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def get_asset_id(self, symbol: str) -> Optional[str]:
        """Get CoinGecko asset ID from symbol."""
        return self.ASSET_IDS.get(symbol.upper())

    def get_historical_range(self, symbol: str, start_date: datetime,
                             end_date: datetime) -> List[Dict]:
        """
        Get historical OHLCV data for a date range.

        Args:
            symbol: Asset symbol (e.g., 'BTC')
            start_date: Start datetime
            end_date: End datetime

        Returns:
            List of {timestamp, open, high, low, close} dicts
        """
        asset_id = self.get_asset_id(symbol)
        if not asset_id:
            logger.warning(f"Unknown asset symbol: {symbol}")
            return []

        self._rate_limit()

        # Convert to Unix timestamps
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())

        try:
            response = self.session.get(
                f"{self.BASE_URL}/coins/{asset_id}/market_chart/range",
                params={
                    'vs_currency': 'usd',
                    'from': start_ts,
                    'to': end_ts
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Parse prices (timestamp, price pairs)
            prices = data.get('prices', [])
            results = []

            for ts, price in prices:
                results.append({
                    'timestamp': datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                    'price': price
                })

            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching CoinGecko data: {e}")
            return []

    def get_price_at_time(self, symbol: str, target_time: datetime) -> Optional[float]:
        """
        Get the closest price to a specific time.

        Args:
            symbol: Asset symbol
            target_time: Target datetime

        Returns:
            Price at or near target time
        """
        # Fetch a window around the target time
        start = target_time - timedelta(hours=1)
        end = target_time + timedelta(hours=1)

        prices = self.get_historical_range(symbol, start, end)

        if not prices:
            return None

        # Find closest price to target time
        closest = min(prices, key=lambda p: abs((p['timestamp'] - target_time).total_seconds()))
        return closest['price']

    def check_strike_hit(self, symbol: str, strike: float, direction: str,
                         start_date: datetime, end_date: datetime) -> Tuple[bool, Optional[datetime]]:
        """
        Check if a price strike was hit during a time period.

        Args:
            symbol: Asset symbol (e.g., 'BTC')
            strike: Strike price
            direction: 'ABOVE' or 'BELOW'
            start_date: Start of period
            end_date: End of period

        Returns:
            (hit: bool, first_hit_time: datetime or None)
        """
        prices = self.get_historical_range(symbol, start_date, end_date)

        if not prices:
            return False, None

        for p in prices:
            price = p['price']
            ts = p['timestamp']

            if direction == 'ABOVE' and price >= strike:
                return True, ts
            elif direction == 'BELOW' and price <= strike:
                return True, ts

        return False, None


class HistoricalPriceLabeler:
    """
    Generate labels for the event-driven trading bot.

    Labels are based on 24-hour price changes from VWAP at event time:
    - UP: Price increased by >= threshold
    - DOWN: Price decreased by >= threshold
    - NEUTRAL: Price change within threshold
    """

    def __init__(self, db_path: str = 'data/training_history.db',
                 price_change_threshold: float = 0.03):
        """
        Initialize the labeler.

        Args:
            db_path: Path to SQLite database
            price_change_threshold: Minimum price change for UP/DOWN label (default 3%)
        """
        self.db_path = db_path
        self.threshold = price_change_threshold

    def get_vwap_at_time(self, condition_id: str, target_time: datetime,
                         window_hours: float = 1.0) -> Optional[float]:
        """
        Calculate VWAP around a target time using on-chain trades.

        Args:
            condition_id: Market condition ID
            target_time: Target datetime
            window_hours: Time window for VWAP calculation

        Returns:
            VWAP or None if insufficient data
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        start_time = target_time - timedelta(hours=window_hours / 2)
        end_time = target_time + timedelta(hours=window_hours / 2)

        cursor.execute("""
            SELECT price, maker_amount_filled
            FROM on_chain_trades
            WHERE condition_id = ?
              AND block_timestamp >= ?
              AND block_timestamp <= ?
        """, (condition_id, start_time.isoformat(), end_time.isoformat()))

        trades = cursor.fetchall()
        conn.close()

        if not trades:
            return None

        total_value = sum(p * v for p, v in trades)
        total_volume = sum(v for _, v in trades)

        if total_volume == 0:
            return None

        return total_value / total_volume

    def calculate_price_change(self, price_before: float, price_after: float) -> float:
        """Calculate percentage price change."""
        if price_before == 0 or price_before is None:
            return 0.0
        return (price_after - price_before) / price_before

    def label_price_change(self, price_before: float, price_after: float) -> str:
        """
        Label a price change as UP, DOWN, or NEUTRAL.

        Args:
            price_before: Price at event time
            price_after: Price after holding period

        Returns:
            Label string: 'UP', 'DOWN', or 'NEUTRAL'
        """
        change = self.calculate_price_change(price_before, price_after)

        if change >= self.threshold:
            return 'UP'
        elif change <= -self.threshold:
            return 'DOWN'
        else:
            return 'NEUTRAL'

    def generate_sample(self, condition_id: str, event_time: datetime,
                        hold_hours: float = 24.0) -> Optional[Dict]:
        """
        Generate a single labeled training sample.

        Args:
            condition_id: Market condition ID
            event_time: Time of the event/signal
            hold_hours: Holding period for label calculation

        Returns:
            Dictionary with features and label, or None if insufficient data
        """
        # Get VWAP at event time
        price_before = self.get_vwap_at_time(condition_id, event_time)
        if price_before is None:
            return None

        # Get VWAP after holding period
        after_time = event_time + timedelta(hours=hold_hours)
        price_after = self.get_vwap_at_time(condition_id, after_time)
        if price_after is None:
            return None

        # Calculate label
        label = self.label_price_change(price_before, price_after)
        price_change = self.calculate_price_change(price_before, price_after)

        return {
            'condition_id': condition_id,
            'event_time': event_time.isoformat(),
            'price_before': price_before,
            'price_after': price_after,
            'price_change': price_change,
            'label': label,
            'hold_hours': hold_hours
        }


class PriceLevelLabeler:
    """
    Generate labels for the price-level trading bot.

    Labels are binary YES/NO based on whether the spot price hit the strike
    during the market's lifetime.
    """

    def __init__(self, db_path: str = 'data/training_history.db'):
        """
        Initialize the labeler.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.coingecko = CoinGeckoClient()

    def parse_market_question(self, question: str) -> Optional[Dict]:
        """
        Parse a market question to extract price level details.

        Args:
            question: Market question text

        Returns:
            Dict with asset, strike, direction, or None if not a price-level market
        """
        q = question.lower()

        # Determine asset
        asset = None
        if 'bitcoin' in q or re.search(r'\bbtc\b', q):
            asset = 'BTC'
        elif 'ethereum' in q or re.search(r'\beth\b', q):
            asset = 'ETH'
        elif 'solana' in q or re.search(r'\bsol\b', q):
            asset = 'SOL'
        elif 'dogecoin' in q or re.search(r'\bdoge\b', q):
            asset = 'DOGE'
        elif 'ripple' in q or re.search(r'\bxrp\b', q):
            asset = 'XRP'

        if not asset:
            return None

        # Extract price
        strike = None
        price_patterns = [
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*[kK]',  # $50K, $100k
            r'\$([0-9,]+(?:\.[0-9]+)?)',  # $50000
            r'([0-9,]+(?:\.[0-9]+)?)\s*(?:dollars|usd)',
        ]

        for pattern in price_patterns:
            match = re.search(pattern, q)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    strike = float(price_str)
                    # Handle 'k' suffix
                    if 'k' in q[match.end():match.end() + 2].lower():
                        strike *= 1000
                    break
                except:
                    pass

        if not strike:
            return None

        # Determine direction
        direction = None
        if any(word in q for word in ['above', 'hit', 'reach', 'break', 'surpass', 'exceed']):
            direction = 'ABOVE'
        elif any(word in q for word in ['below', 'dip', 'drop', 'fall', 'under']):
            direction = 'BELOW'

        if not direction:
            # Default based on context
            direction = 'ABOVE'

        return {
            'asset': asset,
            'strike': strike,
            'direction': direction
        }

    def label_market(self, market: Dict) -> Optional[Dict]:
        """
        Label a resolved market based on historical spot prices.

        Args:
            market: Market dictionary from database

        Returns:
            Labeled sample or None if unable to label
        """
        # Parse market question
        parsed = self.parse_market_question(market.get('question', ''))
        if not parsed:
            return None

        # Get market dates
        created_at = market.get('created_at') or market.get('createdAt')
        end_date = market.get('end_date') or market.get('endDate')
        closed_time = market.get('closed_time') or market.get('closedTime')

        if not created_at or not end_date:
            return None

        try:
            start_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            # Use earlier of end_date or closed_time
            if closed_time:
                end_dt = datetime.fromisoformat(closed_time.replace('Z', '+00:00'))
            else:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except:
            return None

        # Check if strike was hit using CoinGecko data
        hit, hit_time = self.coingecko.check_strike_hit(
            parsed['asset'],
            parsed['strike'],
            parsed['direction'],
            start_date,
            end_dt
        )

        # Get the resolved outcome from the market
        resolved_outcome = market.get('resolved_outcome')

        # If we couldn't check via CoinGecko, use the resolved outcome
        if not hit and resolved_outcome:
            hit = (resolved_outcome.lower() == 'yes')

        label = 'YES' if hit else 'NO'

        # Get spot price at creation for features
        spot_at_creation = self.coingecko.get_price_at_time(parsed['asset'], start_date)

        return {
            'condition_id': market.get('condition_id'),
            'question': market.get('question'),
            'asset': parsed['asset'],
            'strike': parsed['strike'],
            'direction': parsed['direction'],
            'spot_at_creation': spot_at_creation,
            'distance_to_strike': ((parsed['strike'] - spot_at_creation) / spot_at_creation * 100)
                if spot_at_creation else None,
            'market_duration_days': (end_dt - start_date).days,
            'label': label,
            'hit_time': hit_time.isoformat() if hit_time else None,
            'resolved_outcome': resolved_outcome
        }

    def generate_samples_from_resolved_markets(self) -> List[Dict]:
        """
        Generate labeled samples from all resolved price-level markets.

        Returns:
            List of labeled samples
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get resolved markets that look like price-level markets
        cursor.execute("""
            SELECT condition_id, question, description, end_date, created_at,
                   closed_time, resolved_outcome, volume
            FROM markets
            WHERE (resolved = 1 OR active = 0)
              AND question IS NOT NULL
        """)

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        samples = []
        total = len(rows)

        logger.info(f"Processing {total} resolved markets for price-level labels...")

        for i, row in enumerate(rows):
            market = dict(zip(columns, row))
            sample = self.label_market(market)

            if sample:
                samples.append(sample)

            if (i + 1) % 100 == 0:
                logger.info(f"  Processed {i + 1}/{total} markets, {len(samples)} samples generated")

        logger.info(f"Generated {len(samples)} labeled price-level samples")
        return samples


class NewsEventLabeler:
    """
    Generate labels for news events matched to markets.
    """

    def __init__(self, db_path: str = 'data/training_history.db'):
        self.db_path = db_path
        self.price_labeler = HistoricalPriceLabeler(db_path)

    def label_news_event(self, event: Dict, market: Dict,
                         hold_hours: float = 24.0) -> Optional[Dict]:
        """
        Label a news event based on subsequent market price movement.

        Args:
            event: News event dictionary with 'timestamp' field
            market: Matched market dictionary
            hold_hours: Holding period for outcome measurement

        Returns:
            Labeled sample or None
        """
        try:
            event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
        except:
            return None

        condition_id = market.get('condition_id')
        if not condition_id:
            return None

        # Generate label using on-chain price data
        sample = self.price_labeler.generate_sample(condition_id, event_time, hold_hours)

        if not sample:
            return None

        # Add event features
        sample['event_title'] = event.get('title', '')
        sample['event_source'] = event.get('source', '')
        sample['event_url'] = event.get('url', '')

        return sample


def main():
    """Main routine for label generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Historical Label Generator")
    parser.add_argument("--price-level", action="store_true",
                        help="Generate price-level labels from resolved markets")
    parser.add_argument("--event-labels", action="store_true",
                        help="Generate event-based labels")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--stats", action="store_true", help="Show label statistics")
    args = parser.parse_args()

    if args.price_level:
        import pandas as pd

        labeler = PriceLevelLabeler()
        samples = labeler.generate_samples_from_resolved_markets()

        if samples:
            df = pd.DataFrame(samples)
            output_path = args.output or 'data/price_level_labels.csv'
            df.to_csv(output_path, index=False)
            logger.info(f"Saved {len(samples)} samples to {output_path}")

            # Show statistics
            print("\n=== Label Distribution ===")
            print(df['label'].value_counts())
            print(f"\nAsset distribution:")
            print(df['asset'].value_counts())

    if args.stats:
        import pandas as pd

        # Try to load existing labels
        for path in ['data/price_level_labels.csv', 'data/training_event_bot.csv']:
            if Path(path).exists():
                df = pd.read_csv(path)
                print(f"\n=== {path} ===")
                print(f"Total samples: {len(df)}")
                if 'label' in df.columns:
                    print(f"Label distribution:\n{df['label'].value_counts()}")


if __name__ == "__main__":
    main()
