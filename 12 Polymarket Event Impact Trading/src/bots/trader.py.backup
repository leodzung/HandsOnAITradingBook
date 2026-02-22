"""
Live Trading Bot
Executes trades on Polymarket based on model predictions.
"""

import time
import logging
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import numpy as np
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.polymarket_client import PolymarketClient, MarketFilter
from core.price_fetcher import PriceFetcher
from utils.event_detector import EventDetector
from features.feature_extractor import FeatureEngineering
from models.models_v2 import PriceMovementPredictor, TradingSignalGenerator, ModelPerformanceTracker
from utils.price_tracker import PriceTracker
from core.position_manager_v2 import PositionManager
from monitoring.telegram_notifier import TelegramNotifier
from ml.snapshot_collector import MarketSnapshotCollector


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RiskManager:
    """Manages risk for live trading."""

    def __init__(self, max_position_size: float = 100,
                 max_positions: int = 10,
                 max_daily_loss: float = 500,
                 max_market_exposure: float = 0.5,
                 circuit_breaker_losses: int = 3,
                 circuit_breaker_cooldown_hours: float = 4.0):
        """
        Initialize risk manager.

        Args:
            max_position_size: Maximum size per position ($)
            max_positions: Maximum concurrent positions
            max_daily_loss: Maximum loss per day ($)
            max_market_exposure: Maximum exposure to single market (0-1)
            circuit_breaker_losses: Number of consecutive losses to trigger circuit breaker
            circuit_breaker_cooldown_hours: Hours to wait before resuming after circuit breaker
        """
        self.max_position_size = max_position_size
        self.max_positions = max_positions
        self.max_daily_loss = max_daily_loss
        self.max_market_exposure = max_market_exposure

        # Circuit breaker settings
        self.circuit_breaker_losses = circuit_breaker_losses
        self.circuit_breaker_cooldown_hours = circuit_breaker_cooldown_hours
        self.consecutive_losses = 0
        self.circuit_breaker_active = False
        self.circuit_breaker_triggered_at: Optional[datetime] = None

        self.daily_pnl = 0.0
        self.daily_reset_time = datetime.now(timezone.utc).date()
        self.active_positions = {}

    def reset_daily_counters(self):
        """Reset daily counters."""
        today = datetime.now(timezone.utc).date()
        if today > self.daily_reset_time:
            self.daily_pnl = 0.0
            self.daily_reset_time = today

    def check_circuit_breaker(self) -> tuple[bool, str]:
        """
        Check if circuit breaker should be active or can be reset.

        Returns:
            Tuple of (is_active, reason)
        """
        if not self.circuit_breaker_active:
            return False, ""

        # Check if cooldown period has elapsed
        if self.circuit_breaker_triggered_at:
            elapsed_hours = (datetime.now(timezone.utc) - self.circuit_breaker_triggered_at).total_seconds() / 3600
            if elapsed_hours >= self.circuit_breaker_cooldown_hours:
                # Reset circuit breaker after cooldown
                self.circuit_breaker_active = False
                self.consecutive_losses = 0
                self.circuit_breaker_triggered_at = None
                logger.info(f"Circuit breaker RESET after {elapsed_hours:.1f}h cooldown. Trading resumed.")
                return False, ""
            else:
                remaining = self.circuit_breaker_cooldown_hours - elapsed_hours
                return True, f"Circuit breaker active ({self.consecutive_losses} consecutive losses). Resume in {remaining:.1f}h"

        return True, f"Circuit breaker active ({self.consecutive_losses} consecutive losses)"

    def can_open_position(self, position_size: float) -> tuple[bool, str]:
        """
        Check if we can open a new position.

        Args:
            position_size: Size of proposed position

        Returns:
            Tuple of (can_open, reason)
        """
        self.reset_daily_counters()

        # Check circuit breaker first
        cb_active, cb_reason = self.check_circuit_breaker()
        if cb_active:
            return False, cb_reason

        # Check position count
        if len(self.active_positions) >= self.max_positions:
            return False, f"Max positions ({self.max_positions}) reached"

        # Check position size
        if position_size > self.max_position_size:
            return False, f"Position size {position_size} > max {self.max_position_size}"

        # Check daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            return False, f"Daily loss limit ({self.max_daily_loss}) reached"

        return True, "OK"

    def add_position(self, market_id: str, size: float):
        """Add a position to tracking."""
        self.active_positions[market_id] = {
            'size': size,
            'entry_time': datetime.now(timezone.utc)
        }

    def remove_position(self, market_id: str, pnl: float):
        """Remove a position and update PnL, tracking consecutive losses for circuit breaker."""
        if market_id in self.active_positions:
            del self.active_positions[market_id]

        self.daily_pnl += pnl

        # Track consecutive losses for circuit breaker
        if pnl < 0:
            self.consecutive_losses += 1
            logger.info(f"Position closed. PnL: ${pnl:.2f}, Daily PnL: ${self.daily_pnl:.2f}, "
                       f"Consecutive losses: {self.consecutive_losses}/{self.circuit_breaker_losses}")

            # Trigger circuit breaker if threshold reached
            if self.consecutive_losses >= self.circuit_breaker_losses:
                self.circuit_breaker_active = True
                self.circuit_breaker_triggered_at = datetime.now(timezone.utc)
                logger.warning(f"⚠️ CIRCUIT BREAKER TRIGGERED: {self.consecutive_losses} consecutive losses. "
                             f"Trading paused for {self.circuit_breaker_cooldown_hours}h.")
        else:
            # Reset consecutive losses on a win
            if self.consecutive_losses > 0:
                logger.info(f"Win resets consecutive loss counter: {self.consecutive_losses} → 0")
            self.consecutive_losses = 0
            logger.info(f"Position closed. PnL: ${pnl:.2f}, Daily PnL: ${self.daily_pnl:.2f}")

    def get_position_size(self, confidence: float, balance: float) -> float:
        """
        Calculate position size based on confidence and balance.

        Args:
            confidence: Model confidence (0-1)
            balance: Available balance

        Returns:
            Position size
        """
        # Kelly criterion-inspired sizing
        base_size = min(self.max_position_size, balance * 0.1)
        confidence_multiplier = (confidence - 0.5) * 2  # Scale 0.5-1.0 to 0-1

        size = base_size * confidence_multiplier
        return min(size, self.max_position_size)


