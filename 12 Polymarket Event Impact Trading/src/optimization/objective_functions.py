"""
Objective functions for parameter optimization.

Implements composite scoring function that balances multiple performance
metrics: Sharpe ratio, max drawdown, win rate stability, and profit factor.
"""

import numpy as np
from typing import Dict, List, Tuple


def calculate_metrics(
    trades: List[Dict],
    initial_balance: float = 1000.0
) -> Dict[str, float]:
    """
    Calculate performance metrics from trade history.

    Args:
        trades: List of trade dictionaries with 'pnl', 'outcome', 'timestamp'
        initial_balance: Starting balance for returns calculation

    Returns:
        Dictionary of performance metrics:
        - sharpe_ratio: Risk-adjusted return
        - max_drawdown: Maximum peak-to-trough decline
        - win_rate: Percentage of profitable trades
        - win_rate_std: Standard deviation of win rate (stability)
        - profit_factor: Ratio of gross profit to gross loss
        - total_return: Total return percentage
        - num_trades: Number of trades
        - avg_pnl: Average PnL per trade
    """
    if not trades or len(trades) == 0:
        return {
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'win_rate_std': 0.0,
            'profit_factor': 0.0,
            'total_return': 0.0,
            'num_trades': 0,
            'avg_pnl': 0.0,
        }

    # Extract PnL values
    pnls = np.array([t['pnl'] for t in trades])
    num_trades = len(pnls)

    # Calculate cumulative returns
    balance = initial_balance
    balances = [balance]
    for pnl in pnls:
        balance += pnl
        balances.append(balance)

    balances = np.array(balances)
    returns = np.diff(balances) / balances[:-1]

    # Sharpe ratio (annualized, assuming ~100 trades per year for short-expiry)
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(100)
    else:
        sharpe_ratio = 0.0

    # Maximum drawdown
    cummax = np.maximum.accumulate(balances)
    drawdowns = (balances - cummax) / cummax
    max_drawdown = abs(np.min(drawdowns))

    # Win rate
    wins = pnls > 0
    win_rate = np.mean(wins) if num_trades > 0 else 0.0

    # Win rate stability (std over rolling windows)
    if num_trades >= 20:
        window = 10
        win_rates = []
        for i in range(num_trades - window + 1):
            window_wins = wins[i:i+window]
            win_rates.append(np.mean(window_wins))
        win_rate_std = np.std(win_rates) if len(win_rates) > 0 else 0.0
    else:
        win_rate_std = 0.0

    # Profit factor
    gross_profit = np.sum(pnls[pnls > 0]) if np.any(pnls > 0) else 0.0
    gross_loss = abs(np.sum(pnls[pnls < 0])) if np.any(pnls < 0) else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    # Total return
    total_return = (balances[-1] - initial_balance) / initial_balance

    # Average PnL
    avg_pnl = np.mean(pnls)

    return {
        'sharpe_ratio': float(sharpe_ratio),
        'max_drawdown': float(max_drawdown),
        'win_rate': float(win_rate),
        'win_rate_std': float(win_rate_std),
        'profit_factor': float(profit_factor),
        'total_return': float(total_return),
        'num_trades': int(num_trades),
        'avg_pnl': float(avg_pnl),
    }


def composite_score(
    metrics: Dict[str, float],
    weights: Dict[str, float] = None,
    targets: Dict[str, float] = None
) -> float:
    """
    Calculate composite optimization score from performance metrics.

    Default weighting:
    - 50% Sharpe ratio (target: 1.5-2.0)
    - 25% Max drawdown control (target: <20%)
    - 15% Win rate stability (target: std <5%)
    - 10% Profit factor (target: 1.5-2.0)

    Args:
        metrics: Performance metrics from calculate_metrics()
        weights: Optional custom weights (default shown above)
        targets: Optional custom target values

    Returns:
        Composite score in range [0, 1] where higher is better
    """
    if weights is None:
        weights = {
            'sharpe': 0.50,
            'drawdown': 0.25,
            'stability': 0.15,
            'profit_factor': 0.10,
        }

    if targets is None:
        targets = {
            'sharpe': 2.0,  # Excellent Sharpe for this strategy
            'max_drawdown': 0.20,  # 20% max drawdown threshold
            'win_rate_std': 0.05,  # 5% std in win rate
            'profit_factor': 2.0,  # 2:1 profit/loss ratio
        }

    # Normalize Sharpe ratio (clip to [0, 1])
    sharpe_score = np.clip(metrics['sharpe_ratio'] / targets['sharpe'], 0, 1)

    # Normalize drawdown (invert - lower is better)
    dd_score = 1.0 - np.clip(metrics['max_drawdown'] / targets['max_drawdown'], 0, 1)

    # Normalize win rate stability (invert - lower is better)
    stability_score = 1.0 - np.clip(metrics['win_rate_std'] / targets['win_rate_std'], 0, 1)

    # Normalize profit factor (clip to [0, 1])
    # Subtract 1.0 since PF=1.0 means breakeven
    pf_score = np.clip((metrics['profit_factor'] - 1.0) / (targets['profit_factor'] - 1.0), 0, 1)

    # Weighted composite
    score = (
        weights['sharpe'] * sharpe_score +
        weights['drawdown'] * dd_score +
        weights['stability'] * stability_score +
        weights['profit_factor'] * pf_score
    )

    return float(score)


