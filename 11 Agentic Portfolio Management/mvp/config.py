"""Configuration management for MVP"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google Gemini Configuration (primary LLM)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

# Ollama Configuration (fallback LLM - local, free)
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:14b')

# Alpaca Configuration
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

# Risk Management Settings
MAX_POSITION_SIZE_PCT = float(os.getenv('MAX_POSITION_SIZE_PCT', '0.10'))  # 10%
MAX_PORTFOLIO_VOLATILITY = float(os.getenv('MAX_PORTFOLIO_VOLATILITY', '0.15'))  # 15%
MIN_CASH_RESERVE_PCT = float(os.getenv('MIN_CASH_RESERVE_PCT', '0.05'))  # 5%

# Negligible Position Thresholds (positions below these are ignored)
MIN_POSITION_VALUE = float(os.getenv('MIN_POSITION_VALUE', '100'))  # $100 minimum
MIN_POSITION_PCT = float(os.getenv('MIN_POSITION_PCT', '0.001'))  # 0.1% of portfolio

# Report Settings
TOP_K_HOLDINGS = int(os.getenv('TOP_K_HOLDINGS', '10'))  # Show top K holdings in report

# Agent Settings
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '60'))  # For momentum analysis
MOMENTUM_THRESHOLD = float(os.getenv('MOMENTUM_THRESHOLD', '0.05'))  # 5% threshold

# Data Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)


def validate_config():
    """Validate that required configuration is present"""
    errors = []

    # Check Alpaca credentials
    if not ALPACA_API_KEY:
        errors.append('ALPACA_API_KEY')
    if not ALPACA_SECRET_KEY:
        errors.append('ALPACA_SECRET_KEY')

    # At least one LLM must be available (checked at runtime in LLMClient)
    # Gemini needs API key, Ollama needs server running

    if errors:
        raise ValueError(
            f"Missing required environment variables: {', '.join(errors)}\n"
            f"Please check your .env file."
        )

    return True
