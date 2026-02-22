# data_provider.py
# Real Vietnamese stock market data integration module

"""
Vietnamese Stock Market Data Provider

Supports multiple data sources:
1. vnstock (Free) - Primary recommendation, actively maintained
2. FiinGroup API (Premium) - For institutional/serious traders
3. Manual CSV import - For custom data sources

Installation:
    pip install vnstock3
    # For FiinGroup: Contact fiingroup.vn for API credentials
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
import time
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')


class VietnamDataProvider:
    """
    Unified data provider for Vietnamese stock market.
    Supports multiple data sources with fallback mechanisms.
    """

    def __init__(self,
                 data_source='vnstock',
                 cache_dir='./data_cache',
                 api_key=None,
                 enable_cache=True):
        """
        Initialize data provider.

        Args:
            data_source: 'vnstock', 'fiingroup', or 'csv'
            cache_dir: Directory to cache downloaded data
            api_key: API key for premium sources (FiinGroup)
            enable_cache: Whether to cache data locally
        """
        self.data_source = data_source
        self.cache_dir = cache_dir
        self.api_key = api_key
        self.enable_cache = enable_cache

        # Create cache directory
        if enable_cache and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        # Initialize data source
        self._init_data_source()

    def _init_data_source(self):
        """Initialize the selected data source."""
        if self.data_source == 'vnstock':
            try:
                # Try vnstock3 first (new version)
                from vnstock3 import Vnstock
                self.vnstock = Vnstock()
                self.vnstock_version = 3
                print("✅ vnstock3 initialized successfully")
            except ImportError:
                try:
                    # Fall back to legacy vnstock
                    import vnstock
                    self.vnstock = vnstock
                    self.vnstock_version = 'legacy'
                    print("✅ Legacy vnstock initialized successfully")
                    print("⚠️  Consider upgrading: pip install git+https://github.com/thinh-vu/vnstock.git@main")
                except ImportError:
                    print("❌ vnstock not installed. Run: pip install vnstock")
                    print("Falling back to CSV mode")
                    self.data_source = 'csv'

        elif self.data_source == 'fiingroup':
            if not self.api_key:
                print("❌ FiinGroup API key required")
                print("Get your API key from: https://fiingroup.vn/ApiDataFeed")
                raise ValueError("API key required for FiinGroup")
            print("✅ FiinGroup API initialized")

        elif self.data_source == 'csv':
            print("📁 CSV mode - will load data from files")

        else:
            raise ValueError(f"Unknown data source: {self.data_source}")

    # ========== UNIVERSE / STOCK LISTING ==========

    def get_stock_listing(self,
                         exchange: str = 'HOSE',
                         min_market_cap: float = 1_000_000_000_000,
                         min_avg_volume: float = 500_000_000) -> List[str]:
        """
        Get list of stocks from Vietnamese exchanges.

        Args:
            exchange: 'HOSE', 'HNX', or 'UPCOM'
            min_market_cap: Minimum market cap in VND (default 1T = ~$40M USD)
            min_avg_volume: Minimum avg daily volume in VND (default 500M)

        Returns:
            List of stock symbols
        """
        print(f"Fetching {exchange} stock listing...")

        if self.data_source == 'vnstock':
            return self._get_listing_vnstock(exchange, min_market_cap, min_avg_volume)
        elif self.data_source == 'fiingroup':
            return self._get_listing_fiingroup(exchange, min_market_cap, min_avg_volume)
        else:
            return self._get_listing_csv(exchange)

    def _get_listing_vnstock(self, exchange, min_market_cap, min_avg_volume):
        """Get listing using vnstock."""
        try:
            if self.vnstock_version == 3:
                # vnstock3 API
                listing = self.vnstock.stock(symbol='ACB', source='VCI').listing.all_symbols()
            else:
                # Legacy vnstock API
                from vnstock import listing_companies
                listing = listing_companies()

            if listing is None or listing.empty:
                print("❌ Failed to fetch listing from vnstock")
                return self._get_default_universe(exchange)

            # Filter by exchange
            if 'exchange' in listing.columns:
                listing = listing[listing['exchange'] == exchange]
            elif 'exchangeName' in listing.columns:
                # Legacy format
                exchange_map = {'HOSE': 'HOSE', 'HNX': 'HNX', 'UPCOM': 'UPCOM'}
                listing = listing[listing['exchangeName'] == exchange_map.get(exchange, exchange)]

            # Extract symbols
            if 'ticker' in listing.columns:
                symbols = listing['ticker'].tolist()
            elif 'symbol' in listing.columns:
                symbols = listing['symbol'].tolist()
            elif 'Mã CK' in listing.columns:
                symbols = listing['Mã CK'].tolist()
            else:
                symbols = listing.index.tolist()

            print(f"✅ Found {len(symbols)} stocks on {exchange}")
            return symbols if len(symbols) > 0 else self._get_default_universe(exchange)

        except Exception as e:
            print(f"❌ Error fetching listing: {e}")
            # Return common Vietnamese blue chips as fallback
            return self._get_default_universe(exchange)

    def _get_listing_fiingroup(self, exchange, min_market_cap, min_avg_volume):
        """Get listing using FiinGroup API."""
        # Placeholder for FiinGroup API integration
        import requests

        url = "https://api.fiingroup.vn/Symbols/GetAllSymbols"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Filter by exchange and criteria
            # (Adjust based on actual FiinGroup API response format)
            symbols = []
            for stock in data.get('data', []):
                if stock.get('exchange') == exchange:
                    if stock.get('marketCap', 0) >= min_market_cap:
                        symbols.append(stock['symbol'])

            print(f"✅ Found {len(symbols)} stocks on {exchange}")
            return symbols

        except Exception as e:
            print(f"❌ FiinGroup API error: {e}")
            return self._get_default_universe(exchange)

    def _get_listing_csv(self, exchange):
        """Load listing from CSV file."""
        csv_path = os.path.join(self.cache_dir, f'{exchange}_listing.csv')

        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            symbols = df['symbol'].tolist()
            print(f"✅ Loaded {len(symbols)} stocks from {csv_path}")
            return symbols
        else:
            print(f"❌ CSV file not found: {csv_path}")
            return self._get_default_universe(exchange)

    def _get_default_universe(self, exchange):
        """Return default universe of liquid stocks."""
        if exchange == 'HOSE':
            return [
                'VNM', 'VIC', 'VHM', 'VCB', 'BID', 'CTG', 'MBB', 'ACB',
                'HPG', 'MSN', 'FPT', 'POW', 'SAB', 'GAS', 'PLX', 'VJC',
                'VRE', 'TCB', 'SSI', 'HDB', 'VPB', 'MWG', 'REE', 'VNM',
                'DCM', 'DPM', 'GVR', 'HSG', 'KDH', 'NVL', 'PDR', 'PNJ'
            ]
        elif exchange == 'HNX':
            return ['ACE', 'CEO', 'DGC', 'HUT', 'IDC', 'LAS', 'MBS', 'NRC',
                   'PLC', 'PVS', 'SHB', 'SHS', 'TIG', 'VC3', 'VCS', 'VGC']
        else:
            return []

    # ========== HISTORICAL PRICE DATA ==========

    def get_historical_data(self,
                           symbols: List[str],
                           start_date: str,
                           end_date: str,
                           resolution: str = 'D') -> Dict[str, pd.DataFrame]:
        """
        Fetch historical OHLCV data for multiple symbols.

        Args:
            symbols: List of stock symbols
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'
            resolution: 'D' (daily), 'W' (weekly), 'M' (monthly)

        Returns:
            Dictionary: {symbol: DataFrame with columns [date, open, high, low, close, volume]}
        """
        print(f"\nFetching historical data for {len(symbols)} stocks...")
        print(f"Period: {start_date} to {end_date}")

        data = {}
        success_count = 0
        fail_count = 0

        for i, symbol in enumerate(symbols, 1):
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(symbols)} stocks")

            try:
                df = self._fetch_historical_symbol(symbol, start_date, end_date, resolution)

                if df is not None and not df.empty:
                    data[symbol] = df
                    success_count += 1
                else:
                    fail_count += 1

            except Exception as e:
                print(f"  ❌ Error fetching {symbol}: {e}")
                fail_count += 1

            # Rate limiting
            time.sleep(0.2)  # Avoid overwhelming the API

        print(f"\n✅ Successfully fetched: {success_count}/{len(symbols)} stocks")
        if fail_count > 0:
            print(f"⚠️ Failed: {fail_count} stocks")

        return data

    def _fetch_historical_symbol(self, symbol, start_date, end_date, resolution):
        """Fetch historical data for a single symbol."""

        # Check cache first
        if self.enable_cache:
            cached_df = self._load_from_cache(symbol, start_date, end_date)
            if cached_df is not None:
                return cached_df

        # Fetch from data source
        if self.data_source == 'vnstock':
            df = self._fetch_historical_vnstock(symbol, start_date, end_date, resolution)
        elif self.data_source == 'fiingroup':
            df = self._fetch_historical_fiingroup(symbol, start_date, end_date, resolution)
        else:  # csv
            df = self._fetch_historical_csv(symbol, start_date, end_date)

        # Save to cache
        if df is not None and not df.empty and self.enable_cache:
            self._save_to_cache(symbol, df, start_date, end_date)

        return df

    def _fetch_historical_vnstock(self, symbol, start_date, end_date, resolution):
        """Fetch using vnstock."""
        try:
            if self.vnstock_version == 3:
                # vnstock3 API
                stock = self.vnstock.stock(symbol=symbol, source='VCI')
                df = stock.quote.history(start=start_date, end=end_date, interval='1D')
            else:
                # Legacy vnstock API
                from vnstock import stock_historical_data
                df = stock_historical_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    resolution='1D',
                    type='stock'
                )

            if df is None or df.empty:
                return None

            # Standardize column names
            if df.index.name == 'time' or df.index.name == 'tradingDate':
                df = df.reset_index()

            # Map vnstock columns to standard format (both versions)
            column_mapping = {
                'time': 'date',
                'tradingDate': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'priceOpen': 'open',
                'priceHigh': 'high',
                'priceLow': 'low',
                'priceClose': 'close',
                'dealVolume': 'volume'
            }

            # Rename columns
            df = df.rename(columns=column_mapping)

            # Select and order columns
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            df = df[[col for col in required_cols if col in df.columns]]

            # Convert date to datetime
            df['date'] = pd.to_datetime(df['date'])

            # Set date as index
            df = df.set_index('date')

            return df

        except Exception as e:
            # print(f"vnstock error for {symbol}: {e}")
            return None

    def _fetch_historical_fiingroup(self, symbol, start_date, end_date, resolution):
        """Fetch using FiinGroup API."""
        import requests

        url = f"https://api.fiingroup.vn/PriceData/GetHistory"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        params = {
            "symbol": symbol,
            "startDate": start_date,
            "endDate": end_date,
            "resolution": resolution
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            # Convert to DataFrame (adjust based on actual API response)
            df = pd.DataFrame(data.get('data', []))

            if df.empty:
                return None

            # Standardize columns
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            return df[['open', 'high', 'low', 'close', 'volume']]

        except Exception as e:
            # print(f"FiinGroup API error for {symbol}: {e}")
            return None

    def _fetch_historical_csv(self, symbol, start_date, end_date):
        """Load from CSV file."""
        csv_path = os.path.join(self.cache_dir, f'{symbol}_history.csv')

        if not os.path.exists(csv_path):
            return None

        try:
            df = pd.read_csv(csv_path, parse_dates=['date'], index_col='date')

            # Filter by date range
            df = df[(df.index >= start_date) & (df.index <= end_date)]

            return df

        except Exception as e:
            print(f"CSV error for {symbol}: {e}")
            return None

    # ========== FUNDAMENTAL DATA ==========

    def get_fundamental_data(self, symbols: List[str]) -> List[Dict]:
        """
        Fetch fundamental data for multiple symbols.

        Args:
            symbols: List of stock symbols

        Returns:
            List of dictionaries with fundamental metrics
        """
        print(f"\nFetching fundamental data for {len(symbols)} stocks...")

        fundamentals = []
        success_count = 0

        for i, symbol in enumerate(symbols, 1):
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(symbols)} stocks")

            try:
                fund_data = self._fetch_fundamental_symbol(symbol)

                if fund_data:
                    fundamentals.append(fund_data)
                    success_count += 1

            except Exception as e:
                print(f"  ❌ Error fetching fundamentals for {symbol}: {e}")

            time.sleep(0.2)

        print(f"✅ Successfully fetched: {success_count}/{len(symbols)} stocks\n")

        return fundamentals

    def _fetch_fundamental_symbol(self, symbol):
        """Fetch fundamental data for a single symbol."""

        if self.data_source == 'vnstock':
            return self._fetch_fundamental_vnstock(symbol)
        elif self.data_source == 'fiingroup':
            return self._fetch_fundamental_fiingroup(symbol)
        else:
            return self._fetch_fundamental_csv(symbol)

    def _fetch_fundamental_vnstock(self, symbol):
        """Fetch fundamentals using vnstock."""
        try:
            if self.vnstock_version == 3:
                # vnstock3 API
                stock = self.vnstock.stock(symbol=symbol, source='VCI')
                company = stock.company.profile()
                ratios = stock.finance.ratio(period='year', lang='en')
            else:
                # Legacy vnstock API
                from vnstock import financial_ratio
                company = None  # Legacy doesn't have easy company profile
                ratios = financial_ratio(symbol=symbol, report_type='simplified', report_range='annual')

            if ratios is None or ratios.empty:
                return None

            # Get latest ratios
            latest_ratios = ratios.iloc[0] if not ratios.empty else {}

            # Extract fundamental metrics (handle both API versions)
            fund_data = {
                'symbol': symbol,
                'sector': company.get('industryEn', 'Unknown') if (company and isinstance(company, dict)) else 'Unknown',
                'pe_ratio': self._safe_float(latest_ratios.get('pe', latest_ratios.get('PE', None))),
                'pb_ratio': self._safe_float(latest_ratios.get('pb', latest_ratios.get('PB', None))),
                'roe': self._safe_float(latest_ratios.get('roe', latest_ratios.get('ROE', None)), scale=0.01),
                'roa': self._safe_float(latest_ratios.get('roa', latest_ratios.get('ROA', None)), scale=0.01),
                'debt_equity': self._safe_float(latest_ratios.get('debtToEquity', latest_ratios.get('debt_on_equity', None))),
                'current_ratio': self._safe_float(latest_ratios.get('currentRatio', latest_ratios.get('current_ratio', None))),
                'revenue_growth': self._safe_float(latest_ratios.get('revenueGrowth', latest_ratios.get('revenue_growth', None)), scale=0.01),
                'earnings_growth': self._safe_float(latest_ratios.get('earningsGrowth', latest_ratios.get('profit_growth', None)), scale=0.01),
                'div_yield': self._safe_float(latest_ratios.get('dividendYield', latest_ratios.get('dividend_yield', None)), scale=0.01),
                'earnings_stability': 6,  # Default placeholder
                'revenue_growth_consistency': 0.75,  # Default placeholder
                'market_cap': self._safe_float(company.get('marketCap', 0)) if (company and isinstance(company, dict)) else 10_000_000_000_000,
                'avg_dollar_volume': 1_000_000_000  # Placeholder
            }

            # Validate required fields
            if fund_data['pe_ratio'] is None or fund_data['pe_ratio'] <= 0:
                return None

            return fund_data

        except Exception as e:
            # print(f"vnstock fundamental error for {symbol}: {e}")
            return None

    def _fetch_fundamental_fiingroup(self, symbol):
        """Fetch fundamentals using FiinGroup API."""
        import requests

        url = f"https://api.fiingroup.vn/Fundamental/GetFundamental"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        params = {"symbol": symbol}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            # Extract and format data (adjust based on actual API response)
            fund_data = {
                'symbol': symbol,
                'sector': data.get('sector', 'Unknown'),
                'pe_ratio': data.get('pe', None),
                'pb_ratio': data.get('pb', None),
                'roe': data.get('roe', None),
                'roa': data.get('roa', None),
                'debt_equity': data.get('debtEquity', None),
                'current_ratio': data.get('currentRatio', None),
                'revenue_growth': data.get('revenueGrowth', None),
                'earnings_growth': data.get('earningsGrowth', None),
                'div_yield': data.get('dividendYield', None),
                'earnings_stability': data.get('earningsStability', 6),
                'revenue_growth_consistency': data.get('growthConsistency', 0.75),
                'market_cap': data.get('marketCap', 0),
                'avg_dollar_volume': data.get('avgVolume', 1_000_000_000)
            }

            return fund_data

        except Exception as e:
            # print(f"FiinGroup fundamental error for {symbol}: {e}")
            return None

    def _fetch_fundamental_csv(self, symbol):
        """Load fundamentals from CSV."""
        csv_path = os.path.join(self.cache_dir, f'{symbol}_fundamentals.csv')

        if not os.path.exists(csv_path):
            return None

        try:
            df = pd.read_csv(csv_path)
            return df.iloc[0].to_dict()
        except Exception as e:
            return None

    # ========== UTILITY METHODS ==========

    def _safe_float(self, value, scale=1.0):
        """Safely convert value to float with scaling."""
        try:
            if value is None or pd.isna(value):
                return None
            return float(value) * scale
        except:
            return None

    def _load_from_cache(self, symbol, start_date, end_date):
        """Load data from cache if available and fresh."""
        cache_file = os.path.join(self.cache_dir, f'{symbol}_{start_date}_{end_date}.csv')

        if not os.path.exists(cache_file):
            return None

        # Check if cache is fresh (< 1 day old for recent data)
        cache_age = time.time() - os.path.getmtime(cache_file)
        if cache_age > 86400:  # 24 hours
            return None

        try:
            df = pd.read_csv(cache_file, parse_dates=['date'], index_col='date')
            return df
        except:
            return None

    def _save_to_cache(self, symbol, df, start_date, end_date):
        """Save data to cache."""
        cache_file = os.path.join(self.cache_dir, f'{symbol}_{start_date}_{end_date}.csv')

        try:
            df.to_csv(cache_file)
        except Exception as e:
            print(f"Cache save error: {e}")

    def get_market_index(self, index='VNINDEX', start_date=None, end_date=None):
        """
        Get market index data (VN-Index, VN30, HNX-Index).

        Args:
            index: 'VNINDEX', 'VN30', 'HNXINDEX', 'UPCOM'
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'

        Returns:
            DataFrame with index prices
        """
        try:
            if self.data_source == 'vnstock':
                stock = self.vnstock.stock(symbol='ACB', source='VCI')  # Any symbol works
                df = stock.quote.history(symbol=index, start=start_date, end=end_date, interval='1D')
                return df

            else:
                print("Index data only supported with vnstock currently")
                return pd.DataFrame()

        except Exception as e:
            print(f"Error fetching index {index}: {e}")
            return pd.DataFrame()


# Quick test function
def test_data_provider():
    """Test the data provider with real Vietnamese data."""
    print("=" * 70)
    print("TESTING VIETNAM DATA PROVIDER")
    print("=" * 70)

    # Initialize provider
    provider = VietnamDataProvider(data_source='vnstock', enable_cache=True)

    # Test 1: Get stock listing
    print("\n[Test 1] Get Stock Listing")
    symbols = provider.get_stock_listing('HOSE')
    print(f"Found {len(symbols)} stocks")
    print(f"First 10: {symbols[:10]}")

    # Test 2: Get historical data for a few stocks
    print("\n[Test 2] Get Historical Data")
    test_symbols = symbols[:3] if len(symbols) > 0 else ['VNM', 'VCB', 'HPG']
    historical_data = provider.get_historical_data(
        test_symbols,
        start_date='2023-01-01',
        end_date='2024-10-31'
    )

    for symbol, df in historical_data.items():
        print(f"\n{symbol}:")
        print(f"  Data points: {len(df)}")
        print(f"  Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  Latest close: {df['close'].iloc[-1]:,.0f} VND")
        print(df.tail(3))

    # Test 3: Get fundamental data
    print("\n[Test 3] Get Fundamental Data")
    fundamentals = provider.get_fundamental_data(test_symbols)

    for fund in fundamentals:
        print(f"\n{fund['symbol']}:")
        print(f"  Sector: {fund['sector']}")
        print(f"  P/E: {fund['pe_ratio']:.1f}")
        print(f"  P/B: {fund['pb_ratio']:.1f}")
        print(f"  ROE: {fund['roe']*100:.1f}%" if fund['roe'] else "  ROE: N/A")
        print(f"  ROA: {fund['roa']*100:.1f}%" if fund['roa'] else "  ROA: N/A")

    print("\n" + "=" * 70)
    print("✅ DATA PROVIDER TEST COMPLETED")
    print("=" * 70)


if __name__ == '__main__':
    test_data_provider()
