"""
Feature extraction for short-expiry markets.

This module provides specialized feature extractors for short-expiry prediction markets
(2 hours to 7 days). Features are designed to capture time-decay dynamics, momentum,
microstructure signals, and crypto-specific patterns.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TimeDecayFeatures:
    """Extract time-decay related features."""

    @staticmethod
    def extract(market: Dict, bucket: str) -> Dict[str, float]:
        """
        Extract time decay features.

        Args:
            market: Market data dict
            bucket: Time bucket (ultra_short/short/medium)

        Returns:
            Dict of time decay features
        """
        features = {}

        # Parse expiry
        try:
            end_date_iso = market.get('endDate', market.get('end_date_iso', ''))
            if not end_date_iso:
                logger.warning(f"No end_date_iso for market {market.get('conditionId', 'unknown')}")
                expiry = datetime.now(timezone.utc) + timedelta(hours=24)
            else:
                expiry = datetime.fromisoformat(end_date_iso.replace('Z', '+00:00'))
        except Exception as e:
            logger.error(f"Error parsing expiry: {e}")
            expiry = datetime.now(timezone.utc) + timedelta(hours=24)

        now = datetime.now(timezone.utc)
        time_to_expiry = expiry - now

        # Core time features
        features['hours_to_expiry'] = time_to_expiry.total_seconds() / 3600
        features['days_to_expiry'] = time_to_expiry.total_seconds() / 86400
        features['minutes_to_expiry'] = time_to_expiry.total_seconds() / 60

        # Decay rate (higher for shorter horizons)
        hours = features['hours_to_expiry']
        if hours < 1:
            features['decay_rate'] = 1.0  # Max urgency
        else:
            features['decay_rate'] = 1.0 / np.sqrt(hours)

        # Urgency score (0-1, higher = more urgent)
        if bucket == 'ultra_short':
            features['urgency_score'] = max(0, 1.0 - (hours / 24.0))
        elif bucket == 'short':
            features['urgency_score'] = max(0, 1.0 - (hours / 72.0))
        else:  # medium
            features['urgency_score'] = max(0, 1.0 - (hours / 168.0))

        # Intraday patterns (for ultra_short)
        hour_of_day = now.hour
        features['hour_of_day'] = hour_of_day
        features['is_market_hours'] = 1.0 if 9 <= hour_of_day <= 16 else 0.0
        features['is_asian_hours'] = 1.0 if 0 <= hour_of_day <= 8 else 0.0
        features['is_weekend'] = 1.0 if now.weekday() >= 5 else 0.0

        return features


class MomentumFeatures:
    """Extract momentum and velocity features."""

    @staticmethod
    def extract(market: Dict, price_history: Optional[pd.DataFrame] = None) -> Dict[str, float]:
        """
        Extract momentum features.

        Args:
            market: Market data dict
            price_history: Historical prices (if available)

        Returns:
            Dict of momentum features
        """
        features = {}

        # Current price
        current_price = market.get('lastTradePrice', 0.5)
        if isinstance(current_price, str):
            current_price = float(current_price)

        features['current_price'] = current_price

        # If we have price history, calculate changes
        if price_history is not None and len(price_history) > 0:
            prices = price_history['price'].values

            # Price changes at different horizons
            if len(prices) >= 2:
                features['price_change_1h'] = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
            else:
                features['price_change_1h'] = 0.0

            if len(prices) >= 4:
                features['price_change_4h'] = (prices[-1] - prices[-4]) / prices[-4] if prices[-4] > 0 else 0
            else:
                features['price_change_4h'] = 0.0

            if len(prices) >= 12:
                features['price_change_12h'] = (prices[-1] - prices[-12]) / prices[-12] if prices[-12] > 0 else 0
            else:
                features['price_change_12h'] = 0.0

            # Velocity (rate of change)
            if len(prices) >= 3:
                recent_change = prices[-1] - prices[-3]
                features['velocity'] = recent_change / 2.0  # Per hour
            else:
                features['velocity'] = 0.0

            # Acceleration (change in velocity)
            if len(prices) >= 5:
                velocity_now = (prices[-1] - prices[-3]) / 2.0
                velocity_then = (prices[-3] - prices[-5]) / 2.0
                features['acceleration'] = velocity_now - velocity_then
            else:
                features['acceleration'] = 0.0

        else:
            # No history - use zeros
            features['price_change_1h'] = 0.0
            features['price_change_4h'] = 0.0
            features['price_change_12h'] = 0.0
            features['velocity'] = 0.0
            features['acceleration'] = 0.0

        # Direction consistency
        if price_history is not None and len(price_history) >= 3:
            prices = price_history['price'].values[-5:]  # Last 5 points
            changes = np.diff(prices)
            if len(changes) > 0:
                features['trend_consistency'] = np.sum(np.sign(changes) == np.sign(changes[-1])) / len(changes)
            else:
                features['trend_consistency'] = 0.5
        else:
            features['trend_consistency'] = 0.5

        # Distance from 0.5 (neutral)
        features['distance_from_neutral'] = abs(current_price - 0.5)

        return features


class MicrostructureFeatures:
    """Extract order book microstructure features."""

    @staticmethod
    def extract(market: Dict, orderbook: Optional[Dict] = None) -> Dict[str, float]:
        """
        Extract microstructure features from orderbook.

        Args:
            market: Market data dict
            orderbook: Orderbook data (if available)

        Returns:
            Dict of microstructure features
        """
        features = {}

        # Get best bid/ask from market data
        best_bid = market.get('bestBid', 0.45)
        best_ask = market.get('bestAsk', 0.55)

        if isinstance(best_bid, str):
            best_bid = float(best_bid)
        if isinstance(best_ask, str):
            best_ask = float(best_ask)

        # Spread features
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2.0

        features['spread'] = spread
        features['spread_pct'] = (spread / mid_price * 100) if mid_price > 0 else 0
        features['mid_price'] = mid_price

        # If we have orderbook data, calculate depth features
        if orderbook is not None:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])

            # Depth imbalance (bid vs ask volume)
            bid_volume = sum(float(b.get('size', 0)) for b in bids[:5])  # Top 5 levels
            ask_volume = sum(float(a.get('size', 0)) for a in asks[:5])

            total_volume = bid_volume + ask_volume
            if total_volume > 0:
                features['depth_imbalance'] = (bid_volume - ask_volume) / total_volume
            else:
                features['depth_imbalance'] = 0.0

            features['bid_volume_top5'] = bid_volume
            features['ask_volume_top5'] = ask_volume

            # Liquidity ratio (volume at best vs total)
            if len(bids) > 0 and bid_volume > 0:
                features['bid_concentration'] = float(bids[0].get('size', 0)) / bid_volume
            else:
                features['bid_concentration'] = 0.0

            if len(asks) > 0 and ask_volume > 0:
                features['ask_concentration'] = float(asks[0].get('size', 0)) / ask_volume
            else:
                features['ask_concentration'] = 0.0
        else:
            # No orderbook - use defaults
            features['depth_imbalance'] = 0.0
            features['bid_volume_top5'] = 0.0
            features['ask_volume_top5'] = 0.0
            features['bid_concentration'] = 0.0
            features['ask_concentration'] = 0.0

        # Effective spread (from recent trades)
        last_trade_price = market.get('lastTradePrice', mid_price)
        if isinstance(last_trade_price, str):
            last_trade_price = float(last_trade_price)

        features['effective_spread'] = abs(last_trade_price - mid_price)

        return features


class EventVelocityFeatures:
    """Extract event velocity features for crypto markets."""

    @staticmethod
    def extract(market: Dict, event_data: Optional[List[Dict]] = None) -> Dict[str, float]:
        """
        Extract event velocity features.

        Args:
            market: Market data dict
            event_data: Recent GDELT events (if available)

        Returns:
            Dict of event velocity features
        """
        features = {}

        # If we have event data, calculate velocity
        if event_data is not None and len(event_data) > 0:
            # Count events in different time windows
            now = datetime.now(timezone.utc)

            events_1h = sum(1 for e in event_data if (now - e['timestamp']).total_seconds() < 3600)
            events_4h = sum(1 for e in event_data if (now - e['timestamp']).total_seconds() < 14400)
            events_24h = sum(1 for e in event_data if (now - e['timestamp']).total_seconds() < 86400)

            features['event_count_1h'] = events_1h
            features['event_count_4h'] = events_4h
            features['event_count_24h'] = events_24h

            # Event velocity (events per hour)
            features['event_velocity'] = events_1h  # Already per hour

            # Event acceleration (change in velocity)
            if events_4h > 0:
                recent_velocity = events_1h
                avg_velocity = events_4h / 4.0
                features['event_acceleration'] = recent_velocity - avg_velocity
            else:
                features['event_acceleration'] = 0.0
        else:
            # No event data
            features['event_count_1h'] = 0
            features['event_count_4h'] = 0
            features['event_count_24h'] = 0
            features['event_velocity'] = 0.0
            features['event_acceleration'] = 0.0

        return features


class ImpliedMoveFeatures:
    """Extract implied move and probabilistic features."""

    @staticmethod
    def extract(market: Dict, underlying_price: Optional[float] = None) -> Dict[str, float]:
        """
        Extract implied move features (for price prediction markets).

        Args:
            market: Market data dict
            underlying_price: Current BTC/ETH price (if applicable)

        Returns:
            Dict of implied move features
        """
        features = {}

        # Market probability
        market_price = market.get('lastTradePrice', 0.5)
        if isinstance(market_price, str):
            market_price = float(market_price)

        features['market_probability'] = market_price
        features['implied_odds'] = market_price / (1 - market_price) if market_price < 1.0 else 10.0

        # For BTC/ETH price markets, extract strike
        question = market.get('question', '').lower()

        # Try to extract strike price from question
        strike = None
        for word in question.split():
            # Look for price patterns like "$60000" or "60,000" or "60k"
            if '$' in word or 'k' in word.lower():
                try:
                    # Clean and parse
                    cleaned = word.replace('$', '').replace(',', '').replace('k', '000').replace('K', '000')
                    strike = float(cleaned)
                    break
                except:
                    continue

        if strike is not None and underlying_price is not None:
            # Strike distance
            features['strike_distance_pct'] = (strike - underlying_price) / underlying_price
            features['strike_distance_abs'] = abs(strike - underlying_price)

            # Moneyness
            if 'above' in question or 'over' in question or '>' in question:
                # Call option equivalent
                features['moneyness'] = underlying_price / strike
            elif 'below' in question or 'under' in question or '<' in question:
                # Put option equivalent
                features['moneyness'] = strike / underlying_price
            else:
                features['moneyness'] = 1.0
        else:
            features['strike_distance_pct'] = 0.0
            features['strike_distance_abs'] = 0.0
            features['moneyness'] = 1.0

        # Entropy (market uncertainty)
        if market_price > 0 and market_price < 1:
            features['entropy'] = -(market_price * np.log2(market_price) +
                                    (1 - market_price) * np.log2(1 - market_price))
        else:
            features['entropy'] = 0.0

        return features


class ShortExpiryFeatureExtractor:
    """Main feature extractor coordinating all feature types."""

    def __init__(self):
        self.time_decay = TimeDecayFeatures()
        self.momentum = MomentumFeatures()
        self.microstructure = MicrostructureFeatures()
        self.event_velocity = EventVelocityFeatures()
        self.implied_move = ImpliedMoveFeatures()

    def extract_all_features(
        self,
        market: Dict,
        bucket: str,
        price_history: Optional[pd.DataFrame] = None,
        orderbook: Optional[Dict] = None,
        event_data: Optional[List[Dict]] = None,
        underlying_price: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Extract all features for a market.

        Args:
            market: Market data dict
            bucket: Time bucket (ultra_short/short/medium)
            price_history: Historical prices (optional)
            orderbook: Orderbook data (optional)
            event_data: Recent events (optional)
            underlying_price: BTC/ETH price for price markets (optional)

        Returns:
            DataFrame with all features
        """
        all_features = {}

        # Extract each feature group
        try:
            all_features.update(self.time_decay.extract(market, bucket))
        except Exception as e:
            logger.error(f"Error extracting time_decay features: {e}")

        try:
            all_features.update(self.momentum.extract(market, price_history))
        except Exception as e:
            logger.error(f"Error extracting momentum features: {e}")

        try:
            all_features.update(self.microstructure.extract(market, orderbook))
        except Exception as e:
            logger.error(f"Error extracting microstructure features: {e}")

        try:
            all_features.update(self.event_velocity.extract(market, event_data))
        except Exception as e:
            logger.error(f"Error extracting event_velocity features: {e}")

        try:
            all_features.update(self.implied_move.extract(market, underlying_price))
        except Exception as e:
            logger.error(f"Error extracting implied_move features: {e}")

        # Add market metadata
        all_features['bucket'] = bucket
        all_features['market_id'] = market.get('conditionId', '')
        all_features['volume_24h'] = float(market.get('volume24hr', 0))
        all_features['liquidity'] = float(market.get('liquidity', 0))

        # Convert to DataFrame
        return pd.DataFrame([all_features])
