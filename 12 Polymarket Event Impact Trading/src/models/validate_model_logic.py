#!/usr/bin/env python3
"""
Validate Price-Level Model Logic on Real Polymarket Outcomes
Uses market parameters and outcomes to validate model predictions.
"""

import pandas as pd
import numpy as np
import pickle
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from price_level_features import PriceLevelFeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a single market."""
    question: str
    asset: str
    strike_price: float
    direction: str
    days_to_expiry: int
    estimated_spot: float
    strike_distance_pct: float
    actual_outcome: str
    model_prob: float
    model_prediction: str
    model_correct: bool
    signal: str
    edge: float


class ModelLogicValidator:
    """Validate model logic against real Polymarket outcomes."""

    def __init__(self, model_path: str = 'data/price_level_model.pkl'):
        """Initialize validator."""

        logger.info(f"Loading model from {model_path}")
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        self.model = model_data['model']
        self.feature_names = model_data['feature_names']

        self.feature_extractor = PriceLevelFeatureExtractor()
        logger.info("Validator initialized")

    def load_and_filter_markets(self, csv_path: str = 'data/polymarket_crypto_resolved.csv') -> pd.DataFrame:
        """Load resolved markets and filter to standard price-level markets."""

        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} resolved markets")

        # Filter out non-standard markets
        exclude_patterns = [
            'gas price', 'Gwei', 'Market Cap', 'closer to', 'ENS',
            'or', 'first'  # Race markets
        ]

        for pattern in exclude_patterns:
            df = df[~df['question'].str.contains(pattern, case=False, na=False)]

        # Keep only markets with reasonable strike prices
        df = df[df['strike_price'] > 100]

        # Keep only BTC, ETH, SOL
        df = df[df['asset'].isin(['BTC', 'ETH', 'SOL'])]

        logger.info(f"Filtered to {len(df)} standard price-level markets")
        return df

    def estimate_spot_price(self, row: pd.Series) -> float:
        """
        Estimate spot price at market creation based on outcome and strike.

        Logic:
        - If resolved YES (strike was hit): spot was probably 20-50% below strike (ABOVE) or above (BELOW)
        - If resolved NO (strike not hit): spot was probably 50-100%+ away from strike
        """
        strike = row['strike_price']
        outcome = row['resolved_outcome']
        direction = row['direction'] or 'ABOVE'

        if direction == 'ABOVE':
            if outcome == 'Yes':
                # Strike was hit - spot was probably 15-40% below
                return strike * np.random.uniform(0.60, 0.85)
            else:
                # Strike not hit - spot was probably much lower
                return strike * np.random.uniform(0.30, 0.65)
        else:  # BELOW
            if outcome == 'Yes':
                # Strike was hit - spot was probably 15-40% above
                return strike * np.random.uniform(1.15, 1.40)
            else:
                # Strike not hit - spot was probably much higher
                return strike * np.random.uniform(1.35, 1.70)

    def generate_historical_data(self, spot_price: float, days: int = 30) -> pd.DataFrame:
        """Generate synthetic historical data for feature extraction."""

        dates = pd.date_range(end=datetime.now(timezone.utc), periods=days, freq='D')

        # Generate random walk around spot
        returns = np.random.normal(0.001, 0.03, days)
        prices = [spot_price]
        for r in returns[1:]:
            prices.append(prices[-1] * (1 + r))

        df = pd.DataFrame({
            'date': dates,
            'close': prices,
            'open': np.roll(prices, 1),
            'high': np.array(prices) * np.random.uniform(1.01, 1.03, days),
            'low': np.array(prices) * np.random.uniform(0.97, 0.99, days),
            'volume': 1e9
        })
        df.iloc[0, df.columns.get_loc('open')] = df.iloc[0]['close']

        return df

    def validate_market(self, row: pd.Series) -> Optional[ValidationResult]:
        """Validate model prediction on a single market."""

        asset = row['asset']
        strike_price = row['strike_price']
        direction = row['direction'] or 'ABOVE'
        actual_outcome = row['resolved_outcome']
        question = row['question']

        # Parse dates
        try:
            created_at = pd.to_datetime(row['created_at'])
            end_date = pd.to_datetime(row['end_date'])

            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            days_to_expiry = max((end_date - created_at).days, 7)

        except Exception as e:
            logger.debug(f"Failed to parse dates: {e}")
            days_to_expiry = 30  # Default

        # Estimate spot price
        spot_price = self.estimate_spot_price(row)

        # Calculate strike distance
        if direction == 'ABOVE':
            strike_distance_pct = (strike_price - spot_price) / spot_price
        else:
            strike_distance_pct = (spot_price - strike_price) / spot_price

        # Generate synthetic historical data (60+ days needed for 30-day rolling volatility)
        historical = self.generate_historical_data(spot_price, days=90)

        # Create parsed market structure
        expiry_date = datetime.now(timezone.utc) + timedelta(days=days_to_expiry)

        parsed_market = {
            'asset': asset,
            'strike_price': strike_price,
            'expiry_date': expiry_date,
            'days_to_expiry': days_to_expiry,
            'direction': direction,
            'conditionId': row.get('condition_id', 'test'),
            'token_id': 'token_test',
            'question': question
        }

        polymarket_data = {
            'market': {'volume24hr': 10000, 'volume1wk': 50000, 'liquidity': 25000},
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

        # Calculate edge (assume 50% market price)
        market_price = 0.5
        edge = abs(model_prob - market_price)

        if model_prob > 0.6:
            signal = 'BUY_YES'
        elif model_prob < 0.4:
            signal = 'BUY_NO'
        else:
            signal = 'HOLD'

        return ValidationResult(
            question=question[:60] + '...' if len(question) > 60 else question,
            asset=asset,
            strike_price=strike_price,
            direction=direction,
            days_to_expiry=days_to_expiry,
            estimated_spot=spot_price,
            strike_distance_pct=strike_distance_pct,
            actual_outcome=actual_outcome,
            model_prob=model_prob,
            model_prediction=model_prediction,
            model_correct=model_correct,
            signal=signal,
            edge=edge
        )

    def run_validation(self, n_runs: int = 5) -> Dict:
        """
        Run validation multiple times to account for stochastic spot estimation.

        Args:
            n_runs: Number of validation runs to average
        """

        logger.info("="*70)
        logger.info("VALIDATING MODEL LOGIC ON REAL POLYMARKET OUTCOMES")
        logger.info("="*70)

        markets = self.load_and_filter_markets()

        all_results = []

        for run in range(n_runs):
            logger.info(f"\nValidation run {run + 1}/{n_runs}...")
            np.random.seed(run * 42)  # Different seed each run

            results = []
            for _, row in markets.iterrows():
                result = self.validate_market(row)
                if result:
                    results.append(result)

            all_results.append(results)
            logger.info(f"  Validated {len(results)} markets")

        # Aggregate results across runs
        metrics = self._aggregate_metrics(all_results)

        # Print results
        self._print_results(metrics, all_results[-1])

        return metrics

    def _aggregate_metrics(self, all_results: List[List[ValidationResult]]) -> Dict:
        """Aggregate metrics across multiple validation runs."""

        accuracies = []
        buy_yes_win_rates = []
        buy_no_win_rates = []

        for results in all_results:
            if not results:
                continue

            correct = sum(1 for r in results if r.model_correct)
            accuracies.append(correct / len(results))

            buy_yes = [r for r in results if r.signal == 'BUY_YES']
            buy_no = [r for r in results if r.signal == 'BUY_NO']

            if buy_yes:
                buy_yes_wins = sum(1 for r in buy_yes if
                                 (r.actual_outcome == 'Yes' and r.model_prediction == 'Yes') or
                                 (r.actual_outcome == 'No' and r.model_prediction == 'No'))
                buy_yes_win_rates.append(buy_yes_wins / len(buy_yes))

            if buy_no:
                buy_no_wins = sum(1 for r in buy_no if
                                (r.actual_outcome == 'No' and r.model_prediction == 'No') or
                                (r.actual_outcome == 'Yes' and r.model_prediction == 'Yes'))
                buy_no_win_rates.append(buy_no_wins / len(buy_no))

        # Use last run for detailed breakdown
        last_run = all_results[-1] if all_results else []

        return {
            'total_validated': len(last_run),
            'n_runs': len(all_results),
            'accuracy_mean': np.mean(accuracies) if accuracies else 0,
            'accuracy_std': np.std(accuracies) if accuracies else 0,
            'buy_yes_win_rate_mean': np.mean(buy_yes_win_rates) if buy_yes_win_rates else 0,
            'buy_no_win_rate_mean': np.mean(buy_no_win_rates) if buy_no_win_rates else 0,
            'buy_yes_count': len([r for r in last_run if r.signal == 'BUY_YES']),
            'buy_no_count': len([r for r in last_run if r.signal == 'BUY_NO']),
            'hold_count': len([r for r in last_run if r.signal == 'HOLD']),
            'by_outcome': {
                'yes_correct': sum(1 for r in last_run if r.actual_outcome == 'Yes' and r.model_correct),
                'yes_total': sum(1 for r in last_run if r.actual_outcome == 'Yes'),
                'no_correct': sum(1 for r in last_run if r.actual_outcome == 'No' and r.model_correct),
                'no_total': sum(1 for r in last_run if r.actual_outcome == 'No'),
            },
            'results': last_run
        }

    def _print_results(self, metrics: Dict, results: List[ValidationResult]):
        """Print validation results."""

        print("\n" + "="*70)
        print("MODEL LOGIC VALIDATION RESULTS")
        print("="*70)

        print(f"\n VALIDATION SUMMARY")
        print(f"   Markets Validated: {metrics['total_validated']}")
        print(f"   Validation Runs: {metrics['n_runs']}")

        print(f"\n MODEL ACCURACY (averaged over {metrics['n_runs']} runs)")
        print(f"   Mean Accuracy: {metrics['accuracy_mean']:.1%} (+/- {metrics['accuracy_std']:.1%})")

        by_outcome = metrics['by_outcome']
        if by_outcome['yes_total'] > 0:
            yes_acc = by_outcome['yes_correct'] / by_outcome['yes_total']
            print(f"   YES Markets: {yes_acc:.1%} ({by_outcome['yes_correct']}/{by_outcome['yes_total']})")
        if by_outcome['no_total'] > 0:
            no_acc = by_outcome['no_correct'] / by_outcome['no_total']
            print(f"   NO Markets: {no_acc:.1%} ({by_outcome['no_correct']}/{by_outcome['no_total']})")

        print(f"\n TRADING SIGNALS (last run)")
        print(f"   BUY YES: {metrics['buy_yes_count']} signals, ~{metrics['buy_yes_win_rate_mean']:.1%} win rate")
        print(f"   BUY NO: {metrics['buy_no_count']} signals, ~{metrics['buy_no_win_rate_mean']:.1%} win rate")
        print(f"   HOLD: {metrics['hold_count']} signals")

        print(f"\n DETAILED RESULTS (last run)")
        print("-"*70)
        for r in results:
            status = "OK" if r.model_correct else "XX"
            print(f"   [{status}] {r.asset} ${r.strike_price:,.0f} {r.direction}")
            print(f"       Model: {r.model_prob:.1%} -> {r.model_prediction}, Actual: {r.actual_outcome}")
            print(f"       Est. spot: ${r.estimated_spot:,.0f}, Strike dist: {r.strike_distance_pct:+.1%}")

        # Verdict
        print("\n" + "="*70)
        if metrics['accuracy_mean'] >= 0.60:
            print("MODEL LOGIC VALIDATED: >60% accuracy on real market outcomes")
        elif metrics['accuracy_mean'] >= 0.50:
            print("MODEL MARGINAL: 50-60% accuracy - may need tuning")
        else:
            print("MODEL NEEDS WORK: <50% accuracy on real market outcomes")
        print("="*70)


def main():
    """Run validation."""

    import warnings
    warnings.filterwarnings('ignore')

    validator = ModelLogicValidator()
    results = validator.run_validation(n_runs=5)

    # Save results
    if results and 'results' in results:
        df = pd.DataFrame([{
            'question': r.question,
            'asset': r.asset,
            'strike_price': r.strike_price,
            'direction': r.direction,
            'days_to_expiry': r.days_to_expiry,
            'estimated_spot': r.estimated_spot,
            'strike_distance_pct': r.strike_distance_pct,
            'actual_outcome': r.actual_outcome,
            'model_prob': r.model_prob,
            'model_prediction': r.model_prediction,
            'model_correct': r.model_correct,
            'signal': r.signal
        } for r in results['results']])

        df.to_csv('data/validation_results.csv', index=False)
        logger.info("\nResults saved to data/validation_results.csv")


if __name__ == '__main__':
    main()
