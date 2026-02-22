"""
Example Usage Scripts for Vietnam Value-Momentum ML Strategy

This file contains practical examples showing how to use the strategy
in different scenarios.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import strategy modules
from fundamental_screener import FundamentalScreener
from ml_predictor import StockDirectionPredictor
from portfolio_manager import PortfolioManager
from standalone_strategy import VietnamStockStrategy


def example_1_fundamental_screening():
    """
    Example 1: Basic fundamental screening
    Use this to screen stocks without ML predictions
    """
    print("=" * 60)
    print("Example 1: Fundamental Screening Only")
    print("=" * 60)

    # Initialize screener
    screener = FundamentalScreener(
        min_roe=0.12,
        min_roa=0.05,
        max_debt_equity=2.0,
        min_revenue_growth=0.10
    )

    # Sample stock data (replace with actual data from your source)
    sample_stocks = [
        {
            'symbol': 'VNM',
            'sector': 'Consumer Goods',
            'pe_ratio': 15.2,
            'pb_ratio': 6.1,
            'roe': 0.35,
            'roa': 0.18,
            'debt_equity': 0.3,
            'current_ratio': 1.8,
            'revenue_growth': 0.12,
            'earnings_growth': 0.15,
            'div_yield': 0.04,
            'earnings_stability': 8,
            'revenue_growth_consistency': 0.875,
            'market_cap': 150_000_000_000_000,  # 150T VND
            'avg_dollar_volume': 2_000_000_000  # 2B VND daily
        },
        {
            'symbol': 'VCB',
            'sector': 'Banking',
            'pe_ratio': 12.5,
            'pb_ratio': 2.8,
            'roe': 0.22,
            'roa': 0.015,
            'debt_equity': 8.5,  # Banks have high leverage
            'current_ratio': 0.9,
            'revenue_growth': 0.18,
            'earnings_growth': 0.20,
            'div_yield': 0.02,
            'earnings_stability': 8,
            'revenue_growth_consistency': 1.0,
            'market_cap': 200_000_000_000_000,
            'avg_dollar_volume': 5_000_000_000
        },
        {
            'symbol': 'HPG',
            'sector': 'Industrials',
            'pe_ratio': 8.5,
            'pb_ratio': 1.2,
            'roe': 0.15,
            'roa': 0.08,
            'debt_equity': 1.2,
            'current_ratio': 1.5,
            'revenue_growth': 0.25,
            'earnings_growth': 0.30,
            'div_yield': 0.01,
            'earnings_stability': 6,
            'revenue_growth_consistency': 0.75,
            'market_cap': 100_000_000_000_000,
            'avg_dollar_volume': 3_000_000_000
        },
        # Add more stocks here...
    ]

    # Screen stocks
    results = screener.screen_stocks(sample_stocks)

    # Display results
    print(f"\nScreened {len(sample_stocks)} stocks")
    print(f"Passed screening: {len(results)} stocks\n")

    print("Top 5 Stocks:")
    print("-" * 80)
    for i, stock in enumerate(results[:5], 1):
        print(f"{i}. {stock['symbol']} ({stock['sector']})")
        print(f"   Combined Score: {stock['combined_score']:.1f}/100")
        print(f"   Value: {stock['value_score']:.1f} | Quality: {stock['quality_score']:.1f} | Growth: {stock['growth_score']:.1f}")
        print(f"   P/E: {stock['pe_ratio']:.1f} | ROE: {stock['roe']*100:.1f}%")
        print()


def example_2_ml_prediction():
    """
    Example 2: Training and using ML predictor
    """
    print("=" * 60)
    print("Example 2: ML Prediction Training")
    print("=" * 60)

    # Initialize predictor
    predictor = StockDirectionPredictor(
        lookback_days=90,
        prediction_horizon_days=90,
        model_type='gaussian'
    )

    # Generate sample training data
    # In production, this comes from historical prices + fundamentals
    np.random.seed(42)
    n_samples = 200

    training_data = []
    for i in range(n_samples):
        sample = {
            # Technical features
            'price_to_ma20': np.random.uniform(0.9, 1.1),
            'price_to_ma50': np.random.uniform(0.8, 1.2),
            'price_to_ma200': np.random.uniform(0.7, 1.3),
            'return_5d': np.random.normal(0, 0.03),
            'return_20d': np.random.normal(0, 0.08),
            'return_60d': np.random.normal(0, 0.15),
            'volatility_20d': np.random.uniform(0.01, 0.04),
            'volatility_60d': np.random.uniform(0.015, 0.05),
            'rsi_14': np.random.uniform(30, 70),
            'macd': np.random.normal(0, 0.5),
            'macd_signal': np.random.normal(0, 0.4),
            'macd_histogram': np.random.normal(0, 0.2),
            'volume_ratio': np.random.uniform(0.7, 1.5),
            'volume_trend': np.random.normal(0, 0.3),
            'price_range_20d': np.random.uniform(0.05, 0.15),

            # Fundamental features
            'roe_current': np.random.uniform(0.08, 0.25),
            'roa_current': np.random.uniform(0.03, 0.12),
            'pe_ratio': np.random.uniform(8, 20),
            'pb_ratio': np.random.uniform(1, 4),
            'debt_equity': np.random.uniform(0.5, 2.0),
            'roe_change': np.random.normal(0, 0.03),
            'revenue_growth': np.random.uniform(0, 0.25),
            'earnings_growth': np.random.uniform(-0.1, 0.3),

            # Sentiment features
            'foreign_flow_ratio': np.random.uniform(-0.5, 0.5),
            'market_return_20d': np.random.normal(0, 0.05),
            'sector_return_20d': np.random.normal(0, 0.06),
            'sector_vs_market': np.random.normal(0, 0.03),

            # Target (1 = positive return, 0 = negative)
            'target': np.random.choice([0, 1], p=[0.45, 0.55])
        }
        training_data.append(sample)

    training_df = pd.DataFrame(training_data)

    # Train model
    print(f"Training on {len(training_df)} samples...")
    accuracy = predictor.train(training_df)
    print(f"Training accuracy: {accuracy:.1%}\n")

    # Make predictions on new data
    print("Making predictions on sample stocks:")
    print("-" * 80)

    sample_features = training_df.drop('target', axis=1).iloc[:5]

    for i, (idx, features) in enumerate(sample_features.iterrows(), 1):
        prediction = predictor.predict(features)

        print(f"Stock {i}:")
        print(f"  Prediction: {'POSITIVE ↑' if prediction['prediction'] == 1 else 'NEGATIVE ↓'}")
        print(f"  Probability: {prediction['probability']*100:.1f}%")
        print(f"  Confidence: {prediction['confidence']*100:.1f}%")
        print()


def example_3_portfolio_construction():
    """
    Example 3: Constructing portfolio from scored stocks
    """
    print("=" * 60)
    print("Example 3: Portfolio Construction")
    print("=" * 60)

    # Initialize portfolio manager
    pm = PortfolioManager(
        target_stocks=20,
        min_position=0.015,
        max_position=0.08,
        max_sector_weight=0.40
    )

    # Sample scored stocks
    scored_stocks = [
        {'symbol': 'VNM', 'sector': 'Consumer Goods', 'fundamental_score': 85,
         'ml_score': 78, 'sector_momentum': 0.05, 'market_cap': 150e12},
        {'symbol': 'VCB', 'sector': 'Banking', 'fundamental_score': 80,
         'ml_score': 82, 'sector_momentum': 0.03, 'market_cap': 200e12},
        {'symbol': 'HPG', 'sector': 'Industrials', 'fundamental_score': 75,
         'ml_score': 70, 'sector_momentum': 0.08, 'market_cap': 100e12},
        {'symbol': 'VIC', 'sector': 'Real Estate', 'fundamental_score': 72,
         'ml_score': 75, 'sector_momentum': 0.02, 'market_cap': 180e12},
        {'symbol': 'FPT', 'sector': 'Technology', 'fundamental_score': 78,
         'ml_score': 80, 'sector_momentum': 0.06, 'market_cap': 80e12},
        {'symbol': 'MSN', 'sector': 'Consumer Goods', 'fundamental_score': 70,
         'ml_score': 72, 'sector_momentum': 0.05, 'market_cap': 90e12},
        {'symbol': 'GAS', 'sector': 'Energy', 'fundamental_score': 68,
         'ml_score': 65, 'sector_momentum': 0.01, 'market_cap': 120e12},
        {'symbol': 'VHM', 'sector': 'Real Estate', 'fundamental_score': 65,
         'ml_score': 70, 'sector_momentum': 0.02, 'market_cap': 140e12},
        # Add more for realistic portfolio...
    ]

    # Calculate combined scores
    scored_df = pm.calculate_combined_scores(scored_stocks)

    print(f"Scored {len(scored_df)} stocks\n")
    print("Top 5 by Combined Score:")
    print(scored_df[['symbol', 'sector', 'fundamental_score', 'ml_score', 'combined_score']].head())

    # Construct portfolio
    weights = pm.construct_portfolio(scored_df)

    print(f"\nPortfolio constructed: {len(weights)} positions")
    print("\nPortfolio Weights:")
    print("-" * 60)

    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    for symbol, weight in sorted_weights:
        print(f"{symbol:6s}: {weight*100:5.2f}%")

    # Portfolio summary
    summary = pm.get_portfolio_summary(weights)
    print(f"\nPortfolio Summary:")
    print(f"  Positions: {summary['n_positions']}")
    print(f"  Avg position: {summary['avg_position']*100:.2f}%")
    print(f"  Max position: {summary['max_position']*100:.2f}%")
    print(f"  Concentration (HHI): {summary['concentration_hhi']:.4f}")


def example_4_full_backtest():
    """
    Example 4: Running a complete backtest
    """
    print("=" * 60)
    print("Example 4: Full Backtest")
    print("=" * 60)

    # Initialize strategy
    strategy = VietnamStockStrategy(
        initial_capital=1_000_000_000,  # 1 billion VND
        target_stocks=20,
        rebalance_frequency_days=90,
        transaction_cost=0.004
    )

    # Define backtest period
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2024, 10, 1)

    print(f"Backtest period: {start_date.date()} to {end_date.date()}")
    print(f"Initial capital: {strategy.initial_capital:,.0f} VND\n")

    # Run backtest (uses sample data in demo mode)
    results = strategy.run_backtest(start_date, end_date)

    # Show results
    print("\nBacktest completed!")
    print(f"Final portfolio value: {results['portfolio_value'].iloc[-1]:,.0f} VND")
    print(f"Total return: {results['return'].iloc[-1]:.2f}%")

    # Show equity curve (last 10 data points)
    print("\nEquity Curve (last 10 periods):")
    print(results[['date', 'portfolio_value', 'return']].tail(10))

    # Save results
    results.to_csv('vietnam_backtest_results.csv', index=False)
    print("\nResults saved to vietnam_backtest_results.csv")


def example_5_parameter_optimization():
    """
    Example 5: Testing different parameter combinations
    """
    print("=" * 60)
    print("Example 5: Parameter Optimization")
    print("=" * 60)

    # Test different configurations
    configs = [
        {
            'name': 'Conservative',
            'min_roe': 0.15,
            'min_roa': 0.08,
            'max_debt_equity': 1.5,
            'target_stocks': 25,
            'max_position': 0.06
        },
        {
            'name': 'Balanced',
            'min_roe': 0.12,
            'min_roa': 0.05,
            'max_debt_equity': 2.0,
            'target_stocks': 20,
            'max_position': 0.08
        },
        {
            'name': 'Aggressive',
            'min_roe': 0.10,
            'min_roa': 0.03,
            'max_debt_equity': 2.5,
            'target_stocks': 15,
            'max_position': 0.10
        }
    ]

    print("Testing 3 configurations...\n")

    results_summary = []

    for config in configs:
        print(f"Testing {config['name']} configuration...")

        # This would run actual backtest with config
        # For demo, just show configuration
        print(f"  Min ROE: {config['min_roe']*100:.0f}%")
        print(f"  Target stocks: {config['target_stocks']}")
        print(f"  Max position: {config['max_position']*100:.0f}%")

        # Simulate results (in production, run actual backtest)
        simulated_return = np.random.uniform(10, 25)
        simulated_sharpe = np.random.uniform(0.5, 1.2)
        simulated_drawdown = np.random.uniform(-30, -15)

        results_summary.append({
            'Configuration': config['name'],
            'Return (%)': simulated_return,
            'Sharpe Ratio': simulated_sharpe,
            'Max Drawdown (%)': simulated_drawdown
        })
        print(f"  Return: {simulated_return:.1f}%")
        print(f"  Sharpe: {simulated_sharpe:.2f}")
        print(f"  Max DD: {simulated_drawdown:.1f}%\n")

    # Summary table
    results_df = pd.DataFrame(results_summary)
    print("Results Summary:")
    print(results_df.to_string(index=False))

    print("\n✅ Best configuration: Based on your risk tolerance and return targets")


# Main execution
if __name__ == '__main__':
    print("\n")
    print("=" * 70)
    print("VIETNAM VALUE-MOMENTUM ML STRATEGY - USAGE EXAMPLES")
    print("=" * 70)
    print("\nThis script demonstrates how to use the strategy components.")
    print("Each example can be run independently.\n")

    # Run examples
    examples = [
        ('1', 'Fundamental Screening', example_1_fundamental_screening),
        ('2', 'ML Prediction', example_2_ml_prediction),
        ('3', 'Portfolio Construction', example_3_portfolio_construction),
        ('4', 'Full Backtest', example_4_full_backtest),
        ('5', 'Parameter Optimization', example_5_parameter_optimization),
    ]

    print("Available examples:")
    for num, name, _ in examples:
        print(f"  {num}. {name}")

    print("\nRunning all examples...")
    print()

    for num, name, func in examples:
        try:
            func()
            print("\n" + "✅ " + name + " completed successfully\n")
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}\n")

        input("Press Enter to continue to next example...")

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Review the code in each example")
    print("2. Modify parameters to match your preferences")
    print("3. Integrate with real Vietnamese market data")
    print("4. Run backtests on historical data")
    print("5. Paper trade before going live")
    print("\nGood luck with your trading! 📈")
