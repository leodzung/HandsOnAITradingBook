import pandas as pd
from src.optimization.realistic_backtester import RealisticBacktester

# Simulate the slippage calculation manually
entry_price = 0.990
exit_price = 0.99
position_size = 75
volume_24h = 1000
spread_pct = 5.0 / 100.0

# Entry slippage
base_slippage_pct = spread_pct / 2.0
impact_factor = position_size / max(volume_24h, 1)
impact_slippage_pct = impact_factor * 0.5
total_entry_slippage_pct = base_slippage_pct + impact_slippage_pct
entry_slippage_dollars = position_size * total_entry_slippage_pct
entry_slippage_bps = total_entry_slippage_pct * 10000

print('Entry slippage calculation:')
print(f'  Base slippage (spread/2): {base_slippage_pct:.4f} ({base_slippage_pct*100:.2f}%)')
print(f'  Impact factor: {impact_factor:.4f}')
print(f'  Impact slippage: {impact_slippage_pct:.4f} ({impact_slippage_pct*100:.2f}%)')
print(f'  Total slippage: {entry_slippage_dollars:.2f} ({entry_slippage_bps:.0f} bps)')
print(f'  Effective entry: {entry_price + entry_slippage_dollars/position_size:.3f}')

# Exit slippage (1.2x entry)
exit_slippage_dollars = entry_slippage_dollars * 1.2
exit_slippage_bps = entry_slippage_bps * 1.2

print('\nExit slippage calculation:')
print(f'  Exit slippage: {exit_slippage_dollars:.2f} ({exit_slippage_bps:.0f} bps)')
print(f'  Effective exit: {exit_price - exit_slippage_dollars/position_size:.3f}')
print(f'  Limit: 2000 bps')
print(f'  Should reject: {exit_slippage_bps > 2000}')
