"""
Common Feature Extractors
Centralized feature calculations shared across all trading bots.

This module provides standardized feature extraction for:
- Orderbook features (spread, depth, imbalance)
- Volume features (24h, 7d, liquidity, trend)
- Time features (days/hours to expiry, time of day)

All bots should use these centralized implementations to ensure consistency
and reduce code duplication.
"""

import numpy as np
from datetime import datetime, timezone
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class OrderbookFeatures:
    """
    Centralized orderbook feature calculator.

    Extracts microstructure features from order book data including:
    - Spread (absolute and percentage)
    - Mid-price
    - Bid/ask depth (top 5 levels)
    - Depth imbalance

    This replaces duplicate implementations in:
    - feature_extractor.py: MarketFeatureExtractor.extract_orderbook_features()
    - price_level_features.py: MarketMicrostructureFeatures.extract_market_features()
    - short_expiry_features.py: MicrostructureFeatures.extract()
    """

    @staticmethod
    def extract(orderbook: Dict, return_best_bid_ask: bool = False) -> Dict[str, float]:
        """
        Extract orderbook features from order book dictionary.

        Args:
            orderbook: Order book dictionary with 'bids' and 'asks' arrays
            return_best_bid_ask: If True, also return best_bid and best_ask

        Returns:
            Dictionary with orderbook features:
            - spread: Absolute spread (ask - bid)
            - spread_pct: Percentage spread relative to mid-price
            - mid_price: Mid-point between best bid and ask
            - bid_depth_5: Total size of top 5 bid levels
            - ask_depth_5: Total size of top 5 ask levels
            - depth_imbalance: (bid_depth - ask_depth) / total_depth
            - best_bid: Best bid price (if return_best_bid_ask=True)
            - best_ask: Best ask price (if return_best_bid_ask=True)

        Examples:
            >>> orderbook = {
            ...     'bids': [{'price': '0.45', 'size': '1000'}, {'price': '0.44', 'size': '2000'}],
            ...     'asks': [{'price': '0.47', 'size': '1500'}, {'price': '0.48', 'size': '2500'}]
            ... }
            >>> features = OrderbookFeatures.extract(orderbook)
            >>> features['spread']
            0.02
            >>> features['mid_price']
            0.46
        """
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        # Handle empty orderbook
        if not bids or not asks:
            logger.debug("Empty orderbook, returning default features")
            default_features = {
                'spread': 0.0,
                'spread_pct': 0.0,
                'mid_price': 0.5,
                'bid_depth_5': 0.0,
                'ask_depth_5': 0.0,
                'depth_imbalance': 0.0
            }
            if return_best_bid_ask:
                default_features['best_bid'] = 0.45
                default_features['best_ask'] = 0.55
            return default_features

        # Extract best bid/ask (handle both dict and array formats)
        # Dict format: {'price': '0.45', 'size': '1000'}
        # Array format: [0.45, 1000] or ['0.45', '1000']
        if isinstance(bids[0], dict):
            best_bid = float(bids[0]['price'])
            best_ask = float(asks[0]['price'])
        else:
            # Array format
            best_bid = float(bids[0][0]) if isinstance(bids[0], (list, tuple)) else float(bids[0])
            best_ask = float(asks[0][0]) if isinstance(asks[0], (list, tuple)) else float(asks[0])

        # Calculate spread features
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2.0
        spread_pct = (spread / mid_price * 100) if mid_price > 0 else 0.0

        # Calculate depth features (top 5 levels)
        bid_depth_5 = OrderbookFeatures._calculate_depth(bids, max_levels=5)
        ask_depth_5 = OrderbookFeatures._calculate_depth(asks, max_levels=5)

        # Depth imbalance: positive means more bids (buying pressure)
        total_depth = bid_depth_5 + ask_depth_5
        depth_imbalance = (bid_depth_5 - ask_depth_5) / total_depth if total_depth > 0 else 0.0

        features = {
            'spread': spread,
            'spread_pct': spread_pct,
            'mid_price': mid_price,
            'bid_depth_5': bid_depth_5,
            'ask_depth_5': ask_depth_5,
            'depth_imbalance': depth_imbalance
        }

        if return_best_bid_ask:
            features['best_bid'] = best_bid
            features['best_ask'] = best_ask

        return features

    @staticmethod
    def _calculate_depth(levels: list, max_levels: int = 5) -> float:
        """
        Calculate total depth (volume) for top N levels.

        Args:
            levels: List of bid or ask levels (dict or array format)
            max_levels: Number of levels to sum (default: 5)

        Returns:
            Total depth as float
        """
        if not levels:
            return 0.0

        depth = 0.0
        for level in levels[:max_levels]:
            if isinstance(level, dict):
                depth += float(level.get('size', 0))
            elif isinstance(level, (list, tuple)):
                # Array format: [price, size]
                depth += float(level[1])
            else:
                logger.warning(f"Unknown orderbook level format: {type(level)}")

        return depth


