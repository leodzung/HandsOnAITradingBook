"""
Standalone Vietnam Value-Momentum ML Strategy

This implementation is designed to work with local Vietnamese data sources
and can be integrated with Vietnamese brokers (VPS, SSI, VNDIRECT, etc.)

Data Sources:
- FiinGroup (FiinPro) API - Premium data
- VND Direct API - Market data
- Cafef.vn / Vietstock - Free data (web scraping)
- vnquant library - Python wrapper for Vietnamese stock data

Requirements:
    pip install pandas numpy scikit-learn vnquant (or your preferred data library)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import strategy modules
from fundamental_screener import FundamentalScreener
from ml_predictor import StockDirectionPredictor
from portfolio_manager import PortfolioManager


class VietnamStockStrategy:
    """
    Standalone implementation of Vietnam Value-Momentum ML Strategy.
    """

    def __init__(self,
                 initial_capital=1_000_000_000,  # 1 billion VND
                 target_stocks=20,
                 rebalance_frequency_days=90,
                 transaction_cost=0.004):  # 0.4% round-trip
        """
        Initialize strategy.

        Args:
            initial_capital: Starting capital in VND
            target_stocks: Target number of positions
            rebalance_frequency_days: Days between rebalancing
            transaction_cost: Round-trip transaction cost (default 0.4%)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.target_stocks = target_stocks
        self.rebalance_frequency_days = rebalance_frequency_days
        self.transaction_cost = transaction_cost

        # Initialize strategy components
        self.fundamental_screener = FundamentalScreener(
            min_roe=0.12,
            min_roa=0.05,
            max_debt_equity=2.0,
            min_revenue_growth=0.10
        )

        self.ml_predictor = StockDirectionPredictor(
            lookback_days=90,
            prediction_horizon_days=90,
            min_samples=100,
            model_type='gaussian'
        )

        self.portfolio_manager = PortfolioManager(
            target_stocks=target_stocks,
            fundamental_weight=0.4,
            ml_weight=0.4,
            sector_momentum_weight=0.2
        )

        # State tracking
        self.holdings = {}  # {symbol: shares}
        self.last_rebalance = None
        self.historical_data = {}  # Cached price/volume data
        self.performance_history = []

    def load_universe(self, exchange='HOSE', min_market_cap=1_000_000_000_000,
                     min_avg_volume=500_000_000):
        """
        Load universe of stocks to consider.

        Args:
            exchange: 'HOSE' or 'HNX'
            min_market_cap: Minimum market cap in VND (default 1T VND = ~40M USD)
            min_avg_volume: Minimum average daily trading volume in VND

        Returns:
            List of stock symbols
        """
        # NOTE: This is a placeholder. In production, replace with actual data source:
        #
        # Example with vnquant:
        # from vnquant import DataLoader
        # loader = DataLoader('symbols', 'cafe', start_date, end_date)
        # data = loader.download()
        #
        # Example with FiinGroup API:
        # import requests
        # response = requests.get('https://api.fiingroup.vn/...', headers={...})
        # data = response.json()
        #
        # Example with VND Direct:
        # Use their Python SDK or REST API

        print(f"Loading {exchange} universe...")
        print(f"Filters: Market cap > {min_market_cap:,.0f} VND, Volume > {min_avg_volume:,.0f} VND")

        # Placeholder: Common Vietnamese blue-chip stocks
        # Replace with actual data query
        sample_universe = [
            'VNM', 'VIC', 'VHM', 'VCB', 'BID', 'CTG', 'MBB', 'ACB',
            'HPG', 'MSN', 'FPT', 'POW', 'SAB', 'GAS', 'PLX', 'VJC',
            'VRE', 'TCB', 'SSI', 'HDB', 'VPB', 'MWG', 'VNM', 'REE'
        ]

        print(f"Loaded {len(sample_universe)} stocks from {exchange}")
        return sample_universe

    def fetch_historical_data(self, symbols, start_date, end_date):
        """
        Fetch historical price and volume data.

        Args:
            symbols: List of stock symbols
            start_date: Start date (datetime or string 'YYYY-MM-DD')
            end_date: End date (datetime or string 'YYYY-MM-DD')

        Returns:
            Dictionary of DataFrames: {symbol: df with columns [date, open, high, low, close, volume]}
        """
        print(f"Fetching historical data for {len(symbols)} stocks...")

        # NOTE: Replace with actual data source
        # Example with vnquant:
        # from vnquant import DataLoader
        # data = {}
        # for symbol in symbols:
        #     loader = DataLoader(symbol, 'cafe', start_date, end_date)
        #     df = loader.download()
        #     data[symbol] = df

        # Placeholder: Generate sample data
        data = {}
        for symbol in symbols:
            # In production, replace with actual data fetch
            data[symbol] = self._generate_sample_data(symbol, start_date, end_date)

        self.historical_data = data
        print(f"Loaded historical data for {len(data)} stocks")
        return data

    def fetch_fundamental_data(self, symbols):
        """
        Fetch fundamental data for stocks.

        Args:
            symbols: List of stock symbols

        Returns:
            List of dictionaries with fundamental metrics
        """
        print(f"Fetching fundamental data for {len(symbols)} stocks...")

        # NOTE: Replace with actual data source
        # Example with FiinGroup API:
        # fundamentals = []
        # for symbol in symbols:
        #     response = requests.get(f'https://api.fiingroup.vn/fundamental/{symbol}')
        #     data = response.json()
        #     fundamentals.append({
        #         'symbol': symbol,
        #         'pe_ratio': data['pe'],
        #         'pb_ratio': data['pb'],
        #         'roe': data['roe'],
        #         ...
        #     })

        # Placeholder: Sample fundamental data
        fundamentals = []
        for symbol in symbols:
            fundamentals.append(self._generate_sample_fundamentals(symbol))

        print(f"Loaded fundamentals for {len(fundamentals)} stocks")
        return fundamentals

    def train_model(self, start_date, end_date):
        """
        Train ML model on historical data.

        Args:
            start_date: Training period start
            end_date: Training period end
        """
        print(f"Training ML model from {start_date} to {end_date}...")

        training_samples = []

        for symbol, hist_data in self.historical_data.items():
            if len(hist_data) < 180:
                continue

            # Create training samples
            for i in range(120, len(hist_data) - 90):
                # Features from data up to point i
                price_window = hist_data['close'].iloc[:i]
                volume_window = hist_data['volume'].iloc[:i]

                # Calculate features
                tech_features = self.ml_predictor.calculate_technical_features(
                    price_window, volume_window
                )

                # Simplified fundamentals (in production, use time-series fundamentals)
                fund_features = self.ml_predictor.calculate_fundamental_features({
                    'roe': 0.15,
                    'roa': 0.08,
                    'pe_ratio': 15.0,
                    'pb_ratio': 2.0,
                    'debt_equity': 1.0,
                    'revenue_growth': 0.12,
                    'earnings_growth': 0.10
                })

                sentiment_features = self.ml_predictor.calculate_sentiment_features(
                    0, 0, 0, 0  # Placeholders
                )

                # Combine features
                all_features = {}
                all_features.update(tech_features)
                all_features.update(fund_features)
                all_features.update(sentiment_features)

                # Label: forward return
                current_price = hist_data['close'].iloc[i]
                future_price = hist_data['close'].iloc[i + 90]
                forward_return = (future_price - current_price) / current_price
                all_features['target'] = 1 if forward_return > 0 else 0

                training_samples.append(all_features)

        if len(training_samples) < 100:
            print(f"Insufficient training samples: {len(training_samples)}")
            return False

        # Train model
        training_df = pd.DataFrame(training_samples)
        accuracy = self.ml_predictor.train(training_df)

        print(f"Model trained! Accuracy: {accuracy:.2%}, Samples: {len(training_samples)}")
        return True

    def run_backtest(self, start_date, end_date, universe=None):
        """
        Run historical backtest.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            universe: Optional list of symbols (if None, will load universe)

        Returns:
            DataFrame with backtest results
        """
        print(f"\n=== Running Backtest: {start_date} to {end_date} ===\n")

        # Load universe if not provided
        if universe is None:
            universe = self.load_universe()

        # Fetch data
        self.fetch_historical_data(universe, start_date - timedelta(days=365), end_date)

        # Train model on first 2 years
        train_end = start_date + timedelta(days=730)
        self.train_model(start_date - timedelta(days=365), train_end)

        # Run backtest
        current_date = start_date
        portfolio_values = []

        while current_date <= end_date:
            # Rebalance check
            if self.last_rebalance is None or \
               (current_date - self.last_rebalance).days >= self.rebalance_frequency_days:

                print(f"\n--- Rebalancing on {current_date.date()} ---")
                self._rebalance(current_date, universe)

            # Update portfolio value
            portfolio_value = self._calculate_portfolio_value(current_date)
            portfolio_values.append({
                'date': current_date,
                'portfolio_value': portfolio_value,
                'return': (portfolio_value / self.initial_capital - 1) * 100
            })

            # Move to next day
            current_date += timedelta(days=1)

        # Create results DataFrame
        results_df = pd.DataFrame(portfolio_values)

        # Calculate performance metrics
        self._print_performance_metrics(results_df)

        return results_df

    def _rebalance(self, current_date, universe):
        """Execute rebalancing logic."""

        # Step 1: Fundamental screening
        fundamentals = self.fetch_fundamental_data(universe)
        screened = self.fundamental_screener.screen_stocks(fundamentals)

        if len(screened) < 10:
            print(f"Insufficient candidates: {len(screened)}")
            return

        print(f"Fundamental screening: {len(universe)} -> {len(screened)} stocks")

        # Step 2: ML predictions
        ml_scored = []
        for stock in screened:
            symbol = stock['symbol']
            if symbol not in self.historical_data:
                continue

            hist = self.historical_data[symbol]
            if len(hist) < 90:
                continue

            # Get features
            features = self._extract_current_features(symbol, current_date)
            if features is None:
                continue

            # Predict
            try:
                prediction = self.ml_predictor.predict(features)
                stock['ml_score'] = prediction['probability'] * 100
                ml_scored.append(stock)
            except:
                continue

        print(f"ML predictions: {len(ml_scored)} stocks scored")

        # Step 3: Portfolio construction
        scored_df = self.portfolio_manager.calculate_combined_scores(ml_scored)
        target_weights = self.portfolio_manager.construct_portfolio(scored_df)

        # Step 4: Execute trades
        self._execute_trades(target_weights, current_date)

        self.last_rebalance = current_date

        # Print top holdings
        print(f"Portfolio: {len(target_weights)} positions")
        top_5 = list(target_weights.items())[:5]
        for symbol, weight in top_5:
            print(f"  {symbol}: {weight*100:.1f}%")

    def _extract_current_features(self, symbol, date):
        """Extract features for a symbol at a specific date."""
        hist = self.historical_data[symbol]
        hist_until_date = hist[hist.index <= date]

        if len(hist_until_date) < 90:
            return None

        features = {}

        # Technical features
        tech_features = self.ml_predictor.calculate_technical_features(
            hist_until_date['close'],
            hist_until_date['volume']
        )
        features.update(tech_features)

        # Fundamental features (simplified)
        fund_features = self.ml_predictor.calculate_fundamental_features({
            'roe': 0.15, 'roa': 0.08, 'pe_ratio': 15.0,
            'pb_ratio': 2.0, 'debt_equity': 1.0,
            'revenue_growth': 0.12, 'earnings_growth': 0.10
        })
        features.update(fund_features)

        # Sentiment features
        sentiment_features = self.ml_predictor.calculate_sentiment_features(
            0, 0, 0, 0
        )
        features.update(sentiment_features)

        return pd.Series(features)

    def _execute_trades(self, target_weights, date):
        """Execute trades to reach target portfolio."""
        # Calculate target shares
        portfolio_value = self._calculate_portfolio_value(date)
        target_holdings = {}

        for symbol, weight in target_weights.items():
            if symbol not in self.historical_data:
                continue

            price = self._get_price(symbol, date)
            if price is None or price == 0:
                continue

            target_value = portfolio_value * weight
            target_shares = int(target_value / (price * 100)) * 100  # Round to 100 shares

            if target_shares > 0:
                target_holdings[symbol] = target_shares

        # Calculate trades
        for symbol in set(list(self.holdings.keys()) + list(target_holdings.keys())):
            current_shares = self.holdings.get(symbol, 0)
            target_shares = target_holdings.get(symbol, 0)
            trade_shares = target_shares - current_shares

            if trade_shares != 0:
                price = self._get_price(symbol, date)
                trade_value = abs(trade_shares) * price
                cost = trade_value * self.transaction_cost

                # Update cash
                if trade_shares > 0:  # Buy
                    self.current_capital -= (trade_value + cost)
                else:  # Sell
                    self.current_capital += (trade_value - cost)

        # Update holdings
        self.holdings = target_holdings

    def _calculate_portfolio_value(self, date):
        """Calculate total portfolio value at a date."""
        holdings_value = 0

        for symbol, shares in self.holdings.items():
            price = self._get_price(symbol, date)
            if price:
                holdings_value += shares * price

        return self.current_capital + holdings_value

    def _get_price(self, symbol, date):
        """Get price for a symbol at a date."""
        if symbol not in self.historical_data:
            return None

        hist = self.historical_data[symbol]
        prices_until_date = hist[hist.index <= date]

        if len(prices_until_date) == 0:
            return None

        return prices_until_date['close'].iloc[-1]

    def _print_performance_metrics(self, results_df):
        """Print backtest performance metrics."""
        final_value = results_df['portfolio_value'].iloc[-1]
        total_return = (final_value / self.initial_capital - 1) * 100

        returns = results_df['portfolio_value'].pct_change().dropna()
        annual_return = returns.mean() * 252 * 100
        annual_vol = returns.std() * np.sqrt(252) * 100

        sharpe = (annual_return - 3) / annual_vol if annual_vol > 0 else 0

        max_dd = self._calculate_max_drawdown(results_df['portfolio_value'])

        print("\n=== Performance Metrics ===")
        print(f"Total Return: {total_return:.2f}%")
        print(f"Annual Return: {annual_return:.2f}%")
        print(f"Annual Volatility: {annual_vol:.2f}%")
        print(f"Sharpe Ratio: {sharpe:.2f}")
        print(f"Max Drawdown: {max_dd:.2f}%")
        print(f"Final Portfolio Value: {final_value:,.0f} VND")

    def _calculate_max_drawdown(self, portfolio_values):
        """Calculate maximum drawdown."""
        peak = portfolio_values.expanding(min_periods=1).max()
        drawdown = (portfolio_values - peak) / peak * 100
        return drawdown.min()

    # Helper methods for sample data generation (for demo purposes)
    def _generate_sample_data(self, symbol, start_date, end_date):
        """Generate sample price data (replace with actual data fetch)."""
        dates = pd.date_range(start_date, end_date, freq='D')
        n = len(dates)

        # Random walk with drift
        np.random.seed(hash(symbol) % 2**32)
        returns = np.random.normal(0.0005, 0.02, n)
        prices = 20000 * (1 + returns).cumprod()

        df = pd.DataFrame({
            'open': prices,
            'high': prices * 1.02,
            'low': prices * 0.98,
            'close': prices,
            'volume': np.random.randint(100000, 1000000, n)
        }, index=dates)

        return df

    def _generate_sample_fundamentals(self, symbol):
        """Generate sample fundamental data (replace with actual data fetch)."""
        np.random.seed(hash(symbol) % 2**32)

        return {
            'symbol': symbol,
            'sector': np.random.choice(['Banking', 'Real Estate', 'Consumer Goods', 'Industrials']),
            'pe_ratio': np.random.uniform(8, 20),
            'pb_ratio': np.random.uniform(1, 3.5),
            'roe': np.random.uniform(0.08, 0.25),
            'roa': np.random.uniform(0.03, 0.12),
            'debt_equity': np.random.uniform(0.5, 2.5),
            'current_ratio': np.random.uniform(1.0, 2.5),
            'revenue_growth': np.random.uniform(0.05, 0.25),
            'earnings_growth': np.random.uniform(0.02, 0.30),
            'div_yield': np.random.uniform(0, 0.05),
            'earnings_stability': np.random.randint(4, 9),
            'revenue_growth_consistency': np.random.uniform(0.5, 1.0),
            'market_cap': np.random.uniform(1e12, 50e12),
            'avg_dollar_volume': np.random.uniform(5e8, 5e9)
        }


# Example usage
if __name__ == '__main__':
    print("Vietnam Value-Momentum ML Strategy - Standalone Implementation\n")

    # Initialize strategy
    strategy = VietnamStockStrategy(
        initial_capital=1_000_000_000,  # 1 billion VND
        target_stocks=20,
        rebalance_frequency_days=90
    )

    # Run backtest
    from datetime import datetime
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2024, 10, 1)

    results = strategy.run_backtest(start_date, end_date)

    # Save results
    results.to_csv('backtest_results.csv', index=False)
    print("\nResults saved to backtest_results.csv")