class PolymarketTrader:
    """Main trading bot."""

    def __init__(self, config: Dict):
        """
        Initialize trader.

        Args:
            config: Configuration dictionary
        """
        self.config = config

        # Initialize components
        self.client = PolymarketClient(
            api_key=config.get('polymarket_api_key'),
            api_secret=config.get('polymarket_api_secret'),
            private_key=config.get('polymarket_private_key'),
            config=config
        )

        # Initialize centralized price fetcher
        self.price_fetcher = PriceFetcher(self.client)
        logger.info("✓ Price fetcher initialized")

        # Initialize WebSocket orderbook manager for real-time price discovery
        logger.info("Initializing WebSocket orderbook manager...")
        self.client.initialize_orderbook_manager()
        logger.info("✓ WebSocket orderbook manager initialized")

        self.event_detector = EventDetector(
            news_api_key=config.get('news_api_key'),
            twitter_bearer_token=config.get('twitter_bearer_token'),
            rss_feeds=config.get('rss_feeds', []),
            gdelt_db_path=config.get('gdelt_db_path', 'data/gdelt_news.db'),
            use_embeddings=config.get('use_embeddings', True),
            embedding_model=config.get('embedding_model', 'intfloat/e5-large-v2'),
            embedding_threshold=config.get('embedding_threshold', 0.5)
        )

        self.feature_engineering = FeatureEngineering()

        # Load model
        self.model = PriceMovementPredictor(
            model_type=config.get('model_type', 'random_forest')
        )
        model_path = config.get('model_path')
        if model_path:
            try:
                self.model.load(model_path)
                logger.info(f"Loaded model from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                # Note: Telegram not initialized yet, so we can't send alert here

        self.signal_generator = TradingSignalGenerator(
            model=self.model,
            min_confidence=config.get('min_confidence', 0.65),
            min_expected_return=config.get('min_expected_return', 0.03)
        )

        self.risk_manager = RiskManager(
            max_position_size=config.get('max_position_size', 100),
            max_positions=config.get('max_positions', 10),
            max_daily_loss=config.get('max_daily_loss', 500),
            circuit_breaker_losses=config.get('circuit_breaker_losses', 3),
            circuit_breaker_cooldown_hours=config.get('circuit_breaker_cooldown_hours', 4.0)
        )

        self.performance_tracker = ModelPerformanceTracker()

        # Initialize price tracker
        self.price_tracker = PriceTracker()
        logger.info("✓ Price tracker initialized")

        # Initialize position manager (with persistence!)
        self.position_manager = PositionManager(db_path='data/positions.db')
        logger.info("✓ Position manager initialized")

        # Paper trading balance
        self.paper_balance_file = 'data/paper_trading_balance.json'
        self.paper_balance = self._load_paper_balance()
        logger.info(f"✓ Paper trading balance: ${self.paper_balance:.2f}")

        # Trading state
        self.is_running = False
        self.open_orders = {}
        self.position_timers = {}

        # Load positions from database on startup
        self._restore_positions()

        # Initialize Telegram notifier
        telegram_config = config.get('telegram', {})
        self.telegram = TelegramNotifier(
            bot_token=telegram_config.get('bot_token', ''),
            chat_id=telegram_config.get('chat_id', ''),
            enabled=telegram_config.get('enabled', False)
        )
        if telegram_config.get('enabled', False):
            logger.info("✓ Telegram notifications enabled")

        # Initialize snapshot collector (centralized training data collection with alerts)
        self.snapshot_collector = MarketSnapshotCollector(
            db_path='data/market_snapshots.db',
            telegram=self.telegram if telegram_config.get('enabled', False) else None
        )
        logger.info("✓ Snapshot collector initialized")

        logger.info(f"✓ Trading state initialized ({len(self.position_timers)} open positions)")

    def start(self):
        """Start the trading bot."""
        logger.info("Starting Polymarket trading bot...")
        self.is_running = True

        # Main trading loop
        while self.is_running:
            try:
                self.trading_cycle()
                time.sleep(self.config.get('cycle_interval_seconds', 300))  # 5 minutes

            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.stop()
            except Exception as e:
                logger.error(f"Error in trading cycle: {e}", exc_info=True)
                self.telegram.notify_error(
                    f"⚠️ Trading cycle error:\n{str(e)[:200]}",
                    bot_name="Event Trader"
                )
                time.sleep(60)

    def stop(self):
        """Stop the trading bot."""
        logger.info("Stopping trading bot...")
        self.is_running = False

        # Close all positions
        self.close_all_positions()

        logger.info("Trading bot stopped")

    def trading_cycle(self):
        """Execute one trading cycle."""
        logger.info("=== Starting trading cycle ===")

        # 1. Get active markets
        markets = self.get_tradeable_markets()
        logger.info(f"Found {len(markets)} tradeable markets")

        # 2. Detect recent events
        events = self.event_detector.get_all_recent_events(
            lookback_hours=self.config.get('event_lookback_hours', 1)
        )
        logger.info(f"Found {len(events)} recent events")

        # 2.5 Filter events by category if configured
        category_filter = self.config.get('market_category_filter')
        if category_filter == 'crypto':
            events = self.event_detector.matcher.filter_crypto_events(events)
            logger.info(f"Filtered to {len(events)} crypto-related events")

        # 3. Match events to markets (reuse events already fetched)
        matched_events = self.event_detector.matcher.match_events_to_markets(
            events, markets
        )
        logger.info(f"Matched events to {len(matched_events)} markets")

        # 4. Generate signals and execute
        signals_processed = 0
        for market_id, market_events in matched_events.items():
            if not market_events:
                continue

            # Get market details (note: API uses camelCase)
            market = next((m for m in markets if m.get('conditionId') == market_id), None)
            if not market:
                continue

            # Process most recent event
            event = market_events[0]

            try:
                self.process_signal(event, market)
                signals_processed += 1
            except Exception as e:
                logger.error(f"Error processing signal for {market_id}: {e}", exc_info=True)
                self.telegram.notify_error(
                    f"⚠️ Signal processing error:\nMarket: {market.get('question', '')[:60]}\nError: {str(e)[:150]}",
                    bot_name="Event Trader"
                )

        logger.info(f"Processed {signals_processed} signals")

        # 5. Manage existing positions
        self.manage_positions()

        # 6. Log performance
        self.log_performance()

    def _load_paper_balance(self) -> float:
        """
        Load paper trading balance from file.

        Returns:
            Current paper balance
        """
        import os

        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)

        if os.path.exists(self.paper_balance_file):
            try:
                with open(self.paper_balance_file, 'r') as f:
                    data = json.load(f)
                    return data.get('balance', 1000.0)
            except Exception as e:
                logger.warning(f"Could not load paper balance: {e}, using default")

        # Default starting balance
        initial_balance = self.config.get('paper_trading_balance', 1000.0)
        self._save_paper_balance(initial_balance)
        return initial_balance

    def _save_paper_balance(self, balance: float):
        """
        Save paper trading balance to file.

        Args:
            balance: Current balance to save
        """
        try:
            with open(self.paper_balance_file, 'w') as f:
                json.dump({
                    'balance': balance,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save paper balance: {e}")

    def _update_paper_balance(self, amount: float, reason: str = ""):
        """
        Update paper trading balance.

        Args:
            amount: Amount to add (positive) or subtract (negative)
            reason: Reason for the change
        """
        old_balance = self.paper_balance
        self.paper_balance += amount
        self._save_paper_balance(self.paper_balance)

        logger.info(f"Paper balance: ${old_balance:.2f} → ${self.paper_balance:.2f} "
                   f"({amount:+.2f}) - {reason}")

    def _restore_positions(self):
        """
        Restore open positions from database on startup.
        """
        positions = self.position_manager.get_open_positions()

        for pos in positions:
            market_id = pos['market_id']
            # Handle both V1 'side' and V2 'outcome' fields
            outcome = pos.get('outcome', pos.get('side', 'YES'))

            # Restore to position_timers (in-memory tracking)
            self.position_timers[market_id] = {
                'entry_time': pos['entry_time'],
                'entry_price': pos['entry_price'],
                'side': outcome,  # Keep 'side' key for backward compatibility with rest of code
                'size': pos['size']
            }

            # Restore to risk manager
            self.risk_manager.add_position(market_id, pos['size'])

        if positions:
            total_size = sum(p['size'] for p in positions)
            logger.info(f"✓ Restored {len(positions)} positions (${total_size:.2f} deployed)")

    def _transform_features_for_model(self, features: Dict, market: Dict) -> Dict:
        """
        Transform extracted features to match the model's expected 24-feature format.

        The model (retrained_model_v2.pkl) expects these 24 features:
        - trade_count, market_volume
        - price_start, price_end, price_mean, price_std, price_min, price_max, price_range, price_change_pct
        - momentum_5, sma_5, momentum_10, sma_10, volatility_10
        - volume_total, volume_mean, volume_std
        - is_crypto, is_politics, is_sports
        - news_sentiment_mean, news_sentiment_std, news_count

        Args:
            features: Features from feature_engineering.create_training_sample()
            market: Market dictionary

        Returns:
            Dictionary with model-compatible features
        """
        # Get current price using PriceFetcher (entry prices)
        condition_id = market.get('conditionId') or market.get('condition_id')
        if not condition_id:
            logger.warning("No condition_id available for price fetching")
            return {}  # Return empty features - cannot proceed without price

        entry_prices = self.price_fetcher.get_entry_prices(condition_id)
        if entry_prices is None:
            logger.warning("No entry prices available from CLOB")
            return {}  # Return empty features - cannot proceed without price

        current_price = entry_prices.yes_price

        # Get market volume - try multiple sources
        market_volume = features.get('market_volume', 0.0)
        if market_volume == 0:
            market_volume = float(market.get('volume', 0) or 0)

        # Extract price history features from features dict
        prices = features.get('prices', [current_price])
        if not prices:
            prices = [current_price]

        price_array = np.array(prices) if prices else np.array([current_price])

        # Calculate price statistics
        price_start = price_array[0] if len(price_array) > 0 else current_price
        price_end = price_array[-1] if len(price_array) > 0 else current_price
        price_mean = float(np.mean(price_array))
        price_std = float(np.std(price_array)) if len(price_array) > 1 else 0.0
        price_min = float(np.min(price_array))
        price_max = float(np.max(price_array))
        price_range = price_max - price_min
        price_change_pct = ((price_end - price_start) / price_start * 100) if price_start > 0 else 0.0

        # Calculate momentum and SMA
        def calc_sma(arr, window):
            if len(arr) >= window:
                return float(np.mean(arr[-window:]))
            return float(np.mean(arr))

        sma_5 = calc_sma(price_array, 5)
        sma_10 = calc_sma(price_array, 10)
        momentum_5 = (price_end - sma_5) / sma_5 * 100 if sma_5 > 0 else 0.0
        momentum_10 = (price_end - sma_10) / sma_10 * 100 if sma_10 > 0 else 0.0

        # Calculate volatility
        if len(price_array) >= 10:
            returns = np.diff(price_array[-10:]) / price_array[-11:-1]
            volatility_10 = float(np.std(returns)) if len(returns) > 0 else 0.0
        else:
            volatility_10 = price_std

        # Volume features
        volumes = features.get('volumes', [])
        volume_array = np.array(volumes) if volumes else np.array([market_volume])
        volume_total = float(np.sum(volume_array)) if len(volume_array) > 0 else market_volume
        volume_mean = float(np.mean(volume_array)) if len(volume_array) > 0 else market_volume
        volume_std = float(np.std(volume_array)) if len(volume_array) > 1 else 0.0

        # Category detection from market question
        question = market.get('question', '').lower()
        is_crypto = 1 if any(kw in question for kw in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana', 'doge']) else 0
        is_politics = 1 if any(kw in question for kw in ['trump', 'biden', 'election', 'president', 'congress', 'vote', 'republican', 'democrat']) else 0
        is_sports = 1 if any(kw in question for kw in ['nfl', 'nba', 'mlb', 'super bowl', 'championship', 'game', 'win', 'team']) else 0

        # News sentiment features
        news_sentiment_mean = features.get('event_sentiment_score', 0.0)
        news_sentiment_std = features.get('event_sentiment_magnitude', 0.0)
        news_count = features.get('event_keyword_count', 1)  # At least 1 for the current event

        # Trade count (estimate from volume if not available)
        trade_count = features.get('trade_count', max(1, int(volume_total / 10)))

        model_features = {
            'trade_count': trade_count,
            'market_volume': market_volume,
            'price_start': float(price_start),
            'price_end': float(price_end),
            'price_mean': price_mean,
            'price_std': price_std,
            'price_min': float(price_min),
            'price_max': float(price_max),
            'price_range': price_range,
            'price_change_pct': price_change_pct,
            'momentum_5': momentum_5,
            'sma_5': sma_5,
            'momentum_10': momentum_10,
            'sma_10': sma_10,
            'volatility_10': volatility_10,
            'volume_total': volume_total,
            'volume_mean': volume_mean,
            'volume_std': volume_std,
            'is_crypto': is_crypto,
            'is_politics': is_politics,
            'is_sports': is_sports,
            'news_sentiment_mean': news_sentiment_mean,
            'news_sentiment_std': news_sentiment_std,
            'news_count': news_count,
        }

        return model_features

    def get_tradeable_markets(self) -> List[Dict]:
        """Get markets that meet trading criteria."""
        import time as time_module

        # Get active markets with API-level filtering (more efficient than client-side)
        markets = []
        max_pages = self.config.get('max_market_pages', 50)  # Up to 5000 markets

        # Calculate end date range based on expiry config
        from datetime import datetime, timedelta
        now = datetime.now(timezone.utc)
        min_hours = self.config.get('min_hours_to_expiry', 2)
        max_hours = self.config.get('max_hours_to_expiry', 8760)

        end_date_min = (now + timedelta(hours=min_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date_max = (now + timedelta(hours=max_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Apply filters at API level for efficiency
        min_volume = self.config.get('min_market_volume', 1000)

        # Time the pagination
        pagination_start = time_module.time()
        for page in range(max_pages):
            offset = page * 100
            batch = self.client.get_markets(
                limit=100,
                offset=offset,
                active=True,
                end_date_min=end_date_min,
                end_date_max=end_date_max,
                volume_num_min=min_volume
            )
            if not batch:
                break
            markets.extend(batch)
        pagination_duration = time_module.time() - pagination_start

        logger.info(f"Retrieved {len(markets)} filtered markets from API in {pagination_duration:.2f}s "
                   f"({len(markets)/pagination_duration:.1f} markets/sec) "
                   f"(volume>=${min_volume}, expiry: {min_hours}h-{max_hours}h)")

        # IMPORTANT: Also fetch markets from known crypto events (these don't appear in /markets)
        # Use consolidated discovery logic from MarketFilter
        if self.config.get('market_category_filter') == 'crypto':
            event_markets = []
            event_start = time_module.time()

            # Get all crypto event slugs (both long-term and daily)
            event_slugs = MarketFilter.get_all_crypto_event_slugs(days_ahead=7)
            logger.info(f"Fetching markets from {len(event_slugs)} crypto events...")

            for slug in event_slugs:
                try:
                    event_batch = self.client.get_markets_from_event(slug)
                    # Defensive: Filter out closed markets even though client should do this
                    event_batch = [m for m in event_batch if not m.get('closed', False)]
                    if event_batch:
                        event_markets.extend(event_batch)
                        logger.debug(f"  + {len(event_batch)} active markets from event '{slug}'")
                except Exception as e:
                    logger.debug(f"Event {slug} not found or error: {e}")
            event_duration = time_module.time() - event_start

            # De-duplicate by conditionId
            seen_ids = {m.get('conditionId') for m in markets if m.get('conditionId')}
            new_markets = [m for m in event_markets if m.get('conditionId') not in seen_ids]
            markets.extend(new_markets)
            logger.info(f"Added {len(new_markets)} unique active event markets in {event_duration:.2f}s (closed filtered)")

        logger.info(f"Total markets after API filtering: {len(markets)}")

        # Apply remaining client-side filters
        # (active, volume, and expiry already filtered at API level)
        markets = MarketFilter.filter_active_only(markets)

        # Apply category filter if configured (cannot be done at API level)
        category_filter = self.config.get('market_category_filter')
        if category_filter == 'crypto':
            markets = MarketFilter.filter_crypto_markets(markets)
            logger.info(f"Filtered to {len(markets)} crypto markets after category filter")

        # Apply quality filters (spread, price range, trade activity)
        quality_config = self.config.get('quality_filters', {})
        if quality_config.get('enabled', True):
            markets = MarketFilter.filter_by_quality(
                markets=markets,
                price_fetcher=self.price_fetcher,
                min_price=quality_config.get('min_price', 0.05),
                max_price=quality_config.get('max_price', 0.95),
                max_spread_pct=quality_config.get('max_spread_pct', 10.0),
                check_last_trade=quality_config.get('check_last_trade', True),
                logger=logger
            )
            logger.info(f"Filtered to {len(markets)} markets after quality filter")

        logger.info(f"Final market count: {len(markets)}")

        # Register markets for WebSocket orderbook tracking
        if markets:
            logger.info(f"Registering {len(markets)} markets for WebSocket orderbook tracking...")
            for market in markets:
                condition_id = market.get('conditionId')
                question = market.get('question', '')
                if condition_id:
                    self.client.register_market_for_orderbook(condition_id, question)

        return markets

    def process_signal(self, event, market: Dict):
        """
        Process a trading signal.

        Args:
            event: Event object
            market: Market dictionary
        """
        market_id = market.get('conditionId')
        logger.info(f"Processing signal for market: {market.get('question', '')[:60]}")
        # Get token_id from clobTokenIds (first token for binary markets)
        # Note: clobTokenIds is a JSON string, need to parse it
        token_ids_str = market.get('clobTokenIds', '[]')
        try:
            token_ids = json.loads(token_ids_str) if isinstance(token_ids_str, str) else token_ids_str
            token_id = token_ids[0] if token_ids else None
        except (json.JSONDecodeError, IndexError):
            token_id = None

        if not token_id:
            logger.warning(f"No token_id for market {market_id}")
            return

        # Get current prices using PriceFetcher (entry prices)
        condition_id = market.get('conditionId') or market.get('condition_id')
        if not condition_id:
            logger.warning(f"No condition_id for market - skipping")
            return

        entry_prices = self.price_fetcher.get_entry_prices(condition_id)
        if entry_prices is None:
            logger.warning(f"No entry prices available from CLOB - skipping")
            return

        yes_price = entry_prices.yes_price
        no_price = entry_prices.no_price
        current_price = yes_price  # Use YES price for general operations

        # Get orderbook for features
        orderbook = self.client.get_orderbook(token_id)

        # Get historical prices
        historical_prices = self.client.get_historical_prices(
            token_id,
            start_time=datetime.now(timezone.utc) - timedelta(hours=24)
        )

        # Extract features
        features = self.feature_engineering.create_training_sample(
            event=event,
            market=market,
            historical_prices=historical_prices,
            orderbook=orderbook,
            use_transformers=self.config.get('use_transformers', False)
        )

        # Transform features to match training format
        model_features = self._transform_features_for_model(features, market)

        # Check if feature transformation failed (returns empty dict when price fetching fails)
        if not model_features:
            logger.warning(f"Feature transformation failed for {market.get('question', '')[:60]} - skipping signal")
            return

        features_df = pd.DataFrame([model_features])

        # Track this event-market pair for later labeling
        try:
            self.price_tracker.track_event(
                event=event,
                market=market,
                entry_price=current_price,
                features=features
            )
            logger.info(f"  → Tracking price movement for: {market.get('question')[:40]}...")
        except Exception as e:
            logger.error(f"Error tracking event: {e}")

        # Generate signal
        signal = self.signal_generator.generate_signal(features_df, current_price)

        # Map BUY/SELL to YES/NO for clarity
        outcome = 'YES' if signal['action'] == 'BUY' else 'NO' if signal['action'] == 'SELL' else None
        action_display = f"BUY {outcome}" if outcome else signal['action']

        logger.info(f"Signal for {market.get('question', 'Unknown')[:50]}: "
                   f"{action_display} (confidence: {signal.get('confidence', 0):.2%})")

        # Log snapshot for training data collection (regardless of whether trade is executed)
        try:
            # Calculate spread
            spread = yes_price + no_price - 1.0

            # Parse expiry date
            expiry_str = market.get('endDate') or market.get('end_date')
            expiry_date = None
            days_to_expiry = None
            if expiry_str:
                try:
                    expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    days_to_expiry = (expiry_date - datetime.now(timezone.utc)).total_seconds() / 86400
                except:
                    pass

            self.snapshot_collector.log_snapshot(
                market_id=market_id,
                bot_type='event',
                features=model_features,
                prediction={
                    'model_prob': signal.get('probability', 0.5),
                    'confidence': signal.get('confidence', 0.0),
                    'edge': signal.get('edge', 0.0),
                    'predicted_outcome': outcome if outcome else 'HOLD'
                },
                market_data={
                    'question': market.get('question', ''),
                    'asset': market.get('asset'),
                    'expiry_date': expiry_str,
                    'days_to_expiry': days_to_expiry,
                    'market_type': market.get('market_type'),
                    'condition_id': market_id,
                    'token_id': token_id
                },
                prices={
                    'yes': yes_price,
                    'no': no_price,
                    'spread': spread
                },
                position_opened=False,  # Will update in execute_trade if trade happens
                rejection_reason=None  # Will be filled if trade blocked
            )
        except Exception as e:
            logger.warning(f"Failed to log snapshot: {e}")

        # Execute trade if signal is actionable
        if signal['action'] in ['BUY', 'SELL']:
            self.execute_trade(market_id, token_id, signal, current_price, outcome,
                             yes_price, no_price, market)

    def execute_trade(self, market_id: str, token_id: str,
                     signal: Dict, current_price: float, outcome: str = None,
                     yes_price: float = None, no_price: float = None, market: Dict = None):
        """
        Execute a trade with slippage estimation.

        Args:
            market_id: Market ID
            token_id: Token ID
            signal: Trading signal
            current_price: Current price
            outcome: 'YES' or 'NO' - which outcome we're betting on
            yes_price: Current YES price
            no_price: Current NO price
            market: Market dictionary
        """
        # Determine outcome if not provided
        if outcome is None:
            outcome = 'YES' if signal['action'] == 'BUY' else 'NO'

        # Check if already have position
        if market_id in self.risk_manager.active_positions:
            logger.info(f"Already have position in {market_id}")
            return

        # Get balance (use paper balance in paper trading mode)
        if self.config.get('paper_trading', True):
            balance = self.paper_balance
        else:
            balance = self.client.get_balance()

        if balance is None or balance < 10:
            logger.warning(f"Insufficient balance: ${balance}")
            return

        # Calculate position size
        position_size = self.risk_manager.get_position_size(
            signal.get('confidence', 0.5),
            balance
        )

        # Check risk limits
        can_open, reason = self.risk_manager.can_open_position(position_size)
        if not can_open:
            logger.warning(f"Cannot open position: {reason}")
            return

        # Determine quoted price and token_id based on outcome
        if yes_price is None or no_price is None:
            logger.warning("Missing YES/NO prices for slippage estimation")
            quoted_price = current_price
        else:
            quoted_price = yes_price if outcome == 'YES' else no_price

        # Get orderbook for slippage estimation
        orderbook = self.client.get_orderbook(token_id)

        # Estimate slippage
        from slippage_estimator import SlippageEstimator

        estimator = SlippageEstimator(config=self.config.get('slippage_estimation', {}))

        # Get market volume
        market_volume_24h = market.get('volume', 0) if market else 0

        slippage_est = estimator.estimate_slippage(
            order_side='BUY',  # Always BUY for opening positions
            order_size=position_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=market_volume_24h
        )

        # Check if slippage is acceptable
        if not slippage_est.is_acceptable:
            logger.warning(f"Trade REJECTED - {slippage_est.rejection_reason}")
            return

        # Log slippage estimate
        logger.info(f"Slippage estimate: ${slippage_est.slippage_dollars:.3f} "
                   f"({slippage_est.slippage_bps:.0f} bps), "
                   f"levels: {slippage_est.levels_consumed}")

        # Log warnings if any
        for warning in slippage_est.warnings:
            logger.warning(f"Slippage warning: {warning}")

        # Use adjusted execution price
        entry_price = slippage_est.expected_execution_price

        # Place order
        if self.config.get('paper_trading', True):
            logger.info(f"[PAPER TRADE] BUY {outcome} ${position_size:.2f} "
                       f"at ${entry_price:.3f}")

            # Deduct from paper balance
            self._update_paper_balance(-position_size, f"Open BUY {outcome} position")

            # Extract question and asset from market for dashboard display
            question = market.get('question', '') if market else ''
            asset = 'EVENT'  # Default for event-based markets

            # Try to infer asset from question for better dashboard categorization
            if market and question:
                question_lower = question.lower()
                if 'gold' in question_lower or 'gc' in question_lower or 'xau' in question_lower:
                    asset = 'GOLD'
                elif 'bitcoin' in question_lower or 'btc' in question_lower:
                    asset = 'BTC'
                elif 'ethereum' in question_lower or 'eth' in question_lower:
                    asset = 'ETH'
                elif any(keyword in question_lower for keyword in ['trump', 'biden', 'election', 'president']):
                    asset = 'POLITICS'
                elif any(keyword in question_lower for keyword in ['nfl', 'nba', 'sports', 'super bowl']):
                    asset = 'SPORTS'

            # Save to database (persistence!) - store actual token price
            self.position_manager.save_position(
                market_id=market_id,
                token_id=token_id,
                entry_time=datetime.now(timezone.utc),
                entry_price=entry_price,  # Actual token price (YES or NO)
                outcome=outcome,  # YES or NO (V2 uses 'outcome' not 'side')
                size=position_size,
                edge=signal.get('edge', 0),  # V2: track expected edge
                confidence=signal.get('confidence', 0),  # V2: track confidence
                signal_reason='event',  # V2: track which strategy
                metadata={
                    'question': question,
                    'asset': asset,
                    'signal_action': signal['action'],
                    'event_source': signal.get('source', 'unknown')
                }
            )

            # Track paper position (in memory)
            self.risk_manager.add_position(market_id, position_size)
            self.position_timers[market_id] = {
                'entry_time': datetime.now(timezone.utc),
                'entry_price': entry_price,  # Actual token price
                'side': outcome,  # Store YES or NO
                'size': position_size
            }

            # Send Telegram notification
            self.telegram.notify_position_opened(
                market_id=market_id,
                asset="CRYPTO",  # Event trader handles general crypto
                outcome=outcome,
                entry_price=entry_price,  # Actual token price
                position_size=position_size,
                edge=signal.get('expected_return'),
                bot_name="Event Trader"
            )

        else:
            # Real trading
            order = self.client.place_order(
                token_id=token_id,
                side=signal['action'],
                price=signal.get('suggested_price', current_price),
                size=position_size / current_price,
                order_type='GTC'
            )

            if order:
                logger.info(f"Order placed: {order}")
                self.risk_manager.add_position(market_id, position_size)
                self.open_orders[market_id] = order
            else:
                logger.error(f"Failed to place order")

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

    def get_dynamic_tp_sl(self, hours_remaining: float) -> tuple[float, float]:
        """Get TP/SL thresholds based on time remaining.

        Args:
            hours_remaining: Current hours until expiry

        Returns:
            (take_profit_pct, stop_loss_pct)
        """
        decay_config = self.config.get('time_decay_tp_sl', {})

        # If disabled, return static thresholds
        if not decay_config.get('enabled', False):
            tp_pct = self.config.get('take_profit', {}).get('pct', 50)
            sl_pct = self.config.get('stop_loss', {}).get('pct', 15)
            return tp_pct, sl_pct

        # Get thresholds
        thresholds = decay_config.get('thresholds', [])
        if not thresholds:
            # Fallback to static if not configured
            tp_pct = self.config.get('take_profit', {}).get('pct', 50)
            sl_pct = self.config.get('stop_loss', {}).get('pct', 15)
            return tp_pct, sl_pct

        # Find matching threshold based on hours_remaining
        # Thresholds should be sorted by min_hours descending
        for threshold in thresholds:
            if hours_remaining >= threshold['min_hours']:
                tp_pct = threshold['tp_pct'] if decay_config.get('apply_to_tp', True) else self.config.get('take_profit', {}).get('pct', 50)
                sl_pct = threshold['sl_pct'] if decay_config.get('apply_to_sl', True) else self.config.get('stop_loss', {}).get('pct', 15)
                return tp_pct, sl_pct

        # If below all thresholds, use most aggressive (last one)
        if thresholds:
            last = thresholds[-1]
            return last['tp_pct'], last['sl_pct']

        # Final fallback to static
        tp_pct = self.config.get('take_profit', {}).get('pct', 50)
        sl_pct = self.config.get('stop_loss', {}).get('pct', 15)
        return tp_pct, sl_pct

    def manage_positions(self):
        """Manage existing positions with SL/TP checks (with dynamic time-decay)."""
        hold_time = self.config.get('hold_time_hours', 24)
        current_time = datetime.now(timezone.utc)

        sl_config = self.config.get('stop_loss', {})
        tp_config = self.config.get('take_profit', {})

        positions_to_close = []

        for market_id, position in self.position_timers.items():
            time_held = (current_time - position['entry_time']).total_seconds() / 3600
            exit_reason = None

            # Get outcome (YES/NO) - stored in 'side' field in position_timers
            outcome = position.get('side')
            if outcome not in ['YES', 'NO']:
                logger.error(
                    f"[Monitor] ❌ Invalid outcome '{outcome}' detected\n"
                    f"  Market: {market_id[:20]}...\n"
                    f"  Skipping position monitoring to prevent errors"
                )
                self.telegram.notify_error(
                    f"❌ Invalid outcome in position monitoring:\n"
                    f"Outcome: '{outcome}'\n"
                    f"Market: {market_id[:20]}...\n"
                    f"Position skipped - please investigate",
                    bot_name="Event Trader"
                )
                continue

            # Check time-based exit first
            if time_held >= hold_time:
                exit_reason = 'time_exit'
                positions_to_close.append((market_id, exit_reason))
                continue

            # Calculate current hours remaining until expiry
            # Get hours_to_expiry_at_entry from position_manager database
            db_position = self.position_manager.get_position(market_id, outcome)
            hours_to_expiry_at_entry = db_position.get('hours_to_expiry_at_entry') if db_position else None
            hours_remaining = self.calculate_hours_remaining(
                position['entry_time'],
                hours_to_expiry_at_entry
            )

            # Get dynamic TP/SL thresholds based on time remaining
            take_profit_pct, stop_loss_pct = self.get_dynamic_tp_sl(hours_remaining)

            # Log dynamic thresholds for monitoring
            if hours_remaining != float('inf'):
                logger.debug(f"Dynamic TP/SL: market={market_id[:16]}, hours_remaining={hours_remaining:.1f}h, "
                           f"tp={take_profit_pct}%, sl={stop_loss_pct}%")

            # Get current price for SL/TP checks using PriceFetcher (exit prices - bid)
            exit_prices = self.price_fetcher.get_exit_prices(market_id)
            if exit_prices is None:
                continue

            current_yes_price = exit_prices.yes_price

            # Calculate P&L percentage
            entry_price = position['entry_price']
            if entry_price <= 0:
                continue

            # Calculate P&L % based on position type
            # Get current token price based on outcome (YES or NO tokens)
            if outcome == 'YES':
                current_token_price = exit_prices.yes_price
            elif outcome == 'NO':
                current_token_price = exit_prices.no_price
            pnl_pct = ((current_token_price - entry_price) / entry_price) * 100

            # Update price extremes for trailing stop (V2: track by outcome)
            extremes = self.position_manager.update_price_extremes(market_id, outcome, current_token_price)

            # Check stop-loss (using dynamic threshold)
            if sl_config.get('enabled') and pnl_pct <= -stop_loss_pct:
                exit_reason = 'stop_loss'
                logger.info(f"  Stop-loss triggered for {market_id}: P&L {pnl_pct:+.1f}% (threshold: {stop_loss_pct}%)")

            # Check take-profit (using dynamic threshold)
            elif tp_config.get('enabled') and pnl_pct >= take_profit_pct:
                exit_reason = 'take_profit'
                logger.info(f"  Take-profit triggered for {market_id}: P&L {pnl_pct:+.1f}% (threshold: {take_profit_pct}%)")

            # Check trailing stop (if enabled and in profit)
            elif sl_config.get('trailing') and pnl_pct > 0:
                highest = extremes.get('highest_price_seen')
                trailing_dist = sl_config.get('trailing_distance_pct', 10)
                if highest and current_yes_price <= highest * (1 - trailing_dist / 100):
                    exit_reason = 'trailing_stop'
                    logger.info(f"  Trailing stop triggered for {market_id}: "
                               f"peak ${highest:.3f} → ${current_yes_price:.3f}")

            # Force exit if very close to expiry
            force_exit_hours = self.config.get('time_decay_tp_sl', {}).get('force_exit_hours', 1.0)
            if hours_remaining < force_exit_hours and hours_remaining != float('inf'):
                exit_reason = 'pre_expiry_exit'
                logger.info(f"  Pre-expiry exit for {market_id}: {hours_remaining:.1f}h < {force_exit_hours}h")

            if exit_reason:
                positions_to_close.append((market_id, exit_reason))

        # Close positions
        for market_id, exit_reason in positions_to_close:
            self.close_position(market_id, exit_reason=exit_reason)

    def close_position(self, market_id: str, exit_reason: str = None):
        """
        Close a position.

        Args:
            market_id: Market ID
            exit_reason: Why position is being closed (stop_loss, take_profit, trailing_stop, time_exit, manual)
        """
        if market_id not in self.position_timers:
            return

        position = self.position_timers[market_id]

        # Get exit prices using PriceFetcher (bid prices)
        exit_prices = self.price_fetcher.get_exit_prices(market_id)
        if exit_prices is None:
            logger.warning(f"Cannot get exit prices for {market_id} - skipping close")
            return

        # Use actual token price based on outcome (YES or NO tokens)
        outcome = position.get('side')  # This stores the outcome (YES or NO)
        if outcome not in ['YES', 'NO']:
            error_msg = (
                f"  ❌ CRITICAL: Invalid outcome '{outcome}' in position data\n"
                f"  Market: {market_id}\n"
                f"  Skipping close to prevent incorrect P&L calculation"
            )
            logger.error(error_msg)
            self.telegram.notify_error(
                f"❌ Invalid outcome in position close:\n"
                f"Outcome: '{outcome}'\n"
                f"Market: {market_id[:20]}...\n"
                f"Position NOT closed to prevent data corruption",
                bot_name="Event Trader"
            )
            return

        if outcome == 'YES':
            exit_price = exit_prices.yes_price
        elif outcome == 'NO':
            exit_price = exit_prices.no_price

        if exit_price is None:
            logger.warning(f"Cannot get exit price for {outcome} position {market_id} - skipping close")
            return

        logger.info(f"  Fetched exit price for {outcome} position: ${exit_price:.3f}")

        entry_price = position['entry_price']

        # SAFETY: Validate exit price is reasonable (0-1 range)
        if exit_price < 0 or exit_price > 1:
            logger.error(f"  Invalid exit price ${exit_price:.3f} (must be 0-1)")
            logger.error(f"  Skipping close to prevent incorrect P&L calculation")
            return

        # SAFETY: Prevent near-zero exit prices (likely API errors or illiquid markets)
        if exit_price < 0.01 and exit_reason not in ['expiry', 'manual']:
            logger.error(f"  Suspiciously low exit price ${exit_price:.6f} (< $0.01)")
            logger.error(f"  Market likely illiquid or API error - skipping close")
            return

        # SAFETY: Detect YES/NO price confusion
        # If exit_price ≈ (1 - entry_price), the API likely returned NO price instead of YES
        no_price_estimate = 1 - entry_price
        if abs(exit_price - no_price_estimate) < 0.05 and abs(exit_price - entry_price) > 0.3:
            logger.error(f"  YES/NO price confusion detected!")
            logger.error(f"  Entry: ${entry_price:.3f}, Exit: ${exit_price:.3f}, Expected NO: ${no_price_estimate:.3f}")
            logger.error(f"  Exit price looks like NO price - skipping close")
            return

        # SAFETY: Check for suspiciously large price jumps (>300% change)
        if entry_price > 0:
            price_change_pct = abs(exit_price - entry_price) / entry_price * 100
            if price_change_pct > 300 and exit_reason not in ['expiry', 'manual']:
                logger.error(f"  Suspicious exit price: ${entry_price:.3f} → ${exit_price:.3f} ({price_change_pct:.0f}% change)")
                logger.error(f"  Skipping close - price change too large (>300%)")
                return

        # Calculate PnL correctly for prediction markets:
        # entry_price is the actual token price (YES or NO)
        size = position['size']

        if entry_price > 0:
            tokens = size / entry_price
            # exit_price is now the actual token price (YES or NO)
            payout = tokens * exit_price
            pnl = payout - size
            pnl_pct = (pnl / size) * 100
        else:
            payout = 0
            pnl = -size
            pnl_pct = -100

        # Update database (persistence!)
        self.position_manager.close_position(
            market_id=market_id,
            outcome=outcome,
            exit_price=exit_price,
            exit_reason=exit_reason
        )

        # Update paper balance (add the payout)
        if self.config.get('paper_trading', True):
            self._update_paper_balance(payout, f"Close position (PnL: ${pnl:+.2f})")

        # Log with exit reason
        reason_str = f" [{exit_reason}]" if exit_reason else ""
        logger.info(f"Closing position{reason_str}: {market_id}")
        logger.info(f"  Entry: ${entry_price:.3f} → Exit: ${exit_price:.3f}")
        logger.info(f"  P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)")

        # Send Telegram notification
        self.telegram.notify_position_closed(
            market_id=market_id,
            asset="CRYPTO",
            outcome=position['side'],
            entry_price=entry_price,
            exit_price=exit_price,
            position_size=size,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
            bot_name="Event Trader"
        )

        # Remove from tracking (may trigger circuit breaker)
        was_active = self.risk_manager.circuit_breaker_active
        self.risk_manager.remove_position(market_id, pnl)

        # Check if circuit breaker was just triggered
        if not was_active and self.risk_manager.circuit_breaker_active:
            self.telegram.notify_circuit_breaker(
                consecutive_losses=self.risk_manager.consecutive_losses,
                cooldown_hours=self.risk_manager.circuit_breaker_cooldown_hours,
                bot_name="Event Trader"
            )

        del self.position_timers[market_id]

        if market_id in self.open_orders:
            del self.open_orders[market_id]

    def close_all_positions(self):
        """Close all open positions."""
        for market_id in list(self.position_timers.keys()):
            self.close_position(market_id, exit_reason='manual')

    def log_performance(self):
        """Log current performance statistics."""
        stats = self.performance_tracker.get_statistics()

        if stats:
            logger.info(f"Performance - Total trades: {stats.get('total_predictions', 0)}, "
                       f"Accuracy: {stats.get('overall_accuracy', 0):.2%}, "
                       f"24h accuracy: {stats.get('accuracy_last_24h', 0):.2%}")


def load_config(config_path: str = 'config/config.json') -> Dict:
    """Load configuration from file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config file {config_path} not found, using defaults")
        return {}


def main():
    """Main entry point."""
    # Load configuration
    config = load_config()

    # Create and start trader
    trader = PolymarketTrader(config)

    try:
        trader.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        trader.stop()


if __name__ == '__main__':
    main()
