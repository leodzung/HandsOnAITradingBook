"""
External Data Sources for Price-Level Trading Strategy
Fetches spot prices from CoinGecko (BTC/ETH) and Yahoo Finance (Gold).
Implements caching to reduce API calls.
"""

import sqlite3
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SpotPriceDataSource:
    """Fetch spot prices from CoinGecko and Yahoo Finance with caching."""

    # CoinGecko API mappings
    COINGECKO_IDS = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum'
    }

    # Yahoo Finance ticker mappings
    YAHOO_TICKERS = {
        'BTC': 'BTC-USD',
        'ETH': 'ETH-USD',
        'GOLD': 'GC=F'  # Gold futures
    }

    def __init__(self, cache_db_path: str = 'data/spot_prices.db',
                 cache_minutes: int = 10):
        """
        Initialize data source.

        Args:
            cache_db_path: Path to SQLite cache database
            cache_minutes: Cache expiry in minutes (default: 10, increased to reduce API calls)
        """
        self.cache_db_path = cache_db_path
        self.cache_minutes = cache_minutes
        self._last_api_call = 0
        self._min_api_interval = 6.0  # Minimum 6 seconds between API calls (10/min limit)
        self._init_cache()

        logger.info(f"SpotPriceDataSource initialized with cache: {cache_db_path}")

    def _init_cache(self):
        """Create cache database if it doesn't exist."""
        # Ensure data directory exists
        Path(self.cache_db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        # Create table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spot_prices (
                asset TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                price REAL NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY (asset, timestamp)
            )
        ''')

        # Create index for fast lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_asset_timestamp
            ON spot_prices(asset, timestamp DESC)
        ''')

        conn.commit()
        conn.close()

        logger.info("Cache database initialized")

    def get_current_price(self, asset: str) -> float:
        """
        Get current spot price with caching.

        Args:
            asset: 'BTC', 'ETH', or 'GOLD'

        Returns:
            Current price in USD

        Raises:
            ValueError: If asset is not supported
            Exception: If all API calls fail
        """
        # Check cache first
        cached_price = self._get_cached_price(asset)
        if cached_price is not None:
            logger.debug(f"Cache hit for {asset}: ${cached_price:.2f}")
            return cached_price

        # Cache miss - fetch from API
        logger.debug(f"Cache miss for {asset}, fetching from API...")

        try:
            if asset in ['BTC', 'ETH']:
                price = self._fetch_coingecko(asset)
                source = 'coingecko'
            elif asset == 'GOLD':
                price = self._fetch_yahoo_current(asset)
                source = 'yahoo'
            else:
                raise ValueError(f"Unsupported asset: {asset}. Must be BTC, ETH, or GOLD")

            # Cache the price
            self._cache_price(asset, price, source)

            logger.info(f"Fetched {asset} price: ${price:.2f} from {source}")
            return price

        except Exception as e:
            logger.error(f"Error fetching price for {asset}: {e}")
            raise

    def get_historical_ohlcv(self, asset: str, days: int = 365) -> pd.DataFrame:
        """
        Get historical OHLCV data.
        Uses CoinGecko for BTC/ETH (more reliable), Yahoo Finance for GOLD.

        Args:
            asset: 'BTC', 'ETH', or 'GOLD'
            days: Number of days of history (default: 365)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume

        Raises:
            ValueError: If asset is not supported
            Exception: If download fails
        """
        if asset not in ['BTC', 'ETH', 'GOLD']:
            raise ValueError(f"Unsupported asset: {asset}")

        try:
            logger.info(f"Downloading historical data for {asset}...")

            # Use CoinGecko for crypto (more reliable)
            if asset in ['BTC', 'ETH']:
                data = self._fetch_coingecko_historical(asset, days)
            else:
                # Use Yahoo Finance for Gold
                data = self._fetch_yahoo_historical(asset, days)

            if data.empty:
                raise Exception(f"No data returned for {asset}")

            # CoinGecko data is already formatted, Yahoo data needs cleaning
            if asset == 'GOLD':
                # Clean up Yahoo Finance data
                if 'Date' in data.columns or data.index.name == 'Date':
                    data.reset_index(inplace=True)
                data.columns = [c.lower() for c in data.columns]

            # Trim to requested days
            if len(data) > days:
                data = data.tail(days)

            # Ensure we have required columns
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in data.columns for col in required_cols):
                logger.warning(f"Missing some columns. Available: {data.columns.tolist()}")

            logger.info(f"Returned {len(data)} days of data for {asset}")
            return data

        except Exception as e:
            logger.error(f"Error downloading historical data for {asset}: {e}")
            raise

    def _get_cached_price(self, asset: str) -> Optional[float]:
        """
        Get price from cache if fresh enough.

        Args:
            asset: Asset symbol

        Returns:
            Cached price if available and fresh, None otherwise
        """
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.cache_minutes)

        cursor.execute('''
            SELECT price FROM spot_prices
            WHERE asset = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (asset, cutoff.isoformat()))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def _cache_price(self, asset: str, price: float, source: str):
        """
        Cache a price in the database.

        Args:
            asset: Asset symbol
            price: Price value
            source: Data source (coingecko, yahoo)
        """
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        timestamp = datetime.now(timezone.utc)

        cursor.execute('''
            INSERT OR REPLACE INTO spot_prices (asset, timestamp, price, source)
            VALUES (?, ?, ?, ?)
        ''', (asset, timestamp.isoformat(), price, source))

        conn.commit()
        conn.close()

        logger.debug(f"Cached {asset} price: ${price:.2f} from {source}")

    def _rate_limit(self):
        """Enforce rate limiting for API calls."""
        elapsed = time.time() - self._last_api_call
        if elapsed < self._min_api_interval:
            sleep_time = self._min_api_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self._last_api_call = time.time()

    def _fetch_coingecko(self, asset: str) -> float:
        """
        Fetch current price from CoinGecko API with rate limiting and retries.

        Args:
            asset: 'BTC' or 'ETH'

        Returns:
            Current price in USD

        Raises:
            Exception: If API call fails after retries
        """
        url = 'https://api.coingecko.com/api/v3/simple/price'
        params = {
            'ids': self.COINGECKO_IDS[asset],
            'vs_currencies': 'usd'
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Enforce rate limiting
                self._rate_limit()

                response = requests.get(url, params=params, timeout=10)

                # Handle rate limiting (429)
                if response.status_code == 429:
                    wait_time = 60 * (attempt + 1)  # 60s, 120s, 180s
                    logger.warning(f"CoinGecko rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()

                data = response.json()
                price = data[self.COINGECKO_IDS[asset]]['usd']

                return float(price)

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 10 * (attempt + 1)
                    logger.warning(f"CoinGecko API error for {asset}: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"CoinGecko API error for {asset} after {max_retries} attempts: {e}")
                    raise
            except (KeyError, ValueError) as e:
                logger.error(f"Error parsing CoinGecko response for {asset}: {e}")
                raise

        raise Exception(f"Failed to fetch {asset} price after {max_retries} attempts")

    def _fetch_coingecko_historical(self, asset: str, days: int) -> pd.DataFrame:
        """
        Fetch historical OHLCV from CoinGecko API with rate limiting.

        Args:
            asset: 'BTC' or 'ETH'
            days: Number of days of history

        Returns:
            DataFrame with date, open, high, low, close, volume
        """
        url = f'https://api.coingecko.com/api/v3/coins/{self.COINGECKO_IDS[asset]}/ohlc'
        params = {
            'vs_currency': 'usd',
            'days': min(days, 365)  # CoinGecko free tier: max 365 days for OHLC
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Enforce rate limiting
                self._rate_limit()

                response = requests.get(url, params=params, timeout=30)

                # Handle rate limiting (429)
                if response.status_code == 429:
                    wait_time = 60 * (attempt + 1)
                    logger.warning(f"CoinGecko rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                break

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 10 * (attempt + 1)
                    logger.warning(f"Retrying CoinGecko historical in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise

        try:

            data_raw = response.json()

            # Convert to DataFrame
            # Format: [[timestamp, open, high, low, close], ...]
            df = pd.DataFrame(data_raw, columns=['timestamp', 'open', 'high', 'low', 'close'])

            # Convert timestamp to datetime
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.drop('timestamp', axis=1)

            # Add volume column (CoinGecko OHLC doesn't include volume, so set to 0)
            df['volume'] = 0

            # Reorder columns
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

            logger.info(f"Downloaded {len(df)} days from CoinGecko for {asset}")

            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"CoinGecko historical API error for {asset}: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing CoinGecko historical response for {asset}: {e}")
            raise

    def _fetch_yahoo_historical(self, asset: str, days: int) -> pd.DataFrame:
        """
        Fetch historical OHLCV from Yahoo Finance.

        Args:
            asset: Asset symbol
            days: Number of days of history

        Returns:
            DataFrame with date, open, high, low, close, volume
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance is required. Install with: pip install yfinance")

        ticker = self.YAHOO_TICKERS[asset]

        # Calculate start and end dates
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 30)  # Add buffer

        # Download data with retries
        import time
        data = pd.DataFrame()

        for attempt in range(3):
            try:
                # Create Ticker object
                ticker_obj = yf.Ticker(ticker)

                # Download using start/end dates
                data = ticker_obj.history(
                    start=start_date,
                    end=end_date,
                    interval='1d',
                    auto_adjust=False,
                    actions=False
                )

                if not data.empty:
                    logger.info(f"Downloaded {len(data)} days from Yahoo Finance for {asset}")
                    break

                logger.warning(f"Empty data on attempt {attempt+1}, retrying...")
                time.sleep(5 * (attempt + 1))  # 5s, 10s, 15s delays

            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning(f"Attempt {attempt+1} failed: {e}, retrying...")
                time.sleep(5 * (attempt + 1))

        return data

    def _fetch_yahoo_current(self, asset: str) -> float:
        """
        Fetch current price from Yahoo Finance.

        Args:
            asset: Asset symbol

        Returns:
            Current price

        Raises:
            ImportError: If yfinance is not installed
            Exception: If fetch fails
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError(
                "yfinance is required. Install with: pip install yfinance"
            )

        ticker = self.YAHOO_TICKERS[asset]

        try:
            # Get ticker object
            ticker_obj = yf.Ticker(ticker)

            # Get current price from info
            info = ticker_obj.info
            price = info.get('regularMarketPrice') or info.get('previousClose')

            if price is None:
                raise Exception(f"No price data available for {ticker}")

            return float(price)

        except Exception as e:
            logger.error(f"Yahoo Finance error for {asset}: {e}")
            raise

    def clear_cache(self, asset: Optional[str] = None, older_than_days: Optional[int] = None):
        """
        Clear cached prices.

        Args:
            asset: If specified, clear only this asset. Otherwise clear all.
            older_than_days: If specified, clear only prices older than N days
        """
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        if older_than_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            if asset:
                cursor.execute('DELETE FROM spot_prices WHERE asset = ? AND timestamp < ?',
                              (asset, cutoff.isoformat()))
            else:
                cursor.execute('DELETE FROM spot_prices WHERE timestamp < ?',
                              (cutoff.isoformat(),))
        else:
            if asset:
                cursor.execute('DELETE FROM spot_prices WHERE asset = ?', (asset,))
            else:
                cursor.execute('DELETE FROM spot_prices')

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Cleared {deleted} cached prices")

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT asset, COUNT(*), MIN(timestamp), MAX(timestamp) FROM spot_prices GROUP BY asset')
        results = cursor.fetchall()

        stats = {}
        for asset, count, min_ts, max_ts in results:
            stats[asset] = {
                'count': count,
                'oldest': min_ts,
                'newest': max_ts
            }

        conn.close()

        return stats


# Example usage
if __name__ == '__main__':
    # Initialize data source
    data_source = SpotPriceDataSource()

    # Test current price fetching
    print("\n=== Testing Current Prices ===")
    for asset in ['BTC', 'ETH', 'GOLD']:
        try:
            price = data_source.get_current_price(asset)
            print(f"{asset}: ${price:,.2f}")
        except Exception as e:
            print(f"{asset}: ERROR - {e}")

    # Test caching (should return from cache on second call)
    print("\n=== Testing Cache ===")
    for asset in ['BTC']:
        start = time.time()
        price1 = data_source.get_current_price(asset)
        time1 = time.time() - start

        start = time.time()
        price2 = data_source.get_current_price(asset)
        time2 = time.time() - start

        print(f"{asset}: First call {time1*1000:.1f}ms, Second call {time2*1000:.1f}ms (cached)")
        assert abs(price1 - price2) < 0.01, "Cached price should match"

    # Test historical data
    print("\n=== Testing Historical Data ===")
    for asset in ['BTC']:
        try:
            df = data_source.get_historical_ohlcv(asset, days=30)
            print(f"{asset}: Downloaded {len(df)} days, Latest price: ${df['close'].iloc[-1]:,.2f}")
            print(f"  Columns: {df.columns.tolist()}")
        except Exception as e:
            print(f"{asset}: ERROR - {e}")

    # Show cache stats
    print("\n=== Cache Statistics ===")
    stats = data_source.get_cache_stats()
    for asset, data in stats.items():
        print(f"{asset}: {data['count']} entries, Latest: {data['newest']}")
