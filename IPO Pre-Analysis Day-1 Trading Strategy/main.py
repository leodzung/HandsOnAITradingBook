#region imports
from AlgorithmImports import *
from ipocalendar import IPOCalendar, IPOData
from datetime import timedelta
import json
#endregion


class IPOPreAnalysisDayOneAlgorithm(QCAlgorithm):
    """
    IPO Pre-Analysis + Day-1 Trading Strategy

    This algorithm:
    1. Monitors for new IPO listings daily
    2. Uses pre-computed scores from research.ipynb
    3. Executes trades on Day 1 based on high-confidence signals
    4. Manages positions with time-based and profit/loss targets

    Strategy Logic:
    - Only trade IPOs with pre-analysis score > 0.70
    - Enter after first hour of trading (avoid opening volatility)
    - Hold for 30 days or until profit/stop targets hit
    - Max 5 concurrent IPO positions
    - Max 15% per position, 40% total in IPOs
    """

    def initialize(self):
        """Initialize algorithm parameters and data structures."""

        # Set backtest period
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)

        # Strategy parameters (configurable)
        self._score_threshold = self.get_parameter("score_threshold", 0.70)
        self._max_positions = self.get_parameter("max_positions", 5)
        self._max_position_size = self.get_parameter("max_position_size", 0.15)
        self._max_ipo_exposure = self.get_parameter("max_ipo_exposure", 0.40)
        self._holding_period_days = self.get_parameter("holding_period", 30)
        self._profit_target = self.get_parameter("profit_target", 0.30)
        self._stop_loss = self.get_parameter("stop_loss", -0.20)

        # Track IPO positions
        self._ipo_positions = {}  # symbol -> IPOData
        self._pending_exits = {}  # symbol -> exit_date

        # Add VIX for market condition monitoring
        self._vix = self.add_index("VIX", Resolution.DAILY).symbol

        # Add SPY for market benchmark
        self._spy = self.add_equity("SPY", Resolution.DAILY).symbol

        # Schedule daily IPO check and position management
        self.schedule.on(
            self.date_rules.every_day("SPY"),
            self.time_rules.after_market_open("SPY", 60),  # Wait 1 hour after open
            self._check_for_new_ipos
        )

        self.schedule.on(
            self.date_rules.every_day("SPY"),
            self.time_rules.after_market_open("SPY", 120),  # 2 hours after open
            self._manage_positions
        )

        # Load pre-computed IPO scores from Object Store
        self._load_ipo_calendar()

        self.log(f"IPO Day-1 Trading Strategy initialized")
        self.log(f"Score threshold: {self._score_threshold}")
        self.log(f"Max positions: {self._max_positions}")
        self.log(f"Holding period: {self._holding_period_days} days")

    def _load_ipo_calendar(self):
        """Load upcoming IPO calendar with pre-computed scores."""
        self._ipo_calendar = {}

        if self.live_mode and self.object_store.contains_key("ipo_calendar"):
            # Load from Object Store in live trading
            calendar_csv = self.object_store.read("ipo_calendar")

            # Parse CSV
            import pandas as pd
            from io import StringIO
            df = pd.read_csv(StringIO(calendar_csv))

            for _, row in df.iterrows():
                ticker = row['ticker']
                self._ipo_calendar[ticker] = IPOData(
                    ticker=ticker,
                    listing_date=datetime.strptime(row['date'], '%Y-%m-%d'),
                    score=row['score'],
                    offer_price=row['offer_price'],
                    sector=row['sector'],
                    shares_offered=row['shares_offered'],
                    company_name=row['company_name']
                )

            self.log(f"Loaded {len(self._ipo_calendar)} upcoming IPOs from calendar")
        else:
            # In backtest mode, would need historical IPO data
            # For now, using manual entry
            self.log("No IPO calendar found. Add IPOs manually via _ipo_calendar")

    def _check_for_new_ipos(self):
        """
        Check if any IPOs from the calendar are listing today.
        Execute trades for high-confidence opportunities.
        """
        # Check each ticker in the calendar
        for ticker, ipo_data in list(self._ipo_calendar.items()):
            # Is this IPO listing today?
            if ipo_data.listing_date.date() != self.time.date():
                continue

            # Already have a position?
            if ticker in self._ipo_positions:
                continue

            # Check if we should trade this IPO
            if not ipo_data.should_trade(self._score_threshold):
                self.log(f"IPO {ticker} score {ipo_data.score:.2f} below threshold {self._score_threshold}")
                continue

            # Check position limits
            if len(self._ipo_positions) >= self._max_positions:
                self.log(f"Max positions ({self._max_positions}) reached. Skipping {ticker}")
                continue

            # Check if we have room for more IPO exposure
            current_ipo_exposure = sum(
                self.portfolio[symbol].holdings_value / self.portfolio.total_portfolio_value
                for symbol in self._ipo_positions.keys()
                if self.portfolio[symbol].invested
            )

            if current_ipo_exposure >= self._max_ipo_exposure:
                self.log(f"Max IPO exposure ({self._max_ipo_exposure:.0%}) reached. Skipping {ticker}")
                continue

            # Try to add the security
            try:
                symbol = self.add_equity(ticker, Resolution.MINUTE).symbol
            except Exception as e:
                self.log(f"Could not add {ticker}: {e}")
                continue

            # Get current VIX level
            vix_level = self._get_vix_level()

            # Calculate position size
            position_size = ipo_data.calculate_position_size(
                base_size=self._max_position_size,
                vix_level=vix_level
            )

            # Execute trade
            self._enter_ipo_position(symbol, ipo_data, position_size)

    def _enter_ipo_position(self, symbol, ipo_data, position_size):
        """
        Enter a new IPO position.

        Args:
            symbol: QuantConnect Symbol
            ipo_data: IPOData object
            position_size: Target position size (decimal)
        """
        # Use limit order at current price + 2% to avoid extreme slippage
        current_price = self.securities[symbol].price

        if current_price == 0:
            self.log(f"Invalid price for {symbol}. Skipping.")
            return

        limit_price = current_price * 1.02

        # Calculate quantity
        target_value = self.portfolio.total_portfolio_value * position_size
        quantity = int(target_value / limit_price)

        if quantity == 0:
            self.log(f"Calculated quantity is 0 for {symbol}. Skipping.")
            return

        # Place limit order
        ticket = self.limit_order(symbol, quantity, limit_price)

        # Store position data
        ipo_data.entry_price = limit_price
        ipo_data.entry_time = self.time
        ipo_data.exit_target_date = self.time + timedelta(days=self._holding_period_days)
        self._ipo_positions[symbol] = ipo_data

        # Schedule exit
        self._pending_exits[symbol] = ipo_data.exit_target_date

        self.log(
            f"ENTRY: {symbol} | Score: {ipo_data.score:.2f} | "
            f"Size: {position_size:.1%} | Qty: {quantity} | "
            f"Limit: ${limit_price:.2f} | Hold until: {ipo_data.exit_target_date.date()}"
        )

        # Set tags for tracking
        self.plot("IPO Positions", "Active Positions", len(self._ipo_positions))
        self.plot("IPO Scores", symbol.value, ipo_data.score)

    def _manage_positions(self):
        """
        Manage existing IPO positions:
        1. Check profit targets
        2. Check stop losses
        3. Check time-based exits
        """
        for symbol, ipo_data in list(self._ipo_positions.items()):
            # Skip if not invested
            if not self.portfolio[symbol].invested:
                continue

            holding = self.portfolio[symbol]
            current_return = holding.unrealized_profit_percent

            # Check profit target (close 50% of position)
            if current_return >= self._profit_target:
                self._partial_exit(symbol, 0.5, f"Profit target {self._profit_target:.0%} hit")
                continue

            # Check stop loss
            if current_return <= self._stop_loss:
                self._full_exit(symbol, f"Stop loss {self._stop_loss:.0%} hit")
                continue

            # Check time-based exit
            if self.time >= ipo_data.exit_target_date:
                self._full_exit(symbol, f"Holding period {self._holding_period_days} days reached")
                continue

            # Log current status
            days_held = (self.time - ipo_data.entry_time).days
            self.debug(
                f"HOLDING: {symbol} | Days: {days_held} | "
                f"Return: {current_return:.1%} | Target: {ipo_data.exit_target_date.date()}"
            )

    def _partial_exit(self, symbol, fraction, reason):
        """
        Exit a partial position.

        Args:
            symbol: Symbol to exit
            fraction: Fraction to sell (0-1)
            reason: Reason for exit
        """
        holding = self.portfolio[symbol]
        quantity_to_sell = int(holding.quantity * fraction)

        if quantity_to_sell == 0:
            return

        self.liquidate(symbol, quantity=quantity_to_sell, tag=reason)

        current_return = holding.unrealized_profit_percent
        ipo_data = self._ipo_positions[symbol]

        self.log(
            f"PARTIAL EXIT: {symbol} | Sold {fraction:.0%} | "
            f"Return: {current_return:.1%} | Reason: {reason}"
        )

    def _full_exit(self, symbol, reason):
        """
        Exit a full position.

        Args:
            symbol: Symbol to exit
            reason: Reason for exit
        """
        holding = self.portfolio[symbol]
        current_return = holding.unrealized_profit_percent
        ipo_data = self._ipo_positions[symbol]

        days_held = (self.time - ipo_data.entry_time).days

        # Liquidate
        self.liquidate(symbol, tag=reason)

        # Log exit
        self.log(
            f"FULL EXIT: {symbol} | Days held: {days_held} | "
            f"Return: {current_return:.1%} | Reason: {reason} | "
            f"Score was: {ipo_data.score:.2f}"
        )

        # Remove from active positions
        del self._ipo_positions[symbol]
        if symbol in self._pending_exits:
            del self._pending_exits[symbol]

        self.plot("IPO Positions", "Active Positions", len(self._ipo_positions))

    def _get_vix_level(self):
        """Get current VIX level for risk adjustment."""
        vix_history = self.history(self._vix, 1, Resolution.DAILY)
        if vix_history.empty:
            return 15  # Default
        return vix_history['close'].iloc[-1]

    def on_data(self, data):
        """
        Process incoming data.

        This is mainly for monitoring. Most trading logic is scheduled.
        """
        pass

    def on_order_event(self, order_event):
        """Track order fills."""
        if order_event.status != OrderStatus.FILLED:
            return

        order = self.transactions.get_order_by_id(order_event.order_id)

        self.debug(
            f"ORDER FILLED: {order_event.symbol} | "
            f"Qty: {order_event.fill_quantity} | "
            f"Price: ${order_event.fill_price:.2f} | "
            f"Direction: {order.direction}"
        )

    def on_end_of_algorithm(self):
        """Final statistics at end of backtest."""
        self.log("=" * 50)
        self.log("IPO Day-1 Trading Strategy - Final Report")
        self.log("=" * 50)

        total_trades = len(self.transactions.get_orders())
        self.log(f"Total orders placed: {total_trades}")

        self.log(f"Final portfolio value: ${self.portfolio.total_portfolio_value:,.2f}")
        self.log(f"Total return: {self.portfolio.total_unrealized_profit_percent:.2%}")

        # Summary of active positions
        if self._ipo_positions:
            self.log(f"\nActive positions at end: {len(self._ipo_positions)}")
            for symbol, ipo_data in self._ipo_positions.items():
                if self.portfolio[symbol].invested:
                    ret = self.portfolio[symbol].unrealized_profit_percent
                    self.log(f"  {symbol}: {ret:.1%} return")
