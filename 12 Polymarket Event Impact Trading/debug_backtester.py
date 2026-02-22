import pandas as pd
from src.optimization.realistic_backtester import RealisticBacktester
from src.optimization.param_spaces import get_baseline_params

# Load short bucket
df = pd.read_csv('data/REAL_labeled_from_alchemy.csv')
df['block_timestamp'] = pd.to_datetime(df['block_timestamp'])
df['end_date'] = pd.to_datetime(df['end_date'])
df['hours_to_expiry'] = (df['end_date'] - df['block_timestamp']).dt.total_seconds() / 3600
short_df = df[(df['hours_to_expiry'] > 24) & (df['hours_to_expiry'] <= 72)].copy()
short_df['volume_24h'] = 1000
short_df['spread_pct'] = 5.0

# Find winning trades
winners = short_df[short_df['label'] == 1.0]
print('Sample winning trades:')
print(winners[['trade_price', 'outcome', 'label']].head())

# Run backtest on just winners
params = get_baseline_params('short')
bt = RealisticBacktester(initial_balance=1000.0)
trades = bt.backtest(winners.head(10), params, 'short')

print(f'\nBacktest results on 10 winners:')
for i, t in enumerate(trades):
    if not t.rejected:
        print(f'{i+1}. Label={t.actual_outcome}, Entry={t.entry_price:.3f}, '
              f'Exit={t.exit_price:.3f}, Net PnL=${t.net_pnl:.2f}, '
              f'Reason={t.exit_reason}')
    else:
        print(f'{i+1}. REJECTED: {t.rejection_reason}')
