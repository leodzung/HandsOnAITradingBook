#region imports
from AlgorithmImports import *
#endregion


class IPOCalendar(PythonData):
    """
    Custom data class for IPO calendar and pre-computed scores.

    This allows the algorithm to know which IPOs are listing today
    and what their pre-analysis scores are.

    CSV Format:
    date,ticker,company_name,score,offer_price,shares_offered,sector
    2024-12-10,ABNB,Airbnb Inc,0.85,68.00,51750000,Technology
    """

    def get_source(self, config, date, is_live_mode):
        """
        Return the URL or file path for the IPO calendar data.

        For live trading, you would point this to a regularly updated CSV file
        in Dropbox, S3, or your Object Store.
        """
        if is_live_mode:
            # In live mode, read from Object Store or external URL
            # You update this file weekly with upcoming IPOs
            return SubscriptionDataSource(
                "https://yourserver.com/ipo_calendar.csv",
                SubscriptionTransportMedium.REMOTE_FILE
            )
        else:
            # In backtesting, use local historical data
            source = f"data/ipo_scores.csv"
            return SubscriptionDataSource(source, SubscriptionTransportMedium.LOCAL_FILE)

    def reader(self, config, line, date, is_live_mode):
        """
        Parse each line of the CSV file.
        """
        if not (line.strip() and line[0].isdigit()):
            # Skip header and empty lines
            return None

        ipo = IPOCalendar()
        ipo.symbol = config.symbol

        try:
            data = line.split(',')

            # Parse the date
            ipo.time = datetime.strptime(data[0], "%Y-%m-%d")

            # Only process if this IPO is listing today
            if ipo.time.date() != date.date():
                return None

            # Parse IPO data
            ipo.ticker = data[1]
            ipo.company_name = data[2]
            ipo.score = float(data[3])
            ipo.offer_price = float(data[4])
            ipo.shares_offered = int(data[5])
            ipo.sector = data[6]

            # Set required fields
            ipo.value = ipo.score  # Use score as the "value"
            ipo.end_time = ipo.time + timedelta(days=1)

            return ipo

        except Exception as e:
            # Log parsing errors but don't crash
            return None


class IPOData:
    """
    Data class to store IPO metadata and scores.
    Used by the algorithm to make trading decisions.
    """

    def __init__(self, ticker, listing_date, score, offer_price, sector,
                 shares_offered=0, company_name=""):
        self.ticker = ticker
        self.listing_date = listing_date
        self.score = score
        self.offer_price = offer_price
        self.sector = sector
        self.shares_offered = shares_offered
        self.company_name = company_name
        self.entry_price = None
        self.entry_time = None
        self.exit_target_date = None

    def should_trade(self, threshold=0.70):
        """Check if score exceeds trading threshold."""
        return self.score >= threshold

    def calculate_position_size(self, base_size=0.15, vix_level=15):
        """
        Calculate position size based on score confidence and market conditions.

        Args:
            base_size: Base position size (15% default)
            vix_level: Current VIX level (reduce size if high)

        Returns:
            Position size as decimal (0.0-0.15)
        """
        # Scale by confidence
        confidence_factor = (self.score - 0.70) / 0.30  # 0.70-1.00 → 0-1

        # Reduce if VIX is high
        vix_factor = 1.0
        if vix_level > 20:
            vix_factor = 0.75
        if vix_level > 30:
            vix_factor = 0.50

        size = base_size * (0.5 + 0.5 * confidence_factor) * vix_factor
        return min(size, base_size)  # Cap at base size

    def __repr__(self):
        return f"IPO({self.ticker}, {self.listing_date.date()}, score={self.score:.2f})"
