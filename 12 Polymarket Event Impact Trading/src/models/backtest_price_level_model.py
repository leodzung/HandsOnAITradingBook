#!/usr/bin/env python3
"""
Backtest Price-Level Model on Historical Data
Simulates trading decisions and calculates win rate, P&L, and other metrics.
"""

import pandas as pd
import numpy as np
import pickle
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

from price_level_features import PriceLevelFeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade."""
    entry_date: datetime
    asset: str
    direction: str  # ABOVE or BELOW
    strike_price: float
    entry_price: float  # Spot price at entry
    days_to_expiry: int
    model_prob: float  # Model's P(YES)
    market_price: float  # Simulated market price
    signal: str  # BUY_YES, BUY_NO, or HOLD
    edge: float
    actual_outcome: int  # 1 if strike was reached, 0 otherwise
    pnl: float  # Profit/loss on this trade


class PriceLevelBacktester:
    """Backtest price-level model on historical data."""

    def __init__(self, model_path: str = 'data/price_level_model.pkl',
                 price_data_path: str = 'data/historical_prices_real.csv'):
        """Initialize backtester."""

        # Load model
        logger.info(f"Loading model from {model_path}")
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        self.model = model_data['model']
        self.feature_names = model_data['feature_names']

        # Load price data
        logger.info(f"Loading price data from {price_data_path}")
        self.prices = pd.read_csv(price_data_path)
        self.prices['date'] = pd.to_datetime(self.prices['date'])
        self.prices = self.prices.sort_values(['asset', 'date']).reset_index(drop=True)

        # Feature extractor
        self.feature_extractor = PriceLevelFeatureExtractor()

        logger.info(f"Loaded {len(self.prices)} price records")

    def run_backtest(self,
                     num_trades: int = 500,
                     min_days_to_expiry: int = 30,
                     max_days_to_expiry: int = 120,
                     edge_threshold: float = 0.10,
                     position_size: float = 10.0) -> Dict:
        """
        Run backtest simulation.

        Args:
            num_trades: Number of trades to simulate
            min_days_to_expiry: Minimum days to expiry
            max_days_to_expiry: Maximum days to expiry
            edge_threshold: Minimum edge to take a trade
            position_size: Dollar amount per trade

        Returns:
            Dictionary with backtest results
        """
        logger.info(f"\n{'='*70}")
        logger.info("STARTING BACKTEST")
        logger.info(f"{'='*70}")
        logger.info(f"Trades to simulate: {num_trades}")
        logger.info(f"Days to expiry: {min_days_to_expiry}-{max_days_to_expiry}")
        logger.info(f"Edge threshold: {edge_threshold:.0%}")
        logger.info(f"Position size: ${position_size}")

        trades: List[Trade] = []
        skipped = 0

        for i in range(num_trades * 3):  # Generate more to account for HOLD signals
            if len(trades) >= num_trades:
                break

            trade = self._simulate_trade(
                min_days_to_expiry=min_days_to_expiry,
                max_days_to_expiry=max_days_to_expiry,
                edge_threshold=edge_threshold,
                position_size=position_size
            )

            if trade is None:
                continue

            if trade.signal == 'HOLD':
                skipped += 1
                continue

            trades.append(trade)

            if len(trades) % 100 == 0:
                logger.info(f"  Simulated {len(trades)}/{num_trades} trades...")

        if not trades:
            logger.error("No trades generated!")
            return {}

        # Calculate metrics
        results = self._calculate_metrics(trades, skipped)

        # Print results
        self._print_results(results)

        return results

    def _simulate_trade(self, min_days_to_expiry: int, max_days_to_expiry: int,
                       edge_threshold: float, position_size: float) -> Trade:
        """Simulate a single trade."""

        # Random asset
        asset = random.choice(['BTC', 'ETH'])
        asset_prices = self.prices[self.prices['asset'] == asset].copy()

        if len(asset_prices) < max_days_to_expiry + 30:
            return None

        # Random entry point
        lookback_needed = 30
        max_entry_idx = len(asset_prices) - max_days_to_expiry - 1

        if max_entry_idx <= lookback_needed:
            return None

        entry_idx = random.randint(lookback_needed, max_entry_idx)

        entry_row = asset_prices.iloc[entry_idx]
        entry_date = entry_row['date']
        entry_price = entry_row['close']

        # Random expiry
        days_to_expiry = random.randint(min_days_to_expiry, max_days_to_expiry)
        expiry_date = entry_date + timedelta(days=days_to_expiry)

        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

        # Random strike with realistic distribution
        rand = random.random()
        if rand < 0.25:
            strike_pct = random.uniform(0.05, 0.20)   # Near money
        elif rand < 0.50:
            strike_pct = random.uniform(0.20, 0.40)   # Moderate
        elif rand < 0.75:
            strike_pct = random.uniform(0.40, 0.70)   # Far
        else:
            strike_pct = random.uniform(0.70, 1.20)   # Very far

        direction = random.choice(['ABOVE', 'BELOW'])

        if direction == 'ABOVE':
            strike_price = entry_price * (1 + strike_pct)
        else:
            strike_price = entry_price * (1 - strike_pct)

        # Get historical prices for features
        historical_prices = asset_prices.iloc[:entry_idx + 1].copy()
        historical_prices['open'] = historical_prices['close'].shift(1).fillna(historical_prices['close'])
        historical_prices['high'] = historical_prices['close'] * 1.01
        historical_prices['low'] = historical_prices['close'] * 0.99
        historical_prices['volume'] = 1e9

        # Create market structure
        parsed_market = {
            'asset': asset,
            'strike_price': strike_price,
            'expiry_date': expiry_date,
            'days_to_expiry': days_to_expiry,
            'direction': direction,
            'conditionId': f'backtest_{entry_idx}',
            'token_id': f'token_{entry_idx}',
            'question': f'Will {asset} hit ${strike_price:,.0f}?'
        }

        # Simulate market price (use GBM probability as proxy for fair market price)
        # In real markets, price reflects market's estimate of probability
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
            return None

        # Get model prediction
        features_df = pd.DataFrame([features])[self.feature_names]
        model_prob = self.model.predict_proba(features_df)[0][1]

        # Simulate market price (slightly noisy around fair value)
        # Use a blend of GBM probability and random noise
        gbm_prob = features.get('gbm_probability', 0.5)
        noise = random.uniform(-0.15, 0.15)
        market_price = max(0.05, min(0.95, gbm_prob + noise))

        # Calculate edge and signal
        edge = model_prob - market_price

        if edge > edge_threshold:
            signal = 'BUY_YES'
        elif edge < -edge_threshold:
            signal = 'BUY_NO'
        else:
            signal = 'HOLD'

        # Determine actual outcome
        expiry_idx = entry_idx + days_to_expiry
        if expiry_idx >= len(asset_prices):
            return None

        future_prices = asset_prices.iloc[entry_idx:expiry_idx + 1]

        if direction == 'ABOVE':
            max_future = future_prices['close'].max()
            actual_outcome = 1 if max_future >= strike_price else 0
        else:
            min_future = future_prices['close'].min()
            actual_outcome = 1 if min_future <= strike_price else 0

        # Calculate P&L
        if signal == 'BUY_YES':
            # Bought YES at market_price
            if actual_outcome == 1:
                pnl = position_size * (1 - market_price) / market_price  # Win
            else:
                pnl = -position_size  # Lose entire stake
        elif signal == 'BUY_NO':
            # Bought NO at (1 - market_price)
            no_price = 1 - market_price
            if actual_outcome == 0:
                pnl = position_size * market_price / no_price  # Win
            else:
                pnl = -position_size  # Lose entire stake
        else:
            pnl = 0

        return Trade(
            entry_date=entry_date,
            asset=asset,
            direction=direction,
            strike_price=strike_price,
            entry_price=entry_price,
            days_to_expiry=days_to_expiry,
            model_prob=model_prob,
            market_price=market_price,
            signal=signal,
            edge=edge,
            actual_outcome=actual_outcome,
            pnl=pnl
        )

    def _calculate_metrics(self, trades: List[Trade], skipped: int) -> Dict:
        """Calculate backtest metrics."""

        # Separate by signal type
        buy_yes_trades = [t for t in trades if t.signal == 'BUY_YES']
        buy_no_trades = [t for t in trades if t.signal == 'BUY_NO']

        # Win rates
        buy_yes_wins = sum(1 for t in buy_yes_trades if t.pnl > 0)
        buy_no_wins = sum(1 for t in buy_no_trades if t.pnl > 0)

        total_wins = buy_yes_wins + buy_no_wins
        total_trades = len(trades)

        # P&L
        total_pnl = sum(t.pnl for t in trades)
        buy_yes_pnl = sum(t.pnl for t in buy_yes_trades)
        buy_no_pnl = sum(t.pnl for t in buy_no_trades)

        # By asset
        btc_trades = [t for t in trades if t.asset == 'BTC']
        eth_trades = [t for t in trades if t.asset == 'ETH']

        # By edge bucket
        edge_buckets = defaultdict(list)
        for t in trades:
            if abs(t.edge) < 0.20:
                bucket = '10-20%'
            elif abs(t.edge) < 0.30:
                bucket = '20-30%'
            elif abs(t.edge) < 0.40:
                bucket = '30-40%'
            else:
                bucket = '40%+'
            edge_buckets[bucket].append(t)

        return {
            'total_trades': total_trades,
            'skipped_holds': skipped,
            'buy_yes_trades': len(buy_yes_trades),
            'buy_no_trades': len(buy_no_trades),
            'total_wins': total_wins,
            'total_losses': total_trades - total_wins,
            'win_rate': total_wins / total_trades if total_trades > 0 else 0,
            'buy_yes_win_rate': buy_yes_wins / len(buy_yes_trades) if buy_yes_trades else 0,
            'buy_no_win_rate': buy_no_wins / len(buy_no_trades) if buy_no_trades else 0,
            'total_pnl': total_pnl,
            'buy_yes_pnl': buy_yes_pnl,
            'buy_no_pnl': buy_no_pnl,
            'avg_pnl_per_trade': total_pnl / total_trades if total_trades > 0 else 0,
            'btc_trades': len(btc_trades),
            'btc_win_rate': sum(1 for t in btc_trades if t.pnl > 0) / len(btc_trades) if btc_trades else 0,
            'eth_trades': len(eth_trades),
            'eth_win_rate': sum(1 for t in eth_trades if t.pnl > 0) / len(eth_trades) if eth_trades else 0,
            'edge_buckets': {
                bucket: {
                    'count': len(trades_list),
                    'win_rate': sum(1 for t in trades_list if t.pnl > 0) / len(trades_list) if trades_list else 0,
                    'pnl': sum(t.pnl for t in trades_list)
                }
                for bucket, trades_list in edge_buckets.items()
            },
            'trades': trades
        }

    def _print_results(self, results: Dict):
        """Print backtest results."""

        print("\n" + "="*70)
        print("BACKTEST RESULTS")
        print("="*70)

        print(f"\n📊 TRADE SUMMARY")
        print(f"   Total Trades Executed: {results['total_trades']}")
        print(f"   Skipped (HOLD): {results['skipped_holds']}")
        print(f"   BUY YES Trades: {results['buy_yes_trades']}")
        print(f"   BUY NO Trades: {results['buy_no_trades']}")

        print(f"\n🎯 WIN RATES")
        print(f"   Overall Win Rate: {results['win_rate']:.1%}")
        print(f"   BUY YES Win Rate: {results['buy_yes_win_rate']:.1%}")
        print(f"   BUY NO Win Rate: {results['buy_no_win_rate']:.1%}")

        print(f"\n💰 P&L (${10} position size)")
        print(f"   Total P&L: ${results['total_pnl']:,.2f}")
        print(f"   BUY YES P&L: ${results['buy_yes_pnl']:,.2f}")
        print(f"   BUY NO P&L: ${results['buy_no_pnl']:,.2f}")
        print(f"   Avg P&L per Trade: ${results['avg_pnl_per_trade']:.2f}")

        print(f"\n📈 BY ASSET")
        print(f"   BTC: {results['btc_trades']} trades, {results['btc_win_rate']:.1%} win rate")
        print(f"   ETH: {results['eth_trades']} trades, {results['eth_win_rate']:.1%} win rate")

        print(f"\n📊 BY EDGE SIZE")
        for bucket in ['10-20%', '20-30%', '30-40%', '40%+']:
            if bucket in results['edge_buckets']:
                b = results['edge_buckets'][bucket]
                print(f"   {bucket}: {b['count']} trades, {b['win_rate']:.1%} win rate, ${b['pnl']:,.2f} P&L")

        # Determine if profitable
        print("\n" + "="*70)
        if results['win_rate'] > 0.55:
            print("✅ MODEL IS PROFITABLE (>55% win rate)")
        elif results['win_rate'] > 0.50:
            print("⚠️  MODEL IS MARGINALLY PROFITABLE (50-55% win rate)")
        else:
            print("❌ MODEL IS NOT PROFITABLE (<50% win rate)")
        print("="*70)


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')

    backtester = PriceLevelBacktester()

    results = backtester.run_backtest(
        num_trades=500,
        min_days_to_expiry=30,
        max_days_to_expiry=120,
        edge_threshold=0.10,
        position_size=10.0
    )
