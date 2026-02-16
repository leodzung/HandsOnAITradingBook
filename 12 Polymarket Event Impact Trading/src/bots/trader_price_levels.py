#!/usr/bin/env python3
"""
Price-Level Trading Bot
Trades long-term BTC/ETH/Gold price-level markets using volatility + technical analysis.
"""

import json
import pickle
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import pandas as pd
import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.polymarket_client import PolymarketClient
from core.price_fetcher import PriceFetcher
from utils.market_parser import PriceLevelMarketParser
from utils.external_data import SpotPriceDataSource
from features.price_level_features import PriceLevelFeatureExtractor
from core.position_manager_v2 import PositionManager
from core.trade_executor import TradeExecutor, TradeRequest
from utils.conditional_resolution import ConditionalResolutionAnalyzer
from core.exposure_manager import ExposureManager
from monitoring.telegram_notifier import TelegramNotifier
from ml.snapshot_collector import MarketSnapshotCollector


class ArbitrageLogger:
    """Log arbitrage opportunities for future use by dedicated arbitrage bot."""

    def __init__(self, log_file: str = 'data/arbitrage_opportunities.jsonl'):
        """Initialize arbitrage logger."""
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_opportunity(self, market_id: str, question: str, yes_price: float,
                       no_price: float, profit_pct: float, metadata: Dict = None):
        """
        Log an arbitrage opportunity.

        Args:
            market_id: Market condition ID
            question: Market question
            yes_price: YES token price
            no_price: NO token price
            profit_pct: Potential profit percentage
            metadata: Additional market metadata
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'market_id': market_id,
            'question': question,
            'yes_price': yes_price,
            'no_price': no_price,
            'total_price': yes_price + no_price,
            'profit_pct': profit_pct,
            'metadata': metadata or {}
        }

        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        logger.info(f"  📝 Arbitrage opportunity logged to {self.log_file}")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceLevelSignalGenerator:
    """Generate trading signals for price-level markets."""

    def __init__(self, model_path: str, edge_threshold: float = 0.10,
                 min_confidence: float = 0.15, kelly_multiplier: float = 0.5):
        """
        Initialize signal generator.

        Args:
            model_path: Path to trained model pickle file
            edge_threshold: Minimum edge required to trade (default: 10%)
            min_confidence: Minimum model confidence (default: 15%)
            kelly_multiplier: Kelly Criterion multiplier for position sizing
        """
        self.edge_threshold = edge_threshold
        self.min_confidence = min_confidence
        self.kelly_multiplier = kelly_multiplier

        # Load trained model
        logger.info(f"Loading model from {model_path}")
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.feature_names = model_data['feature_names']
        logger.info(f"Model loaded. Features: {len(self.feature_names)}")

    def generate_signal(self, features: pd.DataFrame, market_price: float,
                       balance: float = 1000) -> Dict:
        """
        Generate trading signal.

        Args:
            features: Feature DataFrame (single row)
            market_price: Current Polymarket price (0-1)
            balance: Available balance

        Returns:
            Signal dictionary with action, confidence, edge, position_size
        """
        # Ensure features are in correct order
        features = features[self.feature_names]

        # Get model prediction
        prediction = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]

        # Model probability of YES (price reaches strike)
        model_prob = probabilities[1]
        confidence = max(probabilities)

        # Calculate edge
        edge = model_prob - market_price

        # Decision logic
        if confidence < self.min_confidence:
            return {
                'action': 'HOLD',
                'reason': f'Low confidence: {confidence:.2%} < {self.min_confidence:.2%}',
                'confidence': confidence,
                'model_prob': model_prob,
                'market_price': market_price,
                'edge': edge,
                'position_size': 0
            }

        if abs(edge) < self.edge_threshold:
            return {
                'action': 'HOLD',
                'reason': f'Insufficient edge: {edge:.2%} < {self.edge_threshold:.2%}',
                'confidence': confidence,
                'model_prob': model_prob,
                'market_price': market_price,
                'edge': edge,
                'position_size': 0
            }

        # Calculate position size using Kelly Criterion
        # Kelly = (edge / odds) where odds = 1 for binary markets
        # Apply multiplier to reduce risk
        kelly_fraction = abs(edge) * self.kelly_multiplier
        kelly_fraction = min(kelly_fraction, 0.25)  # Cap at 25%

        position_size = balance * kelly_fraction

        # Determine action
        if edge > self.edge_threshold:
            action = 'BUY'
            reason = f'Positive edge: {edge:.2%}'
        elif edge < -self.edge_threshold:
            action = 'SELL'
            reason = f'Negative edge: {edge:.2%}'
        else:
            action = 'HOLD'
            reason = 'Edge within threshold'

        return {
            'action': action,
            'reason': reason,
            'confidence': confidence,
            'model_prob': model_prob,
            'market_price': market_price,
            'edge': edge,
            'kelly_fraction': kelly_fraction,
            'position_size': position_size
        }


class PriceLevelTrader:
    """Main trading bot for price-level markets."""

    def __init__(self, config_path: str = 'config/config_price_levels.json'):
        """
        Initialize trader.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        logger.info("Initializing Price-Level Trader")
        logger.info(f"Config: {config_path}")

        # Initialize components
        self.client = PolymarketClient(config=self.config)

        # Initialize WebSocket orderbook manager for real-time price discovery
        logger.info("Initializing WebSocket orderbook manager...")
        self.client.initialize_orderbook_manager()

        self.price_fetcher = PriceFetcher(self.client)
        self.parser = PriceLevelMarketParser()
        self.data_source = SpotPriceDataSource(
            cache_minutes=self.config.get('spot_price_cache_minutes', 5)
        )
        self.feature_extractor = PriceLevelFeatureExtractor()

        # Initialize signal generator
        self.signal_generator = PriceLevelSignalGenerator(
            model_path=self.config['model_path'],
            edge_threshold=self.config.get('edge_threshold', 0.10),
            min_confidence=self.config.get('min_confidence', 0.15),
            kelly_multiplier=self.config.get('kelly_multiplier', 0.5)
        )

        # Initialize position manager
        self.position_manager = PositionManager(db_path='data/positions_price_level.db')
        logger.info("✓ Position manager initialized")

        # Initialize trade executor (centralized execution logic)
        self.trade_executor = TradeExecutor(
            client=self.client,
            position_manager=self.position_manager,
            config=self.config,
            paper_trading=self.config.get('paper_trading', True)
        )
        logger.info("✓ Trade executor initialized")

        # Initialize conditional resolution analyzer (for 50-50 markets)
        self.conditional_analyzer = ConditionalResolutionAnalyzer()
        logger.info("✓ Conditional resolution analyzer initialized")

        # Initialize arbitrage logger
        self.arbitrage_logger = ArbitrageLogger()
        logger.info("✓ Arbitrage logger initialized")

        # Initialize exposure manager
        self.exposure_manager = ExposureManager(self.config.get('exposure_limits', {}))
        logger.info("✓ Exposure manager initialized")

        # Paper trading balance
        self.balance_file = Path('data/paper_trading_balance_price_level.json')
        self.balance = self._load_balance()
        logger.info(f"✓ Paper trading balance: ${self.balance:.2f}")

        # Trading state
        self.active_positions = {}
        self.daily_pnl = 0.0
        self.trades_today = []

        # Circuit breaker state
        self.consecutive_losses = 0
        self.circuit_breaker_active = False
        self.circuit_breaker_triggered_at: Optional[datetime] = None
        self.circuit_breaker_losses = self.config.get('circuit_breaker_losses', 3)
        self.circuit_breaker_cooldown_hours = self.config.get('circuit_breaker_cooldown_hours', 4.0)

        # Position monitor thread state
        self.is_running = True
        self.monitor_thread = None
        self.position_lock = threading.Lock()  # Protect against concurrent position closes

        # Restore positions from database
        self._restore_positions()
        logger.info(f"✓ Trading state initialized ({len(self.active_positions)} open positions)")

        # Initialize Telegram notifier
        telegram_config = self.config.get('telegram', {})
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

        logger.info("Initialization complete")

    def _load_balance(self) -> float:
        """Load paper trading balance from file."""
        if self.balance_file.exists():
            with open(self.balance_file, 'r') as f:
                data = json.load(f)
                return data.get('balance', self.config.get('paper_trading_balance', 500.0))
        else:
            # Initialize with default balance
            initial_balance = self.config.get('paper_trading_balance', 500.0)
            self._save_balance(initial_balance)
            return initial_balance

    def _save_balance(self, balance: float):
        """Save paper trading balance to file."""
        self.balance = balance
        with open(self.balance_file, 'w') as f:
            json.dump({
                'balance': balance,
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)

    def _restore_positions(self):
        """Restore open positions from database."""
        positions = self.position_manager.get_open_positions()
        for pos in positions:
            market_id = pos['market_id']
            # Parse expiry_date from string back to datetime
            expiry_str = pos.get('metadata', {}).get('expiry_date')
            expiry_date = datetime.fromisoformat(expiry_str) if expiry_str else None

            # entry_time is already a datetime from position_manager.get_open_positions()
            entry_time = pos['entry_time']
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)

            # Handle both V1 'side' and V2 'outcome' fields
            side = pos.get('outcome', pos.get('side', 'YES'))
            if side in ['BUY', 'SELL']:
                outcome = 'YES' if side == 'BUY' else 'NO'
            else:
                outcome = side  # Already YES or NO

            self.active_positions[market_id] = {
                'market_id': market_id,
                'token_id': pos['token_id'],
                'asset': pos.get('metadata', {}).get('asset', 'UNKNOWN'),
                'question': pos.get('metadata', {}).get('question', ''),
                'outcome': outcome,  # YES or NO
                'entry_price': pos['entry_price'],
                'position_size': pos['size'],
                'entry_time': entry_time,
                'expiry_date': expiry_date,
                'strike_price': pos.get('metadata', {}).get('strike_price'),
                'slug': pos.get('metadata', {}).get('slug')  # For restricted market price lookups
            }
        logger.info(f"✓ Loaded {len(positions)} open positions from database")

    def _start_position_monitor(self):
        """Start background thread for frequent SL/TP checks."""
        check_interval = self.config.get('position_check_interval_seconds', 60)

        def monitor_loop():
            logger.info(f"Position monitor started (checking every {check_interval}s)")
            while self.is_running:
                try:
                    if self.active_positions:
                        self._check_position_exits()
                except Exception as e:
                    logger.error(f"Position monitor error: {e}")
                time.sleep(check_interval)
            logger.info("Position monitor stopped")

        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()

    @staticmethod
    def calculate_hours_remaining(entry_time: datetime, hours_to_expiry_at_entry: float) -> float:
        """Calculate current hours remaining until expiry.

        Args:
            entry_time: When position was opened (datetime)
            hours_to_expiry_at_entry: Hours to expiry when position was opened

        Returns:
            Current hours remaining (can be negative if expired)
        """
        if hours_to_expiry_at_entry is None or hours_to_expiry_at_entry <= 0:
            return float('inf')  # No expiry data, treat as distant

        expiry_time = entry_time + timedelta(hours=hours_to_expiry_at_entry)
        # Use timezone-aware comparison if entry_time has timezone
        now = datetime.now(entry_time.tzinfo) if entry_time.tzinfo else datetime.now()
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
            tp_pct = self.config.get('take_profit', {}).get('pct', 75)
            sl_pct = self.config.get('stop_loss', {}).get('pct', 20)
            return tp_pct, sl_pct

        # Get thresholds
        thresholds = decay_config.get('thresholds', [])
        if not thresholds:
            # Fallback to static if not configured
            tp_pct = self.config.get('take_profit', {}).get('pct', 75)
            sl_pct = self.config.get('stop_loss', {}).get('pct', 20)
            return tp_pct, sl_pct

        # Find matching threshold based on hours_remaining
        # Thresholds should be sorted by min_hours descending
        for threshold in thresholds:
            if hours_remaining >= threshold['min_hours']:
                tp_pct = threshold['tp_pct'] if decay_config.get('apply_to_tp', True) else self.config.get('take_profit', {}).get('pct', 75)
                sl_pct = threshold['sl_pct'] if decay_config.get('apply_to_sl', True) else self.config.get('stop_loss', {}).get('pct', 20)
                return tp_pct, sl_pct

        # If below all thresholds, use most aggressive (last one)
        if thresholds:
            last = thresholds[-1]
            return last['tp_pct'], last['sl_pct']

        # Final fallback to static
        tp_pct = self.config.get('take_profit', {}).get('pct', 75)
        sl_pct = self.config.get('stop_loss', {}).get('pct', 20)
        return tp_pct, sl_pct

    def _check_position_exits(self):
        """
        Check all positions for exit conditions (called by monitor thread).

        This is the ONLY place where positions are closed. Handles:
        - Expiry
        - Stop-loss (dynamic based on time-decay)
        - Take-profit (dynamic based on time-decay)
        - Trailing stop
        - Pre-expiry forced exit
        - 100% profit fallback
        """
        if not self.active_positions:
            return

        sl_config = self.config.get('stop_loss', {})
        tp_config = self.config.get('take_profit', {})

        positions_to_close = []

        for market_id, position in list(self.active_positions.items()):
            try:
                exit_reason = None

                # Get outcome (YES/NO) - handle both V2 (outcome) and V1 (side) fields
                outcome = position.get('outcome') or position.get('side')
                if outcome in ['BUY', 'SELL']:
                    # V1 schema: BUY → YES, SELL → NO
                    outcome = 'YES' if outcome == 'BUY' else 'NO'

                # Validate outcome is YES or NO
                if outcome not in ['YES', 'NO']:
                    logger.error(
                        f"[Monitor] ❌ Invalid outcome '{outcome}' detected\n"
                        f"  Market: {market_id[:20]}...\n"
                        f"  Question: {position.get('question', 'N/A')[:60]}\n"
                        f"  Asset: {position.get('asset', 'N/A')}\n"
                        f"  Skipping position monitoring to prevent errors"
                    )
                    self.telegram.notify_error(
                        f"❌ Invalid outcome in position monitoring:\n"
                        f"Outcome: '{outcome}'\n"
                        f"Market: {market_id[:20]}...\n"
                        f"Asset: {position.get('asset', 'N/A')}\n"
                        f"Position skipped - please investigate",
                        bot_name="Price-Level Trader"
                    )
                    continue

                # Check if market expired
                expiry = position.get('expiry_date')
                if expiry:
                    # Handle timezone-aware comparison
                    now = datetime.now(expiry.tzinfo) if expiry.tzinfo else datetime.now()
                    if now >= expiry:
                        logger.info(f"[Monitor] Position expired: {position['question'][:40]}")
                        positions_to_close.append((market_id, 'expiry'))
                        continue

                # Calculate current hours remaining until expiry
                # Get hours_to_expiry_at_entry from position_manager database
                db_position = self.position_manager.get_position(market_id, outcome)
                hours_to_expiry_at_entry = db_position.get('hours_to_expiry_at_entry') if db_position else None
                entry_time = position.get('entry_time')

                hours_remaining = self.calculate_hours_remaining(
                    entry_time,
                    hours_to_expiry_at_entry
                )

                # Get dynamic TP/SL thresholds based on time remaining
                take_profit_pct, stop_loss_pct = self.get_dynamic_tp_sl(hours_remaining)

                # Log dynamic thresholds for monitoring
                if hours_remaining != float('inf'):
                    logger.debug(f"[Monitor] Dynamic TP/SL: {position['asset']}, hours_remaining={hours_remaining:.1f}h, "
                               f"tp={take_profit_pct}%, sl={stop_loss_pct}%")

                # Get current price for monitoring (use BID prices - what we could sell for)
                exit_prices = self.price_fetcher.get_exit_prices(market_id)
                if exit_prices is None:
                    continue

                # Get current price based on position outcome
                current_token_price = exit_prices.get_outcome_price(outcome)
                current_yes_price = exit_prices.yes_price  # For trailing stop tracking

                entry_price = position['entry_price']
                if entry_price <= 0:
                    continue

                # Calculate P&L % based on position type
                # entry_price and current_token_price are both actual token prices (YES or NO)
                pnl_pct = ((current_token_price - entry_price) / entry_price) * 100

                # Update price extremes for trailing stop (V2: track by outcome)
                extremes = self.position_manager.update_price_extremes(market_id, outcome, current_token_price)

                # Check stop-loss (using dynamic threshold)
                if sl_config.get('enabled') and pnl_pct <= -stop_loss_pct:
                    exit_reason = 'stop_loss'
                    logger.info(f"[Monitor] Stop-loss triggered for {position['asset']}: {pnl_pct:+.1f}% (threshold: {stop_loss_pct}%)")

                # Check take-profit (using dynamic threshold)
                elif tp_config.get('enabled') and pnl_pct >= take_profit_pct:
                    exit_reason = 'take_profit'
                    logger.info(f"[Monitor] Take-profit triggered for {position['asset']}: {pnl_pct:+.1f}% (threshold: {take_profit_pct}%)")

                # Fallback: 100% profit target (2x)
                elif pnl_pct >= 100:
                    exit_reason = 'take_profit'
                    logger.info(f"[Monitor] 100% profit target reached for {position['asset']}")

                # Check trailing stop (if enabled and in profit)
                elif sl_config.get('trailing') and pnl_pct > 0:
                    highest = extremes.get('highest_price_seen')
                    trailing_dist = sl_config.get('trailing_distance_pct', 10)
                    if highest and current_yes_price <= highest * (1 - trailing_dist / 100):
                        exit_reason = 'trailing_stop'
                        logger.info(f"[Monitor] Trailing stop for {position['asset']}: "
                                   f"peak ${highest:.3f} → ${current_yes_price:.3f}")

                # Force exit if very close to expiry
                force_exit_hours = self.config.get('time_decay_tp_sl', {}).get('force_exit_hours', 1.0)
                if hours_remaining < force_exit_hours and hours_remaining != float('inf'):
                    exit_reason = 'pre_expiry_exit'
                    logger.info(f"[Monitor] Pre-expiry exit for {position['asset']}: {hours_remaining:.1f}h < {force_exit_hours}h")

                if exit_reason:
                    positions_to_close.append((market_id, exit_reason))

            except Exception as e:
                logger.error(f"[Monitor] Error checking {market_id}: {e}")
                self.telegram.notify_error(
                    f"⚠️ Position monitoring error:\nMarket: {market_id[:16]}...\nError: {str(e)[:150]}",
                    bot_name="Price-Level Trader"
                )

        # Close triggered positions
        for market_id, exit_reason in positions_to_close:
            self._close_position(market_id, exit_reason=exit_reason)

    def run(self):
        """Run trading bot main loop."""
        logger.info("=" * 70)
        logger.info("PRICE-LEVEL TRADING BOT STARTED")
        logger.info("=" * 70)
        logger.info(f"Mode: {'PAPER TRADING' if self.config.get('paper_trading') else 'LIVE TRADING'}")
        logger.info(f"Assets: {self.config.get('assets')}")
        logger.info(f"Edge Threshold: {self.config.get('edge_threshold'):.1%}")
        logger.info(f"Cycle Interval: {self.config.get('cycle_interval_seconds')}s")

        # Show SL/TP config
        sl_config = self.config.get('stop_loss', {})
        tp_config = self.config.get('take_profit', {})
        if sl_config.get('enabled'):
            logger.info(f"Stop-Loss: {sl_config.get('pct')}%" +
                       (f" (trailing: {sl_config.get('trailing_distance_pct')}%)" if sl_config.get('trailing') else ""))
        if tp_config.get('enabled'):
            logger.info(f"Take-Profit: {tp_config.get('pct')}%")

        logger.info("=" * 70)

        # Start position monitor thread for frequent SL/TP checks
        self._start_position_monitor()

        try:
            while True:
                try:
                    self.trading_cycle()
                    time.sleep(self.config.get('cycle_interval_seconds', 3600))
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error in trading cycle: {e}", exc_info=True)
                    self.telegram.notify_error(
                        f"⚠️ Trading cycle error:\n{str(e)[:200]}",
                        bot_name="Price-Level Trader"
                    )
                    time.sleep(60)  # Wait 1 minute before retrying
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.is_running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)

    def trading_cycle(self):
        """Execute one trading cycle."""
        logger.info("\n" + "=" * 70)
        logger.info(f"TRADING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)

        # 1. Discover price-level markets
        markets = self.discover_price_level_markets()
        logger.info(f"Found {len(markets)} price-level markets")

        # 2. Process each market
        signals_generated = 0
        arbitrage_found = 0
        for parsed_market in markets:
            try:
                signal = self.process_market(parsed_market)
                if signal:
                    if signal['action'] == 'ARBITRAGE':
                        arbitrage_found += 1
                        # Log for future arbitrage bot
                        self.arbitrage_logger.log_opportunity(
                            market_id=parsed_market.get('conditionId', ''),
                            question=parsed_market.get('question', ''),
                            yes_price=signal['market_price'],
                            no_price=signal.get('no_price', 1.0 - signal['market_price']),
                            profit_pct=signal.get('arb_profit_pct', 0),
                            metadata={
                                'asset': parsed_market.get('asset'),
                                'strike_price': parsed_market.get('strike_price'),
                                'expiry_date': str(parsed_market.get('expiry_date'))
                            }
                        )
                        logger.info(f"  📊 Arbitrage logged for future bot: {signal.get('arb_profit_pct', 0):.2f}% profit")
                    elif signal['action'] in ['BUY', 'SELL']:
                        signals_generated += 1
                        self.execute_signal(parsed_market, signal)
            except Exception as e:
                import traceback
                logger.error(f"Error processing market {parsed_market.get('question', '')[:40]}: {e}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
                self.telegram.notify_error(
                    f"⚠️ Market processing error:\nMarket: {parsed_market.get('question', '')[:60]}\nError: {str(e)[:150]}",
                    bot_name="Price-Level Trader"
                )

        logger.info(f"Generated {signals_generated} actionable signals, {arbitrage_found} arbitrage opportunities")

        # 3. Log position status (exits handled by monitor thread)
        self.log_position_status()

        # 4. Log performance
        self.log_performance()

        # 5. Log exposure report
        self._log_exposure_report()

    def discover_price_level_markets(self) -> List[Dict]:
        """
        Discover and parse price-level markets.

        Returns:
            List of parsed price-level markets
        """
        logger.info("Discovering price-level markets...")

        # Calculate end date range based on expiry config
        from datetime import datetime, timedelta
        now = datetime.now()
        min_days = self.config.get('min_days_to_expiry', 1)
        max_days = self.config.get('max_days_to_expiry', 365)

        end_date_min = (now + timedelta(days=min_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date_max = (now + timedelta(days=max_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Apply filters at API level for efficiency
        min_volume = self.config.get('min_market_volume', 1000)
        min_liquidity = self.config.get('min_liquidity', 500)

        # Get active markets from Polymarket with API-level filtering
        all_markets = []
        max_pages = self.config.get('max_market_pages', 50)  # Up to 5000 markets

        for page in range(max_pages):
            offset = page * 100
            markets = self.client.get_markets(
                limit=100,
                offset=offset,
                active=True,
                end_date_min=end_date_min,
                end_date_max=end_date_max,
                volume_num_min=min_volume,
                liquidity_num_min=min_liquidity
            )
            if not markets:
                logger.info(f"No more markets at offset {offset}, stopping pagination")
                break
            all_markets.extend(markets)

        logger.info(f"Retrieved {len(all_markets)} filtered markets from API "
                   f"(volume>=${min_volume}, liquidity>=${min_liquidity}, "
                   f"expiry: {min_days}-{max_days} days)")

        # Also fetch markets from specific event slugs (includes restricted markets)
        # Note: get_markets_from_event() automatically filters out closed markets
        event_slugs = self.config.get('event_slugs', {})
        existing_ids = {m.get('conditionId') for m in all_markets}
        event_markets_added = 0

        for asset, slugs in event_slugs.items():
            for slug in slugs:
                event_markets = self.client.get_markets_from_event(slug)
                # Defensive: Filter out closed markets even though client should do this
                event_markets = [m for m in event_markets if not m.get('closed', False)]
                for m in event_markets:
                    if m.get('conditionId') not in existing_ids:
                        all_markets.append(m)
                        existing_ids.add(m.get('conditionId'))
                        event_markets_added += 1

        if event_markets_added > 0:
            logger.info(f"Added {event_markets_added} active markets from event slugs (closed markets filtered out)")

        logger.info(f"Total markets to scan: {len(all_markets)}")

        # Filter for price-level markets
        assets = self.config.get('assets', ['BTC', 'ETH'])
        price_level_markets = self.parser.filter_price_level_markets(
            all_markets, assets=assets
        )

        # Apply additional filters (volume filtered at API level, but expiry needs rechecking for event slug markets)
        filtered_markets = []
        min_days = self.config.get('min_days_to_expiry', 1)
        max_days = self.config.get('max_days_to_expiry', 365)

        for market in price_level_markets:
            # Find original market data
            orig_market = next((m for m in all_markets
                              if m.get('conditionId') == market.get('conditionId')), None)

            if orig_market:
                # Store original market data
                market['original_market'] = orig_market

            # Apply expiry filter to ALL markets (event slugs bypass API-level filtering)
            days_to_expiry = market.get('days_to_expiry', 0)
            # Ensure days_to_expiry is an integer (handle string case)
            try:
                days_to_expiry = int(days_to_expiry) if days_to_expiry else 0
            except (ValueError, TypeError):
                logger.warning(f"Invalid days_to_expiry for {market.get('question', '')}: {days_to_expiry}")
                continue

            if days_to_expiry < min_days:
                continue
            if days_to_expiry > max_days:
                continue

            filtered_markets.append(market)

        logger.info(f"After expiry filter: {len(filtered_markets)} price-level markets")

        # Apply quality filters (spread, price range, trade activity)
        from core.polymarket_client import MarketFilter
        quality_config = self.config.get('quality_filters', {})
        if quality_config.get('enabled', True):
            # Extract original markets for quality filtering
            markets_for_quality_check = []
            for m in filtered_markets:
                orig = m.get('original_market', m)
                markets_for_quality_check.append(orig)

            quality_filtered = MarketFilter.filter_by_quality(
                markets=markets_for_quality_check,
                price_fetcher=self.price_fetcher,
                min_price=quality_config.get('min_price', 0.05),
                max_price=quality_config.get('max_price', 0.95),
                max_spread_pct=quality_config.get('max_spread_pct', 15.0),
                check_last_trade=quality_config.get('check_last_trade', True),
                logger=logger
            )

            # Keep only markets that passed quality filter
            quality_ids = {m.get('conditionId') for m in quality_filtered}
            filtered_markets = [m for m in filtered_markets
                              if (m.get('original_market', m)).get('conditionId') in quality_ids]

            logger.info(f"After quality filter: {len(filtered_markets)} tradeable price-level markets")
        else:
            logger.info(f"Filtered to {len(filtered_markets)} tradeable price-level markets")

        # Register markets for WebSocket orderbook subscriptions
        if filtered_markets:
            logger.info(f"Registering {len(filtered_markets)} markets for WebSocket orderbook tracking...")
            for market in filtered_markets:
                orig_market = market.get('original_market', market)
                condition_id = orig_market.get('conditionId')
                question = orig_market.get('question', '')
                if condition_id:
                    self.client.register_market_for_orderbook(condition_id, question)

        return filtered_markets

    def _map_features_to_model(self, extracted_features: Dict, parsed_market: Dict) -> Dict:
        """
        Map extracted features to the format expected by the trained model.

        The model (trained on training_data_v2.csv) expects 36 features including:
        - volatility_30d, volatility_90d, volatility_parkinson, vol_regime, vol_percentile, vol_trend
        - rsi_14, macd, macd_signal, macd_histogram, bb_position, bb_width
        - price_vs_ma50_pct, price_vs_ma200_pct, golden_cross
        - strike_distance_pct, is_itm, moneyness, strike_distance_sigma, gbm_probability
        - weeks_to_expiry, months_to_expiry, time_fraction, time_decay, day_of_week, month
        - is_quarter_end, is_year_end
        - market_price, spread, spread_pct, depth_imbalance
        - volume_24h, volume_7d, liquidity, volume_trend

        Args:
            extracted_features: Features from PriceLevelFeatureExtractor
            parsed_market: Parsed market data

        Returns:
            Dictionary with model-compatible features
        """
        # The new model uses the same feature names as extract_all_features
        # Just pass through the extracted features directly
        return extracted_features

    def process_market(self, parsed_market: Dict) -> Optional[Dict]:
        """
        Process a single price-level market.

        Args:
            parsed_market: Parsed market data

        Returns:
            Trading signal or None
        """
        asset = parsed_market['asset']
        question = parsed_market.get('question', '')[:60]
        market_type = parsed_market.get('market_type', 'threshold')

        logger.info(f"\nProcessing: {question}")
        logger.info(f"  Asset: {asset}, Strike: ${parsed_market['strike_price']:,.0f}, "
                   f"Expiry: {parsed_market['days_to_expiry']} days")

        # Skip "race" markets - they have different semantics that our model doesn't handle
        # E.g., "Will BTC hit $80k or $150k first?" - YES means $80k first (bearish bet)
        if market_type == 'race':
            race_prices = parsed_market.get('race_prices', [])
            logger.info(f"  ⚠️  SKIPPING: Race market detected (prices: {race_prices})")
            logger.info(f"     Race markets have different semantics - model not trained for these")
            return {
                'action': 'HOLD',
                'reason': f'Race market not supported (competing prices: {race_prices})',
                'confidence': 0,
                'model_prob': 0,
                'market_price': 0,
                'edge': 0,
                'position_size': 0
            }

        # Get current spot price
        try:
            spot_price = self.data_source.get_current_price(asset)
            logger.info(f"  Spot Price: ${spot_price:,.2f}")
        except Exception as e:
            logger.error(f"  Error fetching spot price: {e}")
            return None

        # Get historical OHLCV data
        try:
            # Get enough history for technical indicators (need at least 90 days)
            historical_ohlcv = self.data_source.get_historical_ohlcv(asset, days=365)
            if len(historical_ohlcv) < 30:
                logger.warning(f"  Insufficient historical data: {len(historical_ohlcv)} days")
                return None
        except Exception as e:
            logger.error(f"  Error fetching historical data: {e}")
            return None

        # Get Polymarket market data
        token_id = parsed_market.get('token_id')
        if not token_id:
            logger.warning("  No token_id available")
            return None

        try:
            # Get entry prices using centralized PriceFetcher
            condition_id = parsed_market.get('conditionId')
            if not condition_id:
                logger.warning("  No condition_id available")
                return None

            # Get entry prices (ASK prices from CLOB orderbook)
            entry_prices = self.price_fetcher.get_entry_prices(condition_id)
            if entry_prices is None:
                logger.warning("  No entry prices available from CLOB orderbook")
                return None

            market_price = entry_prices.yes_price
            no_price = entry_prices.no_price

            # Calculate spread
            spread = market_price + no_price - 1.0  # Market maker spread

            # Orderbook is still useful for liquidity/spread analysis (optional)
            orderbook = self.client.get_orderbook(token_id)

            logger.info(f"  Market Price: YES=${market_price:.3f}, NO=${no_price:.3f}")

            # Check for arbitrage opportunity (YES + NO < 1)
            total_price = market_price + no_price
            if total_price < 0.98:  # 2% profit threshold
                arb_profit = (1.0 - total_price) / total_price * 100
                logger.info(f"  🎯 ARBITRAGE OPPORTUNITY!")
                logger.info(f"     Buy YES @ ${market_price:.3f} + NO @ ${no_price:.3f} = ${total_price:.3f}")
                logger.info(f"     Guaranteed profit: {arb_profit:.2f}%")

                # Return arbitrage signal
                return {
                    'action': 'ARBITRAGE',
                    'reason': f'Arbitrage: YES+NO=${total_price:.3f} < $1 ({arb_profit:.2f}% profit)',
                    'confidence': 1.0,  # Risk-free
                    'model_prob': 0.5,
                    'market_price': market_price,
                    'no_price': no_price,
                    'edge': arb_profit / 100,
                    'position_size': min(self.balance * 0.5, self.config.get('max_position_size', 100)),  # Can use more since risk-free
                    'outcome': 'BOTH',  # Buy both YES and NO
                    'arb_profit_pct': arb_profit
                }

            # Get original market data for feature extraction
            orig_market = parsed_market.get('original_market', {})

            # Prepare polymarket data structure
            polymarket_data = {
                'market': orig_market,
                'orderbook': orderbook
            }

        except Exception as e:
            logger.error(f"  Error fetching market data: {e}")
            return None

        # Extract features
        try:
            features = self.feature_extractor.extract_all_features(
                parsed_market=parsed_market,
                spot_price=spot_price,
                historical_ohlcv=historical_ohlcv,
                polymarket_data=polymarket_data
            )

            # Map extracted features to model's expected format
            model_features = self._map_features_to_model(features, parsed_market)
            features_df = pd.DataFrame([model_features])

        except Exception as e:
            logger.error(f"  Error extracting features: {e}")
            return None

        # Generate signal from ML model
        signal = self.signal_generator.generate_signal(
            features_df, market_price, self.balance
        )

        # Map BUY/SELL to YES/NO for clarity
        outcome = 'YES' if signal['action'] == 'BUY' else 'NO' if signal['action'] == 'SELL' else None
        action_display = f"BUY {outcome}" if outcome else signal['action']

        logger.info(f"  ML Signal: {action_display} (edge: {signal['edge']:+.2%}, "
                   f"confidence: {signal['confidence']:.2%})")

        # Check for conditional resolution rules (50-50, etc.)
        if orig_market:
            # Calculate realistic primary event probability based on strike distance
            # For extreme strikes, override ML model which may be miscalibrated
            strike_price = parsed_market.get('strike_price', 0)
            strike_distance_pct = abs(strike_price - spot_price) / spot_price if spot_price > 0 else 0

            if strike_distance_pct > 5.0:  # More than 500% away
                p_primary = 0.001  # ~0.1% for extreme strikes
                logger.info(f"  Strike is {strike_distance_pct*100:.0f}% away - using p_primary=0.1%")
            elif strike_distance_pct > 2.0:  # More than 200% away
                p_primary = 0.01  # ~1% for very far strikes
                logger.info(f"  Strike is {strike_distance_pct*100:.0f}% away - using p_primary=1%")
            elif strike_distance_pct > 1.0:  # More than 100% away
                p_primary = 0.05  # ~5% for far strikes
                logger.info(f"  Strike is {strike_distance_pct*100:.0f}% away - using p_primary=5%")
            else:
                # Use model probability for reasonable strikes
                p_primary = signal.get('model_prob', 0.5)

            # Analyze conditional resolution
            cond_resolution = self.conditional_analyzer.analyze_market(
                orig_market, p_primary_event=p_primary
            )

            if cond_resolution.has_5050_rule:
                logger.info(f"  ⚠️  50-50 Resolution Rule Detected!")
                if cond_resolution.alternative_event:
                    logger.info(f"      Alternative Event: {cond_resolution.alternative_event.name}")
                    if cond_resolution.alternative_event.expected_date:
                        logger.info(f"      Expected Date: {cond_resolution.alternative_event.expected_date.strftime('%Y-%m-%d')}")

                logger.info(f"      P(Primary): {cond_resolution.p_primary:.1%}")
                logger.info(f"      P(Alternative): {cond_resolution.p_alternative:.1%}")
                logger.info(f"      P(Neither/50-50): {cond_resolution.p_neither:.1%}")
                logger.info(f"      Fair YES: ${cond_resolution.fair_yes:.3f}, Fair NO: ${cond_resolution.fair_no:.3f}")

                # Get trading recommendation based on 50-50 analysis
                cond_recommendation = self.conditional_analyzer.get_trading_recommendation(
                    cond_resolution,
                    current_yes_price=market_price,
                    current_no_price=1.0 - market_price
                )

                # Override ML signal if 50-50 analysis suggests different action
                if cond_recommendation['action'] == 'HOLD' or abs(cond_recommendation['edge']) < 0.05:
                    logger.info(f"  → 50-50 Override: HOLD (edge too small: {cond_recommendation['edge']:.2%})")
                    signal['action'] = 'HOLD'
                    signal['reason'] = f"50-50 rule: {cond_recommendation['reason']}"
                    signal['conditional_analysis'] = cond_recommendation
                elif cond_recommendation['action'] == 'BUY_NO' and signal['action'] == 'BUY':
                    logger.info(f"  → 50-50 Override: Should BUY NO instead of YES")
                    logger.info(f"      NO edge: {cond_recommendation['no_edge']:.2%}")
                    signal['action'] = 'HOLD'  # Can't buy NO with current setup, so HOLD
                    signal['reason'] = f"50-50 suggests BUY NO: {cond_recommendation['reason']}"
                    signal['conditional_analysis'] = cond_recommendation

        # Recalculate outcome after potential 50-50 override
        final_outcome = 'YES' if signal['action'] == 'BUY' else 'NO' if signal['action'] == 'SELL' else None
        final_display = f"BUY {final_outcome}" if final_outcome else signal['action']

        logger.info(f"  Final Signal: {final_display}")
        logger.info(f"  Reason: {signal['reason']}")

        # Store outcome and prices in signal for execute_signal
        signal['outcome'] = final_outcome
        signal['no_price'] = no_price  # Actual NO price from API

        # Log snapshot for training data collection (regardless of whether trade is executed)
        try:
            self.snapshot_collector.log_snapshot(
                market_id=parsed_market.get('conditionId'),
                bot_type='price_level',
                features=model_features,  # Already in model-compatible format
                prediction={
                    'model_prob': signal.get('model_prob', 0.5),
                    'confidence': signal.get('confidence', 0.0),
                    'edge': signal.get('edge', 0.0),
                    'predicted_outcome': final_outcome if final_outcome else 'HOLD'
                },
                market_data={
                    'question': parsed_market.get('question', ''),
                    'asset': parsed_market.get('asset'),
                    'strike_price': parsed_market.get('strike_price'),
                    'expiry_date': parsed_market.get('expiry_date'),
                    'days_to_expiry': parsed_market.get('days_to_expiry'),
                    'market_type': parsed_market.get('market_type'),
                    'condition_id': parsed_market.get('conditionId'),
                    'token_id': parsed_market.get('token_id')
                },
                prices={
                    'yes': market_price,
                    'no': no_price,
                    'spread': spread
                },
                position_opened=False,  # Will update in execute_signal if trade happens
                rejection_reason=None  # Will be filled if trade blocked
            )
        except Exception as e:
            logger.warning(f"Failed to log snapshot: {e}")

        return signal

    def execute_signal(self, parsed_market: Dict, signal: Dict):
        """
        Execute a trading signal.

        Args:
            parsed_market: Parsed market data
            signal: Trading signal
        """
        market_id = parsed_market.get('conditionId')
        token_id = parsed_market.get('token_id')

        # Check if already have position
        if market_id in self.active_positions:
            logger.info(f"  Already have position in this market")
            return

        # Check position limits
        if len(self.active_positions) >= self.config.get('max_positions', 5):
            logger.warning(f"  Max positions reached ({len(self.active_positions)})")
            return

        # Check daily loss limit
        if self.daily_pnl < -self.config.get('max_daily_loss', 500):
            logger.warning(f"  Daily loss limit reached: ${self.daily_pnl:.2f}")
            return

        # Check circuit breaker
        if self._check_circuit_breaker():
            return

        # Cap position size
        position_size = min(
            signal['position_size'],
            self.config.get('max_position_size', 100)
        )

        # Get outcome (YES/NO) from signal
        outcome = signal.get('outcome')
        if outcome is None:
            outcome = 'YES' if signal['action'] == 'BUY' else 'NO'

        # Check exposure limits (correlation check)
        new_position = {
            'asset': parsed_market.get('asset', 'UNKNOWN'),
            'size': position_size,
            'outcome': outcome,
            'strike_price': parsed_market.get('strike_price'),
            'expiry_date': parsed_market.get('expiry_date')
        }

        # Convert active positions to list format for exposure check
        existing_positions = self.position_manager.get_open_positions()

        # Get total capital (current balance + deployed)
        total_capital = self.balance + sum(p.get('size', 0) for p in existing_positions)

        can_open, reason, warnings = self.exposure_manager.can_open_position(
            new_position, existing_positions, total_capital
        )

        if not can_open:
            logger.warning(f"  ⚠️ BLOCKED by exposure limits: {reason}")
            return

        # Determine entry price based on outcome
        # ALWAYS fetch fresh prices to avoid YES/NO confusion
        condition_id = parsed_market.get('conditionId')
        if not condition_id:
            logger.error("  No condition_id - cannot fetch prices")
            return

        entry_prices = self.price_fetcher.get_entry_prices(condition_id)
        if not entry_prices:
            logger.error("  Cannot fetch entry prices")
            return

        if outcome == 'YES':
            entry_price = entry_prices.yes_price
        else:
            entry_price = entry_prices.no_price

        # Get slug from original market data (for restricted market price lookups)
        orig_market = parsed_market.get('original_market', {})
        slug = orig_market.get('slug', '')

        # Prepare expiry date string
        expiry = parsed_market.get('expiry_date')
        if expiry:
            expiry_str = expiry.isoformat() if hasattr(expiry, 'isoformat') else str(expiry)
        else:
            expiry_str = None

        # Build trade request
        request = TradeRequest(
            market_id=market_id,
            token_id=token_id,
            outcome=outcome,
            entry_price=entry_price,
            position_size=position_size,
            question=parsed_market.get('question', ''),
            asset=parsed_market['asset'],
            strike_price=parsed_market.get('strike_price'),
            expiry_date=expiry_str,
            edge=signal['edge'],
            confidence=signal.get('model_prob'),
            signal_reason='price_level_strategy',
            metadata={
                'kelly_fraction': signal.get('kelly_fraction'),
                'slug': slug
            }
        )

        # Execute trade with centralized executor (handles all validation)
        result = self.trade_executor.execute_trade(request)

        if not result.success:
            logger.warning(
                f"  ⚠️ Trade REJECTED ({result.rejection_stage}): "
                f"{result.rejection_reason}"
            )
            return

        # Trade successful - update balance and track in memory
        self.balance -= position_size
        self._save_balance(self.balance)
        logger.info(f"     Balance: ${self.balance:.2f} (spent ${position_size:.2f})")

        # Track position in memory for quick lookups
        self.active_positions[market_id] = {
            'market_id': market_id,
            'token_id': token_id,
            'asset': parsed_market['asset'],
            'question': parsed_market.get('question', ''),
            'outcome': outcome,
            'entry_price': result.entry_price,
            'position_size': position_size,
            'entry_time': datetime.now(),
            'expiry_date': parsed_market.get('expiry_date'),
            'strike_price': parsed_market.get('strike_price'),
            'slug': slug
        }

        # Log successful position opening in snapshot (for training data tracking)
        try:
            # Find the most recent snapshot for this market and update it
            unlabeled = self.snapshot_collector.get_unlabeled_snapshots(bot_type='price_level')
            matching = [s for s in unlabeled if s['market_id'] == market_id or s['condition_id'] == market_id]
            if matching:
                # Get the most recent snapshot
                most_recent = max(matching, key=lambda x: x['snapshot_time'])
                # Note: We can't easily update position_opened flag without modifying the collector
                # For now, we'll log that a position was opened via position_id tracking
                logger.debug(f"Snapshot {most_recent['id']} linked to opened position")
        except Exception as e:
            logger.debug(f"Could not link snapshot to position: {e}")

        # Send Telegram notification
        self.telegram.notify_position_opened(
            market_id=market_id,
            asset=parsed_market['asset'],
            outcome=outcome,
            entry_price=result.entry_price,  # Use actual execution price from result
            position_size=position_size,
            question=parsed_market.get('question', ''),
            edge=signal['edge'],
            bot_name="Price-Level Trader"
        )

    def log_position_status(self):
        """
        Log current status of all positions (for visibility in main loop logs).

        NOTE: This does NOT close positions. All exit logic is handled by the
        monitor thread in _check_position_exits().
        """
        if not self.active_positions:
            logger.info("\nNo open positions")
            return

        logger.info(f"\n--- Position Status ({len(self.active_positions)} positions) ---")

        total_deployed = 0
        total_unrealized_pnl = 0

        for market_id, position in self.active_positions.items():
            try:
                asset = position.get('asset', '?')
                entry_price = position['entry_price']
                position_size = position['position_size']
                total_deployed += position_size

                # Get current price using PriceFetcher (exit prices - bid)
                exit_prices = self.price_fetcher.get_exit_prices(market_id)

                if exit_prices is None or entry_price <= 0:
                    logger.info(f"  {asset}: ${position_size:.0f} @ ${entry_price:.3f} (price unavailable)")
                    continue

                # Calculate unrealized P&L
                # entry_price and current_token_price are both actual token prices (YES or NO)
                outcome = position.get('outcome')
                if outcome not in ['YES', 'NO']:
                    logger.warning(f"  {asset}: Invalid outcome '{outcome}' - skipping P&L calculation")
                    continue
                current_token_price = exit_prices.get_outcome_price(outcome)
                tokens = position_size / entry_price
                current_value = tokens * current_token_price
                unrealized_pnl = current_value - position_size
                pnl_pct = (unrealized_pnl / position_size) * 100
                total_unrealized_pnl += unrealized_pnl

                # Status indicator
                if pnl_pct >= 20:
                    status = "+"
                elif pnl_pct <= -10:
                    status = "-"
                else:
                    status = " "

                logger.info(f"  {status} {asset}: {pnl_pct:+.1f}% (${unrealized_pnl:+.2f})")

            except Exception as e:
                logger.error(f"  Error checking {market_id[:20]}...: {e}")

        logger.info(f"  Total deployed: ${total_deployed:.2f}")
        logger.info(f"  Unrealized P&L: ${total_unrealized_pnl:+.2f}")
        logger.info("---")

    def _close_position(self, market_id: str, exit_reason: str = None, force_exit_price: float = None):
        """
        Close a single position.

        Args:
            market_id: Market ID to close
            exit_reason: Why the position is being closed
            force_exit_price: Override exit price (for manual closes or verified resolutions)
        """
        # Use lock to prevent concurrent closes (race between monitor thread and main loop)
        with self.position_lock:
            if market_id not in self.active_positions:
                logger.debug(f"Position {market_id[:20]}... already closed (skipping)")
                return

            position = self.active_positions[market_id]

            # Get actual exit prices from CLOB API (both YES and NO)
            exit_price = force_exit_price
            outcome = position.get('outcome')

            # SAFETY: Verify outcome is valid
            if outcome not in ['YES', 'NO']:
                error_msg = (
                    f"  ❌ CRITICAL: Invalid outcome '{outcome}' in position data\n"
                    f"  Market: {market_id}\n"
                    f"  Question: {position.get('question', 'N/A')[:80]}\n"
                    f"  Asset: {position.get('asset', 'N/A')}\n"
                    f"  Position Size: ${position.get('position_size', 0):.2f}\n"
                    f"  Skipping close to prevent incorrect P&L calculation"
                )
                logger.error(error_msg)
                self.telegram.notify_error(
                    f"❌ Invalid outcome in position close:\n"
                    f"Outcome: '{outcome}'\n"
                    f"Market: {market_id[:20]}...\n"
                    f"Question: {position.get('question', 'N/A')[:60]}\n"
                    f"Position NOT closed to prevent data corruption",
                    bot_name="Price-Level Trader"
                )
                return

            if exit_price is None:
                # Get exit prices using centralized PriceFetcher (bid prices)
                exit_prices = self.price_fetcher.get_exit_prices(market_id)

                if exit_prices is not None:
                    yes_exit_price = exit_prices.yes_price
                    no_exit_price = exit_prices.no_price

                    # Log both prices for debugging (always log, not just debug mode)
                    logger.info(f"  PriceFetcher returned: YES=${yes_exit_price:.3f}, NO=${no_exit_price:.3f}")

                    # Use actual token price based on outcome
                    exit_price = exit_prices.get_outcome_price(outcome)
                    logger.info(f"  Fetched exit price for {outcome} position: ${exit_price:.3f}")
                else:
                    logger.warning(f"  PriceFetcher returned None for market {market_id}")
                    yes_exit_price = None
                    no_exit_price = None

            # SAFETY: Do NOT close if we can't verify the exit price
            # Exception: expiry-based closes where we should use last known price
            if exit_price is None:
                if exit_reason == 'expiry':
                    # For expired markets, use entry price as conservative fallback
                    # (assume no profit/loss rather than fake profit)
                    exit_price = position.get('entry_price', 0)
                    logger.warning(f"  Market expired but price unavailable - using entry price ${exit_price:.3f}")
                else:
                    logger.error(f"  Cannot close position: price unavailable for {market_id}")
                    logger.error(f"  Skipping close to prevent incorrect P&L calculation")
                    return

            # SAFETY: Validate exit price is reasonable (0-1 range for prediction markets)
            entry_price = position['entry_price']
            if exit_price < 0 or exit_price > 1:
                logger.error(f"  Invalid exit price ${exit_price:.3f} (must be 0-1)")
                logger.error(f"  Skipping close to prevent incorrect P&L calculation")
                return

            # SAFETY: Prevent near-zero exit prices (likely API errors or illiquid markets)
            # For liquid markets, prices should never be < 0.01 unless truly resolved
            if exit_price < 0.01 and exit_reason not in ['expiry', 'manual']:
                logger.error(f"  Suspiciously low exit price ${exit_price:.6f} (< $0.01)")
                logger.error(f"  Market likely illiquid or API error - skipping close")
                return

            # SAFETY: Detect YES/NO price confusion
            # If exit_price ≈ (1 - entry_price), the API likely returned NO price instead of YES
            # This catches the bug where exit_price=0.92 when entry_price=0.08
            no_price_estimate = 1 - entry_price
            if abs(exit_price - no_price_estimate) < 0.05 and abs(exit_price - entry_price) > 0.3:
                logger.error(f"  YES/NO price confusion detected!")
                logger.error(f"  Entry: ${entry_price:.3f}, Exit: ${exit_price:.3f}, Expected NO: ${no_price_estimate:.3f}")
                logger.error(f"  Exit price looks like NO price - skipping close")
                return

            # SAFETY: Check for suspiciously large price jumps (>300% change)
            # Lowered from 500% to catch more anomalies
            if entry_price > 0:
                price_change_pct = abs(exit_price - entry_price) / entry_price * 100
                if price_change_pct > 300 and exit_reason not in ['expiry', 'manual']:
                    logger.error(f"  Suspicious exit price: ${entry_price:.3f} → ${exit_price:.3f} ({price_change_pct:.0f}% change)")
                    logger.error(f"  Skipping close - price change too large (>300%)")
                    return
            position_size = position['position_size']

            # entry_price and exit_price are both actual token prices (YES or NO)
            if entry_price > 0:
                tokens = position_size / entry_price
                payout = tokens * exit_price
                pnl = payout - position_size
                pnl_pct = (pnl / position_size) * 100
            else:
                tokens = 0
                payout = 0
                pnl = -position_size
                pnl_pct = -100

            # SAFETY: Final P&L sanity check - verify calculation is correct
            # This catches any arithmetic errors or variable mismatches
            if entry_price > 0:
                expected_pnl = (position_size / entry_price) * exit_price - position_size
                if abs(pnl - expected_pnl) > 0.01:  # Allow for tiny floating point differences
                    logger.error(f"  ⚠️ P&L calculation mismatch!")
                    logger.error(f"  Calculated: ${pnl:.2f}, Expected: ${expected_pnl:.2f}")
                    logger.error(f"  entry=${entry_price:.3f}, exit=${exit_price:.3f}, size=${position_size:.2f}")
                    logger.error(f"  Skipping close to prevent data corruption")
                    return

            # Update balance (add the payout)
            self.balance += payout
            self._save_balance(self.balance)

            # Log with exit reason
            reason_str = f" [{exit_reason}]" if exit_reason else ""
            logger.info(f"  Closing position{reason_str}: {market_id}")
            logger.info(f"  Entry: ${entry_price:.3f} → Exit: ${exit_price:.3f}")
            logger.info(f"  Tokens: {tokens:.2f}, Payout: ${payout:.2f}")
            logger.info(f"  P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)")

            # Update circuit breaker state (may trigger circuit breaker)
            was_active = self.circuit_breaker_active
            self._update_circuit_breaker(pnl)

            # Check if circuit breaker was just triggered
            if not was_active and self.circuit_breaker_active:
                self.telegram.notify_circuit_breaker(
                    consecutive_losses=self.consecutive_losses,
                    cooldown_hours=self.circuit_breaker_cooldown_hours,
                    bot_name="Price-Level Trader"
                )

            # Close in database with exit reason
            self.position_manager.close_position(
                market_id=market_id,
                exit_time=datetime.now().isoformat(),
                exit_price=exit_price,
                pnl=pnl,
                exit_reason=exit_reason
            )

            # Record outcome in snapshot collector for ML training
            try:
                # Determine outcome based on position direction and exit price
                position_outcome = position.get('outcome', 'YES')

                # For binary outcomes, determine if market resolved favorably
                # If we bought YES and price went up → favorable
                # If we bought NO and price went down → favorable
                # For expiry, use exit price as proxy
                if exit_reason == 'expiry':
                    # Market expired - use final price as resolution proxy
                    # High exit price (~1.0) suggests YES, low price (~0.0) suggests NO
                    if exit_price >= 0.9:
                        actual_outcome = 'YES'
                    elif exit_price <= 0.1:
                        actual_outcome = 'NO'
                    else:
                        actual_outcome = 'EXPIRED'  # Ambiguous
                else:
                    # Position closed early (SL/TP/trailing) - outcome still uncertain
                    # We can't definitively say YES/NO until expiry
                    # So we'll record as incomplete for now
                    actual_outcome = None  # Don't label yet

                if actual_outcome:
                    self.snapshot_collector.record_outcome(
                        market_id=market_id,
                        bot_type='price_level',
                        outcome=actual_outcome,
                        resolution_price=exit_price
                    )
                    logger.debug(f"Recorded outcome '{actual_outcome}' for market snapshots")
            except Exception as e:
                logger.debug(f"Could not record snapshot outcome: {e}")

            # Send Telegram notification
            self.telegram.notify_position_closed(
                market_id=market_id,
                asset=position.get('asset', 'UNKNOWN'),
                outcome=position.get('outcome', 'YES'),
                entry_price=entry_price,
                exit_price=exit_price,
                position_size=position_size,
                pnl=pnl,
                pnl_pct=pnl_pct,
                exit_reason=exit_reason,
                question=position.get('question', ''),
                bot_name="Price-Level Trader"
            )

            # Remove from active positions
            del self.active_positions[market_id]
            logger.info(f"  ✓ Closed position: {market_id} | P&L: ${pnl:+.2f}")

    def _check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker is active.

        Returns:
            True if trading should be blocked, False otherwise
        """
        if not self.circuit_breaker_active:
            return False

        # Check if cooldown period has elapsed
        if self.circuit_breaker_triggered_at:
            elapsed_hours = (datetime.now() - self.circuit_breaker_triggered_at).total_seconds() / 3600
            if elapsed_hours >= self.circuit_breaker_cooldown_hours:
                # Reset circuit breaker after cooldown
                self.circuit_breaker_active = False
                self.consecutive_losses = 0
                self.circuit_breaker_triggered_at = None
                logger.info(f"  Circuit breaker RESET after {elapsed_hours:.1f}h cooldown. Trading resumed.")
                return False
            else:
                remaining = self.circuit_breaker_cooldown_hours - elapsed_hours
                logger.warning(f"  ⚠️ Circuit breaker active ({self.consecutive_losses} consecutive losses). "
                             f"Resume in {remaining:.1f}h")
                return True

        logger.warning(f"  ⚠️ Circuit breaker active ({self.consecutive_losses} consecutive losses)")
        return True

    def _update_circuit_breaker(self, pnl: float):
        """
        Update circuit breaker state based on trade result.

        Args:
            pnl: Profit/loss of the closed position
        """
        if pnl < 0:
            self.consecutive_losses += 1
            logger.info(f"  Consecutive losses: {self.consecutive_losses}/{self.circuit_breaker_losses}")

            # Trigger circuit breaker if threshold reached
            if self.consecutive_losses >= self.circuit_breaker_losses:
                self.circuit_breaker_active = True
                self.circuit_breaker_triggered_at = datetime.now()
                logger.warning(f"  ⚠️ CIRCUIT BREAKER TRIGGERED: {self.consecutive_losses} consecutive losses. "
                             f"Trading paused for {self.circuit_breaker_cooldown_hours}h.")
        else:
            # Reset consecutive losses on a win
            if self.consecutive_losses > 0:
                logger.info(f"  Win resets consecutive loss counter: {self.consecutive_losses} → 0")
            self.consecutive_losses = 0

    def log_performance(self):
        """Log current performance."""
        logger.info(f"\n📊 Performance:")
        logger.info(f"  Active Positions: {len(self.active_positions)}")
        logger.info(f"  Daily P&L: ${self.daily_pnl:.2f}")
        logger.info(f"  Trades Today: {len(self.trades_today)}")
        if self.circuit_breaker_active:
            logger.info(f"  ⚠️ Circuit Breaker: ACTIVE ({self.consecutive_losses} losses)")

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
    """Main entry point."""
    trader = PriceLevelTrader()
    trader.run()


if __name__ == '__main__':
    main()
