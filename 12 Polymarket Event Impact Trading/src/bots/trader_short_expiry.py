"""
Short-Expiry Polymarket Trading Bot

This bot specializes in short-expiry prediction markets (2 hours to 7 days),
with a focus on crypto markets. It uses a 3-bucket architecture with horizon-specific
strategies and risk management.

Buckets:
- Ultra-short: 2-24 hours (high urgency, time decay dominates)
- Short: 1-3 days (moderate urgency, momentum signals)
- Medium: 3-7 days (lower urgency, fundamental analysis)

Phase 1: Simple rule-based trading (arbitrage, mean reversion, momentum)
Phase 2: ML model integration (GBM with walk-forward validation)
Phase 3: Ensemble with cross-market signals
"""

import json
import logging
import time
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.short_expiry_features import ShortExpiryFeatureExtractor
from core.polymarket_client import PolymarketClient
from core.price_fetcher import PriceFetcher
from core.slippage_estimator import SlippageEstimator
from monitoring.telegram_notifier import TelegramNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/short_expiry.log')
    ]
)
logger = logging.getLogger(__name__)


class ShortExpiryPositionManager:
    """Manage positions for short-expiry trading."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    token_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    size REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    exit_price REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    bucket TEXT NOT NULL,
                    hours_to_expiry_at_entry REAL,
                    edge REAL,
                    confidence REAL,
                    signal_reason TEXT,
                    exit_reason TEXT,
                    status TEXT DEFAULT 'open',
                    features_json TEXT,
                    UNIQUE(market_id, outcome)
                )
            """)
            conn.commit()

    def has_position(self, market_id: str) -> bool:
        """Check if we have an open position for this market."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM positions WHERE market_id = ? AND status = 'open'",
                (market_id,)
            )
            return cursor.fetchone()[0] > 0

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM positions WHERE status = 'open'"
            )
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def count_positions_by_bucket(self, bucket: str) -> int:
        """Count open positions in a specific bucket."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM positions WHERE bucket = ? AND status = 'open'",
                (bucket,)
            )
            return cursor.fetchone()[0]

    def add_position(self, position: Dict):
        """Add a new position."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO positions (
                    market_id, token_id, outcome, entry_price, current_price,
                    size, entry_time, bucket, hours_to_expiry_at_entry,
                    edge, confidence, signal_reason, features_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position['market_id'],
                position['token_id'],
                position['outcome'],
                position['entry_price'],
                position['entry_price'],
                position['size'],
                position['entry_time'],
                position['bucket'],
                position.get('hours_to_expiry', 0),
                position.get('edge', 0),
                position.get('confidence', 0),
                position.get('signal_reason', ''),
                position.get('features_json', '{}')
            ))
            conn.commit()

    def update_position_price(self, market_id: str, outcome: str, current_price: float):
        """Update current price for a position."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE positions
                SET current_price = ?
                WHERE market_id = ? AND outcome = ? AND status = 'open'
            """, (current_price, market_id, outcome))
            conn.commit()

    def update_price_extremes(self, market_id: str, outcome: str, current_price: float):
        """Update highest/lowest prices seen for trailing stop logic."""
        with sqlite3.connect(self.db_path) as conn:
            # Get current extremes
            cursor = conn.execute("""
                SELECT highest_price_seen, lowest_price_seen
                FROM positions
                WHERE market_id = ? AND outcome = ? AND status = 'open'
            """, (market_id, outcome))
            row = cursor.fetchone()

            if not row:
                return

            highest, lowest = row

            # Update if new extreme
            new_highest = max(highest or current_price, current_price)
            new_lowest = min(lowest or current_price, current_price)

            conn.execute("""
                UPDATE positions
                SET highest_price_seen = ?, lowest_price_seen = ?, current_price = ?
                WHERE market_id = ? AND outcome = ? AND status = 'open'
            """, (new_highest, new_lowest, current_price, market_id, outcome))
            conn.commit()

    def close_position(self, market_id: str, outcome: str, exit_price: float,
                      exit_reason: str):
        """Close a position."""
        with sqlite3.connect(self.db_path) as conn:
            # Get entry price
            cursor = conn.execute("""
                SELECT entry_price, size FROM positions
                WHERE market_id = ? AND outcome = ? AND status = 'open'
            """, (market_id, outcome))
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Position not found: {market_id} {outcome}")
                return

            entry_price, size = row
            pnl = (exit_price - entry_price) * size
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            # Update position
            conn.execute("""
                UPDATE positions
                SET exit_price = ?, exit_time = ?, pnl = ?, pnl_pct = ?,
                    exit_reason = ?, status = 'closed'
                WHERE market_id = ? AND outcome = ? AND status = 'open'
            """, (
                exit_price,
                datetime.now(timezone.utc).isoformat(),
                pnl,
                pnl_pct,
                exit_reason,
                market_id,
                outcome
            ))
            conn.commit()

            logger.info(f"Closed position: {market_id} {outcome} | "
                       f"Entry: {entry_price:.4f} | Exit: {exit_price:.4f} | "
                       f"P&L: {pnl:.2f} ({pnl_pct:.2f}%) | Reason: {exit_reason}")


class ShortExpiryRiskManager:
    """Risk management for short-expiry trading."""

    def __init__(self, config: Dict):
        self.config = config
        self.consecutive_losses = 0

    def can_open_position(self, bucket: str, position_manager: ShortExpiryPositionManager) -> bool:
        """Check if we can open a new position in this bucket."""
        # Check total positions
        total_open = len(position_manager.get_open_positions())
        if total_open >= self.config['position_limits']['max_total_positions']:
            return False

        # Check bucket-specific limit
        bucket_count = position_manager.count_positions_by_bucket(bucket)
        if bucket_count >= self.config['position_limits']['max_positions_per_bucket'][bucket]:
            return False

        # Check circuit breaker
        if self.consecutive_losses >= self.config['risk_management']['circuit_breaker_losses']:
            logger.warning(f"Circuit breaker triggered: {self.consecutive_losses} consecutive losses")
            return False

        return True

    def can_execute(self, signal: Dict, balance: float, bucket: str) -> bool:
        """Check if we can execute this signal."""
        # Check minimum edge
        if signal.get('edge', 0) < self.config['risk_management']['min_edge']:
            return False

        # Check minimum confidence
        if signal.get('confidence', 0) < self.config['risk_management']['min_confidence']:
            return False

        # Check balance
        max_size = self.config['position_limits']['max_position_size'][bucket]
        if max_size > balance:
            return False

        return True

    def calculate_position_size(self, edge: float, confidence: float, bucket: str) -> float:
        """Calculate position size based on edge and confidence."""
        max_size = self.config['position_limits']['max_position_size'][bucket]

        # Simple sizing: use max size if high confidence, otherwise scale down
        size_multiplier = min(confidence, 1.0)
        size = max_size * size_multiplier

        # Ensure minimum size
        min_size = self.config['position_limits']['min_position_size']
        return max(size, min_size)

    def should_exit(self, position: Dict, current_price: float, bucket: str) -> Optional[str]:
        """Check if we should exit this position."""
        entry_price = position['entry_price']
        pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

        # Stop-loss
        stop_loss_pct = self.config['risk_management']['stop_loss_pct'][bucket]
        if pnl_pct <= -stop_loss_pct:
            return 'stop_loss'

        # Take-profit
        take_profit_pct = self.config['risk_management']['take_profit_pct'][bucket]
        if pnl_pct >= take_profit_pct:
            return 'take_profit'

        # Pre-expiry exit
        if position['hours_to_expiry_at_entry'] < self.config['risk_management']['pre_expiry_exit_hours']:
            return 'pre_expiry_exit'

        return None

    def update_consecutive_losses(self, is_loss: bool):
        """Update consecutive loss counter."""
        if is_loss:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0


class ShortExpiryTrader:
    """Main trading bot for short-expiry markets."""

    def __init__(self, config_path: str):
        # Load config
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Initialize components
        self.client = PolymarketClient(config=self.config)  # Pass config for WebSocket support
        self.price_fetcher = PriceFetcher(self.client)

        # Initialize WebSocket orderbook manager for real-time price discovery
        logger.info("Initializing WebSocket orderbook manager...")
        self.client.initialize_orderbook_manager()
        self.position_manager = ShortExpiryPositionManager(
            self.config['database']['positions_db']
        )
        self.feature_extractor = ShortExpiryFeatureExtractor()
        self.risk_manager = ShortExpiryRiskManager(self.config)

        # Initialize slippage estimator
        self.slippage_estimator = SlippageEstimator(
            config=self.config.get('slippage_estimation', {})
        )

        # Telegram notifications
        telegram_config = self.config.get('telegram', {})
        self.telegram = TelegramNotifier(
            bot_token=telegram_config.get('bot_token', ''),
            chat_id=telegram_config.get('chat_id', ''),
            enabled=telegram_config.get('enabled', False)
        )

        # Paper trading
        self.paper_trading = self.config['paper_trading']
        self.balance = self._load_balance()

        # Market cache
        self.market_cache = {}
        self.cache_time = {}
        self.cache_ttl = self.config['discovery']['api_cache_ttl_seconds']

        logger.info(f"ShortExpiryTrader initialized | Paper trading: {self.paper_trading} | "
                   f"Balance: ${self.balance:.2f}")

        # Send startup notification
        self.telegram.send_message(
            f"🚀 <b>Short-Expiry Bot Started</b>\n\n"
            f"Paper Trading: {'Yes' if self.paper_trading else 'No'}\n"
            f"Initial Balance: ${self.balance:.2f}\n"
            f"Max Positions: {self.config['position_limits']['max_total_positions']}"
        )

    def _load_balance(self) -> float:
        """Load paper trading balance."""
        balance_file = self.config.get('paper_trading_balance_file',
                                       'data/paper_trading_balance_short_expiry.json')
        try:
            with open(balance_file, 'r') as f:
                data = json.load(f)
                return data['balance']
        except:
            # Initialize with default
            balance = self.config['paper_trading_balance']
            self._save_balance(balance)
            return balance

    def _save_balance(self, balance: float):
        """Save paper trading balance."""
        balance_file = self.config.get('paper_trading_balance_file',
                                       'data/paper_trading_balance_short_expiry.json')
        os.makedirs(os.path.dirname(balance_file), exist_ok=True)
        with open(balance_file, 'w') as f:
            json.dump({'balance': balance, 'updated': datetime.now(timezone.utc).isoformat()}, f)

    def run(self):
        """Main loop."""
        logger.info("Starting main trading loop")

        while True:
            try:
                # Discover markets (3 buckets)
                markets = self.discover_markets()

                logger.info(f"Markets discovered | Ultra-short: {len(markets['ultra_short'])} | "
                           f"Short: {len(markets['short'])} | Medium: {len(markets['medium'])}")

                # Process each bucket
                for bucket, bucket_markets in markets.items():
                    self._process_bucket(bucket, bucket_markets)

                # Check existing positions for exits
                self._check_positions()

                # Wait for next cycle
                time.sleep(self.config['execution']['cycle_interval_seconds'])

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(60)

    def discover_markets(self) -> Dict[str, List[Dict]]:
        """
        Discover markets in 3 buckets using consolidated discovery logic.

        Uses MarketFilter.discover_markets() for consistent discovery across all bots.
        """
        from core.polymarket_client import MarketFilter

        config = self.config['discovery']
        markets = {}
        category = 'crypto' if config.get('crypto_only', False) else None

        # Bucket 1: Ultra-short (0-24h)
        try:
            ultra_short_markets = MarketFilter.discover_markets(
                client=self.client,
                category=category,
                min_hours_to_expiry=config['ultra_short_hours'][0],
                max_hours_to_expiry=config['ultra_short_hours'][1],
                min_volume=config['min_volume']['ultra_short'],
                min_liquidity=config['min_liquidity']['ultra_short'],
                max_pages=3,
                include_crypto_events=True,
                crypto_event_days_ahead=1,
                logger=logger
            )
            markets['ultra_short'] = self._filter_tradeable(ultra_short_markets, 'ultra_short')

            # Register ultra_short markets for WebSocket orderbook tracking
            if markets['ultra_short']:
                logger.info(f"Registering {len(markets['ultra_short'])} ultra_short markets for WebSocket orderbook...")
                for market in markets['ultra_short']:
                    condition_id = market.get('conditionId')
                    question = market.get('question', '')
                    if condition_id:
                        self.client.register_market_for_orderbook(condition_id, question)
        except Exception as e:
            logger.error(f"Error discovering ultra_short markets: {e}", exc_info=True)
            markets['ultra_short'] = []

        # Bucket 2: Short (24-72h)
        try:
            short_markets = MarketFilter.discover_markets(
                client=self.client,
                category=category,
                min_hours_to_expiry=config['short_hours'][0],
                max_hours_to_expiry=config['short_hours'][1],
                min_volume=config['min_volume']['short'],
                min_liquidity=config['min_liquidity']['short'],
                max_pages=3,
                include_crypto_events=True,
                crypto_event_days_ahead=3,
                logger=logger
            )
            markets['short'] = self._filter_tradeable(short_markets, 'short')

            # Register short markets for WebSocket orderbook tracking
            if markets['short']:
                logger.info(f"Registering {len(markets['short'])} short markets for WebSocket orderbook...")
                for market in markets['short']:
                    condition_id = market.get('conditionId')
                    question = market.get('question', '')
                    if condition_id:
                        self.client.register_market_for_orderbook(condition_id, question)
        except Exception as e:
            logger.error(f"Error discovering short markets: {e}", exc_info=True)
            markets['short'] = []

        # Bucket 3: Medium (72-168h = 3-7d)
        try:
            medium_markets = MarketFilter.discover_markets(
                client=self.client,
                category=category,
                min_hours_to_expiry=config['medium_hours'][0],
                max_hours_to_expiry=config['medium_hours'][1],
                min_volume=config['min_volume']['medium'],
                min_liquidity=config['min_liquidity']['medium'],
                max_pages=3,
                include_crypto_events=True,
                crypto_event_days_ahead=7,
                logger=logger
            )
            markets['medium'] = self._filter_tradeable(medium_markets, 'medium')

            # Register medium markets for WebSocket orderbook tracking
            if markets['medium']:
                logger.info(f"Registering {len(markets['medium'])} medium markets for WebSocket orderbook...")
                for market in markets['medium']:
                    condition_id = market.get('conditionId')
                    question = market.get('question', '')
                    if condition_id:
                        self.client.register_market_for_orderbook(condition_id, question)
        except Exception as e:
            logger.error(f"Error discovering medium markets: {e}", exc_info=True)
            markets['medium'] = []

        return markets

    def _get_prices(self, market: Dict) -> Dict[str, float]:
        """Get entry prices (ASK) from CLOB orderbook via PriceFetcher."""
        market_id = market.get('conditionId') or market.get('condition_id')
        if not market_id:
            logger.warning("No condition_id available for price fetching")
            return {'yes': None, 'no': None}

        # Use PriceFetcher to get entry prices (ASK prices from CLOB)
        entry_prices = self.price_fetcher.get_entry_prices(market_id)
        if entry_prices is None:
            logger.warning(f"No entry prices available for {market_id[:16]}...")
            return {'yes': None, 'no': None}

        return {'yes': entry_prices.yes_price, 'no': entry_prices.no_price}

    def _get_spread_pct(self, market: Dict) -> float:
        """Calculate spread percentage."""
        best_bid = market.get('bestBid', 0.45)
        best_ask = market.get('bestAsk', 0.55)

        if isinstance(best_bid, str):
            best_bid = float(best_bid)
        if isinstance(best_ask, str):
            best_ask = float(best_ask)

        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2.0

        return (spread / mid_price * 100) if mid_price > 0 else 0

    def _filter_tradeable(self, markets: List[Dict], bucket: str) -> List[Dict]:
        """
        Apply quality filters using centralized MarketFilter.filter_by_quality().

        Note: Crypto filtering is now handled by MarketFilter.discover_markets().
        This method delegates to the centralized quality filter.
        """
        from core.polymarket_client import MarketFilter

        config = self.config['discovery']

        return MarketFilter.filter_by_quality(
            markets=markets,
            price_fetcher=self.price_fetcher,
            min_price=config['min_price'],
            max_price=config['max_price'],
            max_spread_pct=config['max_spread_pct'][bucket],
            check_last_trade=True,
            logger=logger
        )

    def _process_bucket(self, bucket: str, markets: List[Dict]):
        """Process markets in a bucket."""
        # Check position limits
        if not self.risk_manager.can_open_position(bucket, self.position_manager):
            return

        for market in markets:
            # Skip if already have position
            market_id = market.get('conditionId', '')
            if self.position_manager.has_position(market_id):
                continue

            # Extract features
            features = self.feature_extractor.extract_all_features(market, bucket)

            # Generate signal
            signal = self._generate_signal(features, market, bucket)

            if signal['action'] == 'HOLD':
                continue

            # Risk checks
            if not self.risk_manager.can_execute(signal, self.balance, bucket):
                continue

            # Execute trade (paper trading)
            self._execute_trade(market, signal, bucket, features)

    def _generate_signal(self, features: pd.DataFrame, market: Dict,
                         bucket: str) -> Dict:
        """Generate trading signal using rule-based strategies."""
        market_price = features['market_probability'].iloc[0]
        rules_config = self.config['rules']

        # Rule 1: Arbitrage (YES + NO < 0.98)
        if rules_config['arbitrage']['enabled']:
            yes_price = market_price
            no_price = 1.0 - market_price
            total = yes_price + no_price

            if total < rules_config['arbitrage']['max_total_price']:
                edge = rules_config['arbitrage']['max_total_price'] - total
                if edge >= rules_config['arbitrage']['min_edge']:
                    # Buy cheaper side
                    if yes_price < no_price:
                        return {
                            'action': 'BUY',
                            'outcome': 'YES',
                            'edge': edge,
                            'confidence': 0.95,
                            'reason': 'arbitrage'
                        }
                    else:
                        return {
                            'action': 'BUY',
                            'outcome': 'NO',
                            'edge': edge,
                            'confidence': 0.95,
                            'reason': 'arbitrage'
                        }

        # Rule 2: Wide spread mean reversion (ultra_short only)
        if (bucket == rules_config['mean_reversion']['bucket'] and
            rules_config['mean_reversion']['enabled']):

            spread_pct = features.get('spread_pct', pd.Series([0])).iloc[0]
            volume_24h = features.get('volume_24h', pd.Series([0])).iloc[0]

            if (spread_pct > rules_config['mean_reversion']['min_spread_pct'] and
                volume_24h > rules_config['mean_reversion']['min_volume_24h']):

                if market_price < rules_config['mean_reversion']['price_threshold_low']:
                    return {
                        'action': 'BUY',
                        'outcome': 'YES',
                        'edge': 0.05,
                        'confidence': 0.6,
                        'reason': 'mean_reversion'
                    }
                elif market_price > rules_config['mean_reversion']['price_threshold_high']:
                    return {
                        'action': 'BUY',
                        'outcome': 'NO',
                        'edge': 0.05,
                        'confidence': 0.6,
                        'reason': 'mean_reversion'
                    }

        # Rule 3: Crypto momentum (price change > 2% in 1h)
        if rules_config['momentum']['enabled']:
            price_change_1h = features.get('price_change_1h', pd.Series([0])).iloc[0]
            volume_24h = features.get('volume_24h', pd.Series([0])).iloc[0]

            if (abs(price_change_1h) > rules_config['momentum']['min_price_change_1h'] and
                volume_24h > rules_config['momentum']['min_volume_24h']):

                # Follow momentum
                if price_change_1h > 0:
                    return {
                        'action': 'BUY',
                        'outcome': 'YES',
                        'edge': 0.08,
                        'confidence': 0.65,
                        'reason': 'momentum'
                    }
                else:
                    return {
                        'action': 'BUY',
                        'outcome': 'NO',
                        'edge': 0.08,
                        'confidence': 0.65,
                        'reason': 'momentum'
                    }

        return {'action': 'HOLD', 'reason': 'no_signal'}

    def _execute_trade(self, market: Dict, signal: Dict, bucket: str,
                       features: pd.DataFrame):
        """Execute trade (paper trading)."""
        market_id = market.get('conditionId', '')
        outcome = signal['outcome']

        # Calculate position size
        size = self.risk_manager.calculate_position_size(
            signal['edge'],
            signal['confidence'],
            bucket
        )

        # Get entry price using PriceFetcher
        prices = self._get_prices(market)
        entry_price = prices['yes'] if outcome == 'YES' else prices['no']

        # Validate price is available
        if entry_price is None:
            logger.warning(f"No entry price available for {outcome} - skipping trade")
            return

        # Get token_id for the outcome
        token_ids = self.client.get_token_ids(market_id)
        token_id = token_ids.get('yes_token_id') if outcome == 'YES' else token_ids.get('no_token_id')

        if not token_id:
            logger.warning(f"No token_id found for {outcome} - skipping trade")
            return

        # Estimate slippage
        slippage_config = self.config.get('slippage_estimation', {})
        if slippage_config.get('enabled', True):
            # Get bucket-specific limits
            max_slippage_bps = slippage_config.get('max_slippage_bps', {}).get(bucket, 2000)
            max_slippage_dollars = slippage_config.get('max_slippage_dollars', {}).get(bucket, 20.0)
            warn_threshold_bps = slippage_config.get('warn_threshold_bps', {}).get(bucket, 1000)

            # Override config with bucket-specific limits for estimation
            bucket_slippage_config = slippage_config.copy()
            bucket_slippage_config['max_slippage_bps'] = max_slippage_bps
            bucket_slippage_config['max_slippage_dollars'] = max_slippage_dollars
            bucket_slippage_config['warn_threshold_bps'] = warn_threshold_bps

            # Create temporary estimator with bucket-specific config
            estimator = SlippageEstimator(config=bucket_slippage_config)

            # Get orderbook for slippage estimation
            orderbook = self.client.get_orderbook(token_id)
            if not orderbook:
                logger.warning(f"Could not fetch orderbook for slippage estimation - skipping trade")
                return

            # Get market volume
            market_data = self.client.get_market(market_id)
            market_volume_24h = market_data.get('volume_24h', 0) if market_data else 0

            # Estimate slippage using correct API
            slippage_result = estimator.estimate_slippage(
                order_side='BUY',
                order_size=size,
                orderbook=orderbook,
                quoted_price=entry_price,
                market_volume_24h=market_volume_24h
            )

            if not slippage_result.is_acceptable:
                logger.warning(
                    f"TRADE REJECTED - Slippage | Bucket: {bucket} | "
                    f"Market: {market.get('question', '')[:50]} | "
                    f"Reason: {slippage_result.rejection_reason} | "
                    f"Slippage: {slippage_result.slippage_bps:.0f} bps (${slippage_result.slippage_dollars:.2f}) | "
                    f"Limit: {max_slippage_bps} bps (${max_slippage_dollars})"
                )
                return  # Don't execute trade

            # Log slippage info
            slippage_bps = slippage_result.slippage_bps
            slippage_dollars = slippage_result.slippage_dollars

            if slippage_bps > warn_threshold_bps:
                logger.warning(
                    f"HIGH SLIPPAGE WARNING | Bucket: {bucket} | "
                    f"Slippage: {slippage_bps:.0f} bps (${slippage_dollars:.2f}) | "
                    f"Threshold: {warn_threshold_bps} bps | "
                    f"Market: {market.get('question', '')[:50]}"
                )
            else:
                logger.info(
                    f"Slippage check passed | Bucket: {bucket} | "
                    f"Slippage: {slippage_bps:.0f} bps (${slippage_dollars:.2f})"
                )

        # Paper trading: update balance
        if self.paper_trading:
            self.balance -= size
            self._save_balance(self.balance)

        # Record position
        position = {
            'market_id': market_id,
            'token_id': f"{market_id}_{outcome}",
            'outcome': outcome,
            'entry_price': entry_price,
            'size': size,
            'entry_time': datetime.now(timezone.utc).isoformat(),
            'bucket': bucket,
            'hours_to_expiry': features['hours_to_expiry'].iloc[0],
            'edge': signal['edge'],
            'confidence': signal['confidence'],
            'signal_reason': signal['reason'],
            'features_json': features.to_json()
        }

        self.position_manager.add_position(position)

        logger.info(f"TRADE OPENED | Market: {market.get('question', '')[:50]} | "
                   f"Bucket: {bucket} | Outcome: {outcome} | Size: ${size:.2f} | "
                   f"Entry: {entry_price:.4f} | Reason: {signal['reason']} | "
                   f"Balance: ${self.balance:.2f}")

        # Send Telegram notification
        bucket_emoji = {"ultra_short": "⚡", "short": "🔥", "medium": "📊"}
        self.telegram.send_message(
            f"{bucket_emoji.get(bucket, '📈')} <b>POSITION OPENED - Short Expiry</b>\n\n"
            f"<b>Bucket:</b> {bucket.replace('_', '-').title()}\n"
            f"<b>Side:</b> {outcome}\n"
            f"<b>Size:</b> ${size:.2f}\n"
            f"<b>Entry:</b> {entry_price:.3f}\n"
            f"<b>Edge:</b> {signal['edge']:.1%}\n"
            f"<b>Confidence:</b> {signal['confidence']:.1%}\n"
            f"<b>Strategy:</b> {signal['reason'].replace('_', ' ').title()}\n\n"
            f"<i>{market.get('question', '')[:80]}</i>\n\n"
            f"💰 Balance: ${self.balance:.2f}"
        )

    def _check_positions(self):
        """Check open positions for exit conditions."""
        positions = self.position_manager.get_open_positions()

        for pos in positions:
            market_id = pos['market_id']
            outcome = pos['outcome']
            entry_price = pos['entry_price']
            entry_time_str = pos['entry_time']
            hours_to_expiry = pos.get('hours_to_expiry_at_entry', 0)
            bucket = pos.get('bucket', 'unknown')

            logger.debug(f"Checking position: {market_id[:16]}... | "
                        f"Outcome: {outcome} | Entry: {entry_price:.4f}")

            # Check if market has expired based on entry time + hours_to_expiry
            if hours_to_expiry > 0:
                entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                expiry_time = entry_time + timedelta(hours=hours_to_expiry)
                now = datetime.now(timezone.utc)

                if now >= expiry_time:
                    logger.info(f"Position expired: {market_id[:16]}... | "
                               f"Expired {(now - expiry_time).total_seconds() / 3600:.1f}h ago")
                    # Close at entry price (we don't know final outcome)
                    self.position_manager.close_position(
                        market_id, outcome, entry_price, 'expiry_time'
                    )
                    continue

            # Fetch current market data
            try:
                market = self.client.get_market(market_id)
                if not market:
                    logger.warning(f"Could not fetch market data for {market_id[:16]}...")
                    continue

                # Check if market is closed
                if market.get('closed', False) or not market.get('active', True):
                    logger.info(f"Market closed: {market_id[:16]}...")
                    # Close at entry price (we don't know final outcome)
                    self.position_manager.close_position(
                        market_id, outcome, entry_price, 'market_closed'
                    )
                    continue

                # Get current price using PriceFetcher (exit prices - BID)
                exit_prices = self.price_fetcher.get_exit_prices(market_id)
                if exit_prices is None:
                    logger.warning(f"Could not get exit prices for {market_id[:16]}... {outcome}")
                    continue

                # Get price for the specific outcome
                current_price = exit_prices.get_outcome_price(outcome)

                # Check exit conditions (stop-loss, take-profit, trailing stop)
                exit_reason = self.risk_manager.should_exit(pos, current_price, bucket)

                if exit_reason:
                    logger.info(f"Exit signal: {market_id[:16]}... | {outcome} | "
                               f"{entry_price:.4f} → {current_price:.4f} | {exit_reason}")
                    self.position_manager.close_position(
                        market_id, outcome, current_price, exit_reason
                    )
                else:
                    # Update highest/lowest prices seen (for trailing stop)
                    self.position_manager.update_price_extremes(
                        market_id, outcome, current_price
                    )

            except Exception as e:
                logger.error(f"Error checking position {market_id[:16]}...: {e}")


def main():
    """Entry point."""
    config_path = 'config/config_short_expiry.json'

    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)

    # Initialize trader
    trader = ShortExpiryTrader(config_path)

    # Run
    trader.run()


if __name__ == '__main__':
    main()
