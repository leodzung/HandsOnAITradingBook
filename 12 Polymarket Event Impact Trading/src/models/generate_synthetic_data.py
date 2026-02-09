"""
Generate Synthetic Training Data for Price-Level Model
Creates labeled samples by simulating historical price-level markets.
"""

import pandas as pd
import numpy as np
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import json
from pathlib import Path

from external_data import SpotPriceDataSource
from price_level_features import PriceLevelFeatureExtractor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SyntheticDataGenerator:
    """Generate synthetic training data from historical prices."""

    def __init__(self, output_path: str = 'data/synthetic_training_data.csv'):
        """
        Initialize generator.

        Args:
            output_path: Path to save generated dataset
        """
        self.output_path = output_path
        self.data_source = SpotPriceDataSource()
        self.feature_extractor = PriceLevelFeatureExtractor()

        # Ensure data directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        logger.info("SyntheticDataGenerator initialized")

    def generate_dataset(self, assets: List[str] = None,
                        start_date: str = '2020-01-01',
                        num_samples_per_asset: int = 400,
                        min_days_to_expiry: int = 30,
                        max_days_to_expiry: int = 365) -> pd.DataFrame:
        """
        Generate synthetic training dataset.

        Args:
            assets: List of assets to generate data for (default: ['BTC', 'ETH', 'GOLD'])
            start_date: Start date for historical data
            num_samples_per_asset: Number of samples to generate per asset
            min_days_to_expiry: Minimum days to expiry for simulated markets
            max_days_to_expiry: Maximum days to expiry

        Returns:
            DataFrame with features and labels
        """
        if assets is None:
            assets = ['BTC', 'ETH', 'GOLD']

        logger.info(f"Generating synthetic data for {assets}")
        logger.info(f"Target: {num_samples_per_asset} samples per asset")

        all_samples = []

        for asset in assets:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {asset}...")
            logger.info(f"{'='*60}")

            try:
                # Download historical data
                days_back = (datetime.now() - datetime.strptime(start_date, '%Y-%m-%d')).days
                historical_ohlcv = self.data_source.get_historical_ohlcv(asset, days=days_back)

                if historical_ohlcv.empty:
                    logger.warning(f"No historical data for {asset}, skipping...")
                    continue

                logger.info(f"Downloaded {len(historical_ohlcv)} days of data for {asset}")

                # Generate samples
                asset_samples = self._generate_samples_for_asset(
                    asset=asset,
                    historical_ohlcv=historical_ohlcv,
                    num_samples=num_samples_per_asset,
                    min_days_to_expiry=min_days_to_expiry,
                    max_days_to_expiry=max_days_to_expiry
                )

                all_samples.extend(asset_samples)
                logger.info(f"Generated {len(asset_samples)} samples for {asset}")

            except Exception as e:
                logger.error(f"Error processing {asset}: {e}", exc_info=True)
                continue

        # Convert to DataFrame
        if not all_samples:
            logger.error("No samples generated!")
            return pd.DataFrame()

        df = pd.DataFrame(all_samples)

        # Log statistics
        logger.info(f"\n{'='*60}")
        logger.info("Dataset Statistics")
        logger.info(f"{'='*60}")
        logger.info(f"Total samples: {len(df)}")
        logger.info(f"\nBy asset:")
        logger.info(df['asset'].value_counts())
        logger.info(f"\nClass distribution:")
        logger.info(f"Label=1 (reached): {(df['label'] == 1).sum()} ({(df['label'] == 1).mean()*100:.1f}%)")
        logger.info(f"Label=0 (not reached): {(df['label'] == 0).sum()} ({(df['label'] == 0).mean()*100:.1f}%)")

        # Save to CSV
        df.to_csv(self.output_path, index=False)
        logger.info(f"\nSaved dataset to: {self.output_path}")

        return df

    def _generate_samples_for_asset(self, asset: str, historical_ohlcv: pd.DataFrame,
                                   num_samples: int, min_days_to_expiry: int,
                                   max_days_to_expiry: int) -> List[Dict]:
        """
        Generate samples for a single asset.

        Args:
            asset: Asset symbol
            historical_ohlcv: Historical OHLCV DataFrame
            num_samples: Number of samples to generate
            min_days_to_expiry: Min days to expiry
            max_days_to_expiry: Max days to expiry

        Returns:
            List of sample dictionaries
        """
        samples = []

        # We need enough history to check if strike was reached
        # Reserve last max_days_to_expiry days for validation
        # Also need some lookback for feature calculation (30 days min)
        lookback_needed = 30
        max_entry_idx = len(historical_ohlcv) - max_days_to_expiry - 1

        if max_entry_idx < lookback_needed:
            logger.warning(f"Not enough historical data for {asset} (need {lookback_needed + max_days_to_expiry} days, got {len(historical_ohlcv)})")
            return samples

        if len(historical_ohlcv) < 60:  # Minimum viable dataset
            logger.warning(f"Dataset too small for {asset}: {len(historical_ohlcv)} days")
            return samples

        # Generate random entry points
        # Note: Not using np.random.seed() to ensure variety in generated samples
        entry_indices = np.random.randint(lookback_needed, max_entry_idx, num_samples)

        for i, entry_idx in enumerate(entry_indices):
            try:
                sample = self._create_sample(
                    asset=asset,
                    historical_ohlcv=historical_ohlcv,
                    entry_idx=entry_idx,
                    min_days_to_expiry=min_days_to_expiry,
                    max_days_to_expiry=max_days_to_expiry
                )

                if sample:
                    samples.append(sample)

                # Progress logging
                if (i + 1) % 100 == 0:
                    logger.info(f"  Processed {i+1}/{num_samples} samples for {asset}")

            except Exception as e:
                logger.debug(f"Error creating sample {i} for {asset}: {e}")
                continue

        # Log direction distribution
        if hasattr(self, '_direction_counts'):
            logger.info(f"Direction distribution for {asset}: {self._direction_counts}")
            self._direction_counts = {'ABOVE': 0, 'BELOW': 0}  # Reset for next asset

        return samples

    def _create_sample(self, asset: str, historical_ohlcv: pd.DataFrame,
                      entry_idx: int, min_days_to_expiry: int,
                      max_days_to_expiry: int) -> Dict:
        """
        Create a single training sample.

        Args:
            asset: Asset symbol
            historical_ohlcv: Full historical data
            entry_idx: Index in historical data for entry point
            min_days_to_expiry: Min days to expiry
            max_days_to_expiry: Max days to expiry

        Returns:
            Dictionary with features and label, or None if invalid
        """
        # Entry point data
        entry_date = historical_ohlcv.iloc[entry_idx]['date']
        entry_price = historical_ohlcv.iloc[entry_idx]['close']

        # Random expiry (30-365 days in future)
        days_to_expiry = np.random.randint(min_days_to_expiry, max_days_to_expiry)
        expiry_date = entry_date + timedelta(days=days_to_expiry)

        # Make expiry_date timezone-aware
        if isinstance(expiry_date, pd.Timestamp):
            expiry_date = expiry_date.to_pydatetime()
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

        # Random strike price (±10% to ±50% from entry price)
        # More samples near the money (10-30%) than far OTM (30-50%)
        if np.random.random() < 0.7:
            strike_pct = np.random.uniform(0.10, 0.30)  # 70% of samples
        else:
            strike_pct = np.random.uniform(0.30, 0.50)  # 30% of samples

        # Use Python's random module (numpy random state seems corrupted)
        direction = random.choice(['ABOVE', 'BELOW'])

        # Debug: Log direction distribution
        if not hasattr(self, '_direction_counts'):
            self._direction_counts = {'ABOVE': 0, 'BELOW': 0}
        self._direction_counts[direction] += 1

        if direction == 'ABOVE':
            strike_price = entry_price * (1 + strike_pct)
        else:
            strike_price = entry_price * (1 - strike_pct)

        # Get historical data up to entry point (for feature extraction)
        historical_for_features = historical_ohlcv.iloc[:entry_idx+1].copy()

        # Create parsed market (simulate Polymarket market structure)
        parsed_market = {
            'asset': asset,
            'strike_price': strike_price,
            'expiry_date': expiry_date,
            'days_to_expiry': days_to_expiry,
            'direction': direction,
            'conditionId': f'synthetic_{asset}_{entry_idx}',
            'token_id': f'token_{entry_idx}',
            'question': f'Will {asset} {"reach" if direction == "ABOVE" else "drop below"} ${strike_price:,.0f}?'
        }

        # Simulate Polymarket data (orderbook, volume)
        # For training, these don't matter much - we'll use neutral values
        polymarket_data = {
            'market': {
                'volume24hr': 50000,
                'volume1wk': 200000,
                'liquidity': 100000
            },
            'orderbook': {
                'bids': [{'price': '0.48', 'size': '1000'}],
                'asks': [{'price': '0.52', 'size': '1000'}]
            }
        }

        # Extract features
        try:
            features = self.feature_extractor.extract_all_features(
                parsed_market=parsed_market,
                spot_price=entry_price,
                historical_ohlcv=historical_for_features,
                polymarket_data=polymarket_data
            )
        except Exception as e:
            logger.debug(f"Error extracting features: {e}")
            return None

        # Calculate label: Did price reach strike by expiry?
        expiry_idx = entry_idx + days_to_expiry
        if expiry_idx >= len(historical_ohlcv):
            return None  # Not enough future data

        # Get prices between entry and expiry
        future_prices = historical_ohlcv.iloc[entry_idx:expiry_idx+1]

        if direction == 'ABOVE':
            # Did max price reach or exceed strike?
            max_price = future_prices['high'].max()
            label = 1 if max_price >= strike_price else 0
        else:
            # Did min price drop to or below strike?
            min_price = future_prices['low'].min()
            label = 1 if min_price <= strike_price else 0

        # Combine features with metadata
        sample = {
            'asset': asset,
            'entry_date': entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else str(entry_date),
            'entry_price': entry_price,
            'strike_price': strike_price,
            'direction': direction,
            'days_to_expiry': days_to_expiry,
            'label': label,
            **features  # Unpack all features
        }

        return sample


