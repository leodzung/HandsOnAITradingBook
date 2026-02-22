"""
Regime-Aware Backtest with Real Vietnamese Data

This version detects market regime (bull/bear/choppy) and applies
different strategies accordingly:
- BULL: Concentrated (5 stocks, top 3, 33% each)
- CHOPPY: Diversified (15 stocks, top 5, 20% each)
- BEAR: Defensive (cash or dividend stocks)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from data_provider import VietnamDataProvider
from ml_predictor import StockDirectionPredictor
from market_regime import MarketRegimeDetector


def run_regime_aware_backtest(year=2024):
    """Run regime-aware backtest for a specific year."""

    if year == 2024:
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 10, 31)
    elif year == 2023:
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
    elif year == 2022:
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2022, 12, 31)
    else:
        raise ValueError(f"Year {year} not supported")

    print("\n" + "=" * 70)
    print(f"REGIME-AWARE BACKTEST - {year}")
    print("=" * 70)

    # Settings
    initial_capital = 100_000_000  # 100M VND

    # Define universes
    concentrated_universe = ['VNM', 'VCB', 'HPG', 'FPT', 'MSN']
    diversified_universe = [
        'VNM', 'VCB', 'HPG', 'FPT', 'MSN',
        'GAS', 'PLX', 'SAB', 'POW', 'BID',
        'VHM', 'VIC', 'MWG', 'TCB', 'CTG'
    ]
    defensive_stocks = ['VNM', 'VCB', 'GAS']  # Dividend aristocrats

    print(f"\n📋 Backtest Configuration:")
    print(f"   Initial capital: {initial_capital:,} VND")
    print(f"   Period: {start_date.date()} to {end_date.date()}")
    print(f"   Concentrated universe: {len(concentrated_universe)} stocks")
    print(f"   Diversified universe: {len(diversified_universe)} stocks")

    # Initialize data provider
    print(f"\n{'='*70}")
    print("STEP 1: Initialize Data Provider & Regime Detector")
    print('='*70)

    provider = VietnamDataProvider(data_source='vnstock', enable_cache=True)
    regime_detector = MarketRegimeDetector(provider)

    # Load VN-Index data for regime detection
    print("\nLoading market index data for regime detection...")
    regime_detector.load_vnindex_data(start_date, end_date)

    # Load historical data for both universes
    print(f"\n{'='*70}")
    print("STEP 2: Load Historical Price Data")
    print('='*70)

    train_start = start_date - timedelta(days=365)
    train_start_str = train_start.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    # Load diversified universe (includes all concentrated stocks)
    all_stocks_data = provider.get_historical_data(
        symbols=diversified_universe,
        start_date=train_start_str,
        end_date=end_str,
        resolution='D'
    )

    if not all_stocks_data:
        print("❌ Failed to load stock data")
        return None

    print(f"✅ Loaded data for {len(all_stocks_data)} stocks")

    # Train ML predictor
    print(f"\n{'='*70}")
    print("STEP 3: Train ML Model")
    print('='*70)

    predictor = StockDirectionPredictor(
        lookback_days=90,
        prediction_horizon_days=60,
        min_samples=100,
        model_type='gaussian'
    )

    # Prepare training data
    training_samples = []
    for symbol, hist_data in all_stocks_data.items():
        if hist_data is None or len(hist_data) < 200:
            continue

        # Use data before backtest start for training
        training_data = hist_data[hist_data.index < start_date]

        for i in range(100, len(training_data) - 60):
            try:
                # Technical features
                lookback = training_data.iloc[i-90:i]
                tech_features = predictor.calculate_technical_features(
                    lookback['close'],
                    lookback['volume']
                )

                # Simplified fundamental features (defaults)
                fund_features = predictor.calculate_fundamental_features({
                    'roe': 0.15, 'roa': 0.08, 'pe_ratio': 15.0,
                    'pb_ratio': 2.0, 'debt_equity': 1.0,
                    'revenue_growth': 0.12, 'earnings_growth': 0.10
                })

                # Sentiment (neutral)
                sentiment_features = {'sentiment_score': 0.0}

                all_features = {}
                all_features.update(tech_features)
                all_features.update(fund_features)
                all_features.update(sentiment_features)

                # Label
                current_price = training_data['close'].iloc[i]
                future_price = training_data['close'].iloc[i + 60]
                forward_return = (future_price - current_price) / current_price
                all_features['target'] = 1 if forward_return > 0 else 0

                training_samples.append(all_features)
            except:
                continue

    if len(training_samples) < 100:
        print(f"❌ Insufficient training samples: {len(training_samples)}")
        return None

    training_df = pd.DataFrame(training_samples)
    accuracy = predictor.train(training_df)

    print(f"✅ Model trained successfully!")
    print(f"   Training samples: {len(training_samples):,}")
    print(f"   Accuracy: {accuracy:.2%}")

    # Run backtest
    print(f"\n{'='*70}")
    print("STEP 4: Run Regime-Aware Backtest")
    print('='*70)

    portfolio_value = initial_capital
    cash = initial_capital
    holdings = {}
    results = []
    regime_changes = []

    rebalance_interval = 90
    last_rebalance = start_date
    current_regime = None

    # Get all trading days
    sample_stock = list(all_stocks_data.values())[0]
    trading_days = sample_stock[
        (sample_stock.index >= start_date) & (sample_stock.index <= end_date)
    ].index

    for current_date in trading_days:
        # Check if it's time to rebalance
        days_since_rebalance = (current_date - last_rebalance).days

        if days_since_rebalance >= rebalance_interval or current_date == trading_days[0]:
            print(f"\n🔄 Rebalancing on {current_date.date()}")

            # Detect current market regime
            regime_details = regime_detector.get_regime_details(current_date)
            detected_regime = regime_details.get('regime', 'choppy')

            if current_regime != detected_regime:
                print(f"   📊 Regime: {detected_regime.upper()} (was: {current_regime or 'N/A'})")
                if 'confidence' in regime_details:
                    print(f"   Confidence: {regime_details['confidence']}")
                regime_changes.append({
                    'date': current_date,
                    'from': current_regime,
                    'to': detected_regime,
                    'details': regime_details
                })
                current_regime = detected_regime

            # Sell all current holdings
            sell_value = 0
            for symbol, shares in holdings.items():
                if symbol in all_stocks_data:
                    stock_data = all_stocks_data[symbol]
                    price_data = stock_data[stock_data.index == current_date]
                    if len(price_data) > 0:
                        price = price_data['close'].iloc[0]
                        value = shares * price
                        sell_value += value * 0.996  # 0.4% transaction cost
            cash += sell_value
            holdings = {}

            # Choose strategy based on regime
            if detected_regime == 'bull':
                # BULL: Concentrated strategy
                universe = concentrated_universe
                num_stocks = 3
                strategy_name = "Concentrated"
            elif detected_regime == 'choppy':
                # CHOPPY: Diversified strategy
                universe = diversified_universe
                num_stocks = 5
                strategy_name = "Diversified"
            else:  # bear
                # BEAR: Defensive/Cash
                universe = defensive_stocks
                num_stocks = 2
                strategy_name = "Defensive"

            print(f"   Strategy: {strategy_name} ({len(universe)} stocks, select top {num_stocks})")

            # Make predictions for universe
            all_predictions = {}  # Track all predictions
            for symbol in universe:
                if symbol not in all_stocks_data:
                    continue

                stock_data = all_stocks_data[symbol]
                recent_data = stock_data[stock_data.index <= current_date].tail(90)

                if len(recent_data) < 90:
                    continue

                try:
                    tech_features = predictor.calculate_technical_features(
                        recent_data['close'],
                        recent_data['volume']
                    )
                    fund_features = predictor.calculate_fundamental_features({
                        'roe': 0.15, 'roa': 0.08, 'pe_ratio': 15.0,
                        'pb_ratio': 2.0, 'debt_equity': 1.0,
                        'revenue_growth': 0.12, 'earnings_growth': 0.10
                    })
                    sentiment_features = {'sentiment_score': 0.0}

                    all_features = {}
                    all_features.update(tech_features)
                    all_features.update(fund_features)
                    all_features.update(sentiment_features)

                    pred = predictor.predict(pd.Series(all_features))
                    all_predictions[symbol] = pred['probability']
                except:
                    continue

            # Always select top stocks by probability
            # In bear market, stay in cash
            print(f"   Predictions calculated for {len(all_predictions)} stocks")
            if detected_regime == 'bear':
                predictions = {}  # Stay in cash during bear markets
                print(f"   BEAR market detected - staying in cash for safety")
            elif all_predictions:
                # Select top stocks by probability
                sorted_preds = sorted(all_predictions.items(), key=lambda x: x[1], reverse=True)
                predictions = {s: p for s, p in sorted_preds[:num_stocks]}
                print(f"   Top predictions: {[(s, f'{p:.3f}') for s, p in sorted_preds[:3]]}")
            else:
                predictions = {}
                print(f"   WARNING: No predictions calculated!")

            # Buy new holdings based on regime
            if detected_regime == 'bear':
                # In bear market, only invest 30% of capital
                invest_amount = cash * 0.30
            else:
                # In bull/choppy, invest 100%
                invest_amount = cash

            if predictions:
                sorted_preds = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
                selected_stocks = [s for s, _ in sorted_preds]

                print(f"   Selected: {selected_stocks}")

                weight = invest_amount / len(selected_stocks)

                for symbol in selected_stocks:
                    stock_data = all_stocks_data[symbol]
                    price_data = stock_data[stock_data.index == current_date]

                    if len(price_data) > 0:
                        price = price_data['close'].iloc[0]
                        shares = int((weight * 0.996) / price)  # 0.4% transaction cost
                        if shares > 0:
                            holdings[symbol] = shares
                            cash -= shares * price * 1.004  # Include transaction cost
            else:
                print(f"   No predictions available - staying in cash")

            # Always update last_rebalance to prevent daily rebalancing
            last_rebalance = current_date

        # Calculate daily portfolio value
        holdings_value = 0
        for symbol, shares in holdings.items():
            stock_data = all_stocks_data[symbol]
            price_data = stock_data[stock_data.index == current_date]
            if len(price_data) > 0:
                price = price_data['close'].iloc[0]
                holdings_value += shares * price

        portfolio_value = cash + holdings_value
        daily_return = ((portfolio_value - initial_capital) / initial_capital) * 100

        results.append({
            'date': current_date,
            'value': portfolio_value,
            'return': daily_return,
            'cash': cash,
            'holdings_value': holdings_value,
            'regime': current_regime
        })

    # Convert to DataFrame
    results_df = pd.DataFrame(results)

    # Calculate metrics
    final_return = results_df['return'].iloc[-1]
    returns_series = results_df['return'].pct_change().dropna()
    annual_return = ((1 + final_return/100) ** (365 / len(results_df)) - 1) * 100
    volatility = returns_series.std() * np.sqrt(252) * 100
    sharpe = (annual_return - 0) / volatility if volatility > 0 else 0
    max_dd = (results_df['value'] / results_df['value'].cummax() - 1).min() * 100

    # Print results
    print(f"\n{'='*70}")
    print("REGIME-AWARE BACKTEST RESULTS")
    print('='*70)

    print(f"\n📊 Performance Summary:")
    print(f"   Total Return:          {final_return:+.2f}%")
    print(f"   Annual Return:         {annual_return:+.2f}%")
    print(f"   Annual Volatility:     {volatility:.2f}%")
    print(f"   Sharpe Ratio:          {sharpe:.2f}")
    print(f"   Max Drawdown:          {max_dd:.2f}%")

    print(f"\n💰 Portfolio Values:")
    print(f"   Initial:                 {initial_capital:,} VND")
    print(f"   Final:                   {int(results_df['value'].iloc[-1]):,} VND")
    print(f"   Profit/Loss:             {int(results_df['value'].iloc[-1] - initial_capital):+,} VND")

    print(f"\n🎯 Regime Summary:")
    regime_counts = results_df['regime'].value_counts()
    for regime, count in regime_counts.items():
        pct = (count / len(results_df)) * 100
        print(f"   {regime.upper()}: {count} days ({pct:.1f}%)")

    print(f"\n🔄 Regime Changes: {len(regime_changes)}")
    for change in regime_changes:
        print(f"   {change['date'].date()}: {change['from'] or 'START'} → {change['to']}")

    # Save results
    filename = f"regime_aware_{year}_results.csv"
    results_df.to_csv(filename, index=False)
    print(f"\n💾 Results saved to {filename}")

    print(f"\n{'='*70}")
    print("✅ REGIME-AWARE BACKTEST COMPLETED!")
    print('='*70)

    return {
        'results_df': results_df,
        'metrics': {
            'total_return': final_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe': sharpe,
            'max_drawdown': max_dd
        },
        'regime_changes': regime_changes
    }


if __name__ == '__main__':
    """Run regime-aware backtest for specified year."""
    import sys

    # Get year from command line or default to 2024
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2024

    print(f"\n🚀 Starting Regime-Aware Backtest for {year}")
    print("This uses market regime detection to adapt strategy dynamically.")
    print("=" * 70)

    result = run_regime_aware_backtest(year)

    if result:
        print(f"\n✅ Backtest for {year} completed successfully!")
        print(f"   Total Return: {result['metrics']['total_return']:+.2f}%")
        print(f"   Sharpe Ratio: {result['metrics']['sharpe']:.2f}")
        print(f"   Max Drawdown: {result['metrics']['max_drawdown']:.2f}%")
    else:
        print(f"\n❌ Backtest for {year} failed")