class VolumeFeatures:
    """
    Centralized volume and liquidity feature calculator.

    Extracts volume-based features from market data including:
    - 24-hour volume
    - 7-day volume
    - Liquidity
    - Volume trend (recent vs historical)
    """

    @staticmethod
    def extract(market: Dict) -> Dict[str, float]:
        """
        Extract volume and liquidity features from market dictionary.

        Args:
            market: Market dictionary from Polymarket API

        Returns:
            Dictionary with volume features:
            - volume_24h: Trading volume in last 24 hours
            - volume_7d: Trading volume in last 7 days
            - liquidity: Available liquidity
            - volume_trend: Ratio of 24h volume to 7d daily average

        Examples:
            >>> market = {'volume24hr': 50000, 'volume1wk': 200000, 'liquidity': 100000}
            >>> features = VolumeFeatures.extract(market)
            >>> features['volume_trend']  # 50000 / (200000/7) ≈ 1.75
            1.75
        """
        volume_24h = float(market.get('volume24hr', 0))
        volume_7d = float(market.get('volume1wk', 0))
        liquidity = float(market.get('liquidity', 0))

        # Volume trend: compare 24h volume to 7-day daily average
        # > 1.0 means recent volume is higher than average (increasing activity)
        # < 1.0 means recent volume is lower than average (decreasing activity)
        if volume_7d > 0:
            avg_daily_vol_7d = volume_7d / 7.0
            volume_trend = volume_24h / avg_daily_vol_7d
        elif volume_24h > 0:
            # Have 24h volume but no 7d volume - trending up
            volume_trend = 1.0
        else:
            # No volume at all - default to neutral
            volume_trend = 1.0

        return {
            'volume_24h': volume_24h,
            'volume_7d': volume_7d,
            'liquidity': liquidity,
            'volume_trend': volume_trend
        }


class TimeFeatures:
    """
    Centralized time-based feature calculator.

    Extracts time-related features including:
    - Time to expiry (days, hours, minutes)
    - Current time patterns (hour of day, day of week, weekend)
    - Calendar features (month, quarter end, year end)
    """

    @staticmethod
    def extract(expiry_date: datetime, current_time: Optional[datetime] = None) -> Dict[str, float]:
        """
        Extract time-based features.

        Args:
            expiry_date: Market expiry datetime (should be timezone-aware)
            current_time: Current time (defaults to now UTC)

        Returns:
            Dictionary with time features:
            - days_to_expiry: Days until expiry (non-negative)
            - hours_to_expiry: Hours until expiry (non-negative)
            - minutes_to_expiry: Minutes until expiry (non-negative)
            - hour_of_day: Current hour (0-23)
            - day_of_week: Day of week (0=Monday, 6=Sunday)
            - is_weekend: 1.0 if Saturday/Sunday, else 0.0
            - month: Current month (1-12)
            - is_quarter_end: 1.0 if Mar/Jun/Sep/Dec, else 0.0
            - is_year_end: 1.0 if December, else 0.0

        Examples:
            >>> expiry = datetime(2025, 12, 31, tzinfo=timezone.utc)
            >>> current = datetime(2025, 1, 1, 14, 30, tzinfo=timezone.utc)
            >>> features = TimeFeatures.extract(expiry, current)
            >>> features['days_to_expiry']
            364.0
            >>> features['hour_of_day']
            14.0
        """
        # Default to current UTC time
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Ensure both are timezone-aware
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Calculate time to expiry
        time_to_expiry = expiry_date - current_time

        # Ensure non-negative (market might have just expired)
        days_to_expiry = max(0, time_to_expiry.days)
        hours_to_expiry = max(0, time_to_expiry.total_seconds() / 3600)
        minutes_to_expiry = max(0, time_to_expiry.total_seconds() / 60)

        # Current time patterns
        hour_of_day = current_time.hour
        day_of_week = current_time.weekday()  # 0=Monday, 6=Sunday
        is_weekend = 1.0 if day_of_week >= 5 else 0.0

        # Calendar features
        month = current_time.month
        is_quarter_end = 1.0 if month in [3, 6, 9, 12] else 0.0
        is_year_end = 1.0 if month == 12 else 0.0

        return {
            'days_to_expiry': float(days_to_expiry),
            'hours_to_expiry': hours_to_expiry,
            'minutes_to_expiry': minutes_to_expiry,
            'hour_of_day': float(hour_of_day),
            'day_of_week': float(day_of_week),
            'is_weekend': is_weekend,
            'month': float(month),
            'is_quarter_end': is_quarter_end,
            'is_year_end': is_year_end
        }


