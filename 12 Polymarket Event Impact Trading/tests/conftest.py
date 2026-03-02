"""
Pytest fixtures and shared test utilities
"""

import sys
import pytest
import sqlite3
import tempfile
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock
import numpy as np
import pandas as pd

# Ensure src/ is on the path for internal imports (e.g., features.common_features)
_src_path = str(Path(__file__).parent.parent / 'src')
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_json_file():
    """Create a temporary JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def sample_market():
    """Sample market data from Polymarket API."""
    return {
        'conditionId': '0x1234567890abcdef',
        'question': 'Will Bitcoin reach $100,000 by end of 2026?',
        'description': 'This market resolves YES if BTC hits $100k',
        'active': True,
        'closed': False,
        'volume': 50000.0,
        'liquidity': 10000.0,
        'endDate': (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        'endDateIso': (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        'outcomePrices': '[0.35, 0.65]',
        'clobTokenIds': '["0xtoken1", "0xtoken2"]',
        'tokens': [
            {'outcome': 'yes', 'token_id': '0xtoken1', 'price': 0.35},
            {'outcome': 'no', 'token_id': '0xtoken2', 'price': 0.65}
        ],
        'slug': 'bitcoin-100k-2026'
    }


@pytest.fixture
def sample_event():
    """Sample event from news sources."""
    from event_detector import Event
    return Event(
        title='Bitcoin Surges Past $95,000 on ETF Inflows',
        description='Bitcoin price hits new all-time high as institutional demand surges',
        source='Reuters',
        published_time=datetime.now(timezone.utc),
        url='https://example.com/news/btc-surge',
        keywords=['Bitcoin', 'BTC', 'ETF', 'Institutional', 'Price']
    )


@pytest.fixture
def sample_orderbook():
    """Sample orderbook data."""
    return {
        'bids': [
            {'price': 0.34, 'size': 100},
            {'price': 0.33, 'size': 200},
            {'price': 0.32, 'size': 150}
        ],
        'asks': [
            {'price': 0.36, 'size': 120},
            {'price': 0.37, 'size': 180},
            {'price': 0.38, 'size': 160}
        ],
        'last_trade_price': 0.35
    }


@pytest.fixture
def sample_historical_prices():
    """Sample historical price data."""
    timestamps = pd.date_range(
        start=datetime.now() - timedelta(hours=24),
        end=datetime.now(),
        freq='1h'
    )
    return pd.DataFrame({
        'timestamp': timestamps,
        'price': np.random.uniform(0.3, 0.4, len(timestamps)),
        'size': np.random.uniform(10, 100, len(timestamps))
    })


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for price-level markets."""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='D')
    prices = 50000 + np.cumsum(np.random.randn(100) * 1000)

    return pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.uniform(1e9, 5e9, 100)
    })


@pytest.fixture
def sample_features():
    """Sample feature dictionary for ML model."""
    return {
        'trade_count': 150,
        'market_volume': 25000.0,
        'price_start': 0.32,
        'price_end': 0.35,
        'price_mean': 0.335,
        'price_std': 0.015,
        'price_min': 0.30,
        'price_max': 0.38,
        'price_range': 0.08,
        'price_change_pct': 9.375,
        'momentum_5': 0.02,
        'sma_5': 0.34,
        'momentum_10': 0.03,
        'sma_10': 0.33,
        'volatility_10': 0.02,
        'volume_total': 150000.0,
        'volume_mean': 1500.0,
        'volume_std': 300.0,
        'is_crypto': 1,
        'is_politics': 0,
        'is_sports': 0,
        'news_sentiment_mean': 0.6,
        'news_sentiment_std': 0.2,
        'news_count': 5
    }


