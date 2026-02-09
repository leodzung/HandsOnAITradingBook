#!/usr/bin/env python3
"""
Generate Real Training Data for Price-Level Model
Uses actual historical crypto prices to create properly labeled training samples.
"""

import pandas as pd
import numpy as np
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple
from pathlib import Path

from price_level_features import PriceLevelFeatureExtractor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealDataGenerator:
    """Generate training data from real historical prices."""

    def __init__(self,
                 price_data_path: str = 'data/historical_prices_real.csv',
                 output_path: str = 'data/real_training_data.csv'):
        """
        Initialize generator.

        Args:
            price_data_path: Path to historical price CSV
            output_path: Path to save generated dataset
        """
        self.price_data_path = price_data_path
        self.output_path = output_path
        self.feature_extractor = PriceLevelFeatureExtractor()

        # Load historical prices
        self.prices = pd.read_csv(price_data_path)
        self.prices['date'] = pd.to_datetime(self.prices['date'])
        self.prices = self.prices.sort_values(['asset', 'date']).reset_index(drop=True)

        logger.info(f"Loaded {len(self.prices)} price records")
        logger.info(f"Assets: {self.prices['asset'].unique().tolist()}")
        logger.info(f"Date range: {self.prices['date'].min()} to {self.prices['date'].max()}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    def generate_dataset(self,
                        num_samples: int = 1000,
                        min_days_to_expiry: int = 30,
                        max_days_to_expiry: int = 180,
                        target_balance: float = 0.5) -> pd.DataFrame:
        """
        Generate balanced training dataset.

        Args:
            num_samples: Target number of samples
            min_days_to_expiry: Minimum days to market expiry
            max_days_to_expiry: Maximum days to market expiry
            target_balance: Target ratio of YES samples (0.5 = balanced)

        Returns:
            DataFrame with features and labels
        """
        logger.info(f"Generating {num_samples} samples with target balance {target_balance:.0%}")

        all_samples = []
        yes_count = 0
        no_count = 0
        attempts = 0
        max_attempts = num_samples * 20  # Prevent infinite loops

        while len(all_samples) < num_samples and attempts < max_attempts:
            attempts += 1

            # Random asset
            asset = random.choice(['BTC', 'ETH'])
            asset_prices = self.prices[self.prices['asset'] == asset].copy()

            if len(asset_prices) < max_days_to_expiry + 30:
                continue

            # Random entry point (need lookback for features + forward for resolution)
            lookback_needed = 30
            max_entry_idx = len(asset_prices) - max_days_to_expiry - 1

            if max_entry_idx <= lookback_needed:
                continue

            entry_idx = random.randint(lookback_needed, max_entry_idx)

            # Create sample
            sample = self._create_sample(
                asset=asset,
                prices=asset_prices,
                entry_idx=entry_idx,
                min_days_to_expiry=min_days_to_expiry,
                max_days_to_expiry=max_days_to_expiry
            )

            if sample is None:
                continue

            # Balance YES/NO samples
            label = sample['label']
            current_yes_ratio = yes_count / max(yes_count + no_count, 1)

            # Accept sample based on balance
            if label == 1:
                if current_yes_ratio < target_balance or no_count == 0:
                    all_samples.append(sample)
                    yes_count += 1
            else:
                if current_yes_ratio >= target_balance or yes_count == 0:
                    all_samples.append(sample)
                    no_count += 1

            # Progress logging
            if len(all_samples) % 100 == 0:
                logger.info(f"  Generated {len(all_samples)}/{num_samples} samples "
                          f"(YES: {yes_count}, NO: {no_count})")

        if not all_samples:
            logger.error("No samples generated!")
            return pd.DataFrame()

        df = pd.DataFrame(all_samples)

        # Log statistics
        logger.info(f"\n{'='*60}")
        logger.info("Dataset Statistics")
        logger.info(f"{'='*60}")
        logger.info(f"Total samples: {len(df)}")
        logger.info(f"YES (label=1): {(df['label'] == 1).sum()} ({(df['label'] == 1).mean()*100:.1f}%)")
        logger.info(f"NO (label=0): {(df['label'] == 0).sum()} ({(df['label'] == 0).mean()*100:.1f}%)")
        logger.info(f"\nBy asset: {df['asset'].value_counts().to_dict()}")
        logger.info(f"By direction: {df['direction'].value_counts().to_dict()}")

        # Feature statistics
        logger.info(f"\nKey feature ranges:")
        for col in ['strike_distance_pct', 'days_to_expiry', 'volatility_30d']:
            if col in df.columns:
                logger.info(f"  {col}: min={df[col].min():.2f}, max={df[col].max():.2f}, mean={df[col].mean():.2f}")

        # Save
        df.to_csv(self.output_path, index=False)
        logger.info(f"\nSaved dataset to: {self.output_path}")

        return df

    def _create_sample(self, asset: str, prices: pd.DataFrame, entry_idx: int,
                      min_days_to_expiry: int, max_days_to_expiry: int) -> Dict:
        """Create a single training sample."""

        entry_row = prices.iloc[entry_idx]
        entry_date = entry_row['date']
        entry_price = entry_row['close']

        # Random expiry within range
        days_to_expiry = random.randint(min_days_to_expiry, max_days_to_expiry)
        expiry_date = entry_date + timedelta(days=days_to_expiry)

        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

        # Random strike price with realistic distribution
        # Cover from near-the-money (5%) to far OTM (100%+)
        rand = random.random()
        if rand < 0.20:
            strike_pct = random.uniform(0.05, 0.15)   # 20%: Near money
        elif rand < 0.45:
            strike_pct = random.uniform(0.15, 0.35)   # 25%: Moderate
        elif rand < 0.70:
            strike_pct = random.uniform(0.35, 0.60)   # 25%: Far
        elif rand < 0.90:
            strike_pct = random.uniform(0.60, 1.00)   # 20%: Very far
        else:
            strike_pct = random.uniform(1.00, 2.00)   # 10%: Extreme

        # Random direction
        direction = random.choice(['ABOVE', 'BELOW'])

        if direction == 'ABOVE':
            strike_price = entry_price * (1 + strike_pct)
        else:
            strike_price = entry_price * (1 - strike_pct)

        # Get historical prices for feature extraction (up to entry)
        historical_prices = prices.iloc[:entry_idx + 1].copy()
        historical_prices = historical_prices.rename(columns={'close': 'close'})

        # Add OHLCV columns (approximate from close prices)
        historical_prices['open'] = historical_prices['close'].shift(1).fillna(historical_prices['close'])
        historical_prices['high'] = historical_prices['close'] * 1.01  # Approximate
        historical_prices['low'] = historical_prices['close'] * 0.99   # Approximate
        historical_prices['volume'] = 1e9  # Placeholder

        # Create parsed market structure
        parsed_market = {
            'asset': asset,
            'strike_price': strike_price,
            'expiry_date': expiry_date,
            'days_to_expiry': days_to_expiry,
            'direction': direction,
            'conditionId': f'real_{asset}_{entry_idx}',
            'token_id': f'token_{entry_idx}',
            'question': f'Will {asset} {"reach" if direction == "ABOVE" else "drop below"} ${strike_price:,.0f}?'
        }

        # Simulate Polymarket data
        polymarket_data = {
            'market': {'volume24hr': 50000, 'volume1wk': 200000, 'liquidity': 100000},
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
                historical_ohlcv=historical_prices,
                polymarket_data=polymarket_data
            )
        except Exception as e:
            logger.debug(f"Error extracting features: {e}")
            return None

        # Calculate label: Did price reach strike by expiry?
        expiry_idx = entry_idx + days_to_expiry
        if expiry_idx >= len(prices):
            return None

        future_prices = prices.iloc[entry_idx:expiry_idx + 1]

        if direction == 'ABOVE':
            max_future = future_prices['close'].max()
            label = 1 if max_future >= strike_price else 0
        else:
            min_future = future_prices['close'].min()
            label = 1 if min_future <= strike_price else 0

        # Combine features with metadata
        sample = {
            'asset': asset,
            'entry_date': entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else str(entry_date),
            'entry_price': entry_price,
            'strike_price': strike_price,
            'direction': direction,
            'days_to_expiry': days_to_expiry,
            'label': label,
            **features
        }

        return sample


if __name__ == '__main__':
    import time

    logger.info("="*60)
    logger.info("REAL TRAINING DATA GENERATION")
    logger.info("="*60)

    generator = RealDataGenerator()

    start_time = time.time()

    df = generator.generate_dataset(
        num_samples=1000,          # 1000 balanced samples
        min_days_to_expiry=30,     # Min 30 days (realistic for Polymarket)
        max_days_to_expiry=180,    # Max 180 days (limited by data availability)
        target_balance=0.5         # 50% YES, 50% NO
    )

    elapsed = time.time() - start_time

    if not df.empty:
        logger.info(f"\n{'='*60}")
        logger.info("GENERATION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Time elapsed: {elapsed:.1f} seconds")
        logger.info(f"Total samples: {len(df)}")
        logger.info(f"Features per sample: {len(df.columns) - 7}")

        # Verify class balance
        positive_pct = (df['label'] == 1).mean() * 100
        logger.info(f"\nClass balance: {positive_pct:.1f}% YES, {100-positive_pct:.1f}% NO")

        if 40 <= positive_pct <= 60:
            logger.info("✓ Class balance is good!")
        else:
            logger.warning(f"⚠ Class imbalance detected")
