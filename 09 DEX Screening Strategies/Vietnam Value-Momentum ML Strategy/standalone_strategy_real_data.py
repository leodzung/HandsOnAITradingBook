"""
Standalone Vietnam Value-Momentum ML Strategy with REAL DATA

This version integrates with real Vietnamese stock market data using vnstock3.

Installation:
    pip install pandas numpy scikit-learn vnstock3

Usage:
    python standalone_strategy_real_data.py
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
from data_provider import VietnamDataProvider


class VietnamStockStrategyRealData:
    """
    Standalone implementation of Vietnam Value-Momentum ML Strategy using REAL data.
    """

    def __init__(self,
                 initial_capital=1_000_000_000,  # 1 billion VND
                 target_stocks=20,
                 rebalance_frequency_days=90,
                 transaction_cost=0.004,  # 0.4% round-trip
                 data_source='vnstock',
                 api_key=None):
        """
        Initialize strategy with real data integration.

        Args:
            initial_capital: Starting capital in VND
            target_stocks: Target number of positions
            rebalance_frequency_days: Days between rebalancing
            transaction_cost: Round-trip transaction cost (default 0.4%)
            data_source: 'vnstock' (free) or 'fiingroup' (premium)
            api_key: API key for premium sources (FiinGroup)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.target_stocks = target_stocks
        self.rebalance_frequency_days = rebalance_frequency_days
        self.transaction_cost = transaction_cost

        # Initialize data provider
        print("Initializing data provider...")
        self.data_provider = VietnamDataProvider(
            data_source=data_source,
            api_key=api_key,
            enable_cache=True
        )

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
        self.fundamentals_data = []  # Cached fundamental data
        self.performance_history = []
        self.universe = []

    def load_universe(self, exchange='HOSE', min_market_cap=1_000_000_000_000,
                     min_avg_volume=500_000_000):
        """
        Load universe of stocks from real Vietnamese exchanges.

        Args:
            exchange: 'HOSE' or 'HNX'
            min_market_cap: Minimum market cap in VND (default 1T VND = ~40M USD)
            min_avg_volume: Minimum average daily trading volume in VND

        Returns:
            List of stock symbols
        """
        print(f"\n{'='*70}")
        print(f"LOADING {exchange} UNIVERSE")
        print('='*70)

        # Get stock listing from data provider
        self.universe = self.data_provider.get_stock_listing(
            exchange=exchange,
            min_market_cap=min_market_cap,
            min_avg_volume=min_avg_volume
        )

        print(f"✅ Loaded {len(self.universe)} stocks from {exchange}")
        return self.universe

    def load_historical_data(self, start_date, end_date):
        """
        Load historical price data for the universe.

        Args:
            start_date: Start date (datetime or string 'YYYY-MM-DD')
            end_date: End date (datetime or string 'YYYY-MM-DD')
        """
        if not self.universe:
            print("❌ Universe not loaded. Call load_universe() first.")
            return

        # Convert dates to strings if needed
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, datetime):
            end_date = end_date.strftime('%Y-%m-%d')

        print(f"\n{'='*70}")
        print(f"LOADING HISTORICAL DATA")
        print('='*70)

        # Fetch historical data from data provider
        self.historical_data = self.data_provider.get_historical_data(
            self.universe,
            start_date,
            end_date
        )

        print(f"✅ Loaded historical data for {len(self.historical_data)} stocks")

    def load_fundamental_data(self):
        """
        Load fundamental data for the universe.
        """
        if not self.universe:
            print("❌ Universe not loaded. Call load_universe() first.")
            return

        print(f"\n{'='*70}")
        print(f"LOADING FUNDAMENTAL DATA")
        print('='*70)

        # Fetch fundamental data from data provider
        self.fundamentals_data = self.data_provider.get_fundamental_data(self.universe)

        # Filter out None entries
        self.fundamentals_data = [f for f in self.fundamentals_data if f is not None]

        print(f"✅ Loaded fundamentals for {len(self.fundamentals_data)} stocks")

    def train_model(self, train_start_date, train_end_date):
        """
        Train ML model on historical data.

        Args:
            train_start_date: Training period start
            train_end_date: Training period end
        """
        print(f"\n{'='*70}")
        print(f"TRAINING ML MODEL")
        print('='*70)
        print(f"Training period: {train_start_date} to {train_end_date}")

        training_samples = []

        for symbol, hist_data in self.historical_data.items():
            if len(hist_data) < 180:  # Need enough history
                continue

            # Create training samples from historical data
            for i in range(120, len(hist_data) - 90):
                try:
                    # Features from data up to point i
                    price_window = hist_data['close'].iloc[:i]
                    volume_window = hist_data['volume'].iloc[:i]

                    # Calculate features
                    tech_features = self.ml_predictor.calculate_technical_features(
                        price_window, volume_window
                    )

                    # Simplified fundamentals (could enhance with time-series fundamentals)
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
                        0, 0, 0, 0  # Placeholders for foreign flow data
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

                except Exception as e:
                    continue

        if len(training_samples) < self.ml_predictor.min_samples:
            print(f"❌ Insufficient training samples: {len(training_samples)}")
            print(f"   Need at least {self.ml_predictor.min_samples} samples")
            return False

        # Train model
        training_df = pd.DataFrame(training_samples)
        accuracy = self.ml_predictor.train(training_df)

        print(f"✅ Model trained successfully!")
        print(f"   Training samples: {len(training_samples):,}")
        print(f"   Training accuracy: {accuracy:.2%}")

        return True

    def run_backtest(self, start_date, end_date, universe=None):
        """
        Run historical backtest with REAL Vietnamese data.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            universe: Optional list of symbols (if None, will load from exchange)

        Returns:
            DataFrame with backtest results
        """
        print(f"\n{'='*70}")
        print(f"RUNNING BACKTEST WITH REAL DATA")
        print('='*70)
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Initial capital: {self.initial_capital:,.0f} VND\n")

        # Load universe if not provided
        if universe is None:
            self.load_universe('HOSE')
        else:
            self.universe = universe

        # Load historical data (include extra time for training)
        train_start = start_date - timedelta(days=365)
        self.load_historical_data(train_start, end_date)

        # Load fundamental data
        self.load_fundamental_data()

        # Train model on first period
        train_end = start_date + timedelta(days=365)
        trained = self.train_model(train_start, train_end)

        if not trained:
            print("❌ Model training failed. Cannot proceed with backtest.")
            return pd.DataFrame()

        # Run backtest simulation
        print(f"\n{'='*70}")
        print(f"SIMULATING TRADING")
        print('='*70)

        current_date = start_date
        portfolio_values = []
        rebalance_dates = []

        while current_date <= end_date:
            # Rebalance check
            if self.last_rebalance is None or \
               (current_date - self.last_rebalance).days >= self.rebalance_frequency_days:

                print(f"\n--- Rebalancing on {current_date.date()} ---")
                self._rebalance(current_date)
                rebalance_dates.append(current_date)

            # Update portfolio value
            portfolio_value = self._calculate_portfolio_value(current_date)

            if portfolio_value > 0:
                portfolio_values.append({
                    'date': current_date,
                    'portfolio_value': portfolio_value,
                    'return': (portfolio_value / self.initial_capital - 1) * 100,
                    'cash': self.current_capital,
                    'invested': portfolio_value - self.current_capital
                })

            # Move to next trading day (skip weekends)
            current_date += timedelta(days=1)
            while current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                current_date += timedelta(days=1)

        # Create results DataFrame
        results_df = pd.DataFrame(portfolio_values)

        if results_df.empty:
            print("❌ No backtest results generated")
            return results_df

        # Calculate and print performance metrics
        print(f"\n{'='*70}")
        print(f"BACKTEST RESULTS")
        print('='*70)
        self._print_performance_metrics(results_df)

        print(f"\nRebalancing dates: {len(rebalance_dates)}")
        for rdate in rebalance_dates:
            print(f"  - {rdate.date()}")

        return results_df

    def _rebalance(self, current_date):
        """Execute rebalancing logic with real data."""

        # Step 1: Fundamental screening
        screened = self.fundamental_screener.screen_stocks(self.fundamentals_data)

        if len(screened) < 10:
            print(f"⚠️ Insufficient candidates after screening: {len(screened)}")
            return

        print(f"  Fundamental screening: {len(self.fundamentals_data)} → {len(screened)} stocks")

        # Step 2: ML predictions
        ml_scored = []
        for stock in screened:
            symbol = stock['symbol']
            if symbol not in self.historical_data:
                continue

            hist = self.historical_data[symbol]
            if len(hist) < 90:
                continue

            # Get features at current date
            features = self._extract_current_features(symbol, current_date)
            if features is None:
                continue

            # Predict
            try:
                prediction = self.ml_predictor.predict(features)
                stock['ml_score'] = prediction['probability'] * 100
                stock['sector_momentum'] = 0.02  # Placeholder
                ml_scored.append(stock)
            except:
                continue

        if len(ml_scored) < 5:
            print(f"⚠️ Insufficient ML predictions: {len(ml_scored)}")
            return

        print(f"  ML predictions: {len(ml_scored)} stocks scored")

        # Step 3: Portfolio construction
        scored_df = self.portfolio_manager.calculate_combined_scores(ml_scored)
        target_weights = self.portfolio_manager.construct_portfolio(scored_df)

        # Step 4: Execute trades
        self._execute_trades(target_weights, current_date)

        self.last_rebalance = current_date

        # Print portfolio summary
        print(f"  Portfolio: {len(target_weights)} positions")
        top_5 = sorted(target_weights.items(), key=lambda x: x[1], reverse=True)[:5]
        for symbol, weight in top_5:
            print(f"    {symbol}: {weight*100:.1f}%")

    def _extract_current_features(self, symbol, date):
        """Extract features for a symbol at a specific date."""
        hist = self.historical_data[symbol]
        hist_until_date = hist[hist.index <= pd.Timestamp(date)]

        if len(hist_until_date) < 90:
            return None

        features = {}

        # Technical features
        tech_features = self.ml_predictor.calculate_technical_features(
            hist_until_date['close'],
            hist_until_date['volume']
        )
        features.update(tech_features)

        # Fundamental features
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
        portfolio_value = self._calculate_portfolio_value(date)
        target_holdings = {}

        for symbol, weight in target_weights.items():
            if symbol not in self.historical_data:
                continue

            price = self._get_price(symbol, date)
            if price is None or price == 0:
                continue

            target_value = portfolio_value * weight
            # Round to board lots (100 shares in Vietnam)
            target_shares = int(target_value / (price * 100)) * 100

            if target_shares > 0:
                target_holdings[symbol] = target_shares

        # Calculate trades and costs
        total_trade_value = 0
        for symbol in set(list(self.holdings.keys()) + list(target_holdings.keys())):
            current_shares = self.holdings.get(symbol, 0)
            target_shares = target_holdings.get(symbol, 0)
            trade_shares = target_shares - current_shares

            if trade_shares != 0:
                price = self._get_price(symbol, date)
                if price:
                    trade_value = abs(trade_shares) * price
                    cost = trade_value * self.transaction_cost
                    total_trade_value += trade_value

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
        prices_until_date = hist[hist.index <= pd.Timestamp(date)]

        if len(prices_until_date) == 0:
            return None

        return prices_until_date['close'].iloc[-1]

    def _print_performance_metrics(self, results_df):
        """Print backtest performance metrics."""
        if results_df.empty:
            return

        final_value = results_df['portfolio_value'].iloc[-1]
        initial_value = results_df['portfolio_value'].iloc[0]
        total_return = (final_value / initial_value - 1) * 100

        # Calculate returns
        returns = results_df['portfolio_value'].pct_change().dropna()

        # Annualized metrics
        days_elapsed = (results_df['date'].iloc[-1] - results_df['date'].iloc[0]).days
        years = days_elapsed / 365.25
        annual_return = ((final_value / initial_value) ** (1/years) - 1) * 100 if years > 0 else 0

        annual_vol = returns.std() * np.sqrt(252) * 100 if len(returns) > 1 else 0

        # Sharpe ratio (assuming 3% risk-free rate for Vietnam)
        sharpe = (annual_return - 3) / annual_vol if annual_vol > 0 else 0

        # Max drawdown
        max_dd = self._calculate_max_drawdown(results_df['portfolio_value'])

        # Win rate (profitable periods)
        positive_returns = (returns > 0).sum()
        win_rate = positive_returns / len(returns) * 100 if len(returns) > 0 else 0

        print(f"\n📊 Performance Summary:")
        print(f"   Total Return:        {total_return:>8.2f}%")
        print(f"   Annual Return:       {annual_return:>8.2f}%")
        print(f"   Annual Volatility:   {annual_vol:>8.2f}%")
        print(f"   Sharpe Ratio:        {sharpe:>8.2f}")
        print(f"   Max Drawdown:        {max_dd:>8.2f}%")
        print(f"   Win Rate:            {win_rate:>8.1f}%")
        print(f"\n💰 Portfolio Values:")
        print(f"   Initial:             {initial_value:>15,.0f} VND")
        print(f"   Final:               {final_value:>15,.0f} VND")
        print(f"   Profit/Loss:         {final_value-initial_value:>15,.0f} VND")

    def _calculate_max_drawdown(self, portfolio_values):
        """Calculate maximum drawdown."""
        peak = portfolio_values.expanding(min_periods=1).max()
        drawdown = (portfolio_values - peak) / peak * 100
        return drawdown.min()

    def save_results(self, results_df, filename='backtest_results.csv'):
        """Save backtest results to CSV."""
        results_df.to_csv(filename, index=False)
        print(f"\n💾 Results saved to {filename}")