@pytest.fixture
def mock_polymarket_client():
    """Mock Polymarket client with typical responses."""
    client = MagicMock()

    # Mock get_markets
    client.get_markets.return_value = [
        {
            'conditionId': '0xmarket1',
            'question': 'Will BTC hit $100k?',
            'volume': 50000,
            'active': True,
            'outcomePrices': '[0.4, 0.6]'
        },
        {
            'conditionId': '0xmarket2',
            'question': 'Will ETH hit $5k?',
            'volume': 30000,
            'active': True,
            'outcomePrices': '[0.3, 0.7]'
        }
    ]

    # Mock get_market_prices
    client.get_market_prices.return_value = {'yes': 0.35, 'no': 0.65}

    # Mock get_market_yes_price
    client.get_market_yes_price.return_value = 0.35

    # Mock get_orderbook
    client.get_orderbook.return_value = {
        'bids': [{'price': 0.34, 'size': 100}],
        'asks': [{'price': 0.36, 'size': 120}],
        'last_trade_price': 0.35
    }

    # Mock get_market
    client.get_market.return_value = {
        'conditionId': '0xmarket1',
        'tokens': [
            {'outcome': 'yes', 'token_id': '0xtoken1', 'price': 0.35},
            {'outcome': 'no', 'token_id': '0xtoken2', 'price': 0.65}
        ]
    }

    return client


@pytest.fixture
def sample_config():
    """Sample configuration for traders."""
    return {
        'polymarket_api_key': 'test_api_key',
        'polymarket_api_secret': 'test_api_secret',
        'news_api_key': 'test_news_key',
        'model_path': 'models/test_model.pkl',
        'model_type': 'random_forest',
        'min_confidence': 0.65,
        'min_expected_return': 0.03,
        'max_position_size': 100,
        'max_positions': 10,
        'max_daily_loss': 500,
        'paper_trading': True,
        'paper_trading_balance': 1000.0,
        'cycle_interval_seconds': 300,
        'circuit_breaker_losses': 3,
        'circuit_breaker_cooldown_hours': 4.0,
        'stop_loss': {
            'enabled': True,
            'pct': 15,
            'trailing': True,
            'trailing_distance_pct': 10
        },
        'take_profit': {
            'enabled': True,
            'pct': 50
        }
    }


@pytest.fixture
def trained_mock_model():
    """Mock trained ML model."""
    model = MagicMock()
    model.predict.return_value = np.array([1])  # Predict UP
    model.predict_proba.return_value = np.array([[0.1, 0.7, 0.2]])  # [DOWN, UP, NEUTRAL]
    model.is_trained = True
    model.feature_names = [
        'trade_count', 'market_volume', 'price_start', 'price_end',
        'price_mean', 'price_std', 'price_min', 'price_max',
        'price_range', 'price_change_pct', 'momentum_5', 'sma_5',
        'momentum_10', 'sma_10', 'volatility_10', 'volume_total',
        'volume_mean', 'volume_std', 'is_crypto', 'is_politics',
        'is_sports', 'news_sentiment_mean', 'news_sentiment_std', 'news_count'
    ]
    return model


@pytest.fixture
def sample_position():
    """Sample position data."""
    return {
        'market_id': '0xmarket123',
        'token_id': '0xtoken123',
        'entry_time': datetime.now(timezone.utc),
        'entry_price': 0.35,
        'side': 'YES',
        'size': 50.0,
        'metadata': {
            'question': 'Will BTC hit $100k?',
            'confidence': 0.7,
            'edge': 0.15
        }
    }


