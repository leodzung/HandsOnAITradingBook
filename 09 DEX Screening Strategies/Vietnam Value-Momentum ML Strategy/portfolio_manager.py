# portfolio_manager.py
# Portfolio construction and risk management for Vietnamese stock strategy

import pandas as pd
import numpy as np
from collections import defaultdict

class PortfolioManager:
    """
    Manages portfolio construction, position sizing, and risk management
    for the Vietnamese stock strategy.
    """

    def __init__(self,
                 target_stocks=20,
                 min_position=0.015,
                 max_position=0.08,
                 max_sector_weight=0.40,
                 min_sectors=3,
                 fundamental_weight=0.4,
                 ml_weight=0.4,
                 sector_momentum_weight=0.2,
                 max_turnover=1.0):
        """
        Initialize portfolio manager.

        Args:
            target_stocks: Target number of positions (default 20)
            min_position: Minimum position size (default 1.5%)
            max_position: Maximum position size (default 8%)
            max_sector_weight: Maximum sector allocation (default 40%)
            min_sectors: Minimum number of sectors (default 3)
            fundamental_weight: Weight for fundamental score (default 0.4)
            ml_weight: Weight for ML score (default 0.4)
            sector_momentum_weight: Weight for sector momentum (default 0.2)
            max_turnover: Maximum quarterly turnover (default 100%)
        """
        self.target_stocks = target_stocks
        self.min_position = min_position
        self.max_position = max_position
        self.max_sector_weight = max_sector_weight
        self.min_sectors = min_sectors
        self.fundamental_weight = fundamental_weight
        self.ml_weight = ml_weight
        self.sector_momentum_weight = sector_momentum_weight
        self.max_turnover = max_turnover

        self.current_holdings = {}  # {symbol: weight}
        self.sector_allocations = {}  # {sector: weight}

    def calculate_combined_scores(self, candidates):
        """
        Calculate combined scores for candidate stocks.

        Args:
            candidates: List of dictionaries with stock data:
                [{
                    'symbol': 'VNM',
                    'sector': 'Consumer Goods',
                    'fundamental_score': 75,
                    'ml_score': 80,
                    'sector_momentum': 0.05
                }, ...]

        Returns:
            DataFrame with symbols, scores, and sectors sorted by combined score
        """
        scored_stocks = []

        for stock in candidates:
            # Normalize scores to 0-1 range
            fund_score_norm = stock['fundamental_score'] / 100.0
            ml_score_norm = stock['ml_score'] / 100.0
            sector_mom_norm = self._normalize_sector_momentum(stock.get('sector_momentum', 0))

            # Calculate combined score
            combined = (
                fund_score_norm * self.fundamental_weight +
                ml_score_norm * self.ml_weight +
                sector_mom_norm * self.sector_momentum_weight
            )

            scored_stocks.append({
                'symbol': stock['symbol'],
                'sector': stock.get('sector', 'Unknown'),
                'fundamental_score': stock['fundamental_score'],
                'ml_score': stock['ml_score'],
                'combined_score': combined * 100,  # Back to 0-100 scale
                'market_cap': stock.get('market_cap', 0)
            })

        # Sort by combined score
        df = pd.DataFrame(scored_stocks)
        df = df.sort_values('combined_score', ascending=False)

        return df

    def construct_portfolio(self, candidates, sector_returns=None):
        """
        Construct portfolio weights from candidate stocks.

        Args:
            candidates: DataFrame from calculate_combined_scores()
            sector_returns: Optional dict of sector returns for momentum overlay

        Returns:
            Dictionary of portfolio weights: {symbol: weight}
        """
        # Start with top N stocks
        top_candidates = candidates.head(self.target_stocks * 2)  # Take more for filtering

        # Apply sector constraints
        portfolio = self._apply_sector_constraints(top_candidates, sector_returns)

        # Calculate position sizes based on scores
        weights = self._calculate_position_sizes(portfolio)

        # Apply turnover constraint if we have existing holdings
        if self.current_holdings:
            weights = self._apply_turnover_constraint(weights)

        # Normalize to sum to 1.0
        weights = self._normalize_weights(weights)

        # Update current holdings
        self.current_holdings = weights

        return weights

    def _apply_sector_constraints(self, candidates, sector_returns=None):
        """
        Apply sector diversification constraints.

        Args:
            candidates: DataFrame of candidate stocks
            sector_returns: Optional dict of sector returns

        Returns:
            Filtered DataFrame meeting sector constraints
        """
        selected = []
        sector_weights = defaultdict(float)
        sector_counts = defaultdict(int)

        # Calculate sector momentum ranks if provided
        sector_ranks = {}
        if sector_returns:
            sorted_sectors = sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)
            for rank, (sector, _) in enumerate(sorted_sectors):
                sector_ranks[sector] = rank

        # Select stocks while respecting sector constraints
        for _, row in candidates.iterrows():
            sector = row['sector']

            # Check if adding this stock would violate sector cap
            # Estimate weight (will be refined later)
            estimated_weight = 1.0 / self.target_stocks

            if sector_weights[sector] + estimated_weight > self.max_sector_weight:
                continue  # Skip if sector is full

            # Add stock
            selected.append(row)
            sector_weights[sector] += estimated_weight
            sector_counts[sector] += 1

            # Check if we have enough stocks
            if len(selected) >= self.target_stocks:
                break

        # Ensure minimum sector diversification
        if len(sector_counts) < self.min_sectors:
            # Need to add stocks from underrepresented sectors
            selected = self._ensure_min_sectors(candidates, selected, sector_counts)

        self.sector_allocations = dict(sector_weights)

        return pd.DataFrame(selected)

    def _ensure_min_sectors(self, all_candidates, selected, sector_counts):
        """
        Ensure minimum number of sectors are represented.

        Args:
            all_candidates: All candidate stocks
            selected: Currently selected stocks (list of rows)
            sector_counts: Current sector counts

        Returns:
            Updated selected list
        """
        selected_symbols = {s['symbol'] for s in selected}
        sectors_needed = self.min_sectors - len(sector_counts)

        if sectors_needed <= 0:
            return selected

        # Find stocks from new sectors
        for _, row in all_candidates.iterrows():
            if row['symbol'] in selected_symbols:
                continue

            sector = row['sector']
            if sector not in sector_counts:
                selected.append(row)
                sector_counts[sector] = 1
                sectors_needed -= 1

                if sectors_needed == 0:
                    break

        return selected

    def _calculate_position_sizes(self, portfolio_df):
        """
        Calculate position sizes based on combined scores.

        Args:
            portfolio_df: DataFrame of selected stocks

        Returns:
            Dictionary of weights: {symbol: weight}
        """
        weights = {}
        n_stocks = len(portfolio_df)

        if n_stocks == 0:
            return weights

        # Base equal weight
        base_weight = 1.0 / n_stocks

        # Adjust by score
        for _, row in portfolio_df.iterrows():
            symbol = row['symbol']
            score = row['combined_score'] / 100.0  # Normalize to 0-1

            # Weight adjustment based on score: 50% equal weight + 50% score-weighted
            adjusted_weight = base_weight * (0.5 + 0.5 * score)

            # Apply position limits
            adjusted_weight = max(self.min_position, min(self.max_position, adjusted_weight))

            weights[symbol] = adjusted_weight

        return weights

    def _apply_turnover_constraint(self, new_weights):
        """
        Apply maximum turnover constraint.

        Args:
            new_weights: Proposed new weights

        Returns:
            Adjusted weights respecting turnover limit
        """
        # Calculate proposed turnover
        turnover = 0.0
        all_symbols = set(list(self.current_holdings.keys()) + list(new_weights.keys()))

        for symbol in all_symbols:
            old_weight = self.current_holdings.get(symbol, 0.0)
            new_weight = new_weights.get(symbol, 0.0)
            turnover += abs(new_weight - old_weight)

        # If turnover is acceptable, return new weights
        if turnover <= self.max_turnover:
            return new_weights

        # Otherwise, blend old and new weights to reduce turnover
        blend_factor = self.max_turnover / turnover
        blended_weights = {}

        for symbol in all_symbols:
            old_weight = self.current_holdings.get(symbol, 0.0)
            new_weight = new_weights.get(symbol, 0.0)

            # Blend: keep more of old weights to reduce turnover
            blended = old_weight + (new_weight - old_weight) * blend_factor
            if blended > 0.001:  # Minimum threshold
                blended_weights[symbol] = blended

        return blended_weights

    def _normalize_weights(self, weights):
        """
        Normalize weights to sum to 1.0.

        Args:
            weights: Dictionary of weights

        Returns:
            Normalized weights dictionary
        """
        total = sum(weights.values())
        if total == 0:
            return weights

        return {symbol: weight / total for symbol, weight in weights.items()}

    def _normalize_sector_momentum(self, sector_return, min_return=-0.1, max_return=0.1):
        """
        Normalize sector momentum return to 0-1 scale.

        Args:
            sector_return: Sector return (e.g., 0.05 for 5%)
            min_return: Minimum expected return for normalization
            max_return: Maximum expected return for normalization

        Returns:
            Normalized score (0-1)
        """
        # Clip to range
        clipped = max(min_return, min(max_return, sector_return))

        # Normalize to 0-1
        normalized = (clipped - min_return) / (max_return - min_return)

        return normalized

    def calculate_risk_metrics(self, weights, returns_df, volatilities=None):
        """
        Calculate portfolio risk metrics.

        Args:
            weights: Portfolio weights dictionary
            returns_df: DataFrame of historical returns (stocks as columns)
            volatilities: Optional dict of individual stock volatilities

        Returns:
            Dictionary of risk metrics
        """
        # Filter returns to portfolio stocks
        portfolio_symbols = list(weights.keys())
        portfolio_returns = returns_df[portfolio_symbols]

        # Portfolio weights as array
        w = np.array([weights[s] for s in portfolio_symbols])

        # Expected return (simple weighted average)
        mean_returns = portfolio_returns.mean()
        portfolio_return = np.dot(w, mean_returns)

        # Portfolio volatility
        cov_matrix = portfolio_returns.cov()
        portfolio_variance = np.dot(w, np.dot(cov_matrix, w))
        portfolio_volatility = np.sqrt(portfolio_variance)

        # Annualize (assuming daily returns)
        annual_return = portfolio_return * 252
        annual_volatility = portfolio_volatility * np.sqrt(252)

        # Sharpe ratio (assuming 3% risk-free rate for Vietnam)
        risk_free_rate = 0.03
        sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility if annual_volatility > 0 else 0

        return {
            'expected_return_annual': annual_return,
            'volatility_annual': annual_volatility,
            'sharpe_ratio': sharpe_ratio,
            'n_positions': len(weights),
            'avg_position_size': np.mean(list(weights.values())),
            'max_position_size': max(weights.values()) if weights else 0,
            'concentration_hhi': sum([w**2 for w in weights.values()])  # Herfindahl index
        }

    def generate_rebalancing_trades(self, new_weights, current_prices, portfolio_value):
        """
        Generate specific buy/sell orders for rebalancing.

        Args:
            new_weights: Target portfolio weights
            current_prices: Dictionary of current prices {symbol: price}
            portfolio_value: Total portfolio value

        Returns:
            List of trade dictionaries:
                [{'symbol': 'VNM', 'action': 'BUY', 'shares': 100, 'value': 50000}, ...]
        """
        trades = []
        all_symbols = set(list(self.current_holdings.keys()) + list(new_weights.keys()))

        for symbol in all_symbols:
            current_weight = self.current_holdings.get(symbol, 0.0)
            target_weight = new_weights.get(symbol, 0.0)

            if abs(target_weight - current_weight) < 0.001:  # Ignore tiny changes
                continue

            current_value = current_weight * portfolio_value
            target_value = target_weight * portfolio_value
            trade_value = target_value - current_value

            if symbol not in current_prices:
                continue

            price = current_prices[symbol]
            shares = int(trade_value / price)

            if shares == 0:
                continue

            trades.append({
                'symbol': symbol,
                'action': 'BUY' if shares > 0 else 'SELL',
                'shares': abs(shares),
                'price': price,
                'value': abs(trade_value),
                'current_weight': current_weight,
                'target_weight': target_weight
            })

        # Sort by trade value (largest first)
        trades.sort(key=lambda x: x['value'], reverse=True)

        return trades

    def check_risk_limits(self, weights, current_volatility, max_volatility=0.25,
                         max_drawdown=None, current_drawdown=None):
        """
        Check if portfolio respects risk limits.

        Args:
            weights: Portfolio weights
            current_volatility: Current portfolio volatility
            max_volatility: Maximum allowed volatility (default 25%)
            max_drawdown: Maximum allowed drawdown (optional)
            current_drawdown: Current portfolio drawdown (optional)

        Returns:
            Dictionary with risk check results
        """
        checks = {
            'volatility_ok': current_volatility <= max_volatility,
            'current_volatility': current_volatility,
            'max_volatility': max_volatility
        }

        if max_drawdown is not None and current_drawdown is not None:
            checks['drawdown_ok'] = current_drawdown <= max_drawdown
            checks['current_drawdown'] = current_drawdown
            checks['max_drawdown'] = max_drawdown

            # Risk reduction recommendation
            if current_drawdown > 0.15:  # More than 15% drawdown
                checks['recommendation'] = 'REDUCE_EXPOSURE'
                checks['suggested_cash'] = 0.25  # 25% cash
            else:
                checks['recommendation'] = 'MAINTAIN'
                checks['suggested_cash'] = 0.0
        else:
            checks['drawdown_ok'] = True
            checks['recommendation'] = 'MAINTAIN'
            checks['suggested_cash'] = 0.0

        checks['all_ok'] = checks['volatility_ok'] and checks['drawdown_ok']

        return checks

    def get_portfolio_summary(self, weights=None):
        """
        Get summary statistics of current portfolio.

        Args:
            weights: Optional weights to summarize (defaults to current_holdings)

        Returns:
            Dictionary with portfolio summary
        """
        if weights is None:
            weights = self.current_holdings

        if not weights:
            return {
                'n_positions': 0,
                'sectors': {},
                'top_holdings': []
            }

        # Count positions by sector
        sector_weights = defaultdict(float)
        holdings_list = []

        for symbol, weight in weights.items():
            # Note: We'd need sector info passed in for full functionality
            holdings_list.append({'symbol': symbol, 'weight': weight})

        holdings_list.sort(key=lambda x: x['weight'], reverse=True)

        return {
            'n_positions': len(weights),
            'avg_position': np.mean(list(weights.values())),
            'max_position': max(weights.values()),
            'min_position': min(weights.values()),
            'top_5_holdings': holdings_list[:5],
            'concentration_hhi': sum([w**2 for w in weights.values()])
        }
