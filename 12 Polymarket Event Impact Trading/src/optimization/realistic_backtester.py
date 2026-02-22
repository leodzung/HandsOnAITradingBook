"""
Realistic backtester with slippage, fees, and capital constraints.

Simulates trade execution accounting for:
- Entry/exit slippage via orderbook depth
- Trading fees (1% per side)
- Capital constraints (position sizing)
- Dynamic TP/SL thresholds
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from src.core.slippage_estimator import SlippageEstimator

logger = logging.getLogger(__name__)


@dataclass
class TradeSimulation:
    """Result of simulating a single trade"""
    market_id: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    gross_pnl: float
    net_pnl: float
    entry_slippage: float
    exit_slippage: float
    entry_fee: float
    exit_fee: float
    position_size: float
    outcome: str
    actual_outcome: float
    tp_threshold: float
    sl_threshold: float
    exit_reason: str  # 'TP', 'SL', 'EXPIRY', 'CIRCUIT_BREAKER'
    rejected: bool = False
    rejection_reason: Optional[str] = None


class RealisticBacktester:
    """
    Backtester with realistic execution costs and constraints.

    Simulates actual trading conditions including:
    - Entry slippage estimation via SlippageEstimator
    - Exit slippage estimation
    - 1% taker fee on entry and exit (2% total)
    - Capital constraints (available balance)
    - Position sizing based on parameters
    - Dynamic TP/SL based on time-to-expiry
    """

    def __init__(
        self,
        initial_balance: float = 1000.0,
        fee_pct: float = 0.01,  # 1% per side
        min_balance_reserve: float = 50.0,  # Keep $50 in reserve
    ):
        """
        Initialize backtester.

        Args:
            initial_balance: Starting capital
            fee_pct: Trading fee percentage (per side)
            min_balance_reserve: Minimum balance to maintain
        """
        self.initial_balance = initial_balance
        self.fee_pct = fee_pct
        self.min_balance_reserve = min_balance_reserve

        # State
        self.current_balance = initial_balance
        self.trades: List[TradeSimulation] = []

        logger.info(f"RealisticBacktester initialized: balance=${initial_balance}, "
                   f"fee={fee_pct:.2%}, reserve=${min_balance_reserve}")

    def reset(self):
        """Reset backtester to initial state."""
        self.current_balance = self.initial_balance
        self.trades = []

    def backtest(
        self,
        data: pd.DataFrame,
        params: Dict,
        bucket: str,
        ml_predictions: Optional[pd.Series] = None,
        ml_confidence: Optional[pd.Series] = None,
    ) -> List[TradeSimulation]:
        """
        Run backtest on dataset with given parameters.

        Args:
            data: DataFrame with columns:
                - id, condition_id, block_timestamp, trade_price
                - question, end_date, outcome_prices, outcome, label
                - Plus any feature columns needed for filtering
            params: Parameter dictionary with:
                - take_profit_pct, stop_loss_pct
                - max_slippage_bps, max_slippage_dollars
                - max_position_size, min_position_size
                - max_spread_pct, min_volume
                - min_confidence
            bucket: Time bucket name ('ultra_short', 'short', 'medium')
            ml_predictions: Optional ML model predictions (0/1)
            ml_confidence: Optional ML confidence scores (0-1)

        Returns:
            List of TradeSimulation objects
        """
        self.reset()

        # Sort by timestamp
        data = data.sort_values('block_timestamp').copy()

        # Add ML predictions if available
        if ml_predictions is not None:
            data['ml_prediction'] = ml_predictions
        if ml_confidence is not None:
            data['ml_confidence'] = ml_confidence

        logger.info(f"Starting backtest: {len(data)} samples, bucket={bucket}, "
                   f"balance=${self.current_balance}")

        # Simulate each potential trade
        for idx, row in data.iterrows():
            trade = self._simulate_trade(row, params, bucket)
            if trade:
                self.trades.append(trade)

                # Update balance
                if not trade.rejected:
                    self.current_balance += trade.net_pnl

        logger.info(f"Backtest complete: {len(self.trades)} trades, "
                   f"final_balance=${self.current_balance:.2f}")

        return self.trades

    def _simulate_trade(
        self,
        row: pd.Series,
        params: Dict,
        bucket: str
    ) -> Optional[TradeSimulation]:
        """
        Simulate a single trade with realistic execution.

        Args:
            row: Data row with market info
            params: Trading parameters
            bucket: Time bucket

        Returns:
            TradeSimulation object or None if trade not taken
        """
        # Extract market data
        market_id = row.get('condition_id', row.get('id', 'unknown'))
        entry_time = pd.to_datetime(row['block_timestamp'])
        end_time = pd.to_datetime(row['end_date'])
        entry_price = float(row['trade_price'])
        outcome = row['outcome']
        actual_outcome = float(row['label'])

        # Check time-to-expiry matches bucket
        hours_to_expiry = (end_time - entry_time).total_seconds() / 3600
        if not self._in_bucket(hours_to_expiry, bucket):
            return None

        # 1. Check entry filters
        rejection_reason = self._check_entry_filters(row, params)
        if rejection_reason:
            return TradeSimulation(
                market_id=market_id,
                entry_time=entry_time,
                exit_time=end_time,
                entry_price=entry_price,
                exit_price=entry_price,
                gross_pnl=0.0,
                net_pnl=0.0,
                entry_slippage=0.0,
                exit_slippage=0.0,
                entry_fee=0.0,
                exit_fee=0.0,
                position_size=0.0,
                outcome=outcome,
                actual_outcome=actual_outcome,
                tp_threshold=0.0,
                sl_threshold=0.0,
                exit_reason='REJECTED',
                rejected=True,
                rejection_reason=rejection_reason,
            )

        # 2. Calculate position size
        max_size = params['max_position_size']
        available = self.current_balance - self.min_balance_reserve
        position_size = min(max_size, available)

        if position_size < params.get('min_position_size', 10):
            return TradeSimulation(
                market_id=market_id,
                entry_time=entry_time,
                exit_time=end_time,
                entry_price=entry_price,
                exit_price=entry_price,
                gross_pnl=0.0,
                net_pnl=0.0,
                entry_slippage=0.0,
                exit_slippage=0.0,
                entry_fee=0.0,
                exit_fee=0.0,
                position_size=0.0,
                outcome=outcome,
                actual_outcome=actual_outcome,
                tp_threshold=0.0,
                sl_threshold=0.0,
                exit_reason='REJECTED',
                rejected=True,
                rejection_reason='Insufficient capital',
            )

        # 3. Estimate entry slippage
        entry_slippage_est = self._estimate_entry_slippage(
            position_size, entry_price, row, params
        )

        # Check if slippage exceeds limits
        if entry_slippage_est['slippage_bps'] > params['max_slippage_bps']:
            return TradeSimulation(
                market_id=market_id,
                entry_time=entry_time,
                exit_time=end_time,
                entry_price=entry_price,
                exit_price=entry_price,
                gross_pnl=0.0,
                net_pnl=0.0,
                entry_slippage=0.0,
                exit_slippage=0.0,
                entry_fee=0.0,
                exit_fee=0.0,
                position_size=0.0,
                outcome=outcome,
                actual_outcome=actual_outcome,
                tp_threshold=0.0,
                sl_threshold=0.0,
                exit_reason='REJECTED',
                rejected=True,
                rejection_reason=f"Entry slippage {entry_slippage_est['slippage_bps']:.0f}bps exceeds limit",
            )

        # 4. Calculate effective entry price after slippage
        # Cap at 0.99 since prediction market shares can't cost more than $1.00
        # Don't reject - just cap the price
        effective_entry_price = min(
            entry_price + entry_slippage_est['slippage_dollars'] / position_size,
            0.99
        )

        # 5. Calculate entry fee (1% of position size)
        entry_fee = position_size * self.fee_pct

        # 6. Determine TP/SL thresholds
        tp_pct = params['take_profit_pct'] / 100.0
        sl_pct = params['stop_loss_pct'] / 100.0

        # 7. Simulate holding period and exit
        # For prediction markets: winner pays $1.00, loser pays $0.00
        # Label semantics: 1.0 = profitable trade, -1.0 = losing trade
        # We simulate early exit if TP/SL would be hit before resolution

        if actual_outcome == 1.0:  # Profitable trade
            # Trade will profit - take profit or hold to resolution
            # TP price = entry_price + (TP% of entry)
            tp_price = min(effective_entry_price + (effective_entry_price * tp_pct), 0.99)
            # If TP < 1.0, we might exit early at TP
            # Otherwise hold to resolution and get paid
            if tp_price < 0.99:
                exit_price = tp_price
                exit_reason = 'TP'
            else:
                exit_price = 0.99  # Effectively 1.0 at resolution (capped for fees)
                exit_reason = 'RESOLUTION'
        elif actual_outcome == -1.0:  # Losing trade
            # Trade will lose - hit stop loss
            sl_price = max(effective_entry_price - (effective_entry_price * sl_pct), 0.01)
            exit_price = sl_price
            exit_reason = 'SL'
        else:
            # Unknown outcome (shouldn't happen with labeled data)
            logger.warning(f"Unknown outcome: {actual_outcome}")
            exit_price = effective_entry_price
            exit_reason = 'UNKNOWN'

        # 8. Estimate exit slippage
        exit_slippage_est = self._estimate_exit_slippage(
            position_size, exit_price, row, params
        )

        # Check if exit slippage exceeds limits (same as entry check)
        if exit_slippage_est['slippage_bps'] > params['max_slippage_bps']:
            # Exit slippage too high - use entry slippage limit as proxy
            # This prevents trades where we can't exit profitably
            return TradeSimulation(
                market_id=market_id,
                entry_time=entry_time,
                exit_time=end_time,
                entry_price=entry_price,
                exit_price=entry_price,
                gross_pnl=0.0,
                net_pnl=0.0,
                entry_slippage=0.0,
                exit_slippage=0.0,
                entry_fee=0.0,
                exit_fee=0.0,
                position_size=0.0,
                outcome=outcome,
                actual_outcome=actual_outcome,
                tp_threshold=0.0,
                sl_threshold=0.0,
                exit_reason='REJECTED',
                rejected=True,
                rejection_reason=f"Exit slippage {exit_slippage_est['slippage_bps']:.0f}bps exceeds limit",
            )

        # Cap exit price at 0.01 (minimum possible in prediction markets)
        effective_exit_price = max(
            exit_price - exit_slippage_est['slippage_dollars'] / position_size,
            0.01
        )

        # 9. Calculate exit fee
        exit_fee = position_size * self.fee_pct

        # 10. Calculate P&L
        gross_pnl = position_size * (effective_exit_price - effective_entry_price)
        net_pnl = gross_pnl - entry_fee - exit_fee

        # Create trade simulation result
        return TradeSimulation(
            market_id=market_id,
            entry_time=entry_time,
            exit_time=end_time,
            entry_price=effective_entry_price,
            exit_price=effective_exit_price,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            entry_slippage=entry_slippage_est['slippage_dollars'],
            exit_slippage=exit_slippage_est['slippage_dollars'],
            entry_fee=entry_fee,
            exit_fee=exit_fee,
            position_size=position_size,
            outcome=outcome,
            actual_outcome=actual_outcome,
            tp_threshold=tp_pct * 100,
            sl_threshold=sl_pct * 100,
            exit_reason=exit_reason,
            rejected=False,
        )

    def _check_entry_filters(self, row: pd.Series, params: Dict) -> Optional[str]:
        """
        Check if trade passes entry filters.

        Returns:
            Rejection reason string, or None if trade is acceptable
        """
        # Check ML confidence if predictions available
        if 'ml_confidence' in row and row['ml_confidence'] < params['min_confidence']:
            return f"ML confidence {row['ml_confidence']:.2f} < threshold {params['min_confidence']:.2f}"

        # Check volume filter (if available)
        if 'volume_24h' in row and row['volume_24h'] < params['min_volume']:
            return f"Volume ${row['volume_24h']:.0f} < threshold ${params['min_volume']}"

        # Check spread filter (if available)
        if 'spread_pct' in row and row['spread_pct'] > params['max_spread_pct']:
            return f"Spread {row['spread_pct']:.2f}% > threshold {params['max_spread_pct']:.2f}%"

        # Check price limits (very relaxed for prediction markets)
        # Prediction markets often have prices near 0 or 1 as events become certain/unlikely
        entry_price = float(row['trade_price'])
        if entry_price <= 0.001 or entry_price >= 0.999:
            return f"Price {entry_price:.3f} outside (0.001, 0.999) range"

        return None

    def _in_bucket(self, hours_to_expiry: float, bucket: str) -> bool:
        """Check if trade belongs to specified bucket."""
        if bucket == 'ultra_short':
            return 0 <= hours_to_expiry <= 24
        elif bucket == 'short':
            return 24 < hours_to_expiry <= 72
        elif bucket == 'medium':
            return 72 < hours_to_expiry <= 168
        else:
            return False

    def _estimate_entry_slippage(
        self,
        position_size: float,
        entry_price: float,
        row: pd.Series,
        params: Dict
    ) -> Dict:
        """
        Estimate entry slippage using EMPIRICAL estimates from actual trade data.

        Based on analysis of 500K real Polymarket trades (analyze_actual_trade_performance_v2.py):
        - P75 price change: 10 bps (typical slippage)
        - P90 price change: 20 bps
        - P95 price change: 37 bps

        IMPORTANT: Previous approach used spread/2 with synthetic defaults (5% spread)
        which created 2500 bps slippage. Real slippage is 10-37 bps (100x lower!).

        Returns:
            Dict with 'slippage_dollars' and 'slippage_bps'
        """
        # Empirical base slippage from real trade data (P75 = 10 bps)
        base_slippage_bps = 10.0

        # Additional slippage from market impact (for large positions)
        # Use volume if available, otherwise assume high liquidity
        volume_24h = row.get('volume_24h', 10000)  # Assume $10K daily volume if unknown
        impact_factor = position_size / max(volume_24h, 1)
        impact_slippage_bps = impact_factor * 500  # 500 bps per 1.0 impact ratio

        # Total slippage in basis points
        total_slippage_bps = base_slippage_bps + impact_slippage_bps

        # Convert to percentage and dollars
        total_slippage_pct = total_slippage_bps / 10000
        slippage_dollars = position_size * total_slippage_pct

        return {
            'slippage_dollars': slippage_dollars,
            'slippage_bps': total_slippage_bps,
        }

    def _estimate_exit_slippage(
        self,
        position_size: float,
        exit_price: float,
        row: pd.Series,
        params: Dict
    ) -> Dict:
        """
        Estimate exit slippage using EMPIRICAL estimates from actual trade data.

        Based on analysis of 500K real Polymarket trades:
        - P90 price change: 20 bps (exit slippage, slightly worse than entry)

        Exit slippage is typically higher than entry due to worse execution
        when closing positions (especially losers).

        Returns:
            Dict with 'slippage_dollars' and 'slippage_bps'
        """
        # Empirical base slippage for exits (P90 = 20 bps)
        base_slippage_bps = 20.0

        # Additional slippage from market impact
        volume_24h = row.get('volume_24h', 10000)
        impact_factor = position_size / max(volume_24h, 1)
        impact_slippage_bps = impact_factor * 500

        # Total slippage
        total_slippage_bps = base_slippage_bps + impact_slippage_bps
        total_slippage_pct = total_slippage_bps / 10000
        slippage_dollars = position_size * total_slippage_pct

        return {
            'slippage_dollars': slippage_dollars,
            'slippage_bps': total_slippage_bps,
        }

    def get_trades_dataframe(self) -> pd.DataFrame:
        """Convert trades list to DataFrame for analysis."""
        if not self.trades:
            return pd.DataFrame()

        return pd.DataFrame([asdict(t) for t in self.trades])

    def get_performance_summary(self) -> Dict:
        """
        Calculate performance summary statistics.

        Returns:
            Dict with performance metrics
        """
        if not self.trades:
            return {
                'total_trades': 0,
                'final_balance': self.initial_balance,
                'total_return': 0.0,
                'total_pnl': 0.0,
            }

        df = self.get_trades_dataframe()

        # Filter to non-rejected trades
        executed = df[~df['rejected']]

        if len(executed) == 0:
            return {
                'total_trades': 0,
                'rejected_trades': len(df),
                'final_balance': self.initial_balance,
                'total_return': 0.0,
                'total_pnl': 0.0,
            }

        # Calculate metrics
        total_pnl = executed['net_pnl'].sum()
        final_balance = self.initial_balance + total_pnl
        total_return = total_pnl / self.initial_balance

        wins = executed[executed['net_pnl'] > 0]
        losses = executed[executed['net_pnl'] < 0]

        return {
            'total_trades': len(executed),
            'rejected_trades': len(df[df['rejected']]),
            'final_balance': final_balance,
            'total_return': total_return,
            'total_pnl': total_pnl,
            'win_count': len(wins),
            'loss_count': len(losses),
            'win_rate': len(wins) / len(executed) if len(executed) > 0 else 0,
            'avg_win': wins['net_pnl'].mean() if len(wins) > 0 else 0,
            'avg_loss': losses['net_pnl'].mean() if len(losses) > 0 else 0,
            'total_fees': executed['entry_fee'].sum() + executed['exit_fee'].sum(),
            'total_slippage': executed['entry_slippage'].sum() + executed['exit_slippage'].sum(),
        }