@pytest.fixture
def sample_training_data():
    """Sample training dataset for ML models."""
    np.random.seed(42)
    n_samples = 100

    data = {
        'trade_count': np.random.randint(50, 500, n_samples),
        'market_volume': np.random.uniform(10000, 100000, n_samples),
        'price_start': np.random.uniform(0.2, 0.8, n_samples),
        'price_end': np.random.uniform(0.2, 0.8, n_samples),
        'price_mean': np.random.uniform(0.3, 0.7, n_samples),
        'price_std': np.random.uniform(0.01, 0.1, n_samples),
        'price_min': np.random.uniform(0.1, 0.4, n_samples),
        'price_max': np.random.uniform(0.6, 0.9, n_samples),
        'price_range': np.random.uniform(0.1, 0.5, n_samples),
        'price_change_pct': np.random.uniform(-20, 20, n_samples),
        'momentum_5': np.random.uniform(-0.1, 0.1, n_samples),
        'sma_5': np.random.uniform(0.3, 0.7, n_samples),
        'momentum_10': np.random.uniform(-0.1, 0.1, n_samples),
        'sma_10': np.random.uniform(0.3, 0.7, n_samples),
        'volatility_10': np.random.uniform(0.01, 0.1, n_samples),
        'volume_total': np.random.uniform(10000, 100000, n_samples),
        'volume_mean': np.random.uniform(100, 1000, n_samples),
        'volume_std': np.random.uniform(10, 200, n_samples),
        'is_crypto': np.random.randint(0, 2, n_samples),
        'is_politics': np.random.randint(0, 2, n_samples),
        'is_sports': np.random.randint(0, 2, n_samples),
        'news_sentiment_mean': np.random.uniform(-1, 1, n_samples),
        'news_sentiment_std': np.random.uniform(0, 0.5, n_samples),
        'news_count': np.random.randint(1, 20, n_samples)
    }

    X = pd.DataFrame(data)
    y = np.random.choice([-1, 0, 1], n_samples)  # DOWN, NEUTRAL, UP

    return X, y


@pytest.fixture(autouse=True)
def reset_random_state():
    """Reset random state before each test for reproducibility."""
    np.random.seed(42)

# Short-Expiry Bot Specific Fixtures

@pytest.fixture
def sample_market_short_expiry():
    """Sample short-expiry market."""
    now = datetime.now(timezone.utc)
    return {
        'conditionId': 'test_se_market_123',
        'question': 'Will Bitcoin price be above $60,000 by end of day?',
        'endDate': (now + timedelta(hours=12)).isoformat(),
        'volume24hr': '5000.0',
        'liquidity': '2500.0',
        'lastTradePrice': 0.65,
        'bestBid': 0.63,
        'bestAsk': 0.67,
        'outcomes': ['Yes', 'No'],
        'active': True
    }


@pytest.fixture
def short_expiry_config():
    """Configuration for short-expiry bot."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "paper_trading": True,
            "paper_trading_balance": 500.0,
            "paper_trading_balance_file": "data/test_balance_se.json",
            "discovery": {
                "ultra_short_hours": [0, 24],
                "short_hours": [24, 72],
                "medium_hours": [72, 168],
                "min_volume": {"ultra_short": 100, "short": 200, "medium": 300},
                "min_liquidity": {"ultra_short": 50, "short": 100, "medium": 150},
                "max_spread_pct": {"ultra_short": 10.0, "short": 8.0, "medium": 6.0},
                "min_price": 0.05,
                "max_price": 0.95,
                "crypto_only": False
            },
            "position_limits": {
                "max_total_positions": 15,
                "max_positions_per_bucket": {"ultra_short": 5, "short": 7, "medium": 8},
                "max_position_size": {"ultra_short": 50, "short": 75, "medium": 100},
                "min_position_size": 10
            },
            "risk_management": {
                "stop_loss_pct": {"ultra_short": 10, "short": 15, "medium": 20},
                "take_profit_pct": {"ultra_short": 30, "short": 50, "medium": 75},
                "pre_expiry_exit_hours": 2,
                "circuit_breaker_losses": 4,
                "min_edge": 0.03,
                "min_confidence": 0.55
            },
            "rules": {
                "arbitrage": {"enabled": True, "max_total_price": 0.98, "min_edge": 0.02},
                "mean_reversion": {"enabled": True, "min_spread_pct": 5.0, "min_volume_24h": 1000},
                "momentum": {"enabled": True, "min_price_change_1h": 0.02}
            },
            "telegram": {"enabled": False},
            "database": {"positions_db": "data/test_positions_se.db"}
        }
        json.dump(config, f)
        path = f.name
    
    yield path
    
    # Cleanup
    try:
        os.unlink(path)
        os.unlink("data/test_balance_se.json")
        os.unlink("data/test_positions_se.db")
    except:
        pass
