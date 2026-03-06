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
import signal
import time
import sys
import os
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.short_expiry_features import ShortExpiryFeatureExtractor
from core.polymarket_client import PolymarketClient
from core.price_fetcher import PriceFetcher
from core.slippage_estimator import SlippageEstimator
from core.trade_executor import TradeExecutor, TradeRequest
from core.exposure_manager import ExposureManager
from core.position_sizer import PositionSizer
from core.position_manager_v2 import PositionManager
from monitoring.telegram_notifier import TelegramNotifier
from utils.price_tracker import PriceTracker
from ml.snapshot_collector import MarketSnapshotCollector

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


class ShortExpiryRiskManager:
    """Risk management for short-expiry trading."""

    def __init__(self, config: Dict):
        self.config = config
        self.consecutive_losses = 0
        self.circuit_breaker_triggered_at: Optional[datetime] = None

    @staticmethod
    def calculate_hours_remaining(entry_time: datetime, hours_to_expiry_at_entry: float) -> float:
        """Calculate current hours remaining until expiry.

        Args:
            entry_time: When position was opened (UTC datetime)
            hours_to_expiry_at_entry: Hours to expiry when position was opened

        Returns:
            Current hours remaining (can be negative if expired)
        """
        if hours_to_expiry_at_entry is None or hours_to_expiry_at_entry <= 0:
            return float('inf')  # No expiry data, treat as distant

        expiry_time = entry_time + timedelta(hours=hours_to_expiry_at_entry)
        now = datetime.now(timezone.utc)
        remaining = (expiry_time - now).total_seconds() / 3600
        return remaining

    def _get_static_tp_sl(self, bucket: str) -> Tuple[float, float]:
        """Get static TP/SL thresholds from config."""
        tp_pct = self.config['risk_management']['take_profit_pct'][bucket]
        sl_pct = self.config['risk_management']['stop_loss_pct'][bucket]
        return tp_pct, sl_pct

    def get_dynamic_tp_sl(self, hours_remaining: float, bucket: str) -> Tuple[float, float]:
        """Get TP/SL thresholds based on time remaining.

        Args:
            hours_remaining: Current hours until expiry
            bucket: Time bucket (ultra_short, short, medium)

        Returns:
            (take_profit_pct, stop_loss_pct)
        """
        decay_config = self.config.get('time_decay_tp_sl', {})

        # If disabled, return static thresholds
        if not decay_config.get('enabled', False):
            return self._get_static_tp_sl(bucket)

        # Get bucket-specific thresholds
        thresholds = decay_config.get(bucket, [])
        if not thresholds:
            # Fallback to static if bucket not configured
            return self._get_static_tp_sl(bucket)

        # Find matching threshold based on hours_remaining
        # Thresholds should be sorted by min_hours descending
        for threshold in thresholds:
            if hours_remaining >= threshold['min_hours']:
                tp_pct = threshold['tp_pct'] if decay_config.get('apply_to_tp', True) else self._get_static_tp_sl(bucket)[0]
                sl_pct = threshold['sl_pct'] if decay_config.get('apply_to_sl', True) else self._get_static_tp_sl(bucket)[1]
                return tp_pct, sl_pct

        # If below all thresholds, use most aggressive (last one)
        if thresholds:
            last = thresholds[-1]
            return last['tp_pct'], last['sl_pct']

        # Fallback to static
        return self._get_static_tp_sl(bucket)

    def can_open_position(self, bucket: str, position_manager: PositionManager) -> bool:
        """Check if we can open a new position in this bucket."""
        # Check total positions
        total_open = len(position_manager.get_open_positions())
        if total_open >= self.config['position_limits']['max_total_positions']:
            return False

        # Check bucket-specific limit
        bucket_count = position_manager.count_positions_by_metadata('bucket', bucket)
        if bucket_count >= self.config['position_limits']['max_positions_per_bucket'][bucket]:
            return False

        # Check circuit breaker with cooldown
        cb_losses = self.config['risk_management']['circuit_breaker_losses']
        if self.consecutive_losses >= cb_losses:
            cooldown_hours = self.config['risk_management'].get('circuit_breaker_cooldown_hours', 4.0)

            # Record when it first triggered
            if self.circuit_breaker_triggered_at is None:
                self.circuit_breaker_triggered_at = datetime.now(timezone.utc)
                logger.warning(
                    f"Circuit breaker triggered: {self.consecutive_losses} consecutive losses. "
                    f"Pausing for {cooldown_hours}h."
                )

            # Check if cooldown has elapsed
            elapsed_hours = (datetime.now(timezone.utc) - self.circuit_breaker_triggered_at).total_seconds() / 3600
            if elapsed_hours >= cooldown_hours:
                logger.info(
                    f"Circuit breaker cooldown elapsed ({elapsed_hours:.1f}h >= {cooldown_hours}h). "
                    f"Resetting consecutive losses and resuming trading."
                )
                self.consecutive_losses = 0
                self.circuit_breaker_triggered_at = None
            else:
                remaining = cooldown_hours - elapsed_hours
                logger.warning(
                    f"Circuit breaker active: {self.consecutive_losses} losses. "
                    f"Cooldown: {elapsed_hours:.1f}h / {cooldown_hours}h elapsed "
                    f"({remaining:.1f}h remaining)."
                )
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
        min_size = self.config['position_limits']['min_position_size']
        if balance < min_size:
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
        """Check if we should exit this position.

        Args:
            position: Position dict with entry_time, hours_to_expiry_at_entry, entry_price
            current_price: Current token price
            bucket: Time bucket (ultra_short, short, medium)

        Returns:
            Exit reason string or None
        """
        entry_price = position['entry_price']
        pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

        # Calculate current hours remaining (FIX: use current time, not entry time)
        hours_remaining = self.calculate_hours_remaining(
            position.get('entry_time', datetime.now(timezone.utc)),
            position.get('hours_to_expiry_at_entry')
        )

        # Get dynamic TP/SL thresholds based on time remaining
        take_profit_pct, stop_loss_pct = self.get_dynamic_tp_sl(hours_remaining, bucket)

        # Cap TP target at $1.00 (Polymarket max price)
        if entry_price > 0:
            tp_target = entry_price * (1 + take_profit_pct / 100)
            if tp_target > 1.0:
                take_profit_pct = ((1.0 - entry_price) / entry_price) * 100
                # Ensure at least a small TP margin (0.5%) to avoid spurious triggers
                take_profit_pct = max(take_profit_pct, 0.5)

        # Log dynamic thresholds for monitoring
        logger.debug(f"Dynamic TP/SL for {bucket}: hours_remaining={hours_remaining:.1f}h, "
                    f"tp={take_profit_pct:.1f}%, sl={stop_loss_pct}%")

        # Stop-loss
        if pnl_pct <= -stop_loss_pct:
            return 'stop_loss'

        # Take-profit
        if pnl_pct >= take_profit_pct:
            return 'take_profit'

        # Pre-expiry exit (FIX: check current hours remaining, not hours_to_expiry_at_entry)
        pre_expiry_config = self.config['risk_management']['pre_expiry_exit_hours']
        if isinstance(pre_expiry_config, dict):
            pre_expiry_hours = pre_expiry_config.get(bucket, 1.0)
        else:
            pre_expiry_hours = pre_expiry_config  # Legacy scalar config
        if hours_remaining < pre_expiry_hours:
            logger.info(f"Pre-expiry exit triggered: {hours_remaining:.1f}h < {pre_expiry_hours}h")
            return 'pre_expiry_exit'

        return None

    def update_consecutive_losses(self, is_loss: bool):
        """Update consecutive loss counter."""
        if is_loss:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            self.circuit_breaker_triggered_at = None  # Reset cooldown timer on a win


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

        # Initialize enhanced PositionManager V2 (with analytics fields)
        self.position_manager = PositionManager(
            self.config['database']['positions_db']
        )
        self.feature_extractor = ShortExpiryFeatureExtractor()
        self.risk_manager = ShortExpiryRiskManager(self.config)

        # Initialize exposure manager (portfolio concentration limits)
        self.exposure_manager = ExposureManager(self.config.get('exposure_limits', {}))
        logger.info("✓ Exposure manager initialized")

        # Initialize unified position sizer
        self.position_sizer = PositionSizer(self.config.get('position_sizing', {}))
        logger.info("✓ Position sizer initialized")

        # Initialize price tracker for historical price data (enables momentum signals)
        self.price_tracker = PriceTracker(self.config['database']['tracking_db'])
        logger.info("PriceTracker initialized for momentum feature extraction")

        # Initialize trade executor (centralized validation pipeline)
        self.trade_executor = TradeExecutor(
            client=self.client,
            position_manager=self.position_manager,
            config=self.config,
            paper_trading=self.config.get('paper_trading', True)
        )
        logger.info("✓ Trade executor initialized")

        # Initialize slippage estimator
        self.slippage_estimator = SlippageEstimator(
            config=self.config.get('slippage_estimation', {})
        )

        # Telegram notifications — prefer env vars over config file values (Fix L2)
        telegram_config = self.config.get('telegram', {})
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', telegram_config.get('bot_token', ''))
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', telegram_config.get('chat_id', ''))
        self.telegram = TelegramNotifier(
            bot_token=bot_token,
            chat_id=chat_id,
            enabled=telegram_config.get('enabled', False)
        )

        # Initialize snapshot collector (centralized training data collection with alerts)
        self.snapshot_collector = MarketSnapshotCollector(
            db_path='data/market_snapshots.db',
            telegram=self.telegram if telegram_config.get('enabled', False) else None
        )
        logger.info("✓ Snapshot collector initialized")

        # Paper trading
        self.paper_trading = self.config['paper_trading']
        self.balance = self._load_balance()

        # Market cooldown tracking (prevent over-trading same markets)
        self.market_cooldowns = {}  # market_id -> last_close_time

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
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
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
        self.is_running = True

        while self.is_running:
            try:
                # Check minimum balance before trading
                min_balance = self.config['risk_management'].get('min_trading_balance', 50.0)
                if self.balance < min_balance:
                    logger.warning(f"⚠️ Balance too low (${self.balance:.2f} < ${min_balance:.2f}) - pausing new trades")
                    self.telegram.send_message(
                        f"⚠️ <b>Trading Paused - Low Balance</b>\n\n"
                        f"Current Balance: ${self.balance:.2f}\n"
                        f"Minimum Required: ${min_balance:.2f}\n\n"
                        f"Only monitoring existing positions.\n"
                        f"Add funds to resume trading."
                    )
                    # Still check existing positions, but skip market discovery
                    self._check_positions()
                    time.sleep(self.config['execution']['cycle_interval_seconds'])
                    continue

                # Discover markets (3 buckets)
                markets = self.discover_markets()

                logger.info(f"Markets discovered | Ultra-short: {len(markets['ultra_short'])} | "
                           f"Short: {len(markets['short'])} | Medium: {len(markets['medium'])}")

                # Process each bucket
                for bucket, bucket_markets in markets.items():
                    self._process_bucket(bucket, bucket_markets)

                # Check existing positions for exits
                self._check_positions()

                # Fix M3: purge expired cooldowns to prevent memory leak
                max_cooldown_hours = max(
                    self.config['risk_management']['market_cooldown_hours'].values()
                )
                cooldown_cutoff = datetime.now(timezone.utc) - timedelta(hours=max_cooldown_hours)
                self.market_cooldowns = {
                    k: v for k, v in self.market_cooldowns.items() if v > cooldown_cutoff
                }

                # Wait for next cycle
                time.sleep(self.config['execution']['cycle_interval_seconds'])

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                tb = traceback.format_exc()
                logger.error(f"Error in main loop: {e}\n{tb}")
                self.telegram.notify_error(
                    f"⚠️ Main loop error:\n{str(e)[:200]}\n\nTraceback:\n{tb[-500:]}",
                    bot_name="Short-Expiry Trader"
                )
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
            self.telegram.notify_error(
                f"⚠️ Ultra-short market discovery error:\n{str(e)[:200]}",
                bot_name="Short-Expiry Trader"
            )
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
            self.telegram.notify_error(
                f"⚠️ Short market discovery error:\n{str(e)[:200]}",
                bot_name="Short-Expiry Trader"
            )
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
            self.telegram.notify_error(
                f"⚠️ Medium market discovery error:\n{str(e)[:200]}",
                bot_name="Short-Expiry Trader"
            )
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
        """Calculate spread percentage using PriceFetcher (ARCH-001 compliant)."""
        market_id = market.get('conditionId') or market.get('condition_id')
        if not market_id:
            return 0.0

        # Use PriceFetcher for entry (ASK) and exit (BID) prices
        entry_prices = self.price_fetcher.get_entry_prices(market_id)
        exit_prices = self.price_fetcher.get_exit_prices(market_id)

        if entry_prices is None or exit_prices is None:
            return 0.0

        best_ask = entry_prices.yes_price or 0.0
        best_bid = exit_prices.yes_price or 0.0

        if best_bid <= 0 or best_ask <= 0:
            return 0.0

        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2.0

        return (spread / mid_price * 100) if mid_price > 0 else 0.0

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
            check_last_trade=config.get('require_last_trade_price', False),
            logger=logger
        )

    def _process_bucket(self, bucket: str, markets: List[Dict]):
        """Process markets in a bucket."""
        # Check position limits
        if not self.risk_manager.can_open_position(bucket, self.position_manager):
            return

        for market in markets:
            market_id = market.get('conditionId', '')
            if not market_id:
                continue

            # Track current price for momentum features
            # Use PriceFetcher to get real-time CLOB prices (WebSocket/REST)
            try:
                # Get entry prices (ASK) from CLOB - this uses WebSocket orderbook if available
                entry_prices = self.price_fetcher.get_entry_prices(market_id)
                if entry_prices and entry_prices.yes_price is not None:
                    # Track YES price as the market price proxy
                    current_price = entry_prices.yes_price
                    self.price_tracker.track_price(market_id, current_price)
            except Exception as e:
                logger.warning(f"Could not track price for {market_id[:16]}...: {e}")

            # Get price history for momentum calculations (last 24 hours)
            price_history = self.price_tracker.get_price_history(market_id, hours=24)

            # Extract features WITH price history (enables momentum signals)
            features = self.feature_extractor.extract_all_features(
                market,
                bucket,
                price_history=price_history
            )

            # Skip markets with no features (e.g. missing end_date — Fix C4)
            if features.empty:
                logger.debug(f"No features for {market_id[:16]}, skipping market")
                continue

            # Generate signal
            signal = self._generate_signal(features, market, bucket)

            # Log snapshot for training data collection (regardless of whether trade is executed)
            try:
                # Get prices from PriceFetcher
                entry_prices = self.price_fetcher.get_entry_prices(market_id)
                if entry_prices:
                    yes_price = entry_prices.yes_price
                    no_price = entry_prices.no_price
                else:
                    # Fallback to features if PriceFetcher fails (ARCH-008: no synthetic NO price)
                    yes_price = features['market_probability'].iloc[0]
                    no_price = 0.0  # Unknown - don't synthesize from YES

                # Calculate spread
                spread = yes_price + no_price - 1.0

                # Parse expiry date
                expiry_str = market.get('endDate') or market.get('end_date')
                expiry_date = None
                days_to_expiry = features.get('days_to_expiry', pd.Series([None])).iloc[0]
                if expiry_str:
                    try:
                        expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                        if days_to_expiry is None:
                            days_to_expiry = (expiry_date - datetime.now(timezone.utc)).total_seconds() / 86400
                    except (ValueError, TypeError):
                        pass

                # Convert features DataFrame to dict for storage
                features_dict = features.iloc[0].to_dict() if not features.empty else {}

                self.snapshot_collector.log_snapshot(
                    market_id=market_id,
                    bot_type='short_expiry',
                    features=features_dict,
                    prediction={
                        'model_prob': 0.5,  # Rule-based for now, will use ML model prob later
                        'confidence': signal.get('confidence', 0.0),
                        'edge': signal.get('edge', 0.0),
                        'predicted_outcome': signal.get('outcome', 'HOLD')
                    },
                    market_data={
                        'question': market.get('question', ''),
                        'asset': market.get('asset'),
                        'expiry_date': expiry_str,
                        'days_to_expiry': days_to_expiry,
                        'market_type': market.get('market_type'),
                        'condition_id': market_id,
                        'token_id': market.get('clobTokenIds')
                    },
                    prices={
                        'yes': yes_price,
                        'no': no_price,
                        'spread': spread
                    },
                    position_opened=False,  # Will update in _execute_trade if trade happens
                    rejection_reason=None if signal['action'] != 'HOLD' else signal.get('reason', 'no_signal')
                )
            except Exception as e:
                logger.warning(f"Failed to log snapshot for {market_id[:16]}...: {e}")

            if signal['action'] == 'HOLD':
                continue

            # Skip if already have position on this outcome
            outcome = signal.get('outcome', 'YES')
            if self.position_manager.has_position(market_id, outcome):
                continue

            # Check market cooldown (prevent re-entry too soon after close)
            cooldown_hours = self.config.get('risk_management', {}).get('market_cooldown_hours', {}).get(bucket, 2.0)
            if market_id in self.market_cooldowns:
                last_close = self.market_cooldowns[market_id]
                elapsed_hours = (datetime.now(timezone.utc) - last_close).total_seconds() / 3600
                if elapsed_hours < cooldown_hours:
                    logger.debug(f"Market in cooldown: {market_id[:16]}... (elapsed: {elapsed_hours:.1f}h < {cooldown_hours}h)")
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
            # Fix C5: arbitrage check needs BID prices (what market pays out), not ASK
            market_id = market.get('condition_id', market.get('conditionId', ''))
            arb_prices = self.price_fetcher.get_exit_prices(market_id) if market_id else None
            if arb_prices:
                yes_price = arb_prices.yes_price
                no_price = arb_prices.no_price
                if yes_price is None or no_price is None:
                    logger.debug(f"No BID prices for arbitrage check on {market_id[:16]}, skipping")
                    yes_price = market_price
                    no_price = market_price
            else:
                yes_price = market_price
                no_price = market_price  # Safe fallback: total = 2*price, never < 0.98 for valid prices
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

        # Calculate position size using unified PositionSizer
        orderbook = self.client.get_orderbook(market_id) if market_id else None
        size = self.position_sizer.calculate(
            edge=signal['edge'],
            confidence=signal['confidence'],
            balance=self.balance,
            orderbook=orderbook,
            bucket=bucket
        )
        if size == 0:
            logger.info("Position size too small after sizing — skipping")
            return

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

        # Paper trading: validate balance before TradeExecutor
        if self.paper_trading:
            # RISK-007: Check sufficient balance before opening position
            if self.balance < size:
                logger.warning(
                    f"⚠️ Insufficient balance to open position | "
                    f"Required: ${size:.2f} | Available: ${self.balance:.2f} | "
                    f"Market: {market.get('question', '')[:50]}"
                )
                # Record telemetry for rejected trade
                from monitoring.telemetry import record_trade_rejected
                record_trade_rejected(
                    reason='insufficient_balance',
                    required=size,
                    available=self.balance,
                    market_id=market_id
                )
                return  # Skip this trade

        # Extract asset from market question for dashboard display
        question = market.get('question', '')
        asset = 'CRYPTO'  # Default for short-expiry markets

        # Try to infer specific asset from question
        question_lower = question.lower()
        if 'gold' in question_lower or 'gc' in question_lower or 'xau' in question_lower:
            asset = 'GOLD'
        elif 'bitcoin' in question_lower or 'btc' in question_lower:
            asset = 'BTC'
        elif 'ethereum' in question_lower or 'eth' in question_lower:
            asset = 'ETH'
        elif 'solana' in question_lower or 'sol' in question_lower:
            asset = 'SOL'

        # Check exposure limits (portfolio concentration)
        existing_positions = self.position_manager.get_open_positions()
        total_capital = self.balance + sum(p.get('size', 0) for p in existing_positions)
        new_position = {
            'asset': asset,
            'size': size,
            'outcome': outcome,
            'strike_price': None,  # Short-expiry markets don't have strike prices
        }
        can_open_exp, exp_reason, exp_warnings = self.exposure_manager.can_open_position(
            new_position, existing_positions, total_capital
        )
        if not can_open_exp:
            logger.warning(f"  ⚠️ BLOCKED by exposure limits: {exp_reason}")
            return

        # RISK-001: Get bucket-specific stop-loss and take-profit from config
        risk_config = self.config.get('risk_management', {})
        sl_pct_map = risk_config.get('stop_loss_pct', {})
        tp_pct_map = risk_config.get('take_profit_pct', {})
        sl_pct = sl_pct_map.get(bucket, 15)  # Default 15% if bucket not found
        tp_pct = tp_pct_map.get(bucket, 50)  # Default 50% if bucket not found

        # Create TradeRequest
        trade_request = TradeRequest(
            market_id=market_id,
            token_id=token_id,
            outcome=outcome,
            entry_price=entry_price,
            position_size=size,
            question=question,
            asset=asset,
            edge=signal['edge'],
            confidence=signal['confidence'],
            signal_reason=signal['reason'],
            stop_loss_pct=sl_pct,
            take_profit_pct=tp_pct,
            metadata={
                'hours_to_expiry': features['hours_to_expiry'].iloc[0],
                'bucket': bucket,
                'features_json': features.to_json()
            }
        )

        # Execute trade via TradeExecutor (validates slippage, price, and saves position)
        # Note: Use bucket-specific slippage config if needed
        trade_result = self.trade_executor.execute_trade(trade_request, order_side='BUY')

        if not trade_result.success:
            logger.warning(f"❌ Trade rejected by TradeExecutor: {trade_result.rejection_reason}")
            return

        # Deduct from paper balance after successful trade
        if self.paper_trading:
            self.balance -= size
            self._save_balance(self.balance)

        logger.info(f"TRADE OPENED | Market: {market.get('question', '')[:50]} | "
                   f"Bucket: {bucket} | Outcome: {outcome} | Size: ${size:.2f} | "
                   f"Entry: {trade_result.entry_price:.4f} | Reason: {signal['reason']} | "
                   f"Balance: ${self.balance:.2f}")

        # Send Telegram notification
        bucket_emoji = {"ultra_short": "⚡", "short": "🔥", "medium": "📊"}
        self.telegram.send_message(
            f"{bucket_emoji.get(bucket, '📈')} <b>POSITION OPENED - Short Expiry</b>\n\n"
            f"<b>Bucket:</b> {bucket.replace('_', '-').title()}\n"
            f"<b>Side:</b> {outcome}\n"
            f"<b>Size:</b> ${size:.2f}\n"
            f"<b>Entry:</b> {trade_result.entry_price:.3f}\n"
            f"<b>Edge:</b> {signal['edge']:.1%}\n"
            f"<b>Confidence:</b> {signal['confidence']:.1%}\n"
            f"<b>Strategy:</b> {signal['reason'].replace('_', ' ').title()}\n\n"
            f"<i>{market.get('question', '')[:80]}</i>\n\n"
            f"💰 Balance: ${self.balance:.2f}"
        )

    def _get_resolved_exit_price_from_market(self, market: Dict, outcome: str, fallback_price: float) -> float:
        """Get exit price from a resolved market's token data.

        Checks the market's tokens array for resolution info.
        Returns 1.0 for winning outcome, 0.0 for losing, or fallback if unknown.
        """
        tokens = market.get('tokens', [])
        for token in tokens:
            token_outcome = token.get('outcome', '').upper()
            if token_outcome == outcome.upper():
                winner = token.get('winner', None)
                if winner is True:
                    logger.info(f"Market resolved: {outcome} WON -> exit at 1.0")
                    return 1.0
                elif winner is False:
                    logger.info(f"Market resolved: {outcome} LOST -> exit at 0.0")
                    return 0.0
        # Unknown resolution — fall back to entry price
        logger.info(f"Market resolution unknown for {outcome} -> exit at entry price {fallback_price:.4f}")
        return fallback_price

    def _get_resolved_exit_price(self, market_id: str, outcome: str, fallback_price: float) -> float:
        """Get exit price for a resolved/expired market by fetching market data.

        Fetches market from API and checks for resolution.
        Returns 1.0 for winning outcome, 0.0 for losing, or fallback if unknown.
        """
        try:
            market = self.client.get_market(market_id)
            if market:
                return self._get_resolved_exit_price_from_market(market, outcome, fallback_price)
        except Exception as e:
            logger.warning(f"Could not fetch market for resolution check: {e}")
        return fallback_price

    def _execute_close(self, pos: Dict, exit_reason: str):
        """Force close a position at current BID price (fallback to entry price).

        Used for error-recovery closes: missing_expiry_data, invalid_position_size.
        """
        market_id = pos.get('market_id', '')
        outcome = pos.get('outcome', 'YES')
        entry_price = pos.get('entry_price', 0) or 0
        position_size = pos.get('size', 0) or 0
        bucket = pos.get('bucket', 'short') or 'short'

        # Try to get current BID price; fall back to entry price
        current_price = entry_price
        try:
            exit_prices = self.price_fetcher.get_exit_prices(market_id)
            if exit_prices is not None:
                price = exit_prices.get_outcome_price(outcome)
                if price is not None:
                    current_price = price
        except Exception as e:
            logger.warning(f"Could not fetch exit price for forced close {market_id[:16]}: {e}")

        if entry_price > 0 and position_size > 0:
            tokens = position_size / entry_price
            payout = tokens * current_price
            pnl = payout - position_size
            pnl_pct = (pnl / position_size) * 100
        else:
            payout = 0.0
            pnl = -position_size
            pnl_pct = -100.0

        close_result = self.trade_executor.execute_close_trade(
            market_id=market_id,
            outcome=outcome,
            token_id=pos.get('token_id', ''),
            exit_price=current_price,
            position_size=position_size,
            exit_reason=exit_reason,
            question=pos.get('question', ''),
            bucket=bucket
        )

        if not close_result.success:
            logger.warning(f"Force close rejected by TradeExecutor: {close_result.rejection_reason}")
            return

        self.market_cooldowns[market_id] = datetime.now(timezone.utc)
        if self.paper_trading and payout > 0:
            self.balance += payout
            self._save_balance(self.balance)
        self.risk_manager.update_consecutive_losses(is_loss=(pnl < 0))
        logger.info(f"Force closed {market_id[:16]} ({exit_reason}) | P&L: ${pnl:+.2f}")

    def _check_positions(self):
        """Check open positions for exit conditions."""
        positions = self.position_manager.get_open_positions()

        for pos in positions:
            market_id = pos['market_id']
            outcome = pos['outcome']
            entry_price = pos['entry_price']

            # Fix C1: use .get() to avoid KeyError if entry_time is missing
            entry_time = pos.get('entry_time')
            if entry_time is None:
                logger.warning(f"Position {market_id[:16]} missing entry_time, skipping")
                continue

            # Fix C3: handle missing hours_to_expiry — force close rather than stick open forever
            hours_to_expiry = pos.get('hours_to_expiry_at_entry')
            if hours_to_expiry is None:
                logger.warning(f"Position {market_id[:16]} has no expiry data — forcing close")
                self._execute_close(pos, 'missing_expiry_data')
                continue
            hours_to_expiry = float(hours_to_expiry)

            # Fix H1: validate position_size early — invalid size produces wrong P&L
            position_size = pos.get('size')
            if not position_size or position_size <= 0:
                logger.error(f"Position {market_id[:16]} has invalid size={position_size}, forcing close")
                self._execute_close(pos, 'invalid_position_size')
                continue

            # Get bucket from column (V2 stores it as a column, not in metadata)
            bucket = pos.get('bucket')
            if not bucket:
                # Fallback to metadata for old positions; Fix M1: log warning on fallback
                metadata = pos.get('metadata', {})
                if isinstance(metadata, dict):
                    bucket = metadata.get('bucket', 'short')
                else:
                    bucket = 'short'
                logger.warning(f"Position {market_id[:16]} missing bucket column, fell back to '{bucket}'")

            # Fix pandas DataFrame dict format {'0': 'value'} -> 'value'
            if isinstance(bucket, dict) and '0' in bucket:
                bucket = bucket['0']

            # Ensure bucket is a string
            if not isinstance(bucket, str):
                logger.warning(f"Invalid bucket type {type(bucket)} for position {market_id[:16]}..., defaulting to 'short'")
                bucket = 'short'

            logger.debug(f"Checking position: {market_id[:16]}... | "
                        f"Outcome: {outcome} | Entry: {entry_price:.4f}")

            # Check if market has expired based on entry time + hours_to_expiry
            if hours_to_expiry > 0:
                expiry_time = entry_time + timedelta(hours=hours_to_expiry)
                now = datetime.now(timezone.utc)

                if now >= expiry_time:
                    logger.info(f"Position expired: {market_id[:16]}... | "
                               f"Expired {(now - expiry_time).total_seconds() / 3600:.1f}h ago")

                    # Try to get actual resolution price from market data
                    exit_price = self._get_resolved_exit_price(market_id, outcome, entry_price)
                    position_size = pos.get('size', 0)

                    if entry_price > 0:
                        tokens_held = position_size / entry_price
                        payout = tokens_held * exit_price
                        pnl = payout - position_size
                        pnl_pct = (pnl / position_size) * 100
                    else:
                        payout = 0
                        pnl = -position_size
                        pnl_pct = -100

                    # Close via TradeExecutor (validates slippage for SELL order)
                    close_result = self.trade_executor.execute_close_trade(
                        market_id=market_id,
                        outcome=outcome,
                        token_id=pos.get('token_id', ''),
                        exit_price=exit_price,
                        position_size=position_size,
                        exit_reason='expiry_time',
                        question=pos.get('question', ''),
                        bucket=bucket
                    )

                    if not close_result.success:
                        logger.warning(f"❌ Position close rejected by TradeExecutor: {close_result.rejection_reason}")
                        continue

                    # Record market cooldown to prevent immediate re-entry
                    self.market_cooldowns[market_id] = datetime.now(timezone.utc)

                    # Update balance (add payout from resolved position)
                    if self.paper_trading:
                        self.balance += payout
                        self._save_balance(self.balance)

                    # Send Telegram notification
                    self.telegram.notify_position_closed(
                        market_id=market_id,
                        asset=pos.get('metadata', {}).get('asset', 'CRYPTO') if isinstance(pos.get('metadata'), dict) else 'CRYPTO',
                        outcome=outcome,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        position_size=position_size,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason='expiry_time',
                        question=pos.get('question', ''),
                        bot_name="Short-Expiry Trader"
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

                    # Try to get actual resolution price from market data
                    exit_price = self._get_resolved_exit_price_from_market(market, outcome, entry_price)
                    position_size = pos.get('size', 0)

                    if entry_price > 0:
                        tokens_held = position_size / entry_price
                        payout = tokens_held * exit_price
                        pnl = payout - position_size
                        pnl_pct = (pnl / position_size) * 100
                    else:
                        payout = 0
                        pnl = -position_size
                        pnl_pct = -100

                    # Close via TradeExecutor (validates slippage for SELL order)
                    close_result = self.trade_executor.execute_close_trade(
                        market_id=market_id,
                        outcome=outcome,
                        token_id=pos.get('token_id', ''),
                        exit_price=exit_price,
                        position_size=position_size,
                        exit_reason='market_closed',
                        question=pos.get('question', ''),
                        bucket=bucket
                    )

                    if not close_result.success:
                        logger.warning(f"❌ Position close rejected by TradeExecutor: {close_result.rejection_reason}")
                        continue

                    # Record market cooldown to prevent immediate re-entry
                    self.market_cooldowns[market_id] = datetime.now(timezone.utc)

                    # Update balance (add payout from resolved position)
                    if self.paper_trading:
                        self.balance += payout
                        self._save_balance(self.balance)

                    # Send Telegram notification
                    self.telegram.notify_position_closed(
                        market_id=market_id,
                        asset=pos.get('metadata', {}).get('asset', 'CRYPTO') if isinstance(pos.get('metadata'), dict) else 'CRYPTO',
                        outcome=outcome,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        position_size=position_size,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason='market_closed',
                        question=market.get('question'),
                        bot_name="Short-Expiry Trader"
                    )
                    continue

                # Get current price using PriceFetcher (exit prices - BID)
                exit_prices = self.price_fetcher.get_exit_prices(market_id)
                if exit_prices is None:
                    logger.warning(f"Could not get exit prices for {market_id[:16]}... {outcome}")
                    continue

                # Get price for the specific outcome
                current_price = exit_prices.get_outcome_price(outcome)

                # Fix C2: guard against None price before calling should_exit()
                if current_price is None:
                    logger.warning(f"No current price for {market_id[:16]} outcome={outcome}, skipping exit check")
                    continue

                # Check exit conditions (stop-loss, take-profit, trailing stop)
                exit_reason = self.risk_manager.should_exit(pos, current_price, bucket)

                if exit_reason:
                    logger.info(f"Exit signal: {market_id[:16]}... | {outcome} | "
                               f"{entry_price:.4f} → {current_price:.4f} | {exit_reason}")

                    # Calculate P&L
                    position_size = pos.get('size', 0)
                    if entry_price > 0:
                        tokens = position_size / entry_price
                        payout = tokens * current_price
                        pnl = payout - position_size
                        pnl_pct = (pnl / position_size) * 100
                    else:
                        payout = 0
                        pnl = -position_size
                        pnl_pct = -100

                    # Close via TradeExecutor (validates slippage for SELL order)
                    close_result = self.trade_executor.execute_close_trade(
                        market_id=market_id,
                        outcome=outcome,
                        token_id=pos.get('token_id', ''),
                        exit_price=current_price,
                        position_size=position_size,
                        exit_reason=exit_reason,
                        question=pos.get('question', ''),
                        bucket=bucket
                    )

                    if not close_result.success:
                        logger.warning(f"❌ Position close rejected by TradeExecutor: {close_result.rejection_reason}")
                        continue

                    # Record market cooldown to prevent immediate re-entry
                    self.market_cooldowns[market_id] = datetime.now(timezone.utc)

                    # Update balance (add payout)
                    if self.paper_trading:
                        self.balance += payout
                        self._save_balance(self.balance)

                    # Update risk manager (for circuit breaker)
                    was_active = self.risk_manager.consecutive_losses >= self.risk_manager.config['risk_management']['circuit_breaker_losses']
                    self.risk_manager.update_consecutive_losses(is_loss=(pnl < 0))
                    is_now_active = self.risk_manager.consecutive_losses >= self.risk_manager.config['risk_management']['circuit_breaker_losses']

                    # Check if circuit breaker was just triggered
                    if not was_active and is_now_active:
                        self.telegram.notify_circuit_breaker(
                            consecutive_losses=self.risk_manager.consecutive_losses,
                            cooldown_hours=4.0,  # Default cooldown
                            bot_name="Short-Expiry Trader"
                        )

                    # Send Telegram notification
                    self.telegram.notify_position_closed(
                        market_id=market_id,
                        asset=pos.get('metadata', {}).get('asset', 'CRYPTO') if isinstance(pos.get('metadata'), dict) else 'CRYPTO',
                        outcome=outcome,
                        entry_price=entry_price,
                        exit_price=current_price,
                        position_size=position_size,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason=exit_reason,
                        question=market.get('question'),
                        bot_name="Short-Expiry Trader"
                    )
                else:
                    # Update highest/lowest prices seen (for trailing stop)
                    self.position_manager.update_price_extremes(
                        market_id, outcome, current_price
                    )

            except Exception as e:
                logger.error(f"Error checking position {market_id[:16]}...: {e}", exc_info=True)
                self.telegram.notify_error(
                    f"⚠️ Position check error:\nMarket: {market_id[:16]}...\nError: {str(e)[:150]}",
                    bot_name="Short-Expiry Trader"
                )


    def _log_exposure_report(self):
        """Log portfolio exposure report."""
        positions = self.position_manager.get_open_positions()
        total_capital = self.balance + sum(p.get('size', 0) for p in positions)

        if not positions:
            return

        report = self.exposure_manager.format_exposure_report(positions, total_capital)
        for line in report.split('\n'):
            logger.info(line)


def main():
    """Entry point."""
    config_path = 'config/config_short_expiry.json'

    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)

    # Initialize trader
    trader = ShortExpiryTrader(config_path)

    def handle_sigterm(signum, frame):
        logger.info("Received SIGTERM, shutting down gracefully...")
        trader.is_running = False

    signal.signal(signal.SIGTERM, handle_sigterm)

    # Run
    trader.run()


if __name__ == '__main__':
    main()
