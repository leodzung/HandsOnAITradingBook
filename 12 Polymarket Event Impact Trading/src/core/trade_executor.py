"""
Centralized Trade Executor for all Polymarket bots.

Provides consistent trade validation and execution logic:
- Price validation (max_entry_price)
- Slippage estimation
- Position sizing
- Risk checks
- Trade execution (paper/live)
- Position tracking
"""

import logging
from typing import Dict, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass

from core.slippage_estimator import SlippageEstimator
from core.polymarket_client import PolymarketClient
from core.position_manager_v2 import PositionManager


logger = logging.getLogger(__name__)


@dataclass
class TradeRequest:
    """Request to execute a trade."""
    market_id: str
    token_id: str
    outcome: str  # 'YES' or 'NO'
    entry_price: float  # CLOB price for this outcome
    position_size: float  # Dollar amount

    # Market metadata
    question: str
    asset: Optional[str] = None
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None

    # Signal metadata
    edge: Optional[float] = None
    confidence: Optional[float] = None
    signal_reason: Optional[str] = None

    # Risk management (RISK-001 constraint)
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

    # Additional metadata for position tracking
    metadata: Optional[Dict] = None


@dataclass
class TradeResult:
    """Result of trade execution attempt."""
    success: bool
    reason: str

    # If successful
    entry_price: Optional[float] = None
    position_size: Optional[float] = None
    slippage_bps: Optional[float] = None

    # If rejected
    rejection_reason: Optional[str] = None
    rejection_stage: Optional[str] = None  # 'price', 'slippage', 'risk', etc.


