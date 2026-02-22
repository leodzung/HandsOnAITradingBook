#!/usr/bin/env python3
"""
Backtesting Framework for Momentum Agent

This module provides a backtesting engine for the momentum strategy,
allowing historical performance analysis without LLM calls.

Usage:
    python backtest.py                    # Run with defaults
    python backtest.py --start 2023-01-01 --end 2024-12-31
    python backtest.py --initial-cash 100000
    python backtest.py --symbols AAPL MSFT NVDA
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@dataclass
class Trade:
    """Represents a single trade"""
    date: datetime
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    value: float
    reason: str


@dataclass
class BacktestPosition:
    """Represents a position during backtesting"""
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_cost) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_cost == 0:
            return 0
        return ((self.current_price / self.avg_cost) - 1) * 100


@dataclass
class BacktestResult:
    """Results from a backtest run"""
    start_date: datetime
    end_date: datetime
    initial_cash: float
    final_value: float
    total_return: float
    total_return_pct: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    equity_curve: pd.Series
    trades: List[Trade]
    daily_returns: pd.Series
    # Benchmark comparison
    benchmark_return_pct: float = 0.0
    alpha: float = 0.0


class MomentumStrategy:
    """
    Rule-based momentum strategy for backtesting.

    Captures the essence of what the LLM-based momentum agent does:
    - Identifies uptrends/downtrends using moving averages
    - Confirms with volume
    - Generates buy/sell signals with conviction scores
    """

    def __init__(
        self,
        fast_ma: int = 10,
        slow_ma: int = 30,
        roc_period: int = 20,
        volume_ma: int = 20,
        momentum_threshold: float = 0.05,
        max_position_pct: float = 0.15,
        min_conviction: int = 60
    ):
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.roc_period = roc_period
        self.volume_ma = volume_ma
        self.momentum_threshold = momentum_threshold
        self.max_position_pct = max_position_pct
        self.min_conviction = min_conviction

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate momentum indicators"""
        df = df.copy()

        # Moving averages
        df['MA_fast'] = df['Close'].rolling(window=self.fast_ma).mean()
        df['MA_slow'] = df['Close'].rolling(window=self.slow_ma).mean()

        # Rate of change (momentum)
        df['ROC'] = df['Close'].pct_change(periods=self.roc_period)

        # Volume moving average
        df['Volume_MA'] = df['Volume'].rolling(window=self.volume_ma).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']

        # Trend strength (distance from slow MA)
        df['Trend_Strength'] = (df['Close'] - df['MA_slow']) / df['MA_slow']

        # Volatility (for position sizing)
        df['Volatility'] = df['Close'].pct_change().rolling(window=20).std()

        return df

    def generate_signal(
        self,
        df: pd.DataFrame,
        current_position: Optional[BacktestPosition] = None
    ) -> Tuple[str, int, str]:
        """
        Generate trading signal for a symbol.

        Returns:
            Tuple of (action, conviction, reason)
            action: 'buy', 'sell', or 'hold'
            conviction: 0-100
            reason: explanation string
        """
        if len(df) < self.slow_ma + 5:
            return 'hold', 0, 'Insufficient data'

        df = self.calculate_indicators(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Extract indicators
        ma_fast = latest['MA_fast']
        ma_slow = latest['MA_slow']
        roc = latest['ROC']
        volume_ratio = latest['Volume_Ratio']
        trend_strength = latest['Trend_Strength']
        price = latest['Close']

        # Previous values for crossover detection
        prev_ma_fast = prev['MA_fast']
        prev_ma_slow = prev['MA_slow']

        reasons = []
        conviction = 50  # Base conviction

        # Trend analysis
        uptrend = ma_fast > ma_slow
        downtrend = ma_fast < ma_slow

        # Crossover detection
        bullish_cross = (prev_ma_fast <= prev_ma_slow) and (ma_fast > ma_slow)
        bearish_cross = (prev_ma_fast >= prev_ma_slow) and (ma_fast < ma_slow)

        # Momentum confirmation
        strong_momentum = abs(roc) > self.momentum_threshold
        positive_momentum = roc > self.momentum_threshold
        negative_momentum = roc < -self.momentum_threshold

        # Volume confirmation
        high_volume = volume_ratio > 1.2

        # Generate signal
        action = 'hold'

        if current_position is None or current_position.quantity == 0:
            # No position - look for entry
            if uptrend and positive_momentum:
                action = 'buy'
                conviction = 60
                reasons.append('Uptrend with positive momentum')

                if bullish_cross:
                    conviction += 15
                    reasons.append('Bullish MA crossover')

                if high_volume:
                    conviction += 10
                    reasons.append('Volume confirmation')

                if trend_strength > 0.05:
                    conviction += 5
                    reasons.append('Strong trend')

        else:
            # Have position - look for exit or hold
            if downtrend or negative_momentum:
                action = 'sell'
                conviction = 60
                reasons.append('Trend reversal or negative momentum')

                if bearish_cross:
                    conviction += 20
                    reasons.append('Bearish MA crossover')

                if high_volume:
                    conviction += 10
                    reasons.append('Volume confirms selling pressure')

            elif current_position.unrealized_pnl_pct > 20:
                # Take profits on big winners
                action = 'sell'
                conviction = 70
                reasons.append(f'Taking profits at {current_position.unrealized_pnl_pct:.1f}% gain')

            elif current_position.unrealized_pnl_pct < -10:
                # Cut losses
                action = 'sell'
                conviction = 75
                reasons.append(f'Cutting losses at {current_position.unrealized_pnl_pct:.1f}% loss')

            elif uptrend and positive_momentum:
                action = 'hold'
                conviction = 65
                reasons.append('Trend intact, holding position')

        # Cap conviction at 100
        conviction = min(conviction, 100)

        reason = '; '.join(reasons) if reasons else 'No clear signal'
        return action, conviction, reason


class BacktestEngine:
    """
    Backtesting engine for simulating strategy performance.
    """

    def __init__(
        self,
        strategy: MomentumStrategy,
        initial_cash: float = 100000,
        commission: float = 0.0,  # Commission per trade (0 for most brokers now)
        slippage: float = 0.001  # 0.1% slippage
    ):
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage

    def fetch_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, pd.DataFrame]:
        """Fetch historical data for all symbols"""
        data = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Fetching historical data...", total=len(symbols))

            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    # Fetch extra data for indicator warmup
                    warmup_start = start_date - timedelta(days=60)
                    df = ticker.history(start=warmup_start, end=end_date)
                    if not df.empty:
                        data[symbol] = df
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not fetch {symbol}: {e}[/yellow]")

                progress.advance(task)

        return data

    def run(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Run the backtest"""
        console.print(f"\n[bold]Running Momentum Strategy Backtest[/bold]")
        console.print(f"Period: {start_date.date()} to {end_date.date()}")
        console.print(f"Universe: {', '.join(symbols)}")
        console.print(f"Initial Cash: ${self.initial_cash:,.2f}\n")

        # Fetch data
        data = self.fetch_data(symbols, start_date, end_date)

        if not data:
            raise ValueError("No data fetched for any symbols")

        # Get all trading dates
        all_dates = set()
        for df in data.values():
            all_dates.update(df.index.date)
        trading_dates = sorted([d for d in all_dates if start_date.date() <= d <= end_date.date()])

        # Initialize portfolio
        cash = self.initial_cash
        positions: Dict[str, BacktestPosition] = {}
        trades: List[Trade] = []
        equity_curve = []
        daily_values = []

        console.print(f"Simulating {len(trading_dates)} trading days...")

        for date in trading_dates:
            date_dt = datetime.combine(date, datetime.min.time())

            # Update current prices
            for symbol in list(positions.keys()):
                if symbol in data:
                    df = data[symbol]
                    if date in df.index.date:
                        idx = df.index.date == date
                        positions[symbol].current_price = df.loc[idx, 'Close'].iloc[-1]

            # Calculate portfolio value
            portfolio_value = cash + sum(p.market_value for p in positions.values())

            # Generate signals for each symbol
            for symbol in symbols:
                if symbol not in data:
                    continue

                df = data[symbol]
                # Get data up to current date
                historical = df[df.index.date <= date]

                if len(historical) < 35:  # Need enough data for indicators
                    continue

                current_position = positions.get(symbol)
                action, conviction, reason = self.strategy.generate_signal(
                    historical, current_position
                )

                # Execute trade if conviction is high enough
                if conviction >= self.strategy.min_conviction:
                    current_price = historical['Close'].iloc[-1]

                    if action == 'buy' and symbol not in positions:
                        # Calculate position size (max % of portfolio)
                        max_position_value = portfolio_value * self.strategy.max_position_pct
                        position_value = min(max_position_value, cash * 0.95)  # Keep some cash

                        if position_value > 100:  # Minimum trade size
                            # Apply slippage (buy at slightly higher price)
                            exec_price = current_price * (1 + self.slippage)
                            quantity = position_value / exec_price
                            cost = quantity * exec_price + self.commission

                            if cost <= cash:
                                cash -= cost
                                positions[symbol] = BacktestPosition(
                                    symbol=symbol,
                                    quantity=quantity,
                                    avg_cost=exec_price,
                                    current_price=current_price
                                )
                                trades.append(Trade(
                                    date=date_dt,
                                    symbol=symbol,
                                    side='buy',
                                    quantity=quantity,
                                    price=exec_price,
                                    value=cost,
                                    reason=reason
                                ))

                    elif action == 'sell' and symbol in positions:
                        pos = positions[symbol]
                        # Apply slippage (sell at slightly lower price)
                        exec_price = current_price * (1 - self.slippage)
                        proceeds = pos.quantity * exec_price - self.commission

                        cash += proceeds
                        trades.append(Trade(
                            date=date_dt,
                            symbol=symbol,
                            side='sell',
                            quantity=pos.quantity,
                            price=exec_price,
                            value=proceeds,
                            reason=reason
                        ))
                        del positions[symbol]

            # Record daily portfolio value
            portfolio_value = cash + sum(p.market_value for p in positions.values())
            equity_curve.append({'date': date, 'value': portfolio_value})

        # Create equity curve series
        eq_df = pd.DataFrame(equity_curve)
        eq_df['date'] = pd.to_datetime(eq_df['date'])
        eq_df.set_index('date', inplace=True)
        equity_series = eq_df['value']

        # Fetch benchmark (SPY) for comparison
        console.print("Fetching benchmark (SPY)...")
        try:
            spy = yf.Ticker('SPY')
            spy_data = spy.history(start=start_date, end=end_date)
            if not spy_data.empty:
                benchmark_start = spy_data['Close'].iloc[0]
                benchmark_end = spy_data['Close'].iloc[-1]
                benchmark_return_pct = ((benchmark_end / benchmark_start) - 1) * 100
            else:
                benchmark_return_pct = 0
        except:
            benchmark_return_pct = 0

        # Calculate metrics
        result = self._calculate_metrics(
            equity_series, trades, start_date, end_date, benchmark_return_pct
        )

        return result

    def _calculate_metrics(
        self,
        equity_curve: pd.Series,
        trades: List[Trade],
        start_date: datetime,
        end_date: datetime,
        benchmark_return_pct: float = 0.0
    ) -> BacktestResult:
        """Calculate performance metrics"""
        # Basic returns
        initial_value = self.initial_cash
        final_value = equity_curve.iloc[-1]
        total_return = final_value - initial_value
        total_return_pct = (total_return / initial_value) * 100

        # Annualized return
        days = (end_date - start_date).days
        years = days / 365.25
        if years > 0 and final_value > 0:
            annualized_return = ((final_value / initial_value) ** (1 / years) - 1) * 100
        else:
            annualized_return = 0

        # Daily returns
        daily_returns = equity_curve.pct_change().dropna()

        # Sharpe ratio (assuming 0% risk-free rate for simplicity)
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0

        # Maximum drawdown
        rolling_max = equity_curve.expanding().max()
        drawdowns = equity_curve - rolling_max
        max_drawdown = drawdowns.min()
        max_drawdown_pct = (max_drawdown / rolling_max[drawdowns.idxmin()]) * 100

        # Trade statistics
        total_trades = len(trades)

        # Calculate P&L for each round trip by matching buys and sells chronologically
        winning_trades = 0
        losing_trades = 0
        total_wins = 0
        total_losses = 0

        # Group trades by symbol and match buys to sells
        from collections import defaultdict
        symbol_trades = defaultdict(list)
        for t in trades:
            symbol_trades[t.symbol].append(t)

        for symbol, sym_trades in symbol_trades.items():
            pending_buys = []
            for t in sym_trades:
                if t.side == 'buy':
                    pending_buys.append(t)
                elif t.side == 'sell' and pending_buys:
                    # Match with most recent buy (LIFO)
                    buy = pending_buys.pop()
                    pnl = (t.price - buy.price) * min(t.quantity, buy.quantity)
                    if pnl > 0:
                        winning_trades += 1
                        total_wins += pnl
                    else:
                        losing_trades += 1
                        total_losses += abs(pnl)

        completed_trades = winning_trades + losing_trades
        win_rate = (winning_trades / completed_trades * 100) if completed_trades > 0 else 0
        avg_win = total_wins / winning_trades if winning_trades > 0 else 0
        avg_loss = total_losses / losing_trades if losing_trades > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Alpha (excess return over benchmark)
        alpha = total_return_pct - benchmark_return_pct

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_value,
            final_value=final_value,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            equity_curve=equity_curve,
            trades=trades,
            daily_returns=daily_returns,
            benchmark_return_pct=benchmark_return_pct,
            alpha=alpha
        )


def display_results(result: BacktestResult):
    """Display backtest results in a nice format"""
    # Performance summary
    console.print("\n")
    console.print(Panel("[bold]BACKTEST RESULTS[/bold]", style="cyan"))

    # Returns table
    returns_table = Table(title="Performance Summary", show_header=False)
    returns_table.add_column("Metric", style="cyan")
    returns_table.add_column("Value", justify="right")

    ret_color = "green" if result.total_return >= 0 else "red"
    returns_table.add_row("Initial Capital", f"${result.initial_cash:,.2f}")
    returns_table.add_row("Final Value", f"${result.final_value:,.2f}")
    returns_table.add_row("Total Return", f"[{ret_color}]${result.total_return:,.2f}[/{ret_color}]")
    returns_table.add_row("Total Return %", f"[{ret_color}]{result.total_return_pct:.2f}%[/{ret_color}]")
    returns_table.add_row("Annualized Return", f"[{ret_color}]{result.annualized_return:.2f}%[/{ret_color}]")
    # Benchmark comparison
    bench_color = "green" if result.benchmark_return_pct >= 0 else "red"
    returns_table.add_row("Benchmark (SPY)", f"[{bench_color}]{result.benchmark_return_pct:.2f}%[/{bench_color}]")
    alpha_color = "green" if result.alpha >= 0 else "red"
    returns_table.add_row("Alpha (vs SPY)", f"[{alpha_color}]{result.alpha:+.2f}%[/{alpha_color}]")

    console.print(returns_table)

    # Risk metrics table
    risk_table = Table(title="Risk Metrics", show_header=False)
    risk_table.add_column("Metric", style="cyan")
    risk_table.add_column("Value", justify="right")

    sharpe_color = "green" if result.sharpe_ratio > 1 else "yellow" if result.sharpe_ratio > 0 else "red"
    risk_table.add_row("Sharpe Ratio", f"[{sharpe_color}]{result.sharpe_ratio:.2f}[/{sharpe_color}]")
    risk_table.add_row("Max Drawdown", f"[red]${result.max_drawdown:,.2f}[/red]")
    risk_table.add_row("Max Drawdown %", f"[red]{result.max_drawdown_pct:.2f}%[/red]")

    console.print(risk_table)

    # Trade statistics table
    trade_table = Table(title="Trade Statistics", show_header=False)
    trade_table.add_column("Metric", style="cyan")
    trade_table.add_column("Value", justify="right")

    trade_table.add_row("Total Trades", str(result.total_trades))
    trade_table.add_row("Winning Trades", f"[green]{result.winning_trades}[/green]")
    trade_table.add_row("Losing Trades", f"[red]{result.losing_trades}[/red]")
    trade_table.add_row("Win Rate", f"{result.win_rate:.1f}%")
    trade_table.add_row("Avg Win", f"[green]${result.avg_win:,.2f}[/green]")
    trade_table.add_row("Avg Loss", f"[red]${result.avg_loss:,.2f}[/red]")
    pf_color = "green" if result.profit_factor > 1 else "red"
    pf_str = f"{result.profit_factor:.2f}" if result.profit_factor != float('inf') else "∞"
    trade_table.add_row("Profit Factor", f"[{pf_color}]{pf_str}[/{pf_color}]")

    console.print(trade_table)

    # Recent trades
    if result.trades:
        console.print("\n[bold]Recent Trades (last 10):[/bold]")
        trades_table = Table()
        trades_table.add_column("Date", style="dim")
        trades_table.add_column("Symbol", style="cyan")
        trades_table.add_column("Side", justify="center")
        trades_table.add_column("Qty", justify="right")
        trades_table.add_column("Price", justify="right")
        trades_table.add_column("Value", justify="right")
        trades_table.add_column("Reason")

        for trade in result.trades[-10:]:
            side_color = "green" if trade.side == "buy" else "red"
            trades_table.add_row(
                trade.date.strftime("%Y-%m-%d"),
                trade.symbol,
                f"[{side_color}]{trade.side.upper()}[/{side_color}]",
                f"{trade.quantity:.2f}",
                f"${trade.price:.2f}",
                f"${trade.value:,.2f}",
                trade.reason[:40] + "..." if len(trade.reason) > 40 else trade.reason
            )

        console.print(trades_table)


def save_results(result: BacktestResult, filepath: str):
    """Save backtest results to CSV"""
    # Save equity curve
    result.equity_curve.to_csv(filepath.replace('.csv', '_equity.csv'))

    # Save trades
    trades_df = pd.DataFrame([
        {
            'date': t.date,
            'symbol': t.symbol,
            'side': t.side,
            'quantity': t.quantity,
            'price': t.price,
            'value': t.value,
            'reason': t.reason
        }
        for t in result.trades
    ])
    trades_df.to_csv(filepath.replace('.csv', '_trades.csv'), index=False)

    console.print(f"\n[green]Results saved to {filepath}[/green]")


def main():
    parser = argparse.ArgumentParser(
        description='Backtest the Momentum Strategy',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--start', '-s',
        type=str,
        default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end', '-e',
        type=str,
        default=datetime.now().strftime('%Y-%m-%d'),
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--initial-cash', '-c',
        type=float,
        default=100000,
        help='Initial cash (default: 100000)'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'META', 'AMZN'],
        help='Symbols to trade'
    )
    parser.add_argument(
        '--fast-ma',
        type=int,
        default=10,
        help='Fast moving average period'
    )
    parser.add_argument(
        '--slow-ma',
        type=int,
        default=30,
        help='Slow moving average period'
    )
    parser.add_argument(
        '--save',
        type=str,
        help='Save results to CSV file'
    )

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d')

    # Create strategy and engine
    strategy = MomentumStrategy(
        fast_ma=args.fast_ma,
        slow_ma=args.slow_ma
    )
    engine = BacktestEngine(
        strategy=strategy,
        initial_cash=args.initial_cash
    )

    try:
        # Run backtest
        result = engine.run(
            symbols=args.symbols,
            start_date=start_date,
            end_date=end_date
        )

        # Display results
        display_results(result)

        # Save if requested
        if args.save:
            save_results(result, args.save)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
