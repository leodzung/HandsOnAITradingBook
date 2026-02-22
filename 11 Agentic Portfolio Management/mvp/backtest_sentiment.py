#!/usr/bin/env python3
"""
Backtesting Framework for Sentiment Agent

This module provides a backtesting engine for the sentiment strategy,
using historical sentiment proxies since actual news data isn't available.

Sentiment Proxies Used:
- VIX (Fear/Greed indicator)
- Price-Volume Divergence
- Gap Analysis (overnight sentiment)
- Relative Strength vs SPY

Usage:
    python backtest_sentiment.py                    # Run with defaults
    python backtest_sentiment.py --start 2023-01-01 --end 2024-12-31
    python backtest_sentiment.py --compare          # Compare with momentum strategy
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import from existing backtest module
from backtest import (
    Trade, BacktestPosition, BacktestResult,
    BacktestEngine, MomentumStrategy, display_results
)

console = Console()


class SentimentStrategy:
    """
    Sentiment-based strategy using historical proxies.

    Since we can't backtest actual news sentiment, we use proxies:
    - VIX levels and changes (fear indicator)
    - Price gaps (overnight sentiment/news reaction)
    - Volume spikes (unusual activity often news-driven)
    - Relative strength divergence (sentiment vs fundamentals)
    """

    def __init__(
        self,
        vix_oversold: float = 15,      # VIX below this = greedy/complacent
        vix_overbought: float = 25,    # VIX above this = fearful
        gap_threshold: float = 0.02,   # 2% gap is significant
        volume_spike: float = 2.0,     # 2x average volume
        rsi_period: int = 14,
        max_position_pct: float = 0.15,
        min_conviction: int = 60
    ):
        self.vix_oversold = vix_oversold
        self.vix_overbought = vix_overbought
        self.gap_threshold = gap_threshold
        self.volume_spike = volume_spike
        self.rsi_period = rsi_period
        self.max_position_pct = max_position_pct
        self.min_conviction = min_conviction

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_indicators(
        self,
        df: pd.DataFrame,
        vix_data: Optional[pd.DataFrame] = None,
        spy_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """Calculate sentiment indicators"""
        df = df.copy()

        # Gap analysis (overnight sentiment)
        df['Prev_Close'] = df['Close'].shift(1)
        df['Gap'] = (df['Open'] - df['Prev_Close']) / df['Prev_Close']
        df['Gap_Up'] = df['Gap'] > self.gap_threshold
        df['Gap_Down'] = df['Gap'] < -self.gap_threshold

        # Volume analysis
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        df['Volume_Spike'] = df['Volume_Ratio'] > self.volume_spike

        # RSI (sentiment oscillator)
        df['RSI'] = self.calculate_rsi(df['Close'], self.rsi_period)
        df['RSI_Oversold'] = df['RSI'] < 30
        df['RSI_Overbought'] = df['RSI'] > 70

        # Price momentum (5-day)
        df['Momentum_5d'] = df['Close'].pct_change(5)

        # Volatility (sentiment uncertainty)
        df['Volatility'] = df['Close'].pct_change().rolling(window=10).std()

        # VIX-based sentiment (if available)
        if vix_data is not None and not vix_data.empty:
            # Align VIX data with stock data
            vix_aligned = vix_data['Close'].reindex(df.index, method='ffill')
            df['VIX'] = vix_aligned
            df['VIX_Change'] = df['VIX'].pct_change(5)
            df['VIX_Fear'] = df['VIX'] > self.vix_overbought
            df['VIX_Greed'] = df['VIX'] < self.vix_oversold
        else:
            df['VIX'] = np.nan
            df['VIX_Fear'] = False
            df['VIX_Greed'] = False

        # Relative strength vs SPY (if available)
        if spy_data is not None and not spy_data.empty:
            spy_aligned = spy_data['Close'].reindex(df.index, method='ffill')
            df['SPY'] = spy_aligned
            df['Stock_Return_20d'] = df['Close'].pct_change(20)
            df['SPY_Return_20d'] = df['SPY'].pct_change(20)
            df['Relative_Strength'] = df['Stock_Return_20d'] - df['SPY_Return_20d']
            df['Outperforming'] = df['Relative_Strength'] > 0.02
            df['Underperforming'] = df['Relative_Strength'] < -0.02
        else:
            df['Relative_Strength'] = 0
            df['Outperforming'] = False
            df['Underperforming'] = False

        return df

    def calculate_sentiment_score(self, row: pd.Series) -> Tuple[float, List[str]]:
        """
        Calculate aggregate sentiment score from -1 (very bearish) to +1 (very bullish)
        Returns (score, reasons)
        """
        score = 0.0
        reasons = []

        # VIX-based sentiment
        if row.get('VIX_Fear', False):
            score -= 0.2
            reasons.append("High VIX (fear)")
        elif row.get('VIX_Greed', False):
            score += 0.15
            reasons.append("Low VIX (complacency)")

        # Gap sentiment
        if row.get('Gap_Up', False):
            score += 0.25
            reasons.append(f"Positive gap ({row['Gap']:.1%})")
        elif row.get('Gap_Down', False):
            score -= 0.25
            reasons.append(f"Negative gap ({row['Gap']:.1%})")

        # RSI sentiment
        if row.get('RSI_Oversold', False):
            score += 0.2  # Contrarian: oversold = potential bounce
            reasons.append("RSI oversold (potential bounce)")
        elif row.get('RSI_Overbought', False):
            score -= 0.15  # Overbought = potential pullback
            reasons.append("RSI overbought (extended)")

        # Volume spike with direction
        if row.get('Volume_Spike', False):
            momentum = row.get('Momentum_5d', 0)
            if momentum > 0:
                score += 0.15
                reasons.append("High volume on up move")
            elif momentum < 0:
                score -= 0.15
                reasons.append("High volume on down move")

        # Relative strength
        if row.get('Outperforming', False):
            score += 0.15
            reasons.append("Outperforming market")
        elif row.get('Underperforming', False):
            score -= 0.15
            reasons.append("Underperforming market")

        # Clamp score to [-1, 1]
        score = max(-1.0, min(1.0, score))

        return score, reasons

    def generate_signal(
        self,
        df: pd.DataFrame,
        current_position: Optional[BacktestPosition] = None,
        vix_data: Optional[pd.DataFrame] = None,
        spy_data: Optional[pd.DataFrame] = None
    ) -> Tuple[str, int, str]:
        """
        Generate trading signal based on sentiment.

        Returns:
            Tuple of (action, conviction, reason)
        """
        if len(df) < 25:
            return 'hold', 0, 'Insufficient data'

        df = self.calculate_indicators(df, vix_data, spy_data)
        latest = df.iloc[-1]

        # Calculate sentiment score
        sentiment_score, reasons = self.calculate_sentiment_score(latest)

        # Convert sentiment to trading signal
        action = 'hold'
        conviction = 50

        if current_position is None or current_position.quantity == 0:
            # No position - look for entry
            if sentiment_score > 0.3:
                action = 'buy'
                conviction = int(50 + sentiment_score * 40)
                reasons.insert(0, f"Bullish sentiment ({sentiment_score:.2f})")
            elif sentiment_score < -0.3:
                # Strong negative sentiment could be contrarian buy on oversold
                if latest.get('RSI_Oversold', False):
                    action = 'buy'
                    conviction = 55
                    reasons.insert(0, "Contrarian buy on extreme fear")
        else:
            # Have position - look for exit
            if sentiment_score < -0.25:
                action = 'sell'
                conviction = int(50 + abs(sentiment_score) * 40)
                reasons.insert(0, f"Bearish sentiment ({sentiment_score:.2f})")

            # Take profits on sentiment exhaustion
            elif current_position.unrealized_pnl_pct > 15 and sentiment_score < 0.1:
                action = 'sell'
                conviction = 65
                reasons.insert(0, f"Taking profits, sentiment fading")

            # Cut losses if sentiment confirms
            elif current_position.unrealized_pnl_pct < -8 and sentiment_score < 0:
                action = 'sell'
                conviction = 70
                reasons.insert(0, f"Cutting losses, negative sentiment confirms")

        reason = "; ".join(reasons[:3]) if reasons else "No clear sentiment signal"
        return action, min(conviction, 95), reason


class SentimentBacktestEngine(BacktestEngine):
    """Extended backtest engine with VIX and SPY data for sentiment"""

    def __init__(
        self,
        strategy: SentimentStrategy,
        initial_cash: float = 100000,
        commission: float = 0.0,
        slippage: float = 0.001
    ):
        super().__init__(strategy, initial_cash, commission, slippage)
        self.vix_data = None
        self.spy_data = None

    def fetch_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, pd.DataFrame]:
        """Fetch historical data including VIX and SPY"""
        data = {}
        warmup_start = start_date - timedelta(days=60)

        # Fetch VIX for sentiment
        console.print("Fetching VIX data...")
        try:
            vix = yf.Ticker('^VIX')
            self.vix_data = vix.history(start=warmup_start, end=end_date)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch VIX: {e}[/yellow]")
            self.vix_data = pd.DataFrame()

        # Fetch SPY for relative strength
        console.print("Fetching SPY data...")
        try:
            spy = yf.Ticker('SPY')
            self.spy_data = spy.history(start=warmup_start, end=end_date)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch SPY: {e}[/yellow]")
            self.spy_data = pd.DataFrame()

        # Fetch stock data
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Fetching stock data...", total=len(symbols))

            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
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
        """Run the sentiment backtest"""
        console.print(f"\n[bold]Running Sentiment Strategy Backtest[/bold]")
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
                historical = df[df.index.date <= date]

                if len(historical) < 30:
                    continue

                # Get VIX and SPY data up to current date
                vix_hist = None
                spy_hist = None
                if self.vix_data is not None and not self.vix_data.empty:
                    vix_hist = self.vix_data[self.vix_data.index.date <= date]
                if self.spy_data is not None and not self.spy_data.empty:
                    spy_hist = self.spy_data[self.spy_data.index.date <= date]

                current_position = positions.get(symbol)
                action, conviction, reason = self.strategy.generate_signal(
                    historical, current_position, vix_hist, spy_hist
                )

                # Execute trade if conviction is high enough
                if conviction >= self.strategy.min_conviction:
                    current_price = historical['Close'].iloc[-1]

                    if action == 'buy' and symbol not in positions:
                        max_position_value = portfolio_value * self.strategy.max_position_pct
                        position_value = min(max_position_value, cash * 0.95)

                        if position_value > 100:
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

        # Fetch benchmark
        console.print("Calculating benchmark...")
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


def compare_strategies(
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    initial_cash: float
):
    """Compare sentiment vs momentum strategies"""
    console.print(Panel("[bold]Strategy Comparison: Sentiment vs Momentum[/bold]", style="cyan"))

    # Run momentum backtest
    console.print("\n[bold cyan]1. Running Momentum Strategy...[/bold cyan]")
    momentum_strategy = MomentumStrategy()
    momentum_engine = BacktestEngine(momentum_strategy, initial_cash)
    momentum_result = momentum_engine.run(symbols, start_date, end_date)

    # Run sentiment backtest
    console.print("\n[bold cyan]2. Running Sentiment Strategy...[/bold cyan]")
    sentiment_strategy = SentimentStrategy()
    sentiment_engine = SentimentBacktestEngine(sentiment_strategy, initial_cash)
    sentiment_result = sentiment_engine.run(symbols, start_date, end_date)

    # Display comparison
    console.print("\n")
    console.print(Panel("[bold]STRATEGY COMPARISON RESULTS[/bold]", style="green"))

    comparison_table = Table(title="Performance Comparison")
    comparison_table.add_column("Metric", style="cyan")
    comparison_table.add_column("Momentum", justify="right")
    comparison_table.add_column("Sentiment", justify="right")
    comparison_table.add_column("Winner", justify="center")

    def get_winner(m_val, s_val, higher_better=True):
        if higher_better:
            return "[green]Momentum[/green]" if m_val > s_val else "[blue]Sentiment[/blue]"
        else:
            return "[green]Momentum[/green]" if m_val < s_val else "[blue]Sentiment[/blue]"

    comparison_table.add_row(
        "Total Return %",
        f"{momentum_result.total_return_pct:.2f}%",
        f"{sentiment_result.total_return_pct:.2f}%",
        get_winner(momentum_result.total_return_pct, sentiment_result.total_return_pct)
    )
    comparison_table.add_row(
        "Alpha vs SPY",
        f"{momentum_result.alpha:+.2f}%",
        f"{sentiment_result.alpha:+.2f}%",
        get_winner(momentum_result.alpha, sentiment_result.alpha)
    )
    comparison_table.add_row(
        "Sharpe Ratio",
        f"{momentum_result.sharpe_ratio:.2f}",
        f"{sentiment_result.sharpe_ratio:.2f}",
        get_winner(momentum_result.sharpe_ratio, sentiment_result.sharpe_ratio)
    )
    comparison_table.add_row(
        "Max Drawdown",
        f"{momentum_result.max_drawdown_pct:.2f}%",
        f"{sentiment_result.max_drawdown_pct:.2f}%",
        get_winner(momentum_result.max_drawdown_pct, sentiment_result.max_drawdown_pct, higher_better=False)
    )
    comparison_table.add_row(
        "Win Rate",
        f"{momentum_result.win_rate:.1f}%",
        f"{sentiment_result.win_rate:.1f}%",
        get_winner(momentum_result.win_rate, sentiment_result.win_rate)
    )
    comparison_table.add_row(
        "Profit Factor",
        f"{momentum_result.profit_factor:.2f}" if momentum_result.profit_factor != float('inf') else "∞",
        f"{sentiment_result.profit_factor:.2f}" if sentiment_result.profit_factor != float('inf') else "∞",
        get_winner(momentum_result.profit_factor, sentiment_result.profit_factor)
    )
    comparison_table.add_row(
        "Total Trades",
        str(momentum_result.total_trades),
        str(sentiment_result.total_trades),
        "-"
    )

    console.print(comparison_table)

    # Benchmark reference
    console.print(f"\n[dim]Benchmark (SPY): {momentum_result.benchmark_return_pct:.2f}%[/dim]")

    return momentum_result, sentiment_result


def main():
    parser = argparse.ArgumentParser(
        description='Backtest the Sentiment Strategy',
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
        '--compare',
        action='store_true',
        help='Compare with momentum strategy'
    )

    args = parser.parse_args()

    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d')

    try:
        if args.compare:
            compare_strategies(args.symbols, start_date, end_date, args.initial_cash)
        else:
            # Run sentiment backtest only
            strategy = SentimentStrategy()
            engine = SentimentBacktestEngine(strategy, args.initial_cash)
            result = engine.run(args.symbols, start_date, end_date)
            display_results(result)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
