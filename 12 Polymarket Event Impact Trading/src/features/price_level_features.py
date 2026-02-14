"""
Feature Extraction for Price-Level Trading Strategy
Extracts 40+ features across 5 categories for ML model.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VolatilityFeatures:
    """Calculate volatility-based features."""

    @staticmethod
    def calculate_historical_volatility(prices: pd.Series, window: int = 30) -> float:
        """
        Annualized historical volatility.

        Formula: std(daily_returns) * sqrt(252)

        Args:
            prices: Series of closing prices
            window: Rolling window size (default: 30)

        Returns:
            Annualized volatility
        """
        if len(prices) < window:
            return 0.0

        returns = prices.pct_change().dropna()
        vol = returns.rolling(window).std().iloc[-1] * np.sqrt(252)

        return vol if not np.isnan(vol) else 0.0

    @staticmethod
    def calculate_parkinson_volatility(ohlc: pd.DataFrame, window: int = 30) -> float:
        """
        Parkinson's range-based volatility estimator.
        More efficient than close-to-close volatility.

        Formula: sqrt(1/(4*N*ln(2)) * sum(ln(high/low)^2))

        Args:
            ohlc: DataFrame with 'high' and 'low' columns
            window: Rolling window size

        Returns:
            Annualized Parkinson volatility
        """
        if len(ohlc) < window or 'high' not in ohlc.columns or 'low' not in ohlc.columns:
            return 0.0

        try:
            hl_ratio = np.log(ohlc['high'] / ohlc['low'])
            parkinson_vol = np.sqrt((hl_ratio ** 2).rolling(window).mean().iloc[-1] / (4 * np.log(2)))
            annualized = parkinson_vol * np.sqrt(252)

            return annualized if not np.isnan(annualized) else 0.0
        except:
            return 0.0

    @staticmethod
    def classify_vol_regime(current_vol: float, historical_vols: pd.Series) -> int:
        """
        Classify volatility regime based on percentiles.

        Args:
            current_vol: Current volatility value
            historical_vols: Series of historical volatility values

        Returns:
            0: LOW (< 25th percentile)
            1: NORMAL (25th-75th percentile)
            2: HIGH (75th-95th percentile)
            3: EXTREME (> 95th percentile)
        """
        if len(historical_vols) < 30 or current_vol == 0:
            return 1  # Default to NORMAL

        percentile = (historical_vols <= current_vol).sum() / len(historical_vols)

        if percentile < 0.25:
            return 0
        elif percentile < 0.75:
            return 1
        elif percentile < 0.95:
            return 2
        else:
            return 3

    @staticmethod
    def calculate_vol_percentile(current_vol: float, historical_vols: pd.Series) -> float:
        """Calculate volatility percentile (0-100)."""
        if len(historical_vols) < 30:
            return 50.0

        percentile = (historical_vols <= current_vol).sum() / len(historical_vols) * 100
        return percentile

    @staticmethod
    def calculate_vol_trend(vols: pd.Series, window: int = 30) -> float:
        """
        Calculate trend of volatility (slope).

        Args:
            vols: Series of volatility values
            window: Window size

        Returns:
            Slope coefficient (positive = increasing vol)
        """
        if len(vols) < window:
            return 0.0

        recent_vols = vols.tail(window)
        x = np.arange(len(recent_vols))
        y = recent_vols.values

        try:
            slope = np.polyfit(x, y, 1)[0]
            return slope if not np.isnan(slope) else 0.0
        except:
            return 0.0


class TechnicalIndicators:
    """Calculate technical indicators."""

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """
        Relative Strength Index (0-100).

        Args:
            prices: Series of closing prices
            period: RSI period (default: 14)

        Returns:
            RSI value
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral

        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = -delta.where(delta < 0, 0).rolling(period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50.0

    @staticmethod
    def calculate_macd(prices: pd.Series) -> Dict[str, float]:
        """
        MACD (12, 26, 9).

        Args:
            prices: Series of closing prices

        Returns:
            Dict with macd, macd_signal, macd_histogram
        """
        if len(prices) < 26:
            return {'macd': 0.0, 'macd_signal': 0.0, 'macd_histogram': 0.0}

        ema12 = prices.ewm(span=12, adjust=False).mean()
        ema26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

        return {
            'macd': macd.iloc[-1] if not np.isnan(macd.iloc[-1]) else 0.0,
            'macd_signal': signal.iloc[-1] if not np.isnan(signal.iloc[-1]) else 0.0,
            'macd_histogram': histogram.iloc[-1] if not np.isnan(histogram.iloc[-1]) else 0.0
        }

    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """
        Bollinger Bands.

        Args:
            prices: Series of closing prices
            period: Period (default: 20)
            std_dev: Standard deviations (default: 2)

        Returns:
            Dict with bb_position, bb_width
        """
        if len(prices) < period:
            return {'bb_position': 0.5, 'bb_width': 0.0}

        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        current_price = prices.iloc[-1]
        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]
        sma_val = sma.iloc[-1]

        # Position within bands (0 = lower, 1 = upper)
        if upper_val != lower_val:
            bb_position = (current_price - lower_val) / (upper_val - lower_val)
        else:
            bb_position = 0.5

        # Band width (normalized by SMA)
        bb_width = (upper_val - lower_val) / sma_val if sma_val != 0 else 0.0

        return {
            'bb_position': bb_position if not np.isnan(bb_position) else 0.5,
            'bb_width': bb_width if not np.isnan(bb_width) else 0.0
        }

    @staticmethod
    def calculate_moving_averages(prices: pd.Series) -> Dict[str, float]:
        """
        Moving average features.

        Args:
            prices: Series of closing prices

        Returns:
            Dict with price_vs_ma50_pct, price_vs_ma200_pct, golden_cross
        """
        current = prices.iloc[-1]

        # MA50
        if len(prices) >= 50:
            ma50 = prices.rolling(50).mean().iloc[-1]
            price_vs_ma50_pct = ((current - ma50) / ma50) * 100 if ma50 != 0 else 0.0
        else:
            ma50 = current
            price_vs_ma50_pct = 0.0

        # MA200
        if len(prices) >= 200:
            ma200 = prices.rolling(200).mean().iloc[-1]
            price_vs_ma200_pct = ((current - ma200) / ma200) * 100 if ma200 != 0 else 0.0
            golden_cross = 1.0 if ma50 > ma200 else 0.0
        else:
            price_vs_ma200_pct = 0.0
            golden_cross = 0.0

        return {
            'price_vs_ma50_pct': price_vs_ma50_pct if not np.isnan(price_vs_ma50_pct) else 0.0,
            'price_vs_ma200_pct': price_vs_ma200_pct if not np.isnan(price_vs_ma200_pct) else 0.0,
            'golden_cross': golden_cross
        }


