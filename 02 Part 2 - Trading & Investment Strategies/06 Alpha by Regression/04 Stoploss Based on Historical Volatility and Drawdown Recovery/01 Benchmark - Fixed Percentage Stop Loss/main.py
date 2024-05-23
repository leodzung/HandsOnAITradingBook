# region imports
from AlgorithmImports import *
# endregion


class CaseOfTheMondaysAlgorithm(QCAlgorithm):
    """
    This algorithm serves as the benchmark for Parts 2 and 3. This 
    version simply buys 100 shares of AAPL and places a stop market 
    order x% below the current price at 9:32 AM on the first trading
    day of each week. If stop loss isn't hit, the algorithm 
    automatically cancels it and liquidates the position with a market 
    on open order at the start of the following week. If you run an 
    optimization job with this algorithm, the notebook shows how the 
    stop loss percentage `x` affects the trading results.
    """

    def initialize(self):
        self.set_start_date(2018, 12, 31)
        self.set_end_date(2024, 4, 1)
        self.set_cash(100_000)
        self._security = self.add_equity(
            "AAPL", data_normalization_mode=DataNormalizationMode.RAW
        )
        self._symbol = self._security.symbol
        
        self._stop_loss_percent = self.get_parameter("stop_loss_percent", 0.99)
        self._quantity = 100

        date_rule = self.date_rules.week_start(self._symbol)
        self.schedule.on(
            date_rule, 
            self.time_rules.after_market_open(self._symbol, 2), 
            self._enter
        )
        self.schedule.on(
            date_rule, 
            self.time_rules.after_market_open(self._symbol, -30), 
            self.liquidate
        )

    def _enter(self):
        self.market_order(self._symbol, self._quantity)
        self.stop_market_order(
            self._symbol, -self._quantity, 
            round(self._security.price * self._stop_loss_percent, 2)
        )

