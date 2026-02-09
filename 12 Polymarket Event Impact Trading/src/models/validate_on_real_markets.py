#!/usr/bin/env python3
"""
Validate Price-Level Model on Real Polymarket Outcomes
Tests model predictions against actual resolved markets from 2020-2022.
"""

import pandas as pd
import numpy as np
import pickle
import requests
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import time

from price_level_features import PriceLevelFeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a single market."""
    condition_id: str
    question: str
    asset: str
    strike_price: float
    direction: str
    created_at: datetime
    end_date: datetime
    days_to_expiry: int
    spot_price_at_creation: float
    strike_distance_pct: float
    actual_outcome: str  # Yes or No
    model_prob: float  # Model's P(YES)
    model_prediction: str  # Yes or No
    model_correct: bool
    market_volume: float
    signal: str  # BUY_YES, BUY_NO, or HOLD
    edge: float
    potential_pnl: float  # If we traded at 50% market price


class RealMarketValidator:
    """Validate model against real Polymarket outcomes."""

    COINGECKO_IDS = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'SOL': 'solana'
    }

    def __init__(self, model_path: str = 'data/price_level_model.pkl'):
        """Initialize validator."""

        # Load model
        logger.info(f"Loading model from {model_path}")
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        self.model = model_data['model']
        self.feature_names = model_data['feature_names']

        # Feature extractor
        self.feature_extractor = PriceLevelFeatureExtractor()

        # Price cache
        self.price_cache = {}

        logger.info("Validator initialized")

    def load_resolved_markets(self, csv_path: str = 'data/polymarket_crypto_resolved.csv') -> pd.DataFrame:
        """Load resolved markets from CSV."""

        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} resolved markets")

        # Filter to standard price-level markets (exclude gas price markets)
        df = df[~df['question'].str.contains('gas price', case=False, na=False)]
        df = df[~df['question'].str.contains('Gwei', case=False, na=False)]
        df = df[~df['question'].str.contains('Market Cap', case=False, na=False)]
        df = df[~df['question'].str.contains('closer to', case=False, na=False)]  # Race markets
        df = df[~df['question'].str.contains('ENS', case=False, na=False)]  # ENS token, not ETH

        # Filter to markets with valid strike prices (some have $50, $55 which are likely in thousands)
        # These old markets used shorthand like "$50k" which got parsed as $50
        df = df[df['strike_price'] > 100]  # Exclude obviously wrong parses

        logger.info(f"Filtered to {len(df)} standard price-level markets")
        return df

    def get_historical_price(self, asset: str, date: datetime) -> Optional[float]:
        """Get historical price for asset on specific date."""

        if asset not in self.COINGECKO_IDS:
            return None

        coin_id = self.COINGECKO_IDS[asset]
        date_str = date.strftime('%d-%m-%Y')
        cache_key = f"{asset}_{date_str}"

        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/history"
            params = {'date': date_str, 'localization': 'false'}

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 429:
                logger.warning("Rate limited, waiting 60s...")
                time.sleep(60)
                response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                logger.debug(f"Failed to get price for {asset} on {date_str}: {response.status_code}")
                return None

            data = response.json()
            price = data.get('market_data', {}).get('current_price', {}).get('usd')

            if price:
                self.price_cache[cache_key] = price

            time.sleep(0.5)  # Rate limiting
            return price

        except Exception as e:
            logger.debug(f"Error fetching price: {e}")
            return None

    def get_historical_ohlcv(self, asset: str, end_date: datetime, days: int = 30) -> Optional[pd.DataFrame]:
        """Get historical OHLCV data leading up to a date."""

        if asset not in self.COINGECKO_IDS:
            return None

        coin_id = self.COINGECKO_IDS[asset]

        try:
            # Get market chart data
            end_ts = int(end_date.timestamp())
            start_ts = int((end_date - timedelta(days=days)).timestamp())

            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
            params = {
                'vs_currency': 'usd',
                'from': start_ts,
                'to': end_ts
            }

            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 429:
                logger.warning("Rate limited, waiting 60s...")
                time.sleep(60)
                response = requests.get(url, params=params, timeout=15)

            if response.status_code != 200:
                return None

            data = response.json()
            prices = data.get('prices', [])

            if not prices:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(prices, columns=['timestamp', 'close'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['close'].shift(1).fillna(df['close'])
            df['high'] = df['close'] * 1.01
            df['low'] = df['close'] * 0.99
            df['volume'] = 1e9
            df['asset'] = asset

            time.sleep(0.5)  # Rate limiting
            return df

        except Exception as e:
            logger.debug(f"Error fetching OHLCV: {e}")
            return None

    def validate_market(self, row: pd.Series) -> Optional[ValidationResult]:
        """Validate model prediction on a single market."""

        asset = row['asset']
        strike_price = row['strike_price']
        direction = row['direction']
        actual_outcome = row['resolved_outcome']
        question = row['question']
        volume = row.get('volume', 0)

        # Parse dates
        try:
            created_at = pd.to_datetime(row['created_at'])
            end_date = pd.to_datetime(row['end_date'])

            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

        except Exception as e:
            logger.debug(f"Failed to parse dates: {e}")
            return None

        days_to_expiry = (end_date - created_at).days
        if days_to_expiry <= 0:
            return None

        # Get spot price at market creation
        spot_price = self.get_historical_price(asset, created_at)
        if spot_price is None:
            logger.debug(f"No spot price for {asset} on {created_at}")
            return None

        # Calculate strike distance
        if direction == 'ABOVE':
            strike_distance_pct = (strike_price - spot_price) / spot_price
        else:
            strike_distance_pct = (spot_price - strike_price) / spot_price

        # Get historical OHLCV for feature extraction
        historical = self.get_historical_ohlcv(asset, created_at, days=30)
        if historical is None or len(historical) < 10:
            logger.debug(f"Insufficient historical data for {asset}")
            return None

        # Create parsed market structure
        parsed_market = {
            'asset': asset,
            'strike_price': strike_price,
            'expiry_date': end_date,
            'days_to_expiry': days_to_expiry,
            'direction': direction or 'ABOVE',
            'conditionId': row['condition_id'],
            'token_id': f'token_{row["condition_id"][:8]}',
            'question': question
        }

        # Simulated Polymarket data
        polymarket_data = {
            'market': {'volume24hr': volume / 30, 'volume1wk': volume / 4, 'liquidity': volume / 10},
            'orderbook': {
                'bids': [{'price': '0.48', 'size': '1000'}],
                'asks': [{'price': '0.52', 'size': '1000'}]
            }
        }

        # Extract features
        try:
            features = self.feature_extractor.extract_all_features(
                parsed_market=parsed_market,
                spot_price=spot_price,
                historical_ohlcv=historical,
                polymarket_data=polymarket_data
            )
        except Exception as e:
            logger.debug(f"Feature extraction failed: {e}")
            return None

        # Get model prediction
        try:
            features_df = pd.DataFrame([features])[self.feature_names]
            model_prob = self.model.predict_proba(features_df)[0][1]
        except Exception as e:
            logger.debug(f"Model prediction failed: {e}")
            return None

        # Determine prediction and signal
        model_prediction = 'Yes' if model_prob > 0.5 else 'No'
        model_correct = model_prediction == actual_outcome

        # Calculate edge (assume 50% market price for simplicity)
        market_price = 0.5
        edge = model_prob - market_price if model_prob > 0.5 else market_price - model_prob

        if model_prob > 0.6:
            signal = 'BUY_YES'
        elif model_prob < 0.4:
            signal = 'BUY_NO'
        else:
            signal = 'HOLD'

        # Calculate potential P&L (assuming $10 position at 50% market price)
        position_size = 10.0
        if signal == 'BUY_YES':
            if actual_outcome == 'Yes':
                potential_pnl = position_size * (1 - market_price) / market_price
            else:
                potential_pnl = -position_size
        elif signal == 'BUY_NO':
            if actual_outcome == 'No':
                potential_pnl = position_size * market_price / (1 - market_price)
            else:
                potential_pnl = -position_size
        else:
            potential_pnl = 0

        return ValidationResult(
            condition_id=row['condition_id'],
            question=question[:60] + '...' if len(question) > 60 else question,
            asset=asset,
            strike_price=strike_price,
            direction=direction or 'ABOVE',
            created_at=created_at,
            end_date=end_date,
            days_to_expiry=days_to_expiry,
            spot_price_at_creation=spot_price,
            strike_distance_pct=strike_distance_pct,
            actual_outcome=actual_outcome,
            model_prob=model_prob,
            model_prediction=model_prediction,
            model_correct=model_correct,
            market_volume=volume,
            signal=signal,
            edge=edge,
            potential_pnl=potential_pnl
        )

    def run_validation(self) -> Dict:
        """Run full validation on all resolved markets."""

        logger.info("="*70)
        logger.info("VALIDATING MODEL ON REAL POLYMARKET OUTCOMES")
        logger.info("="*70)

        # Load markets
        markets = self.load_resolved_markets()

        results: List[ValidationResult] = []
        failed = 0

        for idx, row in markets.iterrows():
            logger.info(f"\nValidating: {row['question'][:50]}...")

            result = self.validate_market(row)

            if result:
                results.append(result)
                status = "CORRECT" if result.model_correct else "WRONG"
                logger.info(f"  Model: {result.model_prob:.1%} P(YES) -> {result.model_prediction}")
                logger.info(f"  Actual: {result.actual_outcome} | {status}")
            else:
                failed += 1
                logger.info(f"  SKIPPED (missing data)")

        if not results:
            logger.error("No markets could be validated!")
            return {}

        # Calculate metrics
        metrics = self._calculate_metrics(results, failed)

        # Print results
        self._print_results(metrics, results)

        return metrics

    def _calculate_metrics(self, results: List[ValidationResult], failed: int) -> Dict:
        """Calculate validation metrics."""

        total = len(results)
        correct = sum(1 for r in results if r.model_correct)

        # By signal type
        buy_yes = [r for r in results if r.signal == 'BUY_YES']
        buy_no = [r for r in results if r.signal == 'BUY_NO']
        holds = [r for r in results if r.signal == 'HOLD']

        buy_yes_wins = sum(1 for r in buy_yes if r.potential_pnl > 0)
        buy_no_wins = sum(1 for r in buy_no if r.potential_pnl > 0)

        total_pnl = sum(r.potential_pnl for r in results)
        traded_pnl = sum(r.potential_pnl for r in results if r.signal != 'HOLD')

        # By asset
        btc_results = [r for r in results if r.asset == 'BTC']
        eth_results = [r for r in results if r.asset == 'ETH']
        sol_results = [r for r in results if r.asset == 'SOL']

        return {
            'total_validated': total,
            'skipped': failed,
            'accuracy': correct / total if total > 0 else 0,
            'correct': correct,
            'wrong': total - correct,
            'buy_yes_count': len(buy_yes),
            'buy_yes_win_rate': buy_yes_wins / len(buy_yes) if buy_yes else 0,
            'buy_no_count': len(buy_no),
            'buy_no_win_rate': buy_no_wins / len(buy_no) if buy_no else 0,
            'hold_count': len(holds),
            'total_pnl': total_pnl,
            'traded_pnl': traded_pnl,
            'btc_count': len(btc_results),
            'btc_accuracy': sum(1 for r in btc_results if r.model_correct) / len(btc_results) if btc_results else 0,
            'eth_count': len(eth_results),
            'eth_accuracy': sum(1 for r in eth_results if r.model_correct) / len(eth_results) if eth_results else 0,
            'sol_count': len(sol_results),
            'sol_accuracy': sum(1 for r in sol_results if r.model_correct) / len(sol_results) if sol_results else 0,
            'results': results
        }

    def _print_results(self, metrics: Dict, results: List[ValidationResult]):
        """Print validation results."""

        print("\n" + "="*70)
        print("REAL MARKET VALIDATION RESULTS")
        print("="*70)

        print(f"\n VALIDATION SUMMARY")
        print(f"   Markets Validated: {metrics['total_validated']}")
        print(f"   Markets Skipped: {metrics['skipped']}")

        print(f"\n MODEL ACCURACY")
        print(f"   Overall Accuracy: {metrics['accuracy']:.1%}")
        print(f"   Correct: {metrics['correct']}, Wrong: {metrics['wrong']}")

        print(f"\n TRADING SIGNALS")
        print(f"   BUY YES: {metrics['buy_yes_count']} trades, {metrics['buy_yes_win_rate']:.1%} win rate")
        print(f"   BUY NO: {metrics['buy_no_count']} trades, {metrics['buy_no_win_rate']:.1%} win rate")
        print(f"   HOLD: {metrics['hold_count']} trades")

        total_trades = metrics['buy_yes_count'] + metrics['buy_no_count']
        if total_trades > 0:
            total_wins = int(metrics['buy_yes_win_rate'] * metrics['buy_yes_count'] +
                          metrics['buy_no_win_rate'] * metrics['buy_no_count'])
            overall_win_rate = total_wins / total_trades
            print(f"   Overall Trading Win Rate: {overall_win_rate:.1%}")

        print(f"\n POTENTIAL P&L ($10 position size)")
        print(f"   Total P&L (all signals): ${metrics['total_pnl']:,.2f}")
        print(f"   Traded P&L (excluding HOLD): ${metrics['traded_pnl']:,.2f}")

        print(f"\n BY ASSET")
        print(f"   BTC: {metrics['btc_count']} markets, {metrics['btc_accuracy']:.1%} accuracy")
        print(f"   ETH: {metrics['eth_count']} markets, {metrics['eth_accuracy']:.1%} accuracy")
        if metrics['sol_count'] > 0:
            print(f"   SOL: {metrics['sol_count']} markets, {metrics['sol_accuracy']:.1%} accuracy")

        print(f"\n DETAILED RESULTS")
        print("-"*70)
        for r in results:
            status = "OK" if r.model_correct else "XX"
            print(f"   [{status}] {r.asset} ${r.strike_price:,.0f} {r.direction}")
            print(f"       Model: {r.model_prob:.1%} -> {r.model_prediction}, Actual: {r.actual_outcome}")
            print(f"       Strike dist: {r.strike_distance_pct:+.1%}, Days: {r.days_to_expiry}")

        # Verdict
        print("\n" + "="*70)
        if metrics['accuracy'] >= 0.60:
            print("MODEL VALIDATED: >60% accuracy on real markets")
        elif metrics['accuracy'] >= 0.50:
            print("MODEL MARGINAL: 50-60% accuracy on real markets")
        else:
            print("MODEL NEEDS WORK: <50% accuracy on real markets")
        print("="*70)


def main():
    """Run validation."""

    import warnings
    warnings.filterwarnings('ignore')

    validator = RealMarketValidator()
    results = validator.run_validation()

    # Save results
    if results and 'results' in results:
        df = pd.DataFrame([{
            'question': r.question,
            'asset': r.asset,
            'strike_price': r.strike_price,
            'direction': r.direction,
            'days_to_expiry': r.days_to_expiry,
            'spot_price': r.spot_price_at_creation,
            'strike_distance_pct': r.strike_distance_pct,
            'actual_outcome': r.actual_outcome,
            'model_prob': r.model_prob,
            'model_prediction': r.model_prediction,
            'model_correct': r.model_correct,
            'signal': r.signal,
            'potential_pnl': r.potential_pnl
        } for r in results['results']])

        df.to_csv('data/validation_results.csv', index=False)
        logger.info("\nResults saved to data/validation_results.csv")


if __name__ == '__main__':
    main()
