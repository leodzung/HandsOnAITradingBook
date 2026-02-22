"""
Simple Technical-Only Backtest with Real Vietnamese Data

This version bypasses fundamental screening and focuses on:
- Real historical price data from vnstock
- ML predictions using technical indicators
- Portfolio construction

Perfect for getting started quickly!
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from data_provider import VietnamDataProvider
from ml_predictor import StockDirectionPredictor


def run_simple_backtest():
    """Run a simple technical-only backtest with real data."""

    print("\n" + "=" * 70)
    print("SIMPLE TECHNICAL BACKTEST - REAL VIETNAMESE DATA")
    print("=" * 70)

    # Settings
    initial_capital = 100_000_000  # 100M VND
    # Expanded universe: 15 liquid blue-chip stocks across sectors
    universe = [
        'VNM',  # Vinamilk - Dairy
        'VCB',  # Vietcombank - Banking
        'HPG',  # Hoa Phat - Steel
        'FPT',  # FPT Corp - Technology
        'MSN',  # Masan - Consumer
        'GAS',  # PetroVietnam Gas - Energy
        'PLX',  # Petrolimex - Energy/Retail
        'SAB',  # Sabeco - Beverages
        'POW',  # PV Power - Utilities
        'BID',  # BIDV - Banking
        'VHM',  # Vinhomes - Real Estate
        'VIC',  # Vingroup - Conglomerate
        'MWG',  # Mobile World - Retail
        'TCB',  # Techcombank - Banking
        'CTG',  # VietinBank - Banking
    ]
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2022, 12, 31)

    print(f"\n📋 Backtest Configuration:")
    print(f"   Initial capital: {initial_capital:,} VND")
    print(f"   Universe: {universe}")
    print(f"   Period: {start_date.date()} to {end_date.date()}")

    # Initialize data provider
    print(f"\n{'='*70}")
    print("STEP 1: Initialize Data Provider")
    print('='*70)

    provider = VietnamDataProvider(data_source='vnstock', enable_cache=True)

    # Load historical data
    print(f"\n{'='*70}")
    print("STEP 2: Load Historical Price Data")
    print('='*70)

    train_start = start_date - timedelta(days=365)
    historical_data = provider.get_historical_data(
        universe,
        train_start.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )

    if not historical_data:
        print("❌ Failed to load historical data")
        return

    print(f"✅ Loaded data for {len(historical_data)} stocks")

    # Train ML model
    print(f"\n{'='*70}")
    print("STEP 3: Train ML Model (Technical Features Only)")
    print('='*70)

    predictor = StockDirectionPredictor(
        lookback_days=90,
        prediction_horizon_days=60,
        min_samples=100,
        model_type='gaussian'
    )

    # Create training data
    training_samples = []
    for symbol, hist_data in historical_data.items():
        if len(hist_data) < 180:
            continue

        for i in range(120, len(hist_data) - 60):
            try:
                # Technical features
                price_window = hist_data['close'].iloc[:i]
                volume_window = hist_data['volume'].iloc[:i]

                tech_features = predictor.calculate_technical_features(
                    price_window, volume_window
                )

                # Simplified fundamentals (defaults)
                fund_features = predictor.calculate_fundamental_features({
                    'roe': 0.15, 'roa': 0.08, 'pe_ratio': 15.0,
                    'pb_ratio': 2.0, 'debt_equity': 1.0,
                    'revenue_growth': 0.12, 'earnings_growth': 0.10
                })

                sentiment_features = predictor.calculate_sentiment_features(0, 0, 0, 0)

                # Combine
                all_features = {}
                all_features.update(tech_features)
                all_features.update(fund_features)
                all_features.update(sentiment_features)

                # Label
                current_price = hist_data['close'].iloc[i]
                future_price = hist_data['close'].iloc[i + 60]
                forward_return = (future_price - current_price) / current_price
                all_features['target'] = 1 if forward_return > 0 else 0

                training_samples.append(all_features)
            except:
                continue

    if len(training_samples) < 100:
        print(f"❌ Insufficient training samples: {len(training_samples)}")
        return

    training_df = pd.DataFrame(training_samples)
    accuracy = predictor.train(training_df)

    print(f"✅ Model trained successfully!")
    print(f"   Training samples: {len(training_samples):,}")
    print(f"   Accuracy: {accuracy:.2%}")

    # Run backtest
    print(f"\n{'='*70}")
    print("STEP 4: Run Backtest Simulation")
    print('='*70)

    cash = initial_capital
    holdings = {}  # {symbol: shares}
    portfolio_history = []

    current_date = start_date
    rebalance_interval = 90  # days
    last_rebalance = None

    while current_date <= end_date:
        # Rebalance check
        if last_rebalance is None or (current_date - last_rebalance).days >= rebalance_interval:
            print(f"\n🔄 Rebalancing on {current_date.date()}")

            # Get predictions for all stocks
            predictions = {}
            for symbol in universe:
                if symbol not in historical_data:
                    continue

                hist = historical_data[symbol]
                hist_until_date = hist[hist.index <= pd.Timestamp(current_date)]

                if len(hist_until_date) < 90:
                    continue

                # Extract features
                tech_features = predictor.calculate_technical_features(
                    hist_until_date['close'],
                    hist_until_date['volume']
                )
                fund_features = predictor.calculate_fundamental_features({
                    'roe': 0.15, 'roa': 0.08, 'pe_ratio': 15.0,
                    'pb_ratio': 2.0, 'debt_equity': 1.0,
                    'revenue_growth': 0.12, 'earnings_growth': 0.10
                })
                sentiment_features = predictor.calculate_sentiment_features(0, 0, 0, 0)

                all_features = {}
                all_features.update(tech_features)
                all_features.update(fund_features)
                all_features.update(sentiment_features)

                # Predict
                try:
                    pred = predictor.predict(pd.Series(all_features))
                    if pred['prediction'] == 1:  # Positive prediction
                        predictions[symbol] = pred['probability']
                except:
                    continue

            # Select top predictions
            if predictions:
                sorted_preds = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
                selected_stocks = [s for s, _ in sorted_preds[:5]]  # Top 5 (increased diversification)

                print(f"   Selected stocks: {selected_stocks}")

                # Calculate target holdings (equal weight)
                portfolio_value = cash + sum([
                    holdings.get(s, 0) * get_price(s, current_date, historical_data)
                    for s in holdings
                ])

                target_holdings = {}
                weight = 1.0 / len(selected_stocks)
                for symbol in selected_stocks:
                    price = get_price(symbol, current_date, historical_data)
                    if price:
                        target_value = portfolio_value * weight
                        target_shares = int(target_value / (price * 100)) * 100  # Round to 100
                        target_holdings[symbol] = target_shares

                # Execute trades
                all_symbols = set(list(holdings.keys()) + list(target_holdings.keys()))
                for symbol in all_symbols:
                    current_shares = holdings.get(symbol, 0)
                    target_shares = target_holdings.get(symbol, 0)
                    trade_shares = target_shares - current_shares

                    if trade_shares != 0:
                        price = get_price(symbol, current_date, historical_data)
                        if price:
                            trade_value = abs(trade_shares) * price
                            cost = trade_value * 0.004  # 0.4% transaction cost

                            if trade_shares > 0:  # Buy
                                cash -= (trade_value + cost)
                            else:  # Sell
                                cash += (trade_value - cost)

                holdings = target_holdings
                last_rebalance = current_date
            else:
                print("   No positive predictions, holding cash")

        # Calculate portfolio value
        holdings_value = sum([
            holdings.get(s, 0) * get_price(s, current_date, historical_data)
            for s in holdings
        ])
        portfolio_value = cash + holdings_value

        portfolio_history.append({
            'date': current_date,
            'value': portfolio_value,
            'return': (portfolio_value / initial_capital - 1) * 100
        })

        # Next day
        current_date += timedelta(days=1)
        while current_date.weekday() >= 5:
            current_date += timedelta(days=1)

    # Results
    results_df = pd.DataFrame(portfolio_history)

    print(f"\n{'='*70}")
    print("BACKTEST RESULTS")
    print('='*70)

    if not results_df.empty:
        final_value = results_df['value'].iloc[-1]
        total_return = results_df['return'].iloc[-1]

        returns = results_df['value'].pct_change().dropna()
        days = len(results_df)
        years = days / 252
        annual_return = ((final_value / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
        annual_vol = returns.std() * np.sqrt(252) * 100 if len(returns) > 1 else 0
        sharpe = (annual_return - 3) / annual_vol if annual_vol > 0 else 0

        # Max drawdown
        peak = results_df['value'].expanding(min_periods=1).max()
        drawdown = (results_df['value'] - peak) / peak * 100
        max_dd = drawdown.min()

        print(f"\n📊 Performance Summary:")
        print(f"   Total Return:        {total_return:>8.2f}%")
        print(f"   Annual Return:       {annual_return:>8.2f}%")
        print(f"   Annual Volatility:   {annual_vol:>8.2f}%")
        print(f"   Sharpe Ratio:        {sharpe:>8.2f}")
        print(f"   Max Drawdown:        {max_dd:>8.2f}%")
        print(f"\n💰 Portfolio Values:")
        print(f"   Initial:             {initial_capital:>15,} VND")
        print(f"   Final:               {final_value:>15,.0f} VND")
        print(f"   Profit/Loss:         {final_value-initial_capital:>15,.0f} VND")

        # Save results
        results_df.to_csv('simple_backtest_results.csv', index=False)
        print(f"\n💾 Results saved to simple_backtest_results.csv")

        return results_df
    else:
        print("❌ No results generated")
        return pd.DataFrame()


def get_price(symbol, date, historical_data):
    """Get price for a symbol at a date."""
    if symbol not in historical_data:
        return None

    hist = historical_data[symbol]
    prices_until_date = hist[hist.index <= pd.Timestamp(date)]

    if len(prices_until_date) == 0:
        return None

    return prices_until_date['close'].iloc[-1]


if __name__ == '__main__':
    results = run_simple_backtest()

    if not results.empty:
        print("\n" + "=" * 70)
        print("✅ BACKTEST COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nReview simple_backtest_results.csv for detailed results")
        print("This strategy uses REAL Vietnamese stock data! 🇻🇳📈\n")
