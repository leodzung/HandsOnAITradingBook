"""
Slippage Estimation Module for Polymarket Trading Bots

Estimates execution slippage by walking through orderbook levels and simulating
order fills. Provides pre-trade validation to reject trades with excessive costs.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FillLevel:
    """Represents a single orderbook level fill"""
    price: float
    size: float
    amount_filled: float  # Dollar amount filled at this level


@dataclass
class SlippageEstimate:
    """Complete slippage estimation result"""

    # Price information
    quoted_price: float  # Best bid/ask
    expected_execution_price: float  # Volume-weighted average fill price
    worst_case_execution_price: float  # With safety buffers applied

    # Slippage metrics
    slippage_dollars: float  # Absolute slippage cost
    slippage_bps: float  # Basis points (1 bps = 0.01%)
    slippage_pct: float  # Percentage

    # Orderbook analysis
    levels_consumed: int  # Number of price levels needed
    total_liquidity_available: float  # Total $ liquidity in orderbook
    order_fills_immediately: bool  # Can order be fully filled

    # Validation
    is_acceptable: bool
    rejection_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    # Metadata
    orderbook_spread_bps: float = 0.0
    orderbook_timestamp: Optional[datetime] = None
    fill_simulation: List[FillLevel] = field(default_factory=list)


class SlippageEstimator:
    """
    Estimates trade execution slippage using orderbook depth analysis.

    Uses a piecewise linear depth walk-through model with safety buffers.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize slippage estimator with configuration.

        Args:
            config: Configuration dict with keys:
                - enabled (bool): Enable slippage checking
                - max_slippage_bps (float): Maximum acceptable slippage in bps
                - max_slippage_dollars (float): Maximum acceptable slippage in $
                - orderbook_staleness_seconds (int): Max orderbook age
                - depth_buffer_pct (float): Safety margin for depth (e.g., 0.10 = 10%)
                - volatility_adjustment (bool): Apply extra buffer for wide spreads
                - volume_limit_pct (float): Max order as % of daily volume
                - warn_threshold_bps (float): Warning threshold for slippage
        """
        self.config = config or {}

        # Default configuration
        self.enabled = self.config.get('enabled', True)
        self.max_slippage_bps = self.config.get('max_slippage_bps', 100)
        self.max_slippage_dollars = self.config.get('max_slippage_dollars', 5.0)
        self.orderbook_staleness_seconds = self.config.get('orderbook_staleness_seconds', 10)
        self.depth_buffer_pct = self.config.get('depth_buffer_pct', 0.10)
        self.volatility_adjustment = self.config.get('volatility_adjustment', True)
        self.volume_limit_pct = self.config.get('volume_limit_pct', 0.01)
        self.warn_threshold_bps = self.config.get('warn_threshold_bps', 50)

        logger.info(f"SlippageEstimator initialized: max_slippage={self.max_slippage_bps}bps, "
                   f"max_dollars=${self.max_slippage_dollars}, buffer={self.depth_buffer_pct*100}%")

    def _resolve(self, value, bucket: Optional[str], default: float) -> float:
        """Resolve a config value that may be scalar or per-bucket dict."""
        if isinstance(value, dict):
            if bucket and bucket in value:
                return float(value[bucket])
            # Fallback: use max of all bucket values (most permissive)
            return float(max(value.values())) if value else default
        return float(value)

    def estimate_slippage(
        self,
        order_side: str,
        order_size: float,
        orderbook: Dict,
        quoted_price: float,
        market_volume_24h: float = 0,
        bucket: Optional[str] = None
    ) -> SlippageEstimate:
        """
        Estimate slippage for a proposed trade.

        Args:
            order_side: 'BUY' or 'SELL'
            order_size: Order size in dollars
            orderbook: Orderbook dict from polymarket_client.get_orderbook()
                Expected format: {'bids': [[price, size], ...], 'asks': [[price, size], ...]}
            quoted_price: Best bid (for SELL) or best ask (for BUY)
            market_volume_24h: 24-hour market volume in dollars

        Returns:
            SlippageEstimate with complete analysis and validation
        """
        if not self.enabled:
            # Slippage checking disabled - return optimistic estimate
            return SlippageEstimate(
                quoted_price=quoted_price,
                expected_execution_price=quoted_price,
                worst_case_execution_price=quoted_price,
                slippage_dollars=0.0,
                slippage_bps=0.0,
                slippage_pct=0.0,
                levels_consumed=1,
                total_liquidity_available=order_size,
                order_fills_immediately=True,
                is_acceptable=True,
                warnings=["Slippage estimation disabled"]
            )

        # Validate inputs
        if order_side not in ['BUY', 'SELL']:
            raise ValueError(f"Invalid order_side: {order_side}. Must be 'BUY' or 'SELL'")

        if order_size <= 0:
            raise ValueError(f"Invalid order_size: {order_size}. Must be positive")

        # Validate quoted_price
        import math
        if not isinstance(quoted_price, (int, float)) or math.isnan(quoted_price) or math.isinf(quoted_price):
            raise ValueError(f"Invalid quoted_price: {quoted_price}. Must be a valid number")

        if not (0 < quoted_price < 1):
            raise ValueError(f"Invalid quoted_price: {quoted_price}. Must be between 0 and 1")

        # Validate orderbook staleness
        if 'timestamp' in orderbook:
            from datetime import timezone
            try:
                if isinstance(orderbook['timestamp'], str):
                    orderbook_time = datetime.fromisoformat(orderbook['timestamp'].replace('Z', '+00:00'))
                else:
                    orderbook_time = orderbook['timestamp']

                # Ensure orderbook_time is timezone-aware
                if orderbook_time.tzinfo is None:
                    orderbook_time = orderbook_time.replace(tzinfo=timezone.utc)

                age_seconds = (datetime.now(timezone.utc) - orderbook_time).total_seconds()
                if age_seconds > self.orderbook_staleness_seconds:
                    logger.warning(
                        f"Orderbook is stale: {age_seconds:.1f}s old "
                        f"(max: {self.orderbook_staleness_seconds}s)"
                    )
                    return SlippageEstimate(
                        quoted_price=quoted_price,
                        expected_execution_price=quoted_price,
                        worst_case_execution_price=quoted_price,
                        slippage_dollars=0.0,
                        slippage_bps=0.0,
                        slippage_pct=0.0,
                        levels_consumed=0,
                        total_liquidity_available=0.0,
                        order_fills_immediately=False,
                        is_acceptable=False,
                        rejection_reason=f"Orderbook stale ({age_seconds:.0f}s old, max {self.orderbook_staleness_seconds}s)"
                    )
            except (ValueError, AttributeError, TypeError) as e:
                logger.debug(f"Could not parse orderbook timestamp: {e}")

        # Ensure market_volume_24h is numeric
        try:
            market_volume_24h = float(market_volume_24h) if market_volume_24h else 0
        except (ValueError, TypeError):
            market_volume_24h = 0

        # Check volume limit
        if market_volume_24h > 0:
            order_pct_of_volume = order_size / market_volume_24h
            if order_pct_of_volume > self.volume_limit_pct:
                return SlippageEstimate(
                    quoted_price=quoted_price,
                    expected_execution_price=quoted_price,
                    worst_case_execution_price=quoted_price,
                    slippage_dollars=0.0,
                    slippage_bps=0.0,
                    slippage_pct=0.0,
                    levels_consumed=0,
                    total_liquidity_available=0.0,
                    order_fills_immediately=False,
                    is_acceptable=False,
                    rejection_reason=f"Order size ${order_size:.2f} exceeds {self.volume_limit_pct*100}% "
                                   f"of daily volume ${market_volume_24h:.2f} "
                                   f"({order_pct_of_volume*100:.1f}%)"
                )

        # Extract relevant orderbook side
        if order_side == 'BUY':
            levels = orderbook.get('asks', [])
        else:
            levels = orderbook.get('bids', [])

        # Convert dict format to list format [price, size]
        if levels and isinstance(levels[0], dict):
            levels = [[float(level.get('price', 0)), float(level.get('size', 0))] for level in levels]
        elif levels:
            levels = [[float(level[0]), float(level[1])] for level in levels]

        # Handle empty orderbook
        if not levels or len(levels) == 0:
            return SlippageEstimate(
                quoted_price=quoted_price,
                expected_execution_price=quoted_price,
                worst_case_execution_price=quoted_price,
                slippage_dollars=0.0,
                slippage_bps=0.0,
                slippage_pct=0.0,
                levels_consumed=0,
                total_liquidity_available=0.0,
                order_fills_immediately=False,
                is_acceptable=False,
                rejection_reason="No liquidity available in orderbook"
            )

        # Calculate orderbook spread
        spread_bps = self._calculate_spread_bps(orderbook)

        # Simulate order fill across levels
        fill_simulation, total_filled, total_liquidity = self._simulate_fill(
            levels=levels,
            order_size=order_size,
            order_side=order_side
        )

        # Check if order can be filled
        if total_filled < order_size:
            return SlippageEstimate(
                quoted_price=quoted_price,
                expected_execution_price=quoted_price,
                worst_case_execution_price=quoted_price,
                slippage_dollars=0.0,
                slippage_bps=0.0,
                slippage_pct=0.0,
                levels_consumed=len(fill_simulation),
                total_liquidity_available=total_liquidity,
                order_fills_immediately=False,
                is_acceptable=False,
                rejection_reason=f"Insufficient liquidity: ${total_liquidity:.2f} available, "
                               f"${order_size:.2f} requested"
            )

        # Calculate volume-weighted average execution price
        vwap = sum(level.price * level.amount_filled for level in fill_simulation) / order_size

        # Apply safety buffers
        buffered_price, warnings = self._apply_buffers(
            vwap=vwap,
            quoted_price=quoted_price,
            order_side=order_side,
            spread_bps=spread_bps,
            num_levels=len(fill_simulation)
        )

        # Calculate slippage metrics
        if order_side == 'BUY':
            slippage_dollars = buffered_price - quoted_price
        else:
            slippage_dollars = quoted_price - buffered_price

        slippage_dollars = max(0, slippage_dollars * order_size)  # Total slippage cost
        slippage_bps = (slippage_dollars / order_size) * 10000 if order_size > 0 else 0
        slippage_pct = (slippage_dollars / order_size) * 100 if order_size > 0 else 0

        # Validate against thresholds (resolve per-bucket dicts)
        is_acceptable = True
        rejection_reason = None
        max_bps = self._resolve(self.max_slippage_bps, bucket, 100)
        max_dollars = self._resolve(self.max_slippage_dollars, bucket, 5.0)
        warn_bps = self._resolve(self.warn_threshold_bps, bucket, 50)

        if slippage_bps > max_bps:
            is_acceptable = False
            rejection_reason = f"Slippage {slippage_bps:.0f} bps exceeds limit {max_bps:.0f} bps"
        elif slippage_dollars > max_dollars:
            is_acceptable = False
            rejection_reason = f"Slippage ${slippage_dollars:.2f} exceeds limit ${max_dollars:.2f}"

        # Add warning if above warning threshold (but still acceptable)
        if is_acceptable and slippage_bps > warn_bps:
            warnings.append(f"Slippage {slippage_bps:.0f} bps above warning threshold {warn_bps:.0f} bps")

        return SlippageEstimate(
            quoted_price=quoted_price,
            expected_execution_price=vwap,
            worst_case_execution_price=buffered_price,
            slippage_dollars=slippage_dollars,
            slippage_bps=slippage_bps,
            slippage_pct=slippage_pct,
            levels_consumed=len(fill_simulation),
            total_liquidity_available=total_liquidity,
            order_fills_immediately=True,
            is_acceptable=is_acceptable,
            rejection_reason=rejection_reason,
            warnings=warnings,
            orderbook_spread_bps=spread_bps,
            orderbook_timestamp=datetime.utcnow(),
            fill_simulation=fill_simulation
        )

    def _simulate_fill(
        self,
        levels: List[List[float]],
        order_size: float,
        order_side: str
    ) -> Tuple[List[FillLevel], float, float]:
        """
        Simulate filling order across orderbook levels.

        Args:
            levels: List of [price, size] from orderbook
            order_size: Order size in dollars
            order_side: 'BUY' or 'SELL'

        Returns:
            (fill_simulation, total_filled, total_liquidity)
        """
        fill_simulation = []
        remaining_size = order_size
        total_liquidity = 0.0

        for price, size in levels:
            if remaining_size <= 0:
                break

            # Calculate dollar liquidity at this level
            # For prediction markets, size is in shares (contracts)
            # Dollar value = price * size (since each share trades at price)
            level_liquidity = price * size
            total_liquidity += level_liquidity

            # Determine how much to fill at this level
            amount_to_fill = min(remaining_size, level_liquidity)

            fill_simulation.append(FillLevel(
                price=price,
                size=size,
                amount_filled=amount_to_fill
            ))

            remaining_size -= amount_to_fill

        total_filled = order_size - remaining_size

        return fill_simulation, total_filled, total_liquidity

    def _apply_buffers(
        self,
        vwap: float,
        quoted_price: float,
        order_side: str,
        spread_bps: float,
        num_levels: int
    ) -> Tuple[float, List[str]]:
        """
        Apply safety buffers to execution price.

        Args:
            vwap: Volume-weighted average price from simulation
            quoted_price: Best bid/ask
            order_side: 'BUY' or 'SELL'
            spread_bps: Orderbook spread in basis points
            num_levels: Number of orderbook levels consumed

        Returns:
            (buffered_price, warnings)
        """
        warnings = []
        buffer_pct = self.depth_buffer_pct

        # Increase buffer for thin orderbooks (consuming many levels)
        # Only if we're consuming 3+ levels, which indicates thin liquidity
        if num_levels >= 3:
            buffer_pct = 0.20  # 20% buffer for thin books
            warnings.append(f"Thin orderbook ({num_levels} levels consumed), using 20% buffer")

        # Apply volatility adjustment for wide spreads (additive with thin book buffer)
        if self.volatility_adjustment and spread_bps > 500:  # >5% spread
            buffer_pct += 0.20  # Add 20% volatility buffer
            warnings.append(f"Wide spread ({spread_bps:.0f} bps), adding 20% volatility buffer")

        # Apply buffer (makes price worse for trader)
        if order_side == 'BUY':
            buffered_price = vwap * (1 + buffer_pct)
        else:
            buffered_price = vwap * (1 - buffer_pct)

        return buffered_price, warnings

    def _calculate_spread_bps(self, orderbook: Dict) -> float:
        """
        Calculate bid-ask spread in basis points.

        Args:
            orderbook: Orderbook dict with 'bids' and 'asks'

        Returns:
            Spread in basis points (0 if cannot calculate)
        """
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return 0.0

        # Handle both dict and list formats
        if isinstance(bids[0], dict):
            best_bid = float(bids[0].get('price', 0))
            best_ask = float(asks[0].get('price', 0))
        else:
            best_bid = float(bids[0][0]) if len(bids) > 0 else 0
            best_ask = float(asks[0][0]) if len(asks) > 0 else 0

        if best_bid <= 0 or best_ask <= 0:
            return 0.0

        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        if mid_price <= 0:
            return 0.0

        spread_bps = (spread / mid_price) * 10000

        return spread_bps