# Main execution
if __name__ == '__main__':
    import time

    logger.info("="*60)
    logger.info("SYNTHETIC TRAINING DATA GENERATION")
    logger.info("="*60)

    # Initialize generator
    generator = SyntheticDataGenerator()

    # Generate dataset
    start_time = time.time()

    df = generator.generate_dataset(
        assets=['BTC', 'ETH'],  # Skip GOLD (Yahoo Finance blocking)
        start_date='2024-01-01',  # Recent data only (CoinGecko free tier limitation)
        num_samples_per_asset=100,  # Reduced due to limited historical data
        min_days_to_expiry=7,  # Shorter window
        max_days_to_expiry=30  # Max 30 days with 92-day history
    )

    elapsed = time.time() - start_time

    if not df.empty:
        logger.info(f"\n{'='*60}")
        logger.info("GENERATION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Time elapsed: {elapsed:.1f} seconds")
        logger.info(f"Total samples: {len(df)}")
        logger.info(f"Features per sample: {len(df.columns) - 7}")  # Minus metadata columns

        # Show sample
        logger.info(f"\nSample rows:")
        logger.info(df[['asset', 'entry_price', 'strike_price', 'direction', 'days_to_expiry', 'label']].head(10))

        # Check for NaNs
        nan_counts = df.isnull().sum()
        if nan_counts.sum() > 0:
            logger.warning(f"\nColumns with NaN values:")
            logger.warning(nan_counts[nan_counts > 0])
        else:
            logger.info(f"\n✓ No NaN values found")

        # Verify class balance
        positive_pct = (df['label'] == 1).mean() * 100
        if 40 <= positive_pct <= 60:
            logger.info(f"✓ Class balance looks good: {positive_pct:.1f}% positive")
        else:
            logger.warning(f"⚠ Class imbalance: {positive_pct:.1f}% positive (target: 40-60%)")

    else:
        logger.error("Failed to generate dataset")
