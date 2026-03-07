"""Unified position sizing using Kelly criterion with liquidity awareness."""

import logging
from typing import Dict, Optional, Union

from features.common_features import OrderbookFeatures

logger = logging.getLogger(__name__)


class PositionSizer:
    """Unified position sizer for all trading bots.

    Uses fractional Kelly criterion with confidence scaling, liquidity caps,
    and configurable per-bucket max sizes.
    """

    def __init__(self, config: dict):
        self.kelly_multiplier = config.get('kelly_multiplier', 0.5)
        self.max_kelly_fraction = config.get('max_kelly_fraction', 0.25)
        self.max_position_size = config.get('max_position_size', 100)
        self.min_position_size = config.get('min_position_size', 5.0)
        self.liquidity_cap_pct = config.get('liquidity_cap_pct', 0.10)

    def calculate(self, edge: float, confidence: float, balance: float,
                  orderbook: Optional[Dict] = None,
                  bucket: Optional[str] = None) -> float:
        """Calculate position size.

        Formula:
            1. kelly_fraction = min(|edge| * kelly_multiplier, max_kelly_fraction)
            2. base_size = balance * kelly_fraction
            3. confidence_scaled = base_size * (0.5 + 0.5 * clamp(confidence, 0, 1))
            4. Cap at max_position_size (bucket-specific if provided)
            5. Cap at liquidity limit (% of orderbook depth)
            6. Return 0 if below min_position_size

        Args:
            edge: Expected edge (model_prob - market_price)
            confidence: Model confidence (0-1)
            balance: Available trading balance
            orderbook: Optional orderbook dict with 'bids'/'asks'
            bucket: Optional time bucket for bucket-specific max sizes

        Returns:
            Position size in dollars, or 0 if too small
        """
        if abs(edge) < 1e-9:
            return 0.0

        # 1. Kelly fraction
        kelly_fraction = min(abs(edge) * self.kelly_multiplier, self.max_kelly_fraction)

        # 2. Base size
        base_size = balance * kelly_fraction

        # 3. Confidence scaling: maps [0, 1] -> [0.5, 1.0]
        clamped_confidence = max(0.0, min(1.0, confidence))
        confidence_multiplier = 0.5 + 0.5 * clamped_confidence
        sized = base_size * confidence_multiplier

        # 4. Max cap (bucket-specific or flat)
        max_cap = self._get_max_size(bucket)
        sized = min(sized, max_cap)

        # 5. Liquidity cap
        if orderbook is not None:
            liquidity_limit = self._get_liquidity_limit(orderbook)
            if liquidity_limit > 0:
                if sized > liquidity_limit:
                    logger.debug(
                        f"PositionSizer: liquidity cap applied ${sized:.2f} -> ${liquidity_limit:.2f} "
                        f"(cap={self.liquidity_cap_pct:.0%} of orderbook depth)"
                    )
                sized = min(sized, liquidity_limit)

        # 6. Min floor
        if sized < self.min_position_size:
            logger.warning(
                f"PositionSizer: size ${sized:.2f} below min ${self.min_position_size} — returning 0 "
                f"[edge={edge:.4f} kelly={kelly_fraction:.4f} base=${base_size:.2f} "
                f"conf={confidence:.2f} conf_scaled=${base_size * (0.5 + 0.5 * clamped_confidence):.2f} "
                f"after_liq=${sized:.2f} min={self.min_position_size}]"
            )
            return 0.0

        logger.info(
            f"PositionSizer: edge={edge:.4f} kelly={kelly_fraction:.4f} "
            f"conf={confidence:.2f} base=${base_size:.2f} "
            f"final=${sized:.2f} (max={max_cap}, min={self.min_position_size})"
        )
        return round(sized, 2)

    def _get_max_size(self, bucket: Optional[str]) -> float:
        """Get max position size, optionally per-bucket."""
        if bucket is not None and isinstance(self.max_position_size, dict):
            return float(self.max_position_size.get(bucket, 100))
        if isinstance(self.max_position_size, dict):
            # No bucket specified but dict config — use max of all buckets
            return float(max(self.max_position_size.values()))
        return float(self.max_position_size)

    def _get_liquidity_limit(self, orderbook: Dict) -> float:
        """Calculate liquidity-based position cap using orderbook depth."""
        features = OrderbookFeatures.extract(orderbook)
        # Use ask depth for buys (we lift asks), bid depth for sells
        # Since we don't know direction here, use the smaller side as conservative cap
        depth = min(features['bid_depth_5'], features['ask_depth_5'])
        if depth <= 0:
            return 0.0
        return depth * self.liquidity_cap_pct