class TradeExecutor:
    """
    Centralized trade execution logic for all bots.

    Ensures consistent validation and execution across:
    - Price level trader
    - Event trader
    - Short-expiry trader
    - Arbitrage bot
    """

    def __init__(
        self,
        client: PolymarketClient,
        position_manager: PositionManager,
        config: Dict,
        paper_trading: bool = True
    ):
        """
        Initialize trade executor.

        Args:
            client: Polymarket API client
            position_manager: Position tracking manager
            config: Bot configuration dict
            paper_trading: If True, simulate trades without real execution
        """
        self.client = client
        self.position_manager = position_manager
        self.config = config
        self.paper_trading = paper_trading

        # Initialize slippage estimator
        slippage_config = config.get('slippage_estimation', {})
        self.slippage_estimator = SlippageEstimator(config=slippage_config)

        # Get config values
        self.max_entry_price = config.get('max_entry_price', 0.90)
        self.slippage_enabled = slippage_config.get('enabled', True)

        logger.info(
            f"TradeExecutor initialized | "
            f"Paper trading: {paper_trading} | "
            f"Max entry price: ${self.max_entry_price:.2f} | "
            f"Slippage checks: {self.slippage_enabled}"
        )

    def execute_trade(self, request: TradeRequest) -> TradeResult:
        """
        Execute trade with full validation pipeline.

        Validation stages:
        1. Price validation (max_entry_price)
        2. Slippage estimation (if enabled)
        3. Position tracking

        Args:
            request: TradeRequest with all trade parameters

        Returns:
            TradeResult with success/failure status
        """
        # Stage 1: Price validation
        price_check = self._validate_price(request)
        if not price_check['valid']:
            return TradeResult(
                success=False,
                reason=price_check['reason'],
                rejection_reason=price_check['reason'],
                rejection_stage='price'
            )

        # Stage 2: Slippage estimation
        if self.slippage_enabled:
            slippage_check = self._estimate_slippage(request)
            if not slippage_check['valid']:
                return TradeResult(
                    success=False,
                    reason=slippage_check['reason'],
                    rejection_reason=slippage_check['reason'],
                    rejection_stage='slippage',
                    slippage_bps=slippage_check.get('slippage_bps')
                )

            # Use slippage estimator's recommended price if available
            if slippage_check.get('recommended_price'):
                recommended_price = slippage_check['recommended_price']

                # Validate the recommended price before accepting it
                if recommended_price > self.max_entry_price:
                    logger.warning(
                        f"⚠️ Trade rejected - Recommended price too high | "
                        f"{request.outcome} @ ${recommended_price:.3f} | "
                        f"Max: ${self.max_entry_price:.2f} | "
                        f"Market: {request.question[:50]}"
                    )
                    return TradeResult(
                        success=False,
                        reason=f"Recommended price ${recommended_price:.3f} exceeds max ${self.max_entry_price:.2f}",
                        rejection_reason=f"Recommended price ${recommended_price:.3f} exceeds max ${self.max_entry_price:.2f}",
                        rejection_stage='price'
                    )

                request.entry_price = recommended_price

        # Stage 3: Execute trade
        execution_result = self._execute_position(request)

        if execution_result['success']:
            return TradeResult(
                success=True,
                reason='Trade executed successfully',
                entry_price=request.entry_price,
                position_size=request.position_size,
                slippage_bps=slippage_check.get('slippage_bps') if self.slippage_enabled else None
            )
        else:
            return TradeResult(
                success=False,
                reason=execution_result['reason'],
                rejection_reason=execution_result['reason'],
                rejection_stage='execution'
            )

    def _validate_price(self, request: TradeRequest) -> Dict:
        """
        Validate entry price is within acceptable range.

        Rejects trades where entry price > max_entry_price (e.g., 0.90).

        Args:
            request: TradeRequest

        Returns:
            Dict with 'valid' (bool) and 'reason' (str)
        """
        if request.entry_price > self.max_entry_price:
            reason = (
                f"Entry price ${request.entry_price:.3f} exceeds "
                f"max ${self.max_entry_price:.2f}"
            )
            logger.warning(
                f"⚠️ Trade rejected - Price too high | "
                f"{request.outcome} @ ${request.entry_price:.3f} | "
                f"Max: ${self.max_entry_price:.2f} | "
                f"Market: {request.question[:50]}"
            )
            return {'valid': False, 'reason': reason}

        return {'valid': True, 'reason': 'Price within limit'}

    def _estimate_slippage(self, request: TradeRequest) -> Dict:
        """
        Estimate slippage and validate within acceptable range.

        Args:
            request: TradeRequest

        Returns:
            Dict with 'valid', 'reason', 'slippage_bps', 'recommended_price'
        """
        # Get orderbook for the specific token
        orderbook = self.client.get_orderbook(request.token_id)
        if not orderbook:
            return {
                'valid': False,
                'reason': 'Could not fetch orderbook for slippage estimation'
            }

        # Get market data for volume
        market = self.client.get_market(request.market_id)
        market_volume_24h = market.get('volume_24h', 0) if market else 0

        # Estimate slippage using the correct method and parameters
        slippage_result = self.slippage_estimator.estimate_slippage(
            order_side='BUY',
            order_size=request.position_size,
            orderbook=orderbook,
            quoted_price=request.entry_price,
            market_volume_24h=market_volume_24h
        )

        # Check if trade is acceptable
        if not slippage_result.is_acceptable:
            logger.warning(
                f"⚠️ Trade rejected - Slippage | "
                f"{request.outcome} @ ${request.entry_price:.3f} | "
                f"Slippage: {slippage_result.slippage_bps:.0f} bps | "
                f"Reason: {slippage_result.rejection_reason} | "
                f"Market: {request.question[:50]}"
            )
            return {
                'valid': False,
                'reason': slippage_result.rejection_reason,
                'slippage_bps': slippage_result.slippage_bps
            }

        # Log slippage info
        logger.info(
            f"Slippage estimate: {slippage_result.slippage_bps:.0f} bps "
            f"(${slippage_result.slippage_dollars:.2f}) | "
            f"Levels: {slippage_result.levels_consumed}"
        )

        # Log warnings if any
        for warning in slippage_result.warnings:
            logger.warning(f"⚠️ Slippage warning: {warning}")

        return {
            'valid': True,
            'reason': 'Slippage within acceptable range',
            'slippage_bps': slippage_result.slippage_bps,
            'recommended_price': slippage_result.expected_execution_price
        }

    def _execute_position(self, request: TradeRequest) -> Dict:
        """
        Execute position (paper trading or live).

        Args:
            request: TradeRequest

        Returns:
            Dict with 'success' (bool) and 'reason' (str)
        """
        if self.paper_trading:
            logger.info(
                f"\n  💰 [PAPER TRADE] BUY {request.outcome} ${request.position_size:.2f}"
            )
            logger.info(f"     Market: {request.question[:50]}")
            logger.info(f"     {request.outcome} Price: ${request.entry_price:.3f}")
            if request.edge:
                logger.info(f"     Edge: {request.edge:+.2%}")
            if request.confidence:
                logger.info(f"     Confidence: {request.confidence:.2%}")

        # Build metadata for position
        metadata = self._build_metadata(request)

        # Save position (using V2 API with analytics fields)
        try:
            self.position_manager.save_position(
                market_id=request.market_id,
                token_id=request.token_id,
                outcome=request.outcome,  # V2 uses 'outcome' instead of 'side'
                entry_time=datetime.now(timezone.utc),
                entry_price=request.entry_price,
                size=request.position_size,
                edge=request.edge,  # V2: track expected edge
                confidence=request.confidence,  # V2: track confidence
                signal_reason=request.signal_reason,  # V2: track strategy
                stop_loss_pct=request.stop_loss_pct,  # RISK-001: Always set stop-loss
                take_profit_pct=request.take_profit_pct,  # RISK-001: Always set take-profit
                metadata=metadata
            )
            logger.info("✓ Position tracked and persisted (SL: {}%, TP: {}%)".format(
                request.stop_loss_pct if request.stop_loss_pct else 'N/A',
                request.take_profit_pct if request.take_profit_pct else 'N/A'
            ))

            return {'success': True, 'reason': 'Position opened successfully'}

        except Exception as e:
            logger.error(f"Failed to save position: {e}", exc_info=True)
            return {'success': False, 'reason': f'Failed to save position: {e}'}

    def _build_metadata(self, request: TradeRequest) -> Dict:
        """
        Build metadata dict for position tracking.

        Args:
            request: TradeRequest

        Returns:
            Dict with metadata fields
        """
        metadata = {
            'question': request.question,
            'outcome': request.outcome,
            'entry_price': request.entry_price,
            'position_size': request.position_size,
        }

        # Add optional fields if present
        if request.asset:
            metadata['asset'] = request.asset
        if request.strike_price:
            metadata['strike_price'] = request.strike_price
        if request.expiry_date:
            metadata['expiry_date'] = request.expiry_date
        if request.edge:
            metadata['edge'] = request.edge
        if request.confidence:
            metadata['confidence'] = request.confidence
        if request.signal_reason:
            metadata['signal_reason'] = request.signal_reason

        # Merge additional metadata if provided
        if request.metadata:
            metadata.update(request.metadata)

        return metadata