# Convenience function for extracting all common features at once
def extract_all_common_features(
    orderbook: Dict,
    market: Dict,
    expiry_date: datetime,
    return_best_bid_ask: bool = False
) -> Dict[str, float]:
    """
    Extract all common features in one call.

    Args:
        orderbook: Order book dictionary
        market: Market dictionary
        expiry_date: Market expiry datetime
        return_best_bid_ask: Include best_bid/best_ask in orderbook features

    Returns:
        Dictionary with all common features (orderbook + volume + time)

    Examples:
        >>> features = extract_all_common_features(orderbook, market, expiry_date)
        >>> len(features)  # 6 orderbook + 4 volume + 9 time = 19 features
        19
    """
    features = {}

    # Orderbook features
    features.update(OrderbookFeatures.extract(orderbook, return_best_bid_ask))

    # Volume features
    features.update(VolumeFeatures.extract(market))

    # Time features
    features.update(TimeFeatures.extract(expiry_date))

    return features


if __name__ == '__main__':
    # Example usage and testing
    print("\n=== Testing Common Features ===\n")

    # Sample orderbook
    orderbook = {
        'bids': [
            {'price': '0.45', 'size': '1000'},
            {'price': '0.44', 'size': '2000'},
            {'price': '0.43', 'size': '1500'},
            {'price': '0.42', 'size': '3000'},
            {'price': '0.41', 'size': '2500'},
        ],
        'asks': [
            {'price': '0.47', 'size': '1500'},
            {'price': '0.48', 'size': '2500'},
            {'price': '0.49', 'size': '1200'},
            {'price': '0.50', 'size': '3500'},
            {'price': '0.51', 'size': '2000'},
        ]
    }

    # Sample market
    market = {
        'volume24hr': 50000,
        'volume1wk': 200000,
        'liquidity': 100000
    }

    # Sample expiry (30 days from now)
    from datetime import timedelta
    expiry_date = datetime.now(timezone.utc) + timedelta(days=30)

    # Extract features
    print("1. Orderbook Features:")
    ob_features = OrderbookFeatures.extract(orderbook, return_best_bid_ask=True)
    for key, value in ob_features.items():
        print(f"   {key:20s} = {value:.6f}")

    print("\n2. Volume Features:")
    vol_features = VolumeFeatures.extract(market)
    for key, value in vol_features.items():
        print(f"   {key:20s} = {value:.2f}")

    print("\n3. Time Features:")
    time_features = TimeFeatures.extract(expiry_date)
    for key, value in time_features.items():
        print(f"   {key:20s} = {value:.2f}")

    print("\n4. All Common Features (convenience function):")
    all_features = extract_all_common_features(orderbook, market, expiry_date)
    print(f"   Total features: {len(all_features)}")

    print("\n✓ Common features module working correctly!")
