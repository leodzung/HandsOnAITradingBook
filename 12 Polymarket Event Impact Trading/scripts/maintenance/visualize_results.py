#!/usr/bin/env python3
"""
Visualize backtesting results with detailed charts
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from backtester import Backtester, create_sample_signals, create_sample_prices
from models import PriceMovementPredictor

print("="*70)
print("CREATING DETAILED BACKTEST VISUALIZATIONS")
print("="*70)

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette('husl')

# Generate sample data
print("\nGenerating sample data...")
signals_df = create_sample_signals(n_signals=200, n_markets=20)
market_ids = signals_df['market_id'].unique()
start_time = signals_df['timestamp'].min()
end_time = signals_df['timestamp'].max()
price_data = create_sample_prices(market_ids, start_time, end_time)

# Run backtest
print("Running backtest...")
backtester = Backtester(
    initial_capital=10000,
    position_size=100,
    hold_time_hours=24,
    max_positions=10
)

results = backtester.run_backtest(signals_df, price_data)

# Create visualization
print("Creating charts...\n")
backtester.plot_results(save_path='backtest_results.png')

print("="*70)
print("✓ Charts saved to: backtest_results.png")
print("="*70)

# Print detailed statistics
print("\n📊 DETAILED STATISTICS\n")

if backtester.portfolio.closed_trades:
    trades_df = pd.DataFrame([t.to_dict() for t in backtester.portfolio.closed_trades])

    print("Trade Duration Analysis:")
    print(f"  Average Hold Time: {trades_df['duration_hours'].mean():.1f} hours")
    print(f"  Min Hold Time: {trades_df['duration_hours'].min():.1f} hours")
    print(f"  Max Hold Time: {trades_df['duration_hours'].max():.1f} hours")

    print("\nReturn Distribution:")
    print(f"  Best Trade: +{trades_df['return_pct'].max():.2f}%")
    print(f"  Worst Trade: {trades_df['return_pct'].min():.2f}%")
    print(f"  Median Return: {trades_df['return_pct'].median():.2f}%")
    print(f"  Std Deviation: {trades_df['return_pct'].std():.2f}%")

    print("\nProfitability by Trade Side:")
    side_stats = trades_df.groupby('side').agg({
        'pnl': ['sum', 'mean', 'count'],
        'return_pct': 'mean'
    }).round(2)
    print(side_stats)

    # Calculate consecutive wins/losses
    trades_df['is_win'] = trades_df['pnl'] > 0
    trades_df['streak'] = (trades_df['is_win'] != trades_df['is_win'].shift()).cumsum()
    win_streaks = trades_df[trades_df['is_win']].groupby('streak').size()
    loss_streaks = trades_df[~trades_df['is_win']].groupby('streak').size()

    print("\nStreak Analysis:")
    print(f"  Longest Win Streak: {win_streaks.max() if len(win_streaks) > 0 else 0} trades")
    print(f"  Longest Loss Streak: {loss_streaks.max() if len(loss_streaks) > 0 else 0} trades")

    # Monthly performance (if applicable)
    trades_df['month'] = pd.to_datetime(trades_df['exit_time']).dt.to_period('M')
    monthly = trades_df.groupby('month')['pnl'].agg(['sum', 'count'])

    print("\nMonthly Breakdown:")
    for month, row in monthly.iterrows():
        print(f"  {month}: ${row['sum']:.2f} ({int(row['count'])} trades)")

print("\n" + "="*70)
print("Open backtest_results.png to see the charts!")
print("="*70)