# Main execution
if __name__ == '__main__':
    print("\n")
    print("=" * 70)
    print("VIETNAM VALUE-MOMENTUM ML STRATEGY")
    print("WITH REAL VIETNAMESE STOCK DATA")
    print("=" * 70)

    # Initialize strategy with real data
    strategy = VietnamStockStrategyRealData(
        initial_capital=1_000_000_000,  # 1 billion VND
        target_stocks=20,
        rebalance_frequency_days=90,
        data_source='vnstock'  # Free Vietnamese data source
    )

    # Define backtest period
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 10, 31)

    # Run backtest
    results = strategy.run_backtest(start_date, end_date)

    # Save results
    if not results.empty:
        strategy.save_results(results, 'vietnam_backtest_real_data.csv')

        # Plot results (if matplotlib is available)
        try:
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

            # Portfolio value
            ax1.plot(results['date'], results['portfolio_value'] / 1_000_000, linewidth=2)
            ax1.set_title('Portfolio Value Over Time', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Portfolio Value (Million VND)')
            ax1.grid(True, alpha=0.3)
            ax1.axhline(y=1000, color='r', linestyle='--', label='Initial Capital')
            ax1.legend()

            # Returns
            ax2.plot(results['date'], results['return'], linewidth=2, color='green')
            ax2.set_title('Cumulative Returns', fontsize=14, fontweight='bold')
            ax2.set_ylabel('Return (%)')
            ax2.set_xlabel('Date')
            ax2.grid(True, alpha=0.3)
            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

            plt.tight_layout()
            plt.savefig('vietnam_backtest_results.png', dpi=150)
            print("📊 Chart saved to vietnam_backtest_results.png")

        except ImportError:
            print("ℹ️ Install matplotlib to generate charts: pip install matplotlib")

    print("\n" + "=" * 70)
    print("✅ BACKTEST COMPLETED")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Review the results in the CSV file")
    print("2. Analyze the performance metrics")
    print("3. Adjust strategy parameters if needed")
    print("4. Try paper trading before going live")
    print("\nGood luck with your Vietnamese stock investing! 🇻🇳📈\n")
