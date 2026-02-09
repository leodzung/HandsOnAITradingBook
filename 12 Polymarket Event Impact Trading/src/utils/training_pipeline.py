#!/usr/bin/env python3
"""
Training Data Pipeline Orchestrator
Coordinates on-chain data collection, market mapping, and label generation
to produce training datasets for both trading bots.

Based on IMDEA paper methodology.
"""

import json
import sqlite3
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TrainingDataPipeline:
    """
    Orchestrates the complete training data collection pipeline.

    Steps:
    1. Backfill on-chain trades via Alchemy
    2. Build token-to-condition mapping
    3. Collect historical news events (optional)
    4. Generate labels for both bots
    5. Export training CSVs
    """

    def __init__(self, config_path: str = 'config.json',
                 db_path: str = 'data/training_history.db'):
        """
        Initialize the pipeline.

        Args:
            config_path: Path to configuration file
            db_path: Path to SQLite database
        """
        self.config_path = Path(config_path)
        self.db_path = db_path

        # Load config
        self.config = {}
        if self.config_path.exists():
            with open(self.config_path) as f:
                self.config = json.load(f)

        # Initialize components lazily
        self._alchemy_collector = None
        self._market_mapper = None
        self._gdelt_collector = None

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @property
    def alchemy_collector(self):
        """Lazy initialization of Alchemy collector."""
        if self._alchemy_collector is None:
            from alchemy_collector import AlchemyDataCollector
            api_key = self.config.get('alchemy_api_key')
            if not api_key:
                raise ValueError("alchemy_api_key not found in config.json")

            data_config = self.config.get('data_collection', {})
            self._alchemy_collector = AlchemyDataCollector(
                api_key=api_key,
                db_path=self.db_path,
                rate_limit_per_sec=data_config.get('rate_limit_per_sec', 5.0),
                batch_size_blocks=data_config.get('batch_size_blocks', 2000)
            )
        return self._alchemy_collector

    @property
    def market_mapper(self):
        """Lazy initialization of market mapper."""
        if self._market_mapper is None:
            from market_mapper import MarketConditionMapper
            self._market_mapper = MarketConditionMapper(db_path=self.db_path)
        return self._market_mapper

    @property
    def gdelt_collector(self):
        """Lazy initialization of GDELT collector."""
        if self._gdelt_collector is None:
            from gdelt_collector import GDELTCollector
            self._gdelt_collector = GDELTCollector(db_path=self.db_path)
        return self._gdelt_collector

    def run_full_pipeline(self, backfill_days: int = 180,
                          skip_on_chain: bool = False,
                          skip_news: bool = False) -> Dict:
        """
        Execute the complete data collection and labeling pipeline.

        Args:
            backfill_days: Number of days to backfill
            skip_on_chain: Skip on-chain trade collection
            skip_news: Skip news collection

        Returns:
            Dictionary with pipeline results
        """
        results = {
            'started_at': datetime.now(timezone.utc).isoformat(),
            'steps': {}
        }

        logger.info("=" * 70)
        logger.info("TRAINING DATA PIPELINE")
        logger.info("=" * 70)

        # Step 1: On-chain trade collection
        if not skip_on_chain:
            logger.info("\n[1/5] Collecting on-chain trades...")
            try:
                start_date = datetime.now(timezone.utc) - timedelta(days=backfill_days)
                trades = self.alchemy_collector.backfill_historical_trades(
                    start_date=start_date,
                    resume=True
                )
                results['steps']['on_chain_trades'] = {
                    'status': 'success',
                    'trades_collected': trades
                }
            except Exception as e:
                logger.error(f"On-chain collection failed: {e}")
                results['steps']['on_chain_trades'] = {
                    'status': 'failed',
                    'error': str(e)
                }
        else:
            logger.info("\n[1/5] Skipping on-chain trade collection")
            results['steps']['on_chain_trades'] = {'status': 'skipped'}

        # Step 2: Market mapping
        logger.info("\n[2/5] Building market mappings...")
        try:
            mappings = self.market_mapper.build_mapping()
            # Update trades with condition IDs
            updated = self.market_mapper.update_trades_with_condition_ids()
            results['steps']['market_mapping'] = {
                'status': 'success',
                'mappings_created': mappings,
                'trades_updated': updated
            }
        except Exception as e:
            logger.error(f"Market mapping failed: {e}")
            results['steps']['market_mapping'] = {
                'status': 'failed',
                'error': str(e)
            }

        # Step 3: Historical news collection (optional)
        if not skip_news:
            logger.info("\n[3/5] Collecting historical news...")
            try:
                events = self.gdelt_collector.collect_crypto_news(days_back=backfill_days)
                results['steps']['news_collection'] = {
                    'status': 'success',
                    'events_collected': events
                }
            except Exception as e:
                logger.error(f"News collection failed: {e}")
                results['steps']['news_collection'] = {
                    'status': 'failed',
                    'error': str(e)
                }
        else:
            logger.info("\n[3/5] Skipping news collection")
            results['steps']['news_collection'] = {'status': 'skipped'}

        # Step 4: Generate event-bot training data
        logger.info("\n[4/5] Generating event-bot training data...")
        try:
            event_samples = self.generate_event_bot_training_data()
            results['steps']['event_bot_labels'] = {
                'status': 'success',
                'samples_generated': len(event_samples)
            }
        except Exception as e:
            logger.error(f"Event-bot label generation failed: {e}")
            results['steps']['event_bot_labels'] = {
                'status': 'failed',
                'error': str(e)
            }

        # Step 5: Generate price-level training data
        logger.info("\n[5/5] Generating price-level training data...")
        try:
            price_level_samples = self.generate_price_level_training_data()
            results['steps']['price_level_labels'] = {
                'status': 'success',
                'samples_generated': len(price_level_samples)
            }
        except Exception as e:
            logger.error(f"Price-level label generation failed: {e}")
            results['steps']['price_level_labels'] = {
                'status': 'failed',
                'error': str(e)
            }

        results['completed_at'] = datetime.now(timezone.utc).isoformat()

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 70)

        for step, data in results['steps'].items():
            status = data.get('status', 'unknown')
            logger.info(f"  {step}: {status}")

        return results

    def generate_event_bot_training_data(self,
                                         output_path: str = 'data/training_event_bot.csv') -> pd.DataFrame:
        """
        Generate training data for the event-driven trading bot.

        Features:
        - Sentiment scores from news events
        - Market price/volume features at event time
        - Time features (market age, time to expiry)

        Labels:
        - UP/DOWN/NEUTRAL based on 24h price change (3% threshold)

        Returns:
            DataFrame with training samples
        """
        from historical_labeler import HistoricalPriceLabeler, NewsEventLabeler
        from feature_extractor import SentimentAnalyzer

        labeler = NewsEventLabeler(db_path=self.db_path)
        sentiment = SentimentAnalyzer()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get news events with timestamps
        cursor.execute("""
            SELECT * FROM news_events
            WHERE timestamp IS NOT NULL
            ORDER BY timestamp DESC
        """)

        # Check if table exists
        try:
            columns = [desc[0] for desc in cursor.description]
            events = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except:
            events = []
            logger.warning("No news_events table found, using market-based sampling")

        # If no news events, sample from on-chain trades directly
        if not events:
            cursor.execute("""
                SELECT DISTINCT condition_id, DATE(block_timestamp) as date
                FROM on_chain_trades
                WHERE condition_id IS NOT NULL
                GROUP BY condition_id, date
                HAVING COUNT(*) >= 10
                ORDER BY RANDOM()
                LIMIT 10000
            """)
            sample_points = cursor.fetchall()

            samples = []
            for condition_id, date in sample_points:
                try:
                    event_time = datetime.fromisoformat(f"{date}T12:00:00+00:00")
                    sample = labeler.price_labeler.generate_sample(condition_id, event_time)
                    if sample:
                        # Add market features
                        market = self.market_mapper.get_market(condition_id)
                        if market:
                            sample['question'] = market.get('question', '')
                            sample['volume'] = market.get('volume', 0)

                            # Add sentiment from question
                            sent = sentiment.analyze_sentiment_simple(sample['question'])
                            sample.update(sent)

                        samples.append(sample)
                except:
                    continue

            if samples:
                df = pd.DataFrame(samples)
                df.to_csv(output_path, index=False)
                logger.info(f"Saved {len(df)} event-bot samples to {output_path}")
                conn.close()
                return df

            conn.close()
            return pd.DataFrame()

        # Process news events
        samples = []
        resolved_markets = self.market_mapper.get_resolved_markets()

        for event in events:
            # Match event to markets (simple keyword matching for now)
            event_text = f"{event.get('title', '')} {event.get('description', '')}"

            for market in resolved_markets:
                # Very basic matching - should be improved with embeddings
                question = market.get('question', '').lower()
                if any(kw in event_text.lower() for kw in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto']):
                    if any(kw in question for kw in ['bitcoin', 'btc', 'ethereum', 'eth']):
                        sample = labeler.label_news_event(event, market)
                        if sample:
                            # Add sentiment features
                            sent = sentiment.analyze_sentiment_simple(event_text)
                            sample.update(sent)
                            samples.append(sample)
                            break  # One market per event

        conn.close()

        if samples:
            df = pd.DataFrame(samples)
            df.to_csv(output_path, index=False)
            logger.info(f"Saved {len(df)} event-bot samples to {output_path}")
            return df

        return pd.DataFrame()

    def generate_price_level_training_data(self,
                                           output_path: str = 'data/training_price_level.csv') -> pd.DataFrame:
        """
        Generate training data for the price-level trading bot.

        Features (36 total):
        - Asset type (one-hot)
        - Strike price
        - Distance to strike (%)
        - Direction (ABOVE/BELOW)
        - Market duration
        - Historical volatility
        - Volume/liquidity metrics

        Labels:
        - YES/NO (strike hit during market lifetime)

        Returns:
            DataFrame with training samples
        """
        from historical_labeler import PriceLevelLabeler

        labeler = PriceLevelLabeler(db_path=self.db_path)
        samples = labeler.generate_samples_from_resolved_markets()

        if not samples:
            logger.warning("No price-level samples generated")
            return pd.DataFrame()

        df = pd.DataFrame(samples)

        # Add engineered features
        df = self._engineer_price_level_features(df)

        # Save
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(df)} price-level samples to {output_path}")

        # Show distribution
        logger.info(f"Label distribution:\n{df['label'].value_counts()}")

        return df

    def _engineer_price_level_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add engineered features to price-level samples."""

        # Asset one-hot encoding
        if 'asset' in df.columns:
            asset_dummies = pd.get_dummies(df['asset'], prefix='asset')
            df = pd.concat([df, asset_dummies], axis=1)

        # Direction encoding
        if 'direction' in df.columns:
            df['direction_above'] = (df['direction'] == 'ABOVE').astype(int)

        # Distance to strike buckets
        if 'distance_to_strike' in df.columns:
            df['distance_bucket'] = pd.cut(
                df['distance_to_strike'].fillna(0),
                bins=[-100, -20, -10, -5, 0, 5, 10, 20, 100],
                labels=['far_below', 'below_20', 'below_10', 'below_5',
                        'above_5', 'above_10', 'above_20', 'far_above']
            )
            distance_dummies = pd.get_dummies(df['distance_bucket'], prefix='dist')
            df = pd.concat([df, distance_dummies], axis=1)

        # Duration buckets
        if 'market_duration_days' in df.columns:
            df['duration_bucket'] = pd.cut(
                df['market_duration_days'].fillna(7),
                bins=[0, 1, 7, 30, 90, 365, 1000],
                labels=['1d', '1w', '1m', '3m', '1y', 'long']
            )
            duration_dummies = pd.get_dummies(df['duration_bucket'], prefix='dur')
            df = pd.concat([df, duration_dummies], axis=1)

        # Normalize strike price by asset typical range
        asset_scale = {'BTC': 100000, 'ETH': 10000, 'SOL': 500, 'DOGE': 1, 'XRP': 5}
        if 'asset' in df.columns and 'strike' in df.columns:
            df['strike_normalized'] = df.apply(
                lambda r: r['strike'] / asset_scale.get(r['asset'], 10000)
                if pd.notna(r['strike']) else 0,
                axis=1
            )

        return df

    def validate_data_quality(self) -> Dict:
        """
        Validate the quality of collected data.

        Returns:
            Dictionary with validation results
        """
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': {}
        }

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check 1: On-chain trades count
        cursor.execute("SELECT COUNT(*) FROM on_chain_trades")
        trade_count = cursor.fetchone()[0]
        results['checks']['on_chain_trades'] = {
            'count': trade_count,
            'status': 'ok' if trade_count >= 1000 else 'low'
        }

        # Check 2: Trades with condition_id
        cursor.execute("""
            SELECT COUNT(*) FROM on_chain_trades WHERE condition_id IS NOT NULL
        """)
        mapped_count = cursor.fetchone()[0]
        mapping_rate = mapped_count / trade_count if trade_count > 0 else 0
        results['checks']['condition_mapping'] = {
            'mapped_count': mapped_count,
            'mapping_rate': f"{mapping_rate:.1%}",
            'status': 'ok' if mapping_rate >= 0.5 else 'low'
        }

        # Check 3: Date range coverage
        cursor.execute("""
            SELECT MIN(block_timestamp), MAX(block_timestamp)
            FROM on_chain_trades WHERE block_timestamp != ''
        """)
        date_range = cursor.fetchone()
        results['checks']['date_range'] = {
            'earliest': date_range[0],
            'latest': date_range[1],
            'status': 'ok'
        }

        # Check 4: Market metadata
        cursor.execute("SELECT COUNT(*) FROM markets")
        market_count = cursor.fetchone()[0]
        results['checks']['markets'] = {
            'count': market_count,
            'status': 'ok' if market_count >= 100 else 'low'
        }

        # Check 5: Training data files
        for path in ['data/training_event_bot.csv', 'data/training_price_level.csv']:
            if Path(path).exists():
                df = pd.read_csv(path)
                results['checks'][Path(path).stem] = {
                    'samples': len(df),
                    'columns': list(df.columns),
                    'status': 'ok' if len(df) >= 100 else 'low'
                }
            else:
                results['checks'][Path(path).stem] = {
                    'status': 'missing'
                }

        conn.close()
        return results

    def get_statistics(self) -> Dict:
        """Get comprehensive pipeline statistics."""
        stats = {}

        # Alchemy stats
        try:
            stats['alchemy'] = self.alchemy_collector.get_statistics()
        except:
            stats['alchemy'] = {'error': 'not initialized'}

        # Mapper stats
        try:
            stats['market_mapper'] = self.market_mapper.get_statistics()
        except:
            stats['market_mapper'] = {'error': 'not initialized'}

        # Training data stats
        for name, path in [('event_bot', 'data/training_event_bot.csv'),
                           ('price_level', 'data/training_price_level.csv')]:
            if Path(path).exists():
                df = pd.read_csv(path)
                stats[f'{name}_data'] = {
                    'samples': len(df),
                    'label_distribution': df['label'].value_counts().to_dict()
                    if 'label' in df.columns else {}
                }

        return stats


def main():
    """Main pipeline execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Training Data Pipeline")
    parser.add_argument("--full", action="store_true", help="Run full pipeline")
    parser.add_argument("--labels-only", action="store_true", help="Generate labels only (skip collection)")
    parser.add_argument("--event-bot", action="store_true", help="Generate event-bot labels only")
    parser.add_argument("--price-level", action="store_true", help="Generate price-level labels only")
    parser.add_argument("--validate", action="store_true", help="Validate data quality")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--backfill-days", type=int, default=180, help="Days to backfill")
    args = parser.parse_args()

    pipeline = TrainingDataPipeline()

    if args.stats:
        stats = pipeline.get_statistics()
        print(json.dumps(stats, indent=2, default=str))
        return

    if args.validate:
        results = pipeline.validate_data_quality()
        print("\n=== Data Quality Validation ===")
        for check, data in results['checks'].items():
            status = data.get('status', 'unknown')
            print(f"\n{check}:")
            for k, v in data.items():
                print(f"  {k}: {v}")
        return

    if args.full:
        pipeline.run_full_pipeline(backfill_days=args.backfill_days)
        return

    if args.labels_only:
        pipeline.run_full_pipeline(
            backfill_days=args.backfill_days,
            skip_on_chain=True,
            skip_news=True
        )
        return

    if args.event_bot:
        pipeline.generate_event_bot_training_data()
        return

    if args.price_level:
        pipeline.generate_price_level_training_data()
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
