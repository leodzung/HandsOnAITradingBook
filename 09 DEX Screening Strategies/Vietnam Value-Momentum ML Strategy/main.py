# region imports
from AlgorithmImports import *

# Import custom modules
# Note: In QuantConnect, you would need to add these as project files
# For local testing, ensure they are in the same directory
try:
    from fundamental_screener import FundamentalScreener
    from ml_predictor import StockDirectionPredictor
    from portfolio_manager import PortfolioManager
except ImportError:
    # Fallback for when running outside QuantConnect
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from fundamental_screener import FundamentalScreener
    from ml_predictor import StockDirectionPredictor
    from portfolio_manager import PortfolioManager

import pickle
from datetime import timedelta
import pandas as pd
import numpy as np
# endregion


class VietnamValueMomentumMLStrategy(QCAlgorithm):
    """
    Vietnam Value-Momentum ML Strategy

    A hybrid fundamental/value and AI/ML-driven strategy for mid-term (3-6 month)
    opportunities in Vietnamese stock markets (HOSE/HNX).

    Strategy Components:
    1. Fundamental Screening - Value, Quality, Growth metrics
    2. ML Prediction - Gaussian Naive Bayes for direction forecasting
    3. Portfolio Construction - Risk-managed position sizing with sector constraints
    4. Quarterly Rebalancing - Aligned with earnings seasons

    Note: This algorithm is designed for Vietnamese stocks but uses US market data
    as a demonstration. To run on Vietnamese stocks:
    - Add custom data source via AddData() for HOSE/HNX stocks
    - Integrate with FiinGroup, VND Direct, or other Vietnamese data providers
    - Adjust market hours, settlement, and transaction costs for Vietnamese market
    """

    def initialize(self):
        # Set dates and initial capital
        self.set_start_date(2019, 1, 1)
        self.set_end_date(2024, 10, 1)
        self.set_cash(1_000_000)  # $1M USD (or VND equivalent)

        # Strategy parameters (configurable via QuantConnect parameter optimization)
        self.universe_size = self.get_parameter('universe_size', 100)
        self.target_stocks = self.get_parameter('target_stocks', 20)
        self.rebalance_frequency = self.get_parameter('rebalance_frequency', 90)  # days

        # Initialize strategy components
        self.fundamental_screener = FundamentalScreener(
            min_roe=0.12,  # 12% ROE threshold for Vietnam
            min_roa=0.05,
            max_debt_equity=2.0,
            min_revenue_growth=0.10
        )

        self.ml_predictor = StockDirectionPredictor(
            lookback_days=90,
            prediction_horizon_days=90,  # 3 month prediction
            min_samples=100,
            model_type='gaussian'
        )

        self.portfolio_manager = PortfolioManager(
            target_stocks=self.target_stocks,
            min_position=0.015,  # 1.5% min
            max_position=0.08,   # 8% max
            max_sector_weight=0.40,
            fundamental_weight=0.4,
            ml_weight=0.4,
            sector_momentum_weight=0.2
        )

        # Data storage
        self.stocks_data = {}  # Store price/volume history per symbol
        self.sector_performance = {}  # Track sector returns
        self.trained = False

        # Schedule training and rebalancing
        # Note: For Vietnamese market, adjust to local trading hours (GMT+7)
        schedule_symbol = Symbol.create("SPY", SecurityType.EQUITY, Market.USA)

        # Train model quarterly (before earnings season)
        self.train(
            self.date_rules.every([DayOfWeek.MONDAY]),  # Weekly training initially
            self.time_rules.at(9, 0),
            self._train_model
        )

        # Rebalance quarterly
        self.schedule.on(
            self.date_rules.month_start(),  # Monthly check, will filter to quarterly
            self.time_rules.after_market_open(schedule_symbol, 30),
            self._rebalance_portfolio
        )

        # Universe selection
        # NOTE: This uses US stocks as example. For Vietnamese stocks, use:
        # self.add_universe(self._select_vietnamese_stocks)
        # Or use AddData() to add custom HOSE/HNX data

        self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW
        self.universe_settings.resolution = Resolution.DAILY
        self._last_rebalance = self.time

        # For demo: Use large-cap US stocks
        # In production: Replace with Vietnamese stock universe
        self.add_universe(self._select_demo_universe)

        # Load pre-trained model in live mode
        if self.live_mode:
            self._model_key = 'vietnam_ml_model.pkl'
            if self.object_store.contains_key(self._model_key):
                try:
                    model_data = pickle.loads(
                        self.object_store.read_bytes(self._model_key)
                    )
                    self.ml_predictor.model = model_data['model']
                    self.ml_predictor.scaler = model_data['scaler']
                    self.ml_predictor.feature_names = model_data['feature_names']
                    self.ml_predictor.is_trained = True
                    self.trained = True
                    self.log("Loaded pre-trained ML model from Object Store")
                except Exception as e:
                    self.log(f"Error loading model: {e}")

    def _select_demo_universe(self, fundamental):
        """
        Demo universe selector using US stocks.
        Replace this with Vietnamese stock selection logic.
        """
        # Filter for liquid, profitable stocks
        filtered = [
            f for f in fundamental
            if f.has_fundamental_data
            and f.market_cap > 1e9  # > $1B market cap
            and f.volume > 500000  # Liquid
            and f.valuation_ratios.pe_ratio > 0
            and f.valuation_ratios.pe_ratio < 30
            and f.operation_ratios.roe.value > 0.10
        ]

        # Sort by market cap and take top N
        sorted_by_market_cap = sorted(
            filtered,
            key=lambda x: x.market_cap,
            reverse=True
        )

        return [x.symbol for x in sorted_by_market_cap[:self.universe_size]]

    def on_securities_changed(self, changes):
        """Handle universe changes."""
        for security in changes.added_securities:
            # Initialize data storage for new stocks
            symbol = security.symbol
            self.stocks_data[symbol] = {
                'prices': pd.Series(dtype=float),
                'volumes': pd.Series(dtype=float),
                'returns': pd.Series(dtype=float)
            }

            # Warm up with historical data
            history = self.history(
                symbol,
                252,  # 1 year of daily data
                Resolution.DAILY,
                data_normalization_mode=DataNormalizationMode.RAW
            )

            if not history.empty and symbol in history.index:
                hist_symbol = history.loc[symbol]
                self.stocks_data[symbol]['prices'] = hist_symbol['close']
                self.stocks_data[symbol]['volumes'] = hist_symbol['volume']

        for security in changes.removed_securities:
            symbol = security.symbol
            if symbol in self.stocks_data:
                del self.stocks_data[symbol]

    def on_data(self, data):
        """
        Update price/volume data daily.
        Main trading logic is in _rebalance_portfolio.
        """
        for symbol in self.stocks_data.keys():
            if symbol in data and data[symbol]:
                bar = data[symbol]
                self.stocks_data[symbol]['prices'][self.time] = bar.close
                self.stocks_data[symbol]['volumes'][self.time] = bar.volume

                # Keep last 252 days
                self.stocks_data[symbol]['prices'] = \
                    self.stocks_data[symbol]['prices'].tail(252)
                self.stocks_data[symbol]['volumes'] = \
                    self.stocks_data[symbol]['volumes'].tail(252)

    def _train_model(self):
        """
        Train ML model on historical data.
        Runs weekly to keep model fresh.
        """
        self.log(f"Training ML model at {self.time}")

        training_data = []

        for symbol, data in self.stocks_data.items():
            if len(data['prices']) < 150:  # Need enough history
                continue

            # Get fundamental data
            security = self.securities[symbol]
            if not security.fundamentals:
                continue

            fundamentals = security.fundamentals

            # Prepare features for each point in time (rolling window)
            prices = data['prices']
            volumes = data['volumes']

            # Create training samples from historical data
            # We'll create samples for each day with enough lookback
            for i in range(120, len(prices) - 90):  # Need 90 days forward for label
                # Extract data up to point i
                price_window = prices.iloc[:i]
                volume_window = volumes.iloc[:i]

                # Calculate features at time i
                features = self._extract_features_at_time(
                    price_window,
                    volume_window,
                    fundamentals
                )

                # Calculate forward return (label)
                current_price = prices.iloc[i]
                future_price = prices.iloc[i + 90]  # 90 days forward
                forward_return = (future_price - current_price) / current_price

                # Binary label: 1 if positive return, 0 otherwise
                label = 1 if forward_return > 0 else 0

                # Add to training data
                features['target'] = label
                training_data.append(features)

        if len(training_data) < self.ml_predictor.min_samples:
            self.log(f"Insufficient training data: {len(training_data)} samples")
            return

        # Convert to DataFrame and train
        training_df = pd.DataFrame(training_data)

        try:
            accuracy = self.ml_predictor.train(training_df)
            self.trained = True
            self.log(f"Model trained successfully. Accuracy: {accuracy:.3f}")

            # Save model in live mode
            if self.live_mode:
                model_data = {
                    'model': self.ml_predictor.model,
                    'scaler': self.ml_predictor.scaler,
                    'feature_names': self.ml_predictor.feature_names
                }
                self.object_store.save_bytes(
                    self._model_key,
                    pickle.dumps(model_data)
                )

        except Exception as e:
            self.log(f"Error training model: {e}")

    def _extract_features_at_time(self, prices, volumes, fundamentals):
        """
        Extract features for a single point in time.
        """
        # Technical features
        tech_features = self.ml_predictor.calculate_technical_features(
            prices, volumes
        )

        # Fundamental features
        fund_metrics = {
            'roe': fundamentals.operation_ratios.roe.value if fundamentals.operation_ratios.roe else 0.10,
            'roa': fundamentals.operation_ratios.roa.value if fundamentals.operation_ratios.roa else 0.05,
            'pe_ratio': fundamentals.valuation_ratios.pe_ratio if fundamentals.valuation_ratios.pe_ratio > 0 else 15,
            'pb_ratio': fundamentals.valuation_ratios.pb_ratio if fundamentals.valuation_ratios.pb_ratio > 0 else 2,
            'debt_equity': fundamentals.operation_ratios.total_assets_growth.value if fundamentals.operation_ratios.total_assets_growth else 1.0,
            'revenue_growth': fundamentals.operation_ratios.revenue_growth.value if fundamentals.operation_ratios.revenue_growth else 0,
            'earnings_growth': fundamentals.operation_ratios.net_income_growth.value if fundamentals.operation_ratios.net_income_growth else 0
        }

        fund_features = self.ml_predictor.calculate_fundamental_features(
            fund_metrics
        )

        # Sentiment features (simplified - in production use foreign flow data)
        sentiment_features = self.ml_predictor.calculate_sentiment_features(
            foreign_buy_volume=0,
            foreign_sell_volume=0,
            market_index_return=0,
            sector_return=0
        )

        # Combine all features
        all_features = {}
        all_features.update(tech_features)
        all_features.update(fund_features)
        all_features.update(sentiment_features)

        return all_features

    def _rebalance_portfolio(self):
        """
        Main rebalancing logic - runs quarterly.
        """
        # Check if enough time has passed since last rebalance
        days_since_rebalance = (self.time - self._last_rebalance).days
        if days_since_rebalance < self.rebalance_frequency:
            return

        self.log(f"Rebalancing portfolio at {self.time}")

        # Step 1: Fundamental Screening
        candidate_stocks = self._screen_fundamentals()

        if len(candidate_stocks) < 10:
            self.log(f"Insufficient candidates after fundamental screening: {len(candidate_stocks)}")
            return

        # Step 2: ML Prediction
        if self.trained:
            scored_stocks = self._apply_ml_predictions(candidate_stocks)
        else:
            self.log("ML model not trained yet, using fundamental scores only")
            scored_stocks = candidate_stocks
            for stock in scored_stocks:
                stock['ml_score'] = 50  # Neutral score

        # Step 3: Portfolio Construction
        portfolio_weights = self._construct_portfolio(scored_stocks)

        # Step 4: Execute Trades
        self._execute_rebalance(portfolio_weights)

        self._last_rebalance = self.time

    def _screen_fundamentals(self):
        """
        Screen universe using fundamental metrics.
        """
        candidates = []

        for symbol in self.active_securities.keys:
            security = self.securities[symbol]

            if not security.fundamentals:
                continue

            fund = security.fundamentals

            # Extract fundamental metrics
            metrics = {
                'symbol': str(symbol),
                'sector': fund.asset_classification.morningstar_sector_code.name if fund.asset_classification.morningstar_sector_code else 'Unknown',
                'pe_ratio': fund.valuation_ratios.pe_ratio if fund.valuation_ratios.pe_ratio > 0 else 15,
                'pb_ratio': fund.valuation_ratios.pb_ratio if fund.valuation_ratios.pb_ratio > 0 else 2,
                'roe': fund.operation_ratios.roe.value if fund.operation_ratios.roe else 0,
                'roa': fund.operation_ratios.roa.value if fund.operation_ratios.roa else 0,
                'debt_equity': fund.operation_ratios.financial_leverage.value if fund.operation_ratios.financial_leverage else 1,
                'current_ratio': fund.operation_ratios.current_ratio.value if fund.operation_ratios.current_ratio else 1,
                'revenue_growth': fund.operation_ratios.revenue_growth.value if fund.operation_ratios.revenue_growth else 0,
                'earnings_growth': fund.operation_ratios.net_income_growth.value if fund.operation_ratios.net_income_growth else 0,
                'div_yield': fund.valuation_ratios.dividend_yield if fund.valuation_ratios.dividend_yield else 0,
                'earnings_stability': 6,  # Placeholder
                'revenue_growth_consistency': 0.75,  # Placeholder
                'market_cap': fund.market_cap,
                'avg_dollar_volume': fund.dollar_volume
            }

            candidates.append(metrics)

        # Screen using FundamentalScreener
        screened = self.fundamental_screener.screen_stocks(candidates)

        self.log(f"Fundamental screening: {len(candidates)} -> {len(screened)} stocks")

        return screened

    def _apply_ml_predictions(self, fundamental_stocks):
        """
        Apply ML predictions to fundamentally screened stocks.
        """
        predictions = []

        for stock in fundamental_stocks:
            symbol_str = stock['symbol']
            symbol = Symbol.create(symbol_str, SecurityType.EQUITY, Market.USA)

            if symbol not in self.stocks_data:
                continue

            if len(self.stocks_data[symbol]['prices']) < 90:
                continue

            # Extract current features
            prices = self.stocks_data[symbol]['prices']
            volumes = self.stocks_data[symbol]['volumes']
            security = self.securities[symbol]

            features = self._extract_features_at_time(
                prices,
                volumes,
                security.fundamentals
            )

            # Get ML prediction
            try:
                prediction = self.ml_predictor.predict(pd.Series(features))
                ml_score = prediction['probability'] * 100  # Convert to 0-100 scale

                stock['ml_score'] = ml_score
                stock['ml_prediction'] = prediction['prediction']
                stock['ml_confidence'] = prediction['confidence']

                predictions.append(stock)

            except Exception as e:
                self.log(f"Error predicting {symbol}: {e}")
                continue

        self.log(f"ML predictions: {len(predictions)} stocks scored")

        return predictions

    def _construct_portfolio(self, scored_stocks):
        """
        Construct portfolio weights from scored stocks.
        """
        if not scored_stocks:
            return {}

        # Calculate combined scores
        scored_df = self.portfolio_manager.calculate_combined_scores(scored_stocks)

        # Construct portfolio with constraints
        weights = self.portfolio_manager.construct_portfolio(scored_df)

        self.log(f"Portfolio construction: {len(weights)} positions")

        return weights

    def _execute_rebalance(self, target_weights):
        """
        Execute portfolio rebalancing trades.
        """
        if not target_weights:
            self.log("No target weights, liquidating portfolio")
            self.liquidate()
            return

        # Convert string symbols to Symbol objects
        portfolio_targets = []
        for symbol_str, weight in target_weights.items():
            symbol = Symbol.create(symbol_str, SecurityType.EQUITY, Market.USA)
            portfolio_targets.append(PortfolioTarget(symbol, weight))

        # Execute trades
        self.set_holdings(portfolio_targets, True)

        # Log top holdings
        top_holdings = sorted(
            target_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        self.log(f"Top 5 holdings: {top_holdings}")

        # Plot portfolio metrics
        self.plot("Portfolio", "Positions", len(target_weights))
        self.plot("Portfolio", "Max Weight", max(target_weights.values()) if target_weights else 0)

    def on_end_of_algorithm(self):
        """
        Save final model state in live mode.
        """
        if self.live_mode and self.trained:
            model_data = {
                'model': self.ml_predictor.model,
                'scaler': self.ml_predictor.scaler,
                'feature_names': self.ml_predictor.feature_names
            }
            self.object_store.save_bytes(
                self._model_key,
                pickle.dumps(model_data)
            )
            self.log("Saved final model state to Object Store")