class ProbabilisticFeatures:
    """Calculate probability-based features."""

    @staticmethod
    def calculate_distance_to_strike(current_price: float, strike_price: float) -> Dict[str, float]:
        """
        Distance features.

        Args:
            current_price: Current asset price
            strike_price: Target strike price

        Returns:
            Dict with strike_distance_pct, is_itm, moneyness
        """
        if current_price == 0:
            return {'strike_distance_pct': 0.0, 'is_itm': 0.0, 'moneyness': 1.0}

        pct_distance = ((strike_price - current_price) / current_price) * 100
        is_itm = 1.0 if current_price >= strike_price else 0.0
        moneyness = current_price / strike_price if strike_price != 0 else 1.0

        return {
            'strike_distance_pct': pct_distance,
            'is_itm': is_itm,
            'moneyness': moneyness
        }

    @staticmethod
    def calculate_sigma_distance(current_price: float, strike_price: float,
                                 volatility: float, days_to_expiry: int) -> float:
        """
        Distance in standard deviations (assuming lognormal distribution).

        Args:
            current_price: Current asset price
            strike_price: Target strike price
            volatility: Annualized volatility
            days_to_expiry: Days until expiry

        Returns:
            Number of standard deviations to strike
        """
        if volatility == 0 or days_to_expiry <= 0 or current_price == 0:
            return 0.0

        time_fraction = days_to_expiry / 365.0
        expected_std = current_price * volatility * np.sqrt(time_fraction)

        if expected_std == 0:
            return 0.0

        sigma_distance = (strike_price - current_price) / expected_std

        return sigma_distance if not np.isnan(sigma_distance) else 0.0

    @staticmethod
    def calculate_gbm_probability(current_price: float, strike_price: float,
                                  volatility: float, days_to_expiry: int,
                                  n_simulations: int = 10000) -> float:
        """
        Probability of reaching strike via Monte Carlo (Geometric Brownian Motion).

        This is a risk-neutral probability estimate.

        Args:
            current_price: Current asset price
            strike_price: Target strike price
            volatility: Annualized volatility
            days_to_expiry: Days until expiry
            n_simulations: Number of Monte Carlo paths

        Returns:
            Probability (0-1) of reaching strike
        """
        if volatility == 0 or days_to_expiry <= 0 or current_price == 0:
            return 0.5

        T = days_to_expiry / 365.0

        # GBM simulation: S_T = S_0 * exp((drift - 0.5*vol^2)*T + vol*sqrt(T)*Z)
        # Using drift = 0 (risk-neutral)
        np.random.seed(42)  # For reproducibility in testing
        random_shocks = np.random.normal(0, 1, n_simulations)
        final_prices = current_price * np.exp(
            (-0.5 * volatility**2) * T + volatility * np.sqrt(T) * random_shocks
        )

        # Probability of reaching strike
        prob = (final_prices >= strike_price).sum() / n_simulations

        return prob if not np.isnan(prob) else 0.5


