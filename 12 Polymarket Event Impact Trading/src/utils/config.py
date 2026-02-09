"""
Configuration file for Polymarket trading system.
Copy this to config.json and fill in your API keys.
"""

DEFAULT_CONFIG = {
    # Polymarket API credentials
    "polymarket_api_key": "YOUR_API_KEY_HERE",
    "polymarket_api_secret": "YOUR_API_SECRET_HERE",
    "polymarket_private_key": "YOUR_PRIVATE_KEY_HERE",

    # News API credentials
    "news_api_key": "YOUR_NEWS_API_KEY",  # From https://newsapi.org
    "twitter_bearer_token": None,  # Optional: Twitter API v2 bearer token

    # RSS feeds for news
    "rss_feeds": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://www.reuters.com/rssFeed/topNews",
    ],

    # Model settings
    "model_type": "random_forest",  # random_forest, gradient_boost, logistic, svm
    "model_path": "trained_model.pkl",  # Path to trained model
    "use_transformers": False,  # Use FinBERT for sentiment (requires GPU)

    # Trading parameters
    "paper_trading": True,  # Set to False for real trading
    "min_confidence": 0.65,  # Minimum model confidence to trade
    "min_expected_return": 0.03,  # Minimum expected return (3%)

    # Risk management
    "max_position_size": 100,  # Maximum $ per position
    "max_positions": 10,  # Maximum concurrent positions
    "max_daily_loss": 500,  # Maximum daily loss limit
    "hold_time_hours": 24,  # How long to hold positions

    # Market filters
    "min_market_volume": 1000,  # Minimum market volume
    "min_hours_to_expiry": 2,  # Minimum hours until market expires
    "max_hours_to_expiry": 720,  # Maximum hours (30 days)

    # Bot settings
    "cycle_interval_seconds": 300,  # Check for signals every 5 minutes
    "event_lookback_hours": 1,  # How far back to look for events

    # Feature engineering
    "use_sentiment_transformers": False,  # Use transformer models for sentiment
    "price_history_hours": 24,  # Hours of price history to use

    # Logging
    "log_level": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "log_file": "trader.log"
}


def create_config_file(filepath: str = "config.json"):
    """Create a template config file."""
    import json

    with open(filepath, 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)

    print(f"Created config template at {filepath}")
    print("Please edit this file and add your API keys before running the trader.")


if __name__ == '__main__':
    create_config_file()
