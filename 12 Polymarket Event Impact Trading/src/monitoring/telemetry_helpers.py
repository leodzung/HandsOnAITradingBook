#!/usr/bin/env python3
"""
Telemetry Helper Functions

Convenience functions for trading bots to record telemetry data
without needing to manage TradeTelemetry instances directly.

Usage in trading bots:
    from monitoring.telemetry_helpers import (
        record_trade_attempt,
        record_position_opened,
        record_circuit_breaker_trip,
        record_sl_tp_exit
    )

Created: 2026-02-24 (Phase 3: Telemetry Integration)
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_telemetry():
    """Get telemetry instance with lazy import."""
    try:
        from monitoring.telemetry import get_telemetry
        return get_telemetry()
    except ImportError:
        logger.warning("Telemetry system not available")
        return None


def record_trade_attempt(market_id: str,
                         outcome: str,
                         decision: str,
                         features: Optional[Dict] = None,
                         reason: Optional[str] = None,
                         source: str = 'unknown'):
    """
    Record a trade decision (whether executed or rejected).

    Args:
        market_id: Market condition ID
        outcome: YES or NO
        decision: 'executed', 'rejected', or 'skipped'
        features: Optional feature dict
        reason: Optional reason for decision
        source: Bot name (e.g., 'event_trader')
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_event(
        'trade_attempt',
        event_data={
            'market_id': market_id,
            'outcome': outcome,
            'decision': decision,
            'reason': reason,
            'features': features
        },
        severity='info',
        source=source
    )


def record_position_opened(market_id: str,
                            outcome: str,
                            size: float,
                            entry_price: float,
                            has_sl_tp: bool = True,
                            source: str = 'unknown'):
    """
    Record a position being opened.

    Args:
        market_id: Market condition ID
        outcome: YES or NO
        size: Position size ($)
        entry_price: Entry price
        has_sl_tp: Whether SL/TP are set
        source: Bot name
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_event(
        'position_opened',
        event_data={
            'market_id': market_id,
            'outcome': outcome,
            'size': size,
            'entry_price': entry_price,
            'has_sl_tp': has_sl_tp
        },
        severity='info',
        source=source
    )

    # Also update metric for positions without SL/TP
    if not has_sl_tp:
        # Increment counter
        metrics = telemetry.get_latest_metrics([f'positions_without_sl_tp_{source}'])
        current = metrics.get(f'positions_without_sl_tp_{source}', 0)
        telemetry.record_metric(f'positions_without_sl_tp_{source}', current + 1, source=source)


def record_circuit_breaker_trip(consecutive_losses: int,
                                 cooldown_hours: float,
                                 source: str = 'unknown'):
    """
    Record circuit breaker activation.

    Args:
        consecutive_losses: Number of consecutive losses
        cooldown_hours: Hours until auto-resume
        source: Bot name
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_event(
        'circuit_breaker_trip',
        event_data={
            'consecutive_losses': consecutive_losses,
            'cooldown_hours': cooldown_hours,
            'timestamp': datetime.now(timezone.utc).isoformat()
        },
        severity='warning',
        source=source
    )

    # Increment trip counter
    metrics = telemetry.get_latest_metrics(['circuit_breaker_trips'])
    current = metrics.get('circuit_breaker_trips', 0)
    telemetry.record_metric('circuit_breaker_trips', current + 1, source=source)


def record_sl_tp_exit(market_id: str,
                      exit_reason: str,
                      entry_price: float,
                      exit_price: float,
                      pnl_pct: float,
                      source: str = 'unknown'):
    """
    Record a stop-loss or take-profit exit.

    Args:
        market_id: Market condition ID
        exit_reason: 'stop_loss' or 'take_profit'
        entry_price: Entry price
        exit_price: Exit price
        pnl_pct: P&L percentage
        source: Bot name
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_event(
        exit_reason,
        event_data={
            'market_id': market_id,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct
        },
        severity='info',
        source=source
    )


def record_slippage_rejection(market_id: str,
                               estimated_slippage: float,
                               max_allowed: float,
                               source: str = 'unknown'):
    """
    Record a trade rejected due to excessive slippage.

    Args:
        market_id: Market condition ID
        estimated_slippage: Estimated slippage (bps)
        max_allowed: Maximum allowed slippage (bps)
        source: Bot name
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_event(
        'slippage_rejection',
        event_data={
            'market_id': market_id,
            'estimated_slippage_bps': estimated_slippage,
            'max_allowed_bps': max_allowed
        },
        severity='info',
        source=source
    )

    # Update rejection rate metric
    # This would ideally track rejections vs total attempts
    metrics = telemetry.get_latest_metrics([f'slippage_rejections_{source}'])
    current = metrics.get(f'slippage_rejections_{source}', 0)
    telemetry.record_metric(f'slippage_rejections_{source}', current + 1, source=source)


def record_websocket_fallback(reason: str, source: str = 'unknown'):
    """
    Record WebSocket falling back to REST API.

    Args:
        reason: Reason for fallback (e.g., 'connection_failed')
        source: Component name
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_event(
        'websocket_fallback',
        event_data={'reason': reason},
        severity='warning',
        source=source
    )

    # Update fallback rate
    # This would ideally be (fallbacks / total_requests)
    metrics = telemetry.get_latest_metrics(['websocket_fallbacks'])
    current = metrics.get('websocket_fallbacks', 0)
    telemetry.record_metric('websocket_fallbacks', current + 1, source=source)


def record_feature_drift_alert(drift_type: str,
                                metric_value: float,
                                threshold: float,
                                source: str = 'ml_system'):
    """
    Record feature drift detection alert.

    Args:
        drift_type: Type of drift (e.g., 'kendall_tau_rank_stability')
        metric_value: Current metric value
        threshold: Threshold that was violated
        source: Source component
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_event(
        'feature_drift_detected',
        event_data={
            'drift_type': drift_type,
            'value': metric_value,
            'threshold': threshold
        },
        severity='warning',
        source=source
    )

    # Record the actual drift metric
    telemetry.record_metric(drift_type, metric_value, source=source)


def update_open_positions_count(bot_name: str, count: int):
    """
    Update the count of currently open positions for a bot.

    Args:
        bot_name: Bot identifier (e.g., 'event_trader')
        count: Number of open positions
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_metric(f'open_positions_{bot_name}', count, source=bot_name)


def update_balance(bot_name: str, balance: float):
    """
    Update bot's current balance.

    Args:
        bot_name: Bot identifier
        balance: Current balance ($)
    """
    telemetry = get_telemetry()
    if not telemetry:
        return

    telemetry.record_metric(f'balance_{bot_name}', balance, source=bot_name)


# Example usage in a trading bot:
"""
from monitoring.telemetry_helpers import (
    record_trade_attempt,
    record_position_opened,
    record_circuit_breaker_trip,
    update_open_positions_count
)

class MyTradingBot:
    def __init__(self):
        self.bot_name = 'my_trader'

    def execute_trade(self, market_id, outcome, size):
        # ... trading logic ...

        # Record the trade
        record_position_opened(
            market_id=market_id,
            outcome=outcome,
            size=size,
            entry_price=entry_price,
            has_sl_tp=True,
            source=self.bot_name
        )

        # Update position count
        positions = self.position_manager.get_open_positions()
        update_open_positions_count(self.bot_name, len(positions))

    def check_circuit_breaker(self):
        if self.consecutive_losses >= 3:
            record_circuit_breaker_trip(
                consecutive_losses=self.consecutive_losses,
                cooldown_hours=4.0,
                source=self.bot_name
            )
"""
