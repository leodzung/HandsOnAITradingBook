"""
Backtesting Framework
Tests trading strategies on historical data.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from collections import defaultdict


class Trade:
    """Represents a single trade."""

    def __init__(self, market_id: str, side: str, entry_price: float,
                 size: float, entry_time: datetime):
        self.market_id = market_id
        self.side = side  # 'BUY' or 'SELL'
        self.entry_price = entry_price
        self.size = size
        self.entry_time = entry_time
        self.exit_price = None
        self.exit_time = None
        self.pnl = 0.0
        self.is_open = True

    def close(self, exit_price: float, exit_time: datetime):
        """Close the trade."""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.is_open = False

        # Calculate PnL
        if self.side == 'BUY':
            self.pnl = (exit_price - self.entry_price) * self.size
        else:  # SELL
            self.pnl = (self.entry_price - exit_price) * self.size

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'market_id': self.market_id,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'size': self.size,
            'entry_time': self.entry_time,
            'exit_time': self.exit_time,
            'pnl': self.pnl,
            'return_pct': (self.pnl / (self.entry_price * self.size) * 100)
                          if self.entry_price * self.size > 0 else 0,
            'duration_hours': (self.exit_time - self.entry_time).total_seconds() / 3600
                             if self.exit_time else None
        }


class Portfolio:
    """Manages portfolio state during backtesting."""

    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # market_id -> Trade
        self.closed_trades = []
        self.equity_curve = []
        self.timestamps = []

    def get_equity(self) -> float:
        """Calculate total equity."""
        position_value = sum(
            trade.size * trade.entry_price
            for trade in self.positions.values()
        )
        return self.cash + position_value

    def open_position(self, trade: Trade) -> bool:
        """
        Open a new position.

        Args:
            trade: Trade object

        Returns:
            True if successful
        """
        cost = trade.size * trade.entry_price

        if cost > self.cash:
            return False

        self.cash -= cost
        self.positions[trade.market_id] = trade
        return True

    def close_position(self, market_id: str, exit_price: float,
                      exit_time: datetime) -> Optional[Trade]:
        """
        Close a position.

        Args:
            market_id: Market ID
            exit_price: Exit price
            exit_time: Exit time

        Returns:
            Closed trade or None
        """
        if market_id not in self.positions:
            return None

        trade = self.positions.pop(market_id)
        trade.close(exit_price, exit_time)

        # Add proceeds to cash
        proceeds = trade.size * exit_price
        self.cash += proceeds

        self.closed_trades.append(trade)
        return trade

    def record_equity(self, timestamp: datetime):
        """Record equity at timestamp."""
        equity = self.get_equity()
        self.equity_curve.append(equity)
        self.timestamps.append(timestamp)

    def get_statistics(self) -> Dict:
        """Calculate portfolio statistics."""
        if not self.closed_trades:
            return {}

        trades_df = pd.DataFrame([t.to_dict() for t in self.closed_trades])

        total_pnl = trades_df['pnl'].sum()
        total_return = (self.get_equity() - self.initial_capital) / self.initial_capital * 100

        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] < 0]

        win_rate = len(winning_trades) / len(trades_df) * 100 if len(trades_df) > 0 else 0

        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0

        # Calculate Sharpe ratio
        if len(self.equity_curve) > 1:
            returns = pd.Series(self.equity_curve).pct_change().dropna()
            sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe = 0

        # Maximum drawdown
        equity_series = pd.Series(self.equity_curve)
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax * 100
        max_drawdown = drawdown.min()

        return {
            'total_trades': len(trades_df),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_return_pct': total_return,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown,
            'final_equity': self.get_equity()
        }


class Backtester:
    """Main backtesting engine."""

    def __init__(self, initial_capital: float = 10000,
                 position_size: float = 100,
                 hold_time_hours: int = 24,
                 max_positions: int = 10):
        """
        Initialize backtester.

        Args:
            initial_capital: Starting capital
            position_size: Size of each position in $
            hold_time_hours: How long to hold positions
            max_positions: Maximum concurrent positions
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.hold_time_hours = hold_time_hours
        self.max_positions = max_positions
        self.portfolio = Portfolio(initial_capital)

    def run_backtest(self, signals_df: pd.DataFrame,
                    price_data: Dict[str, pd.DataFrame]) -> Dict:
        """
        Run backtest on historical signals.

        Args:
            signals_df: DataFrame with columns ['timestamp', 'market_id', 'action',
                       'confidence', 'entry_price']
            price_data: Dict mapping market_id to price DataFrame

        Returns:
            Dictionary with backtest results
        """
        # Sort signals by timestamp
        signals_df = signals_df.sort_values('timestamp').reset_index(drop=True)

        for idx, signal in signals_df.iterrows():
            timestamp = pd.to_datetime(signal['timestamp'])
            market_id = signal['market_id']
            action = signal['action']
            entry_price = signal.get('entry_price', signal.get('price', 0.5))

            # Record equity
            self.portfolio.record_equity(timestamp)

            # Skip if no action
            if action == 'HOLD':
                continue

            # Skip if max positions reached
            if len(self.portfolio.positions) >= self.max_positions:
                continue

            # Skip if already have position in this market
            if market_id in self.portfolio.positions:
                continue

            # Open position
            if action in ['BUY', 'SELL']:
                trade = Trade(
                    market_id=market_id,
                    side=action,
                    entry_price=entry_price,
                    size=self.position_size / entry_price,
                    entry_time=timestamp
                )

                self.portfolio.open_position(trade)

            # Check for positions to close
            positions_to_close = []
            for market_id, trade in self.portfolio.positions.items():
                # Close if held long enough
                time_held = (timestamp - trade.entry_time).total_seconds() / 3600
                if time_held >= self.hold_time_hours:
                    positions_to_close.append(market_id)

            # Close positions
            for market_id in positions_to_close:
                if market_id in price_data:
                    prices = price_data[market_id]
                    exit_price = self._get_price_at_time(prices, timestamp)
                    if exit_price is not None:
                        self.portfolio.close_position(market_id, exit_price, timestamp)

        # Close any remaining positions at final price
        final_timestamp = signals_df['timestamp'].max()
        for market_id in list(self.portfolio.positions.keys()):
            if market_id in price_data:
                prices = price_data[market_id]
                exit_price = self._get_price_at_time(prices, final_timestamp)
                if exit_price is not None:
                    self.portfolio.close_position(market_id, exit_price, final_timestamp)

        # Calculate statistics
        stats = self.portfolio.get_statistics()

        return stats

    def _get_price_at_time(self, prices_df: pd.DataFrame,
                          timestamp: datetime) -> Optional[float]:
        """Get price at specific timestamp."""
        if len(prices_df) == 0:
            return None

        # Find closest price
        prices_df['timestamp'] = pd.to_datetime(prices_df['timestamp'])
        prices_df = prices_df.sort_values('timestamp')

        # Get price at or before timestamp
        valid_prices = prices_df[prices_df['timestamp'] <= timestamp]

        if len(valid_prices) == 0:
            return None

        return valid_prices.iloc[-1]['price']

    def plot_results(self, save_path: Optional[str] = None):
        """Plot backtest results."""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # Equity curve
        if self.portfolio.equity_curve:
            axes[0, 0].plot(self.portfolio.timestamps, self.portfolio.equity_curve)
            axes[0, 0].axhline(y=self.initial_capital, color='r', linestyle='--',
                             label='Initial Capital')
            axes[0, 0].set_title('Equity Curve')
            axes[0, 0].set_xlabel('Time')
            axes[0, 0].set_ylabel('Equity ($)')
            axes[0, 0].legend()
            axes[0, 0].grid(True)

        # PnL distribution
        if self.portfolio.closed_trades:
            pnls = [t.pnl for t in self.portfolio.closed_trades]
            axes[0, 1].hist(pnls, bins=30, edgecolor='black')
            axes[0, 1].axvline(x=0, color='r', linestyle='--')
            axes[0, 1].set_title('PnL Distribution')
            axes[0, 1].set_xlabel('PnL ($)')
            axes[0, 1].set_ylabel('Frequency')
            axes[0, 1].grid(True)

        # Cumulative returns
        if len(self.portfolio.equity_curve) > 0:
            returns = pd.Series(self.portfolio.equity_curve).pct_change().fillna(0)
            cum_returns = (1 + returns).cumprod() - 1
            axes[1, 0].plot(self.portfolio.timestamps, cum_returns * 100)
            axes[1, 0].set_title('Cumulative Returns')
            axes[1, 0].set_xlabel('Time')
            axes[1, 0].set_ylabel('Return (%)')
            axes[1, 0].grid(True)

        # Win/Loss by side
        if self.portfolio.closed_trades:
            trades_df = pd.DataFrame([t.to_dict() for t in self.portfolio.closed_trades])
            win_loss = trades_df.groupby('side')['pnl'].apply(
                lambda x: [len(x[x > 0]), len(x[x < 0])]
            )

            sides = list(win_loss.index)
            wins = [wl[0] for wl in win_loss.values]
            losses = [wl[1] for wl in win_loss.values]

            x = np.arange(len(sides))
            width = 0.35

            axes[1, 1].bar(x - width/2, wins, width, label='Wins', color='green')
            axes[1, 1].bar(x + width/2, losses, width, label='Losses', color='red')
            axes[1, 1].set_title('Wins vs Losses by Side')
            axes[1, 1].set_xlabel('Trade Side')
            axes[1, 1].set_ylabel('Count')
            axes[1, 1].set_xticks(x)
            axes[1, 1].set_xticklabels(sides)
            axes[1, 1].legend()
            axes[1, 1].grid(True)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()


