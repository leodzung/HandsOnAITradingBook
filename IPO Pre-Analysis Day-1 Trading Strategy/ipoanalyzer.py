#region imports
from AlgorithmImports import *
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
#endregion


class IPOFeatureExtractor:
    """
    Extracts features from S-1 filings and market data for IPO scoring.

    In a real implementation, you would:
    1. Download S-1 PDF from SEC EDGAR
    2. Parse financial tables (BeautifulSoup, PDFPlumber)
    3. Extract text sections (risk factors, business description)
    4. Calculate ratios and metrics

    For now, this shows the feature engineering logic.
    """

    def __init__(self, qb=None):
        """
        Initialize with QuantBook for historical data access.

        Args:
            qb: QuantBook instance (for research) or None (for live)
        """
        self.qb = qb

    def extract_all_features(self, ipo_data):
        """
        Extract all 28 features for model scoring.

        Args:
            ipo_data: Dictionary with IPO information from S-1 and market data

        Returns:
            List of 28 feature values
        """
        features = []

        # 1. Fundamental Features (10)
        features.extend(self._extract_fundamental_features(ipo_data))

        # 2. Deal Characteristics (8)
        features.extend(self._extract_deal_features(ipo_data))

        # 3. Market Conditions (5)
        features.extend(self._extract_market_features(ipo_data))

        # 4. Sentiment Features (5)
        features.extend(self._extract_sentiment_features(ipo_data))

        return features

    def _extract_fundamental_features(self, ipo_data):
        """
        Extract fundamental metrics from S-1 filing.

        Example S-1 sections to parse:
        - Summary Financial Data table
        - Management's Discussion & Analysis (MD&A)
        - Balance Sheet
        - Income Statement
        """
        fundamentals = ipo_data.get('fundamentals', {})

        # Revenue (most recent fiscal year, in millions)
        revenue = fundamentals.get('revenue', 0) / 1e6

        # Revenue growth YoY (%)
        revenue_growth = fundamentals.get('revenue_growth_yoy', 0) * 100

        # Gross margin (%)
        gross_margin = fundamentals.get('gross_margin', 0) * 100

        # Operating margin (%)
        operating_margin = fundamentals.get('operating_margin', 0) * 100

        # Profitability (1 if profitable, 0 if not)
        is_profitable = 1 if fundamentals.get('net_income', 0) > 0 else 0

        # Cash position (in millions)
        cash = fundamentals.get('cash', 0) / 1e6

        # Debt-to-equity ratio
        debt_to_equity = fundamentals.get('debt_to_equity', 0)

        # Customer concentration (% revenue from top 5 customers)
        customer_concentration = fundamentals.get('top5_customer_pct', 0) * 100

        # Employee count
        employees = fundamentals.get('employees', 0)

        # Company age (years since founding)
        founded_year = fundamentals.get('founded_year', 2020)
        company_age = datetime.now().year - founded_year

        return [
            revenue, revenue_growth, gross_margin, operating_margin,
            is_profitable, cash, debt_to_equity, customer_concentration,
            employees, company_age
        ]

    def _extract_deal_features(self, ipo_data):
        """
        Extract IPO deal characteristics.

        Sources:
        - Pricing announcement (usually 1 day before listing)
        - IPO prospectus final amendment
        - Underwriter syndicate info
        """
        deal = ipo_data.get('deal', {})

        # Offer price vs. expected range midpoint (%)
        offer_price = deal.get('offer_price', 20)
        range_low = deal.get('range_low', 18)
        range_high = deal.get('range_high', 22)
        range_midpoint = (range_low + range_high) / 2
        price_vs_range = ((offer_price - range_midpoint) / range_midpoint) * 100

        # Float percentage (shares offered / total shares outstanding)
        shares_offered = deal.get('shares_offered', 10e6)
        shares_outstanding = deal.get('shares_outstanding', 100e6)
        float_pct = (shares_offered / shares_outstanding) * 100

        # Price-to-sales ratio (valuation / revenue)
        market_cap = offer_price * shares_outstanding
        revenue = ipo_data.get('fundamentals', {}).get('revenue', 1)
        price_to_sales = market_cap / revenue if revenue > 0 else 0

        # Underwriter tier (1 = bulge bracket, 0 = others)
        # Bulge bracket: Goldman Sachs, Morgan Stanley, JP Morgan, etc.
        lead_underwriter = deal.get('lead_underwriter', '').lower()
        bulge_bracket = ['goldman', 'morgan stanley', 'jpmorgan', 'jp morgan',
                        'bank of america', 'citigroup', 'barclays', 'credit suisse']
        is_bulge_bracket = any(uw in lead_underwriter for uw in bulge_bracket)
        underwriter_tier = 1 if is_bulge_bracket else 0

        # Lock-up period (days, typically 180)
        lockup_days = deal.get('lockup_period', 180)

        # Greenshoe option size (% of offering, typically 15%)
        greenshoe_pct = deal.get('greenshoe_pct', 15)

        # Use of proceeds (1 = growth, 0 = selling shareholders)
        # Parse S-1 "Use of Proceeds" section
        use_for_growth = deal.get('proceeds_for_growth', 0.5)  # 0-1 scale

        # Over/under subscription (estimate from pricing vs range)
        # Strong pricing = oversubscribed
        subscription_level = max(0, price_vs_range / 10)  # Normalize

        return [
            price_vs_range, float_pct, price_to_sales, underwriter_tier,
            lockup_days, greenshoe_pct, use_for_growth, subscription_level
        ]

    def _extract_market_features(self, ipo_data):
        """
        Extract market condition features at time of IPO.

        Can be calculated in real-time using QuantConnect data.
        """
        market = ipo_data.get('market', {})

        # VIX level on pricing date
        vix = market.get('vix', 15)

        # S&P 500 return over prior 30 days (%)
        spy_return_30d = market.get('spy_return_30d', 0) * 100

        # Sector ETF return over prior 30 days (%)
        sector_return_30d = market.get('sector_return_30d', 0) * 100

        # IPO market temperature (avg return of recent IPOs)
        # Track all IPOs from past 30 days, calculate avg first-day return
        ipo_market_temp = market.get('recent_ipo_avg_return', 0) * 100

        # Number of IPOs in same week (supply saturation)
        ipos_same_week = market.get('ipos_same_week', 1)

        return [vix, spy_return_30d, sector_return_30d, ipo_market_temp, ipos_same_week]

    def _extract_sentiment_features(self, ipo_data):
        """
        Extract sentiment features from news and social media.

        Uses FinBERT for news sentiment (similar to Example 19).
        """
        sentiment = ipo_data.get('sentiment', {})

        # FinBERT sentiment score (-1 to +1, aggregate of pre-IPO news)
        finbert_score = sentiment.get('finbert_score', 0)

        # News volume (number of articles in past 30 days)
        news_volume = sentiment.get('news_count', 0)

        # Sentiment velocity (change in sentiment over time)
        # Positive = improving sentiment
        sentiment_velocity = sentiment.get('sentiment_trend', 0)

        # Social media buzz (normalized score, 0-100)
        # From Twitter, Reddit, StockTwits mentions
        social_buzz = sentiment.get('social_buzz', 0)

        # Google Trends score (0-100)
        google_trends = sentiment.get('google_trends', 0)

        return [finbert_score, news_volume, sentiment_velocity, social_buzz, google_trends]

    def get_feature_names(self):
        """Return list of all feature names for model training."""
        return [
            # Fundamentals (10)
            'revenue_mm', 'revenue_growth_yoy', 'gross_margin', 'operating_margin',
            'is_profitable', 'cash_mm', 'debt_to_equity', 'customer_concentration',
            'employees', 'company_age',

            # Deal Characteristics (8)
            'price_vs_range', 'float_pct', 'price_to_sales', 'underwriter_tier',
            'lockup_days', 'greenshoe_pct', 'proceeds_for_growth', 'subscription_level',

            # Market Conditions (5)
            'vix', 'spy_return_30d', 'sector_return_30d', 'ipo_market_temp', 'ipos_same_week',

            # Sentiment (5)
            'finbert_score', 'news_volume', 'sentiment_velocity', 'social_buzz', 'google_trends'
        ]

    def calculate_market_features_live(self, algorithm, ipo_date, sector_etf='QQQ'):
        """
        Calculate market features in live trading using QuantConnect data.

        Args:
            algorithm: QCAlgorithm instance
            ipo_date: Date of the IPO
            sector_etf: Ticker of relevant sector ETF

        Returns:
            Dictionary with market features
        """
        # Get VIX
        vix_symbol = algorithm.add_index("VIX", Resolution.DAILY).symbol
        vix_history = algorithm.history(vix_symbol, 1, Resolution.DAILY)
        vix = vix_history['close'].iloc[-1] if not vix_history.empty else 15

        # Get SPY return (30 days)
        spy_symbol = algorithm.add_equity("SPY", Resolution.DAILY).symbol
        spy_history = algorithm.history(spy_symbol, 30, Resolution.DAILY)
        spy_return_30d = (spy_history['close'].iloc[-1] / spy_history['close'].iloc[0] - 1)

        # Get sector ETF return (30 days)
        sector_symbol = algorithm.add_equity(sector_etf, Resolution.DAILY).symbol
        sector_history = algorithm.history(sector_symbol, 30, Resolution.DAILY)
        sector_return_30d = (sector_history['close'].iloc[-1] / sector_history['close'].iloc[0] - 1)

        # IPO market temperature - would need to track recent IPOs
        # For simplicity, use SPY performance as proxy
        ipo_market_temp = spy_return_30d

        # IPOs same week - would need to track from calendar
        ipos_same_week = 1  # Default

        return {
            'vix': vix,
            'spy_return_30d': spy_return_30d,
            'sector_return_30d': sector_return_30d,
            'ipo_market_temp': ipo_market_temp,
            'ipos_same_week': ipos_same_week
        }


class IPOScorer:
    """
    Scores IPOs using a trained machine learning model.
    """

    def __init__(self, model_path=None):
        """
        Initialize with a trained model.

        Args:
            model_path: Path to serialized model (pickle file)
        """
        self.model = None
        self.feature_extractor = IPOFeatureExtractor()

        if model_path:
            self.load_model(model_path)

    def load_model(self, path):
        """Load trained model from file."""
        import joblib
        self.model = joblib.load(path)

    def score_ipo(self, ipo_data):
        """
        Score an IPO using the trained model.

        Args:
            ipo_data: Dictionary with all IPO information

        Returns:
            Score between 0 and 1 (probability of success)
        """
        if not self.model:
            # If no model, return neutral score
            return 0.50

        # Extract features
        features = self.feature_extractor.extract_all_features(ipo_data)

        # Predict probability
        features_array = np.array(features).reshape(1, -1)
        probability = self.model.predict_proba(features_array)[0][1]

        return probability