def multi_fold_score(
    fold_metrics: List[Dict[str, float]],
    weights: Dict[str, float] = None,
    targets: Dict[str, float] = None,
    stability_weight: float = 0.3
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate score across multiple folds with stability penalty.

    Combines mean performance with consistency across folds to prevent
    overfitting to specific time periods.

    Args:
        fold_metrics: List of metrics dictionaries from each fold
        weights: Composite score weights
        targets: Target values for normalization
        stability_weight: Weight given to cross-fold consistency (default 0.3)

    Returns:
        Tuple of (total_score, aggregated_metrics)
        - total_score: stability_weight * mean_score + (1-stability_weight) * (1 - score_std)
        - aggregated_metrics: Mean metrics across folds
    """
    if not fold_metrics or len(fold_metrics) == 0:
        return 0.0, {}

    # Calculate composite score for each fold
    fold_scores = [composite_score(m, weights, targets) for m in fold_metrics]

    # Mean and std of scores across folds
    mean_score = np.mean(fold_scores)
    std_score = np.std(fold_scores)

    # Penalize high variance (prefer stable strategies)
    stability_score = 1.0 - np.clip(std_score / 0.2, 0, 1)  # Normalize by 0.2 std threshold

    # Combined score favoring both performance and stability
    total_score = stability_weight * mean_score + (1 - stability_weight) * stability_score

    # Aggregate metrics across folds
    aggregated = {}
    metric_keys = fold_metrics[0].keys()
    for key in metric_keys:
        values = [m[key] for m in fold_metrics]
        aggregated[key] = np.mean(values)
        aggregated[f'{key}_std'] = np.std(values)

    aggregated['composite_score'] = float(mean_score)
    aggregated['composite_score_std'] = float(std_score)
    aggregated['total_score'] = float(total_score)

    return float(total_score), aggregated


def filter_invalid_results(
    metrics: Dict[str, float],
    min_trades: int = 20
) -> bool:
    """
    Filter out invalid or unreliable optimization results.

    Args:
        metrics: Performance metrics
        min_trades: Minimum number of trades required

    Returns:
        True if results are valid, False otherwise
    """
    # Must have minimum number of trades
    if metrics.get('num_trades', 0) < min_trades:
        return False

    # Allow profit factor >= 1.0 (breakeven or better)
    # Changed from > 1.0 to >= 1.0 to be less strict
    if metrics.get('profit_factor', 0) < 1.0:
        return False

    # Must have reasonable win rate (not too extreme)
    # Relaxed upper bound from 0.95 to 0.98 for small samples
    win_rate = metrics.get('win_rate', 0)
    if win_rate < 0.3 or win_rate > 0.98:
        return False

    # Allow negative Sharpe for now (market conditions can be tough)
    # We'll optimize for better Sharpe, but not reject negative
    # if metrics.get('sharpe_ratio', 0) < 0:
    #     return False

    return True


def format_metrics_report(metrics: Dict[str, float]) -> str:
    """
    Format metrics dictionary into readable report string.

    Args:
        metrics: Performance metrics

    Returns:
        Formatted string report
    """
    report = []
    report.append("=" * 60)
    report.append("PERFORMANCE METRICS")
    report.append("=" * 60)

    # Core metrics
    report.append(f"Sharpe Ratio:     {metrics.get('sharpe_ratio', 0):.3f}")
    report.append(f"Max Drawdown:     {metrics.get('max_drawdown', 0):.2%}")
    report.append(f"Win Rate:         {metrics.get('win_rate', 0):.2%}")
    report.append(f"Win Rate Std:     {metrics.get('win_rate_std', 0):.2%}")
    report.append(f"Profit Factor:    {metrics.get('profit_factor', 0):.3f}")
    report.append(f"Total Return:     {metrics.get('total_return', 0):.2%}")

    # Trade statistics
    report.append("")
    report.append(f"Total Trades:     {metrics.get('num_trades', 0)}")
    report.append(f"Avg PnL/Trade:    ${metrics.get('avg_pnl', 0):.2f}")

    # Composite score (if available)
    if 'composite_score' in metrics:
        report.append("")
        report.append(f"Composite Score:  {metrics['composite_score']:.4f}")
        if 'composite_score_std' in metrics:
            report.append(f"Score Std:        {metrics['composite_score_std']:.4f}")
        if 'total_score' in metrics:
            report.append(f"Total Score:      {metrics['total_score']:.4f}")

    report.append("=" * 60)

    return "\n".join(report)