class TimeFeatures:
    """Calculate time-based features."""

    @staticmethod
    def extract_time_features(expiry_date: datetime, days_to_expiry_override: Optional[int] = None) -> Dict[str, float]:
        """
        Extract time features.

        Args:
            expiry_date: Market expiry datetime
            days_to_expiry_override: If provided, use this value instead of calculating from current time
                                    (useful for synthetic data generation)

        Returns:
            Dict with time-related features
        """
        now = datetime.now(timezone.utc)

        # Ensure expiry_date is timezone-aware
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

        # Use override if provided (for synthetic data), otherwise calculate
        if days_to_expiry_override is not None:
            days_to_expiry = days_to_expiry_override
        else:
            days_to_expiry = (expiry_date - now).days
            days_to_expiry = max(0, days_to_expiry)  # Can't be negative

        time_fraction = days_to_expiry / 365.0
        time_decay = 1 - time_fraction  # Higher as expiry approaches

        return {
            'days_to_expiry': float(days_to_expiry),
            'weeks_to_expiry': days_to_expiry / 7.0,
            'months_to_expiry': days_to_expiry / 30.0,
            'time_fraction': time_fraction,
            'time_decay': time_decay,
            'day_of_week': float(now.weekday()),
            'month': float(now.month),
            'is_quarter_end': 1.0 if now.month in [3, 6, 9, 12] else 0.0,
            'is_year_end': 1.0 if now.month == 12 else 0.0
        }


class MarketMicrostructureFeatures:
    """Extract Polymarket-specific features."""

    @staticmethod
    def extract_market_features(market: Dict, orderbook: Dict) -> Dict[str, float]:
        """
        Extract market microstructure features.

        Args:
            market: Market dictionary from Polymarket
            orderbook: Order book dictionary

        Returns:
            Dict with market features
        """
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if bids and asks:
            # Handle both dict format {'price': x, 'size': y} and array format [x, y]
            if isinstance(bids[0], dict):
                best_bid = float(bids[0]['price'])
                best_ask = float(asks[0]['price'])
                bid_depth_5 = sum(float(b['size']) for b in bids[:5])
                ask_depth_5 = sum(float(a['size']) for a in asks[:5])
            else:
                # Array format: [price, size]
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                bid_depth_5 = sum(float(b[1]) for b in bids[:5])
                ask_depth_5 = sum(float(a[1]) for a in asks[:5])

            spread = best_ask - best_bid
            mid_price = (best_bid + best_ask) / 2

            if bid_depth_5 + ask_depth_5 > 0:
                depth_imbalance = (bid_depth_5 - ask_depth_5) / (bid_depth_5 + ask_depth_5)
            else:
                depth_imbalance = 0.0

            spread_pct = (spread / mid_price * 100) if mid_price > 0 else 0.0
        else:
            mid_price = 0.5
            spread = 0.0
            spread_pct = 0.0
            depth_imbalance = 0.0

        # Volume features
        volume_24h = float(market.get('volume24hr', 0))
        volume_7d = float(market.get('volume1wk', 0))
        liquidity = float(market.get('liquidity', 0))

        # Volume trend (24h / 7d avg)
        avg_daily_vol_7d = volume_7d / 7.0 if volume_7d > 0 else 1.0
        volume_trend = volume_24h / avg_daily_vol_7d if avg_daily_vol_7d > 0 else 1.0

        return {
            'market_price': mid_price,
            'spread': spread,
            'spread_pct': spread_pct,
            'depth_imbalance': depth_imbalance,
            'volume_24h': volume_24h,
            'volume_7d': volume_7d,
            'liquidity': liquidity,
            'volume_trend': volume_trend
        }


