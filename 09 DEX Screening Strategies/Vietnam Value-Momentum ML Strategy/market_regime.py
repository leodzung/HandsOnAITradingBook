"""
Market Regime Detection for Vietnamese Stock Market

Detects whether the market is in:
- Bull (trending up)
- Bear (trending down)
- Choppy (sideways/volatile)

Uses VN-Index data with multiple indicators.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class MarketRegimeDetector:
    """Detect market regime using VN-Index data."""

    def __init__(self, data_provider):
        """
        Initialize regime detector.

        Args:
            data_provider: VietnamDataProvider instance
        """
        self.data_provider = data_provider
        self.vnindex_data = None

    def load_vnindex_data(self, start_date, end_date):
        """
        Load VN-Index historical data.

        Args:
            start_date: Start date
            end_date: End date
        """
        # Fetch extra history for MA calculations
        fetch_start = start_date - timedelta(days=365)

        # Format dates as strings
        start_str = fetch_start.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        try:
            # Try to fetch VN-Index data
            self.vnindex_data = self.data_provider.get_market_index(
                index='VNINDEX',
                start_date=start_str,
                end_date=end_str
            )

            if self.vnindex_data is None or len(self.vnindex_data) == 0:
                print("⚠️  VN-Index data not available, using fallback")
                # Create synthetic index from top stocks as proxy
                return self._create_synthetic_index(fetch_start, end_date)

            return True

        except Exception as e:
            print(f"⚠️  Error fetching VN-Index: {e}")
            print("   Using synthetic index as fallback")
            return self._create_synthetic_index(fetch_start, end_date)

    def _create_synthetic_index(self, start_date, end_date):
        """Create synthetic market index from top stocks."""
        top_stocks = ['VNM', 'VCB', 'HPG', 'FPT', 'MSN']

        # Format dates as strings
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        # Fetch data for all stocks
        all_stocks_data = self.data_provider.get_historical_data(
            symbols=top_stocks,
            start_date=start_str,
            end_date=end_str,
            resolution='D'
        )

        if not all_stocks_data:
            return False

        # Extract close prices
        all_data = {}
        for symbol, data in all_stocks_data.items():
            if data is not None and len(data) > 0:
                all_data[symbol] = data['close']

        if not all_data:
            return False

        # Create equal-weight index
        df = pd.DataFrame(all_data)
        df['vnindex_synthetic'] = df.mean(axis=1)

        # Normalize to start at 1000 (like VN-Index)
        df['vnindex_synthetic'] = (df['vnindex_synthetic'] / df['vnindex_synthetic'].iloc[0]) * 1000

        self.vnindex_data = pd.DataFrame({
            'close': df['vnindex_synthetic']
        })
        self.vnindex_data.index = df.index

        return True

    def detect_regime(self, as_of_date):
        """
        Detect market regime as of a specific date.

        Args:
            as_of_date: Date to detect regime for

        Returns:
            str: 'bull', 'bear', or 'choppy'
        """
        if self.vnindex_data is None:
            return 'choppy'  # Default to choppy if no data

        # Filter data up to as_of_date
        data = self.vnindex_data[self.vnindex_data.index <= as_of_date].copy()

        if len(data) < 200:
            # Not enough data for 200-day MA
            return self._simple_regime_detection(data)

        # Calculate moving averages
        data['ma20'] = data['close'].rolling(window=20).mean()
        data['ma50'] = data['close'].rolling(window=50).mean()
        data['ma200'] = data['close'].rolling(window=200).mean()

        # Get latest values
        current_price = data['close'].iloc[-1]
        ma20 = data['ma20'].iloc[-1]
        ma50 = data['ma50'].iloc[-1]
        ma200 = data['ma200'].iloc[-1]

        # Calculate additional indicators

        # 1. Price vs MAs
        above_ma50 = current_price > ma50
        above_ma200 = current_price > ma200
        ma50_above_ma200 = ma50 > ma200

        # 2. MA slopes (rate of change)
        ma50_slope = (ma50 - data['ma50'].iloc[-10]) / data['ma50'].iloc[-10]
        ma200_slope = (ma200 - data['ma200'].iloc[-30]) / data['ma200'].iloc[-30]

        # 3. Volatility (choppy markets are more volatile)
        returns = data['close'].pct_change()
        volatility_20d = returns.tail(20).std() * np.sqrt(252)  # Annualized

        # 4. Momentum
        momentum_60d = (current_price - data['close'].iloc[-60]) / data['close'].iloc[-60]

        # Regime classification logic

        # BULL: Strong uptrend
        bull_conditions = [
            above_ma50 and above_ma200,  # Price above both MAs
            ma50_above_ma200,  # Golden cross
            ma50_slope > 0.02,  # MA50 rising > 2%
            momentum_60d > 0.05,  # Positive 60-day momentum > 5%
        ]

        # BEAR: Strong downtrend
        bear_conditions = [
            not above_ma50 and not above_ma200,  # Price below both MAs
            not ma50_above_ma200,  # Death cross
            ma50_slope < -0.02,  # MA50 falling > 2%
            momentum_60d < -0.05,  # Negative 60-day momentum > 5%
        ]

        # CHOPPY: Mixed signals or high volatility
        choppy_conditions = [
            volatility_20d > 0.25,  # High volatility (>25% annualized)
            abs(ma50_slope) < 0.015,  # Flat MA50 (< 1.5% change)
        ]

        # Decision logic
        bull_score = sum(bull_conditions)
        bear_score = sum(bear_conditions)
        choppy_score = sum(choppy_conditions)

        if bull_score >= 3:
            return 'bull'
        elif bear_score >= 3:
            return 'bear'
        elif choppy_score >= 1 or (bull_score == 2 and bear_score == 2):
            return 'choppy'
        else:
            # Mixed signals, use simple price vs MA200
            if current_price > ma200 * 1.03:
                return 'bull'
            elif current_price < ma200 * 0.97:
                return 'bear'
            else:
                return 'choppy'

    def _simple_regime_detection(self, data):
        """Simple regime detection when insufficient data for MAs."""
        if len(data) < 20:
            return 'choppy'

        # Use 20-day momentum
        current = data['close'].iloc[-1]
        past_20d = data['close'].iloc[-20] if len(data) >= 20 else data['close'].iloc[0]

        momentum = (current - past_20d) / past_20d

        if momentum > 0.10:  # >10% up in 20 days
            return 'bull'
        elif momentum < -0.10:  # >10% down in 20 days
            return 'bear'
        else:
            return 'choppy'

    def get_regime_details(self, as_of_date):
        """
        Get detailed regime information.

        Args:
            as_of_date: Date to analyze

        Returns:
            dict: Regime details including regime, indicators, confidence
        """
        regime = self.detect_regime(as_of_date)

        if self.vnindex_data is None:
            return {
                'regime': regime,
                'confidence': 'low',
                'reason': 'No VN-Index data available'
            }

        data = self.vnindex_data[self.vnindex_data.index <= as_of_date].copy()

        if len(data) < 200:
            return {
                'regime': regime,
                'confidence': 'medium',
                'reason': 'Limited historical data'
            }

        # Calculate indicators
        data['ma50'] = data['close'].rolling(window=50).mean()
        data['ma200'] = data['close'].rolling(window=200).mean()

        current_price = data['close'].iloc[-1]
        ma50 = data['ma50'].iloc[-1]
        ma200 = data['ma200'].iloc[-1]

        returns = data['close'].pct_change()
        volatility = returns.tail(20).std() * np.sqrt(252)
        momentum_60d = (current_price - data['close'].iloc[-60]) / data['close'].iloc[-60]

        # Build details
        details = {
            'regime': regime,
            'date': as_of_date,
            'price': current_price,
            'ma50': ma50,
            'ma200': ma200,
            'price_vs_ma50': (current_price / ma50 - 1) * 100,  # %
            'price_vs_ma200': (current_price / ma200 - 1) * 100,  # %
            'volatility': volatility * 100,  # %
            'momentum_60d': momentum_60d * 100,  # %
            'ma50_above_ma200': ma50 > ma200,
        }

        # Confidence assessment
        if regime == 'bull':
            if details['price_vs_ma200'] > 10 and details['momentum_60d'] > 10:
                details['confidence'] = 'high'
            elif details['price_vs_ma200'] > 5:
                details['confidence'] = 'medium'
            else:
                details['confidence'] = 'low'
        elif regime == 'bear':
            if details['price_vs_ma200'] < -10 and details['momentum_60d'] < -10:
                details['confidence'] = 'high'
            elif details['price_vs_ma200'] < -5:
                details['confidence'] = 'medium'
            else:
                details['confidence'] = 'low'
        else:  # choppy
            if details['volatility'] > 25:
                details['confidence'] = 'high'
            else:
                details['confidence'] = 'medium'

        return details


if __name__ == '__main__':
    """Test the regime detector."""
    from data_provider import VietnamDataProvider

    print("Testing Market Regime Detector")
    print("=" * 70)

    provider = VietnamDataProvider(data_source='vnstock', enable_cache=True)
    detector = MarketRegimeDetector(provider)

    # Load data
    end_date = datetime.now()
    start_date = datetime(2022, 1, 1)

    print("\nLoading VN-Index data...")
    success = detector.load_vnindex_data(start_date, end_date)

    if success:
        print("✅ Data loaded successfully")

        # Test on various dates
        test_dates = [
            datetime(2022, 6, 1),  # Expected: bear
            datetime(2023, 6, 1),  # Expected: choppy
            datetime(2024, 6, 1),  # Expected: bull
        ]

        print("\nRegime Detection Results:")
        print("-" * 70)

        for test_date in test_dates:
            details = detector.get_regime_details(test_date)
            print(f"\nDate: {test_date.date()}")
            print(f"Regime: {details['regime'].upper()} (confidence: {details.get('confidence', 'N/A')})")
            if 'price_vs_ma200' in details:
                print(f"Price vs MA200: {details['price_vs_ma200']:+.2f}%")
                print(f"60-day Momentum: {details['momentum_60d']:+.2f}%")
                print(f"Volatility: {details['volatility']:.2f}%")
    else:
        print("❌ Failed to load data")