def create_sample_signals(n_signals: int = 100,
                         n_markets: int = 10) -> pd.DataFrame:
    """Create sample signals for testing."""
    np.random.seed(42)

    signals = []
    start_time = datetime.now() - timedelta(days=30)

    for i in range(n_signals):
        signal = {
            'timestamp': start_time + timedelta(hours=i*2),
            'market_id': f'market_{np.random.randint(0, n_markets)}',
            'action': np.random.choice(['BUY', 'SELL', 'HOLD'], p=[0.3, 0.3, 0.4]),
            'confidence': np.random.uniform(0.5, 0.95),
            'entry_price': np.random.uniform(0.3, 0.7)
        }
        signals.append(signal)

    return pd.DataFrame(signals)


def create_sample_prices(market_ids: List[str],
                        start_time: datetime,
                        end_time: datetime) -> Dict[str, pd.DataFrame]:
    """Create sample price data for testing."""
    np.random.seed(42)

    price_data = {}
    timestamps = pd.date_range(start_time, end_time, freq='1H')

    for market_id in market_ids:
        prices = []
        current_price = np.random.uniform(0.4, 0.6)

        for ts in timestamps:
            # Random walk
            current_price += np.random.normal(0, 0.01)
            current_price = np.clip(current_price, 0.01, 0.99)

            prices.append({
                'timestamp': ts,
                'price': current_price,
                'size': np.random.uniform(10, 100)
            })

        price_data[market_id] = pd.DataFrame(prices)

    return price_data