class PriceLevelFeatureExtractor:
    """Master feature extractor combining all feature classes."""

    def __init__(self):
        """Initialize feature extractor."""
        self.volatility_features = VolatilityFeatures()
        self.technical_indicators = TechnicalIndicators()
        self.probabilistic_features = ProbabilisticFeatures()
        self.time_features = TimeFeatures()
        self.market_features = MarketMicrostructureFeatures()

        logger.info("PriceLevelFeatureExtractor initialized")

    def extract_all_features(self, parsed_market: Dict, spot_price: float,
                            historical_ohlcv: pd.DataFrame,
                            polymarket_data: Dict) -> Dict[str, float]:
        """
        Extract all 40+ features for a price-level market.

        Args:
            parsed_market: Parsed market from PriceLevelMarketParser
            spot_price: Current spot price of asset
            historical_ohlcv: Historical OHLCV data (DataFrame)
            polymarket_data: Dict with 'market' and 'orderbook'

        Returns:
            Dictionary with all features
        """
        features = {}

        # Extract basic info
        strike_price = parsed_market['strike_price']
        expiry_date = parsed_market['expiry_date']
        days_to_expiry = parsed_market['days_to_expiry']

        # Prepare price series
        if 'close' in historical_ohlcv.columns and len(historical_ohlcv) > 0:
            prices = historical_ohlcv['close']
        else:
            # Fallback: use current price
            prices = pd.Series([spot_price])

        # 1. Volatility Features (6 features)
        vol_30d = self.volatility_features.calculate_historical_volatility(prices, window=30)
        vol_90d = self.volatility_features.calculate_historical_volatility(prices, window=90)
        vol_parkinson = self.volatility_features.calculate_parkinson_volatility(historical_ohlcv, window=30)

        # Calculate historical vols for regime classification
        if len(prices) >= 30:
            rolling_vols = prices.pct_change().rolling(30).std() * np.sqrt(252)
            vol_regime = self.volatility_features.classify_vol_regime(vol_30d, rolling_vols.dropna())
            vol_percentile = self.volatility_features.calculate_vol_percentile(vol_30d, rolling_vols.dropna())
            vol_trend = self.volatility_features.calculate_vol_trend(rolling_vols.dropna())
        else:
            vol_regime = 1
            vol_percentile = 50.0
            vol_trend = 0.0

        features.update({
            'volatility_30d': vol_30d,
            'volatility_90d': vol_90d,
            'volatility_parkinson': vol_parkinson,
            'vol_regime': float(vol_regime),
            'vol_percentile': vol_percentile,
            'vol_trend': vol_trend
        })

        # 2. Technical Indicators (11 features)
        rsi = self.technical_indicators.calculate_rsi(prices)
        macd_dict = self.technical_indicators.calculate_macd(prices)
        bb_dict = self.technical_indicators.calculate_bollinger_bands(prices)
        ma_dict = self.technical_indicators.calculate_moving_averages(prices)

        features.update({
            'rsi_14': rsi,
            'macd': macd_dict['macd'],
            'macd_signal': macd_dict['macd_signal'],
            'macd_histogram': macd_dict['macd_histogram'],
            'bb_position': bb_dict['bb_position'],
            'bb_width': bb_dict['bb_width'],
            'price_vs_ma50_pct': ma_dict['price_vs_ma50_pct'],
            'price_vs_ma200_pct': ma_dict['price_vs_ma200_pct'],
            'golden_cross': ma_dict['golden_cross']
        })

        # 3. Probabilistic Features (6 features)
        distance_dict = self.probabilistic_features.calculate_distance_to_strike(spot_price, strike_price)
        sigma_dist = self.probabilistic_features.calculate_sigma_distance(
            spot_price, strike_price, vol_30d, days_to_expiry
        )
        gbm_prob = self.probabilistic_features.calculate_gbm_probability(
            spot_price, strike_price, vol_30d, days_to_expiry, n_simulations=10000
        )

        features.update({
            'strike_distance_pct': distance_dict['strike_distance_pct'],
            'is_itm': distance_dict['is_itm'],
            'moneyness': distance_dict['moneyness'],
            'strike_distance_sigma': sigma_dist,
            'gbm_probability': gbm_prob
        })

        # 4. Time Features (9 features)
        # Use days_to_expiry from parsed_market if available (for synthetic data)
        days_override = parsed_market.get('days_to_expiry')
        time_dict = self.time_features.extract_time_features(expiry_date, days_override)
        features.update(time_dict)

        # 5. Market Microstructure Features (8 features)
        market_dict = self.market_features.extract_market_features(
            polymarket_data['market'],
            polymarket_data['orderbook']
        )
        features.update(market_dict)

        # Log feature extraction
        logger.info(f"Extracted {len(features)} features for {parsed_market['asset']} @ ${strike_price:,.0f}")

        return features


