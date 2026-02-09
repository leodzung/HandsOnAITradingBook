#!/usr/bin/env python3
"""
Generate Training Data V2 for Price-Level Model
Fixed version that properly correlates strike distance with outcomes.
"""

import pandas as pd
import numpy as np
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict
from pathlib import Path

from price_level_features import PriceLevelFeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TrainingDataGeneratorV2:
    """Generate properly correlated training data."""

    def __init__(self,
                 price_data_path: str = 'data/historical_prices_real.csv',
                 output_path: str = 'data/training_data_v2.csv'):
        """Initialize generator."""
        self.price_data_path = price_data_path
        self.output_path = output_path
        self.feature_extractor = PriceLevelFeatureExtractor()

        # Load historical prices
        self.prices = pd.read_csv(price_data_path)
        self.prices['date'] = pd.to_datetime(self.prices['date'])
        self.prices = self.prices.sort_values(['asset', 'date']).reset_index(drop=True)

        logger.info(f"Loaded {len(self.prices)} price records")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    def generate_dataset(self, num_samples: int = 2000) -> pd.DataFrame:
        """
        Generate training dataset with proper strike/outcome correlation.

        Strategy:
        1. Generate YES samples by finding strikes that WERE actually hit
        2. Generate NO samples by finding strikes that WERE NOT hit
        3. Ensure variety in strike distances for both classes
        """
        logger.info(f"Generating {num_samples} samples with proper correlations")

        yes_samples = []
        no_samples = []

        target_per_class = num_samples // 2

        # Generate YES samples - strikes that were actually hit
        logger.info("Generating YES samples (strikes that were hit)...")
        attempts = 0
        while len(yes_samples) < target_per_class and attempts < num_samples * 10:
            attempts += 1
            sample = self._generate_yes_sample()
            if sample:
                yes_samples.append(sample)
                if len(yes_samples) % 100 == 0:
                    logger.info(f"  YES samples: {len(yes_samples)}/{target_per_class}")

        # Generate NO samples - strikes that were NOT hit
        logger.info("Generating NO samples (strikes that were NOT hit)...")
        attempts = 0
        while len(no_samples) < target_per_class and attempts < num_samples * 10:
            attempts += 1
            sample = self._generate_no_sample()
            if sample:
                no_samples.append(sample)
                if len(no_samples) % 100 == 0:
                    logger.info(f"  NO samples: {len(no_samples)}/{target_per_class}")

        # Combine and shuffle
        all_samples = yes_samples + no_samples
        random.shuffle(all_samples)

        df = pd.DataFrame(all_samples)

        # Log statistics
        self._log_statistics(df)

        # Save
        df.to_csv(self.output_path, index=False)
        logger.info(f"\nSaved dataset to: {self.output_path}")

        return df

    def _generate_yes_sample(self) -> Dict:
        """Generate a sample where strike was actually hit (label=1)."""

        asset = random.choice(['BTC', 'ETH'])
        asset_prices = self.prices[self.prices['asset'] == asset].copy()

        if len(asset_prices) < 200:
            return None

        # Pick random entry point
        lookback = 30
        max_entry = len(asset_prices) - 180
        if max_entry <= lookback:
            return None

        entry_idx = random.randint(lookback, max_entry)
        entry_price = asset_prices.iloc[entry_idx]['close']
        entry_date = asset_prices.iloc[entry_idx]['date']

        # Random days to expiry (include short-term 7-30 day markets)
        days_to_expiry = random.randint(7, 150)
        expiry_idx = entry_idx + days_to_expiry

        if expiry_idx >= len(asset_prices):
            return None

        # Get actual price movement
        future_prices = asset_prices.iloc[entry_idx:expiry_idx + 1]['close']
        max_price = future_prices.max()
        min_price = future_prices.min()

        # Choose direction and find a strike that WAS hit
        direction = random.choice(['ABOVE', 'BELOW'])

        if direction == 'ABOVE':
            # Strike must be <= max_price to have been hit
            # But we want variety in strike distances
            max_reachable_pct = (max_price - entry_price) / entry_price

            if max_reachable_pct <= 0.01:  # Price didn't go up much
                return None

            # Random strike between current and max reached
            strike_pct = random.uniform(0.02, max_reachable_pct * 0.95)
            strike_price = entry_price * (1 + strike_pct)

        else:  # BELOW
            # Strike must be >= min_price to have been hit
            max_reachable_pct = (entry_price - min_price) / entry_price

            if max_reachable_pct <= 0.01:  # Price didn't go down much
                return None

            strike_pct = random.uniform(0.02, max_reachable_pct * 0.95)
            strike_price = entry_price * (1 - strike_pct)

        # Extract features
        return self._create_sample(
            asset=asset,
            prices=asset_prices,
            entry_idx=entry_idx,
            entry_price=entry_price,
            entry_date=entry_date,
            strike_price=strike_price,
            direction=direction,
            days_to_expiry=days_to_expiry,
            label=1
        )

    def _generate_no_sample(self) -> Dict:
        """Generate a sample where strike was NOT hit (label=0)."""

        asset = random.choice(['BTC', 'ETH'])
        asset_prices = self.prices[self.prices['asset'] == asset].copy()

        if len(asset_prices) < 200:
            return None

        lookback = 30
        max_entry = len(asset_prices) - 180
        if max_entry <= lookback:
            return None

        entry_idx = random.randint(lookback, max_entry)
        entry_price = asset_prices.iloc[entry_idx]['close']
        entry_date = asset_prices.iloc[entry_idx]['date']

        days_to_expiry = random.randint(7, 150)
        expiry_idx = entry_idx + days_to_expiry

        if expiry_idx >= len(asset_prices):
            return None

        # Get actual price movement
        future_prices = asset_prices.iloc[entry_idx:expiry_idx + 1]['close']
        max_price = future_prices.max()
        min_price = future_prices.min()

        direction = random.choice(['ABOVE', 'BELOW'])

        if direction == 'ABOVE':
            # Strike must be > max_price to NOT have been hit
            max_reached_pct = (max_price - entry_price) / entry_price

            # Generate strike BEYOND what was reached
            # Variety: some just beyond, some way beyond
            rand = random.random()
            if rand < 0.3:
                # Just beyond
                strike_pct = max_reached_pct * random.uniform(1.05, 1.20)
            elif rand < 0.6:
                # Moderately beyond
                strike_pct = max_reached_pct * random.uniform(1.20, 1.50)
            else:
                # Way beyond (far OTM)
                strike_pct = max(max_reached_pct * 1.5, 0.30) + random.uniform(0.1, 0.5)

            strike_price = entry_price * (1 + strike_pct)

        else:  # BELOW
            # Strike must be < min_price to NOT have been hit
            min_reached_pct = (entry_price - min_price) / entry_price

            rand = random.random()
            if rand < 0.3:
                strike_pct = min_reached_pct * random.uniform(1.05, 1.20)
            elif rand < 0.6:
                strike_pct = min_reached_pct * random.uniform(1.20, 1.50)
            else:
                strike_pct = max(min_reached_pct * 1.5, 0.30) + random.uniform(0.1, 0.5)

            strike_price = entry_price * (1 - strike_pct)
            if strike_price <= 0:
                return None

        return self._create_sample(
            asset=asset,
            prices=asset_prices,
            entry_idx=entry_idx,
            entry_price=entry_price,
            entry_date=entry_date,
            strike_price=strike_price,
            direction=direction,
            days_to_expiry=days_to_expiry,
            label=0
        )

    def _create_sample(self, asset: str, prices: pd.DataFrame, entry_idx: int,
                       entry_price: float, entry_date, strike_price: float,
                       direction: str, days_to_expiry: int, label: int) -> Dict:
        """Create a sample with features."""

        expiry_date = entry_date + timedelta(days=days_to_expiry)
        if hasattr(expiry_date, 'tzinfo') and expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

        # Historical data for features
        historical = prices.iloc[:entry_idx + 1].copy()
        historical['open'] = historical['close'].shift(1).fillna(historical['close'])
        historical['high'] = historical['close'] * 1.01
        historical['low'] = historical['close'] * 0.99
        historical['volume'] = 1e9

        parsed_market = {
            'asset': asset,
            'strike_price': strike_price,
            'expiry_date': expiry_date,
            'days_to_expiry': days_to_expiry,
            'direction': direction,
            'conditionId': f'v2_{asset}_{entry_idx}',
            'token_id': f'token_{entry_idx}',
            'question': f'Will {asset} hit ${strike_price:,.0f}?'
        }

        polymarket_data = {
            'market': {'volume24hr': 50000, 'volume1wk': 200000, 'liquidity': 100000},
            'orderbook': {
                'bids': [{'price': '0.48', 'size': '1000'}],
                'asks': [{'price': '0.52', 'size': '1000'}]
            }
        }

        try:
            features = self.feature_extractor.extract_all_features(
                parsed_market=parsed_market,
                spot_price=entry_price,
                historical_ohlcv=historical,
                polymarket_data=polymarket_data
            )
        except Exception as e:
            return None

        return {
            'asset': asset,
            'entry_date': entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else str(entry_date),
            'entry_price': entry_price,
            'strike_price': strike_price,
            'direction': direction,
            'days_to_expiry': days_to_expiry,
            'label': label,
            **features
        }

    def _log_statistics(self, df: pd.DataFrame):
        """Log dataset statistics."""

        logger.info(f"\n{'='*60}")
        logger.info("Dataset Statistics")
        logger.info(f"{'='*60}")
        logger.info(f"Total samples: {len(df)}")
        logger.info(f"YES (label=1): {(df['label'] == 1).sum()} ({(df['label'] == 1).mean()*100:.1f}%)")
        logger.info(f"NO (label=0): {(df['label'] == 0).sum()} ({(df['label'] == 0).mean()*100:.1f}%)")

        # Critical: Check correlation
        logger.info(f"\n*** KEY CORRELATIONS ***")
        logger.info(f"strike_distance_pct vs label: {df['strike_distance_pct'].corr(df['label']):.3f}")
        logger.info(f"gbm_probability vs label: {df['gbm_probability'].corr(df['label']):.3f}")

        # Check by label
        for label in [0, 1]:
            subset = df[df['label'] == label]
            label_name = 'NO' if label == 0 else 'YES'
            logger.info(f"\n{label_name} samples:")
            logger.info(f"  strike_distance_pct: mean={subset['strike_distance_pct'].mean():.1f}%, "
                       f"range=[{subset['strike_distance_pct'].min():.1f}%, {subset['strike_distance_pct'].max():.1f}%]")
            logger.info(f"  gbm_probability: mean={subset['gbm_probability'].mean():.3f}")


if __name__ == '__main__':
    import time

    logger.info("="*60)
    logger.info("TRAINING DATA GENERATION V2")
    logger.info("="*60)

    generator = TrainingDataGeneratorV2()

    start_time = time.time()
    df = generator.generate_dataset(num_samples=2000)
    elapsed = time.time() - start_time

    if not df.empty:
        logger.info(f"\n{'='*60}")
        logger.info("GENERATION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Time elapsed: {elapsed:.1f} seconds")

        # Verify correlations
        strike_corr = df['strike_distance_pct'].corr(df['label'])
        gbm_corr = df['gbm_probability'].corr(df['label'])

        logger.info(f"\nCorrelation check:")
        logger.info(f"  strike_distance_pct vs label: {strike_corr:.3f} (should be NEGATIVE)")
        logger.info(f"  gbm_probability vs label: {gbm_corr:.3f} (should be POSITIVE)")

        if strike_corr < 0 and gbm_corr > 0:
            logger.info("\nCorrelations are correct!")
        else:
            logger.warning("\nCorrelations may need review!")
