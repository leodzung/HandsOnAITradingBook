# ml_predictor.py
# ML prediction module for Vietnamese stock direction forecasting

import numpy as np
import pandas as pd
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import pickle

class StockDirectionPredictor:
    """
    Predicts 3-6 month forward return direction for Vietnamese stocks using Gaussian Naive Bayes.
    Features include technical indicators, fundamental changes, and market sentiment.
    """

    def __init__(self,
                 lookback_days=90,
                 prediction_horizon_days=90,  # 3 months
                 min_samples=100,
                 model_type='gaussian',
                 use_scaler=True):
        """
        Initialize the ML predictor.

        Args:
            lookback_days: Number of days to look back for features (default 90)
            prediction_horizon_days: Forward return prediction period (default 90 for 3 months)
            min_samples: Minimum training samples required (default 100)
            model_type: 'gaussian' or 'random_forest'
            use_scaler: Whether to standardize features (default True)
        """
        self.lookback_days = lookback_days
        self.prediction_horizon_days = prediction_horizon_days
        self.min_samples = min_samples
        self.model_type = model_type
        self.use_scaler = use_scaler

        if model_type == 'gaussian':
            self.model = GaussianNB()
        elif model_type == 'random_forest':
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        if use_scaler:
            self.scaler = StandardScaler()
        else:
            self.scaler = None

        self.is_trained = False
        self.feature_names = []

    def calculate_technical_features(self, price_series, volume_series=None):
        """
        Calculate technical indicator features from price and volume data.

        Args:
            price_series: Pandas Series of daily prices (indexed by date)
            volume_series: Optional Pandas Series of daily volumes

        Returns:
            Dictionary of technical features
        """
        features = {}

        # Moving averages and ratios
        ma_20 = price_series.rolling(20).mean()
        ma_50 = price_series.rolling(50).mean()
        ma_200 = price_series.rolling(200).mean()

        current_price = price_series.iloc[-1]
        features['price_to_ma20'] = current_price / ma_20.iloc[-1] if len(ma_20) >= 20 and ma_20.iloc[-1] > 0 else 1.0
        features['price_to_ma50'] = current_price / ma_50.iloc[-1] if len(ma_50) >= 50 and ma_50.iloc[-1] > 0 else 1.0
        features['price_to_ma200'] = current_price / ma_200.iloc[-1] if len(ma_200) >= 200 and ma_200.iloc[-1] > 0 else 1.0

        # Momentum features
        features['return_5d'] = self._safe_return(price_series, 5)
        features['return_20d'] = self._safe_return(price_series, 20)
        features['return_60d'] = self._safe_return(price_series, 60)

        # Volatility (standard deviation of returns)
        returns = price_series.pct_change()
        features['volatility_20d'] = returns.tail(20).std() if len(returns) >= 20 else 0.0
        features['volatility_60d'] = returns.tail(60).std() if len(returns) >= 60 else 0.0

        # RSI (Relative Strength Index)
        features['rsi_14'] = self._calculate_rsi(price_series, 14)

        # MACD features
        macd_line, signal_line = self._calculate_macd(price_series)
        features['macd'] = macd_line
        features['macd_signal'] = signal_line
        features['macd_histogram'] = macd_line - signal_line

        # Volume features (if available)
        if volume_series is not None and len(volume_series) > 20:
            vol_ma_20 = volume_series.rolling(20).mean()
            features['volume_ratio'] = volume_series.iloc[-1] / vol_ma_20.iloc[-1] if vol_ma_20.iloc[-1] > 0 else 1.0
            features['volume_trend'] = self._safe_return(volume_series, 20)
        else:
            features['volume_ratio'] = 1.0
            features['volume_trend'] = 0.0

        # Price range (high-low spread as % of price)
        if len(price_series) >= 20:
            recent_prices = price_series.tail(20)
            price_range = (recent_prices.max() - recent_prices.min()) / recent_prices.mean() if recent_prices.mean() > 0 else 0
            features['price_range_20d'] = price_range
        else:
            features['price_range_20d'] = 0.0

        return features

    def calculate_fundamental_features(self, current_metrics, previous_metrics=None):
        """
        Calculate fundamental change features.

        Args:
            current_metrics: Dictionary of current fundamental metrics
            previous_metrics: Optional dictionary of previous quarter's metrics

        Returns:
            Dictionary of fundamental features
        """
        features = {}

        # Current fundamental levels (normalized)
        features['roe_current'] = current_metrics.get('roe', 0.10)
        features['roa_current'] = current_metrics.get('roa', 0.05)
        features['pe_ratio'] = current_metrics.get('pe_ratio', 15.0)
        features['pb_ratio'] = current_metrics.get('pb_ratio', 2.0)
        features['debt_equity'] = current_metrics.get('debt_equity', 1.0)

        # Changes from previous quarter (if available)
        if previous_metrics is not None:
            features['roe_change'] = (current_metrics.get('roe', 0) -
                                     previous_metrics.get('roe', 0))
            features['revenue_growth'] = current_metrics.get('revenue_growth', 0)
            features['earnings_growth'] = current_metrics.get('earnings_growth', 0)
        else:
            features['roe_change'] = 0.0
            features['revenue_growth'] = current_metrics.get('revenue_growth', 0)
            features['earnings_growth'] = current_metrics.get('earnings_growth', 0)

        return features

    def calculate_sentiment_features(self, foreign_buy_volume, foreign_sell_volume,
                                    market_index_return, sector_return):
        """
        Calculate market sentiment and positioning features.

        Args:
            foreign_buy_volume: Foreign buying volume (last 20 days)
            foreign_sell_volume: Foreign selling volume (last 20 days)
            market_index_return: VN-Index return (e.g., 20-day)
            sector_return: Sector index return (e.g., 20-day)

        Returns:
            Dictionary of sentiment features
        """
        features = {}

        # Foreign flow ratio (positive = net buying)
        total_volume = foreign_buy_volume + foreign_sell_volume
        if total_volume > 0:
            features['foreign_flow_ratio'] = (foreign_buy_volume - foreign_sell_volume) / total_volume
        else:
            features['foreign_flow_ratio'] = 0.0

        # Market and sector momentum
        features['market_return_20d'] = market_index_return
        features['sector_return_20d'] = sector_return
        features['sector_vs_market'] = sector_return - market_index_return

        return features

    def prepare_features(self, price_data, volume_data=None, fundamental_current=None,
                        fundamental_previous=None, foreign_buy=0, foreign_sell=0,
                        market_return=0, sector_return=0):
        """
        Prepare all features for a single stock at a point in time.

        Args:
            price_data: Pandas Series of historical prices
            volume_data: Pandas Series of historical volumes (optional)
            fundamental_current: Current fundamental metrics dict
            fundamental_previous: Previous quarter fundamental metrics dict
            foreign_buy: Foreign buying volume
            foreign_sell: Foreign selling volume
            market_return: Market index return
            sector_return: Sector return

        Returns:
            Pandas Series of features
        """
        all_features = {}

        # Technical features
        tech_features = self.calculate_technical_features(price_data, volume_data)
        all_features.update(tech_features)

        # Fundamental features
        if fundamental_current is not None:
            fund_features = self.calculate_fundamental_features(
                fundamental_current, fundamental_previous
            )
            all_features.update(fund_features)

        # Sentiment features
        sentiment_features = self.calculate_sentiment_features(
            foreign_buy, foreign_sell, market_return, sector_return
        )
        all_features.update(sentiment_features)

        # Store feature names on first run
        if not self.feature_names:
            self.feature_names = sorted(all_features.keys())

        # Return features in consistent order
        return pd.Series([all_features.get(name, 0.0) for name in self.feature_names])

    def train(self, training_data):
        """
        Train the model on historical data.

        Args:
            training_data: DataFrame with features (columns) and 'target' column
                          target: 1 (positive return), 0 (negative/flat return)

        Returns:
            Training accuracy score
        """
        if len(training_data) < self.min_samples:
            raise ValueError(f"Insufficient training samples: {len(training_data)} < {self.min_samples}")

        X = training_data.drop('target', axis=1)
        y = training_data['target']

        # Store feature names from training data
        if not self.feature_names:
            self.feature_names = list(X.columns)

        # Standardize features if using scaler
        if self.use_scaler:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = X.values

        # Train model
        self.model.fit(X_scaled, y)
        self.is_trained = True

        # Calculate training accuracy
        train_score = self.model.score(X_scaled, y)

        return train_score

    def predict(self, features):
        """
        Predict return direction for a stock.

        Args:
            features: Pandas Series or 1D array of features

        Returns:
            Dictionary with:
                - prediction: 1 (positive) or 0 (negative/flat)
                - probability: Probability of positive return
                - confidence: Max probability (measure of confidence)
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet. Call train() first.")

        # Ensure features are in correct order
        if isinstance(features, pd.Series):
            features_array = np.array([features[name] for name in self.feature_names]).reshape(1, -1)
        else:
            features_array = np.array(features).reshape(1, -1)

        # Scale features if using scaler
        if self.use_scaler:
            features_scaled = self.scaler.transform(features_array)
        else:
            features_scaled = features_array

        # Get prediction and probabilities
        prediction = self.model.predict(features_scaled)[0]
        probabilities = self.model.predict_proba(features_scaled)[0]

        return {
            'prediction': int(prediction),
            'probability': probabilities[1] if len(probabilities) > 1 else 0.5,
            'confidence': max(probabilities)
        }

    def predict_batch(self, features_df):
        """
        Predict for multiple stocks at once.

        Args:
            features_df: DataFrame where each row is a stock's features

        Returns:
            List of prediction dictionaries
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet. Call train() first.")

        # Ensure features are in correct order
        X = features_df[self.feature_names]

        # Scale features if using scaler
        if self.use_scaler:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X.values

        # Get predictions and probabilities
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        results = []
        for i in range(len(predictions)):
            results.append({
                'prediction': int(predictions[i]),
                'probability': probabilities[i][1] if probabilities.shape[1] > 1 else 0.5,
                'confidence': max(probabilities[i])
            })

        return results

    def save_model(self, filepath):
        """Save trained model to disk."""
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")

        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'lookback_days': self.lookback_days,
            'prediction_horizon_days': self.prediction_horizon_days,
            'model_type': self.model_type,
            'use_scaler': self.use_scaler
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

    def load_model(self, filepath):
        """Load trained model from disk."""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.lookback_days = model_data['lookback_days']
        self.prediction_horizon_days = model_data['prediction_horizon_days']
        self.model_type = model_data['model_type']
        self.use_scaler = model_data['use_scaler']
        self.is_trained = True

    # Helper methods
    def _safe_return(self, series, periods):
        """Calculate return safely handling edge cases."""
        if len(series) < periods + 1:
            return 0.0
        start_val = series.iloc[-periods-1]
        end_val = series.iloc[-1]
        if start_val == 0:
            return 0.0
        return (end_val - start_val) / start_val

    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator."""
        if len(prices) < period + 1:
            return 50.0  # Neutral

        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0.0)
        losses = -deltas.where(deltas < 0, 0.0)

        avg_gain = gains.rolling(period).mean().iloc[-1]
        avg_loss = losses.rolling(period).mean().iloc[-1]

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD indicator."""
        if len(prices) < slow:
            return 0.0, 0.0

        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()

        return macd.iloc[-1], signal_line.iloc[-1]

    def get_feature_importance(self):
        """
        Get feature importance scores (only works for RandomForest model).

        Returns:
            DataFrame with feature names and importance scores
        """
        if self.model_type != 'random_forest':
            raise ValueError("Feature importance only available for RandomForest model")

        if not self.is_trained:
            raise ValueError("Model not trained yet")

        importances = self.model.feature_importances_
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)

        return feature_importance