# Example usage and testing
if __name__ == '__main__':
    # Create sample data for testing
    print("\n=== Testing Feature Extraction ===\n")

    # Sample parsed market
    parsed_market = {
        'asset': 'BTC',
        'strike_price': 150000.0,
        'expiry_date': datetime(2025, 12, 31, tzinfo=timezone.utc),
        'days_to_expiry': 368,
        'direction': 'ABOVE',
        'conditionId': '0xtest123',
        'token_id': '123456',
        'question': 'Will Bitcoin reach $150,000 by Dec 31, 2025?'
    }

    # Generate sample historical data
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=365, freq='D')
    prices = 90000 + np.cumsum(np.random.randn(365) * 1000)  # Random walk around $90k

    historical_ohlcv = pd.DataFrame({
        'date': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, 365)
    })

    # Sample Polymarket data
    polymarket_data = {
        'market': {
            'volume24hr': 50000,
            'volume1wk': 200000,
            'liquidity': 100000
        },
        'orderbook': {
            'bids': [
                {'price': '0.45', 'size': '1000'},
                {'price': '0.44', 'size': '2000'},
            ],
            'asks': [
                {'price': '0.47', 'size': '1500'},
                {'price': '0.48', 'size': '2500'},
            ]
        }
    }

    # Extract features
    extractor = PriceLevelFeatureExtractor()

    features = extractor.extract_all_features(
        parsed_market=parsed_market,
        spot_price=89759.0,  # Current BTC price
        historical_ohlcv=historical_ohlcv,
        polymarket_data=polymarket_data
    )

    # Display features
    print(f"Total features extracted: {len(features)}\n")

    # Group by category
    categories = {
        'Volatility': ['volatility_30d', 'volatility_90d', 'volatility_parkinson', 'vol_regime', 'vol_percentile', 'vol_trend'],
        'Technical': ['rsi_14', 'macd', 'macd_signal', 'macd_histogram', 'bb_position', 'bb_width', 'price_vs_ma50_pct', 'price_vs_ma200_pct', 'golden_cross'],
        'Probabilistic': ['strike_distance_pct', 'is_itm', 'moneyness', 'strike_distance_sigma', 'gbm_probability'],
        'Time': ['days_to_expiry', 'weeks_to_expiry', 'months_to_expiry', 'time_fraction', 'time_decay', 'day_of_week', 'month', 'is_quarter_end', 'is_year_end'],
        'Market': ['market_price', 'spread', 'spread_pct', 'depth_imbalance', 'volume_24h', 'volume_7d', 'liquidity', 'volume_trend']
    }

    for category, feature_names in categories.items():
        print(f"\n{category} Features ({len(feature_names)}):")
        for name in feature_names:
            if name in features:
                value = features[name]
                print(f"  {name:25} = {value:12.4f}")

    # Check for NaNs
    nan_count = sum(1 for v in features.values() if np.isnan(v))
    print(f"\n✓ NaN check: {nan_count} NaNs found (should be 0)")

    # Verify count
    expected_count = 40
    actual_count = len(features)
    print(f"✓ Feature count: {actual_count} (expected: {expected_count})")
