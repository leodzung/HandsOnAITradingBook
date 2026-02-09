#!/usr/bin/env python3
"""
Download historical crypto prices for validation.
Downloads 2020-2022 data for BTC, ETH, SOL using CoinGecko range endpoint.
"""

import requests
import pandas as pd
import logging
import time
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def download_historical_prices():
    """Download historical prices for validation period using CoinGecko."""

    coins = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'SOL': 'solana'
    }

    all_data = []

    # Download in chunks of 365 days to avoid API limits
    date_ranges = [
        ('2020-01-01', '2020-12-31'),
        ('2021-01-01', '2021-12-31'),
        ('2022-01-01', '2022-12-31'),
    ]

    for symbol, coin_id in coins.items():
        logger.info(f"Downloading {symbol} historical data...")

        for start_str, end_str in date_ranges:
            start_dt = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            end_dt = datetime.strptime(end_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)

            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
            params = {
                'vs_currency': 'usd',
                'from': int(start_dt.timestamp()),
                'to': int(end_dt.timestamp())
            }

            try:
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 429:
                    logger.warning("Rate limited, waiting 60s...")
                    time.sleep(60)
                    response = requests.get(url, params=params, timeout=30)

                if response.status_code != 200:
                    logger.warning(f"  Failed {start_str}-{end_str}: {response.status_code}")
                    time.sleep(5)
                    continue

                data = response.json()
                prices = data.get('prices', [])
                logger.info(f"  {symbol} {start_str[:4]}: {len(prices)} points")

                for ts, price in prices:
                    date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                    all_data.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'asset': symbol,
                        'close': price
                    })

                time.sleep(3)  # Rate limiting between requests

            except Exception as e:
                logger.error(f"  Error {start_str}-{end_str}: {e}")
                time.sleep(5)

    if not all_data:
        logger.error("No data downloaded!")
        return None

    # Create DataFrame and deduplicate by date
    df = pd.DataFrame(all_data)
    df['date'] = pd.to_datetime(df['date'])
    df = df.drop_duplicates(subset=['date', 'asset'])
    df = df.sort_values(['asset', 'date']).reset_index(drop=True)

    # Add OHLCV approximations
    df['open'] = df.groupby('asset')['close'].shift(1).fillna(df['close'])
    df['high'] = df['close'] * 1.02
    df['low'] = df['close'] * 0.98
    df['volume'] = 1e9

    # Save
    output_path = 'data/historical_prices_2020_2022.csv'
    df.to_csv(output_path, index=False)
    logger.info(f"\nSaved {len(df)} records to {output_path}")

    # Summary
    for asset in df['asset'].unique():
        asset_df = df[df['asset'] == asset]
        logger.info(f"  {asset}: {len(asset_df)} days, {asset_df['date'].min().date()} to {asset_df['date'].max().date()}")

    return df


if __name__ == '__main__':
    download_historical_prices()
