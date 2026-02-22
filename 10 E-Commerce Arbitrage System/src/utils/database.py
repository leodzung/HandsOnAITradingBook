"""Database models and operations for the arbitrage system."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    Text,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

Base = declarative_base()


class Deal(Base):
    """Represents a potential arbitrage deal."""

    __tablename__ = "deals"

    id = Column(Integer, primary_key=True)

    # Product Information
    asin = Column(String(20), nullable=False, index=True)
    product_title = Column(String(500), nullable=False)
    brand = Column(String(200))
    category = Column(String(200))
    product_url = Column(String(1000))
    image_url = Column(String(1000))

    # Source Information
    source = Column(String(50), nullable=False)  # amazon, walmart, wholesale, etc.
    source_url = Column(String(1000))
    source_price = Column(Float, nullable=False)
    source_shipping = Column(Float, default=0.0)
    source_availability = Column(String(50))

    # Amazon Marketplace Data
    amazon_price = Column(Float)
    amazon_fba_price = Column(Float)  # Lowest FBA price
    num_sellers = Column(Integer)
    num_fba_sellers = Column(Integer)
    sales_rank = Column(Integer)
    sales_rank_category = Column(String(200))

    # Profit Metrics
    estimated_profit = Column(Float)
    roi_percentage = Column(Float)
    profit_margin = Column(Float)

    # Fees & Costs
    amazon_referral_fee = Column(Float)
    amazon_fba_fee = Column(Float)
    storage_fee = Column(Float)
    shipping_cost = Column(Float)
    total_fees = Column(Float)

    # Product Metrics
    review_count = Column(Integer)
    average_rating = Column(Float)
    weight_oz = Column(Float)
    dimensions = Column(String(100))

    # Risk Indicators
    price_volatility_score = Column(Float)
    rank_volatility_score = Column(Float)
    competition_score = Column(Float)
    overall_risk_score = Column(Float)

    # Status
    status = Column(
        String(20), default="new"
    )  # new, reviewed, purchased, rejected, expired
    flagged = Column(Boolean, default=False)
    flag_reason = Column(Text)

    # Timestamps
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    purchased_at = Column(DateTime)

    # Indexes
    __table_args__ = (
        Index("idx_roi", "roi_percentage"),
        Index("idx_profit", "estimated_profit"),
        Index("idx_status", "status"),
        Index("idx_source", "source"),
        Index("idx_first_seen", "first_seen"),
    )

    def __repr__(self):
        return f"<Deal(asin={self.asin}, title={self.product_title[:30]}, roi={self.roi_percentage:.1f}%)>"


class PriceHistory(Base):
    """Tracks historical prices for products."""

    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)
    asin = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    availability = Column(String(50))
    num_sellers = Column(Integer)
    sales_rank = Column(Integer)

    __table_args__ = (Index("idx_asin_timestamp", "asin", "timestamp"),)

    def __repr__(self):
        return f"<PriceHistory(asin={self.asin}, price={self.price}, source={self.source})>"


class ScanLog(Base):
    """Logs scan operations and their results."""

    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True)
    scanner_name = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(20))  # success, failed, partial
    products_scanned = Column(Integer, default=0)
    deals_found = Column(Integer, default=0)
    errors_encountered = Column(Integer, default=0)
    error_message = Column(Text)

    def __repr__(self):
        return f"<ScanLog(scanner={self.scanner_name}, deals_found={self.deals_found})>"


class Purchase(Base):
    """Tracks purchased items and their performance."""

    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, nullable=False, index=True)
    asin = Column(String(20), nullable=False)

    # Purchase details
    purchased_at = Column(DateTime, default=datetime.utcnow)
    purchase_price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    source = Column(String(50))
    order_id = Column(String(100))

    # Fulfillment
    received_at = Column(DateTime)
    listed_at = Column(DateTime)
    sold_at = Column(DateTime)
    sale_price = Column(Float)

    # Actual costs (versus estimates)
    actual_shipping = Column(Float)
    actual_prep_cost = Column(Float)
    actual_amazon_fees = Column(Float)
    actual_storage_fees = Column(Float)

    # Performance
    actual_profit = Column(Float)
    actual_roi = Column(Float)
    days_to_sell = Column(Integer)

    # Status
    status = Column(
        String(20), default="ordered"
    )  # ordered, received, listed, sold, returned
    notes = Column(Text)

    def __repr__(self):
        return f"<Purchase(asin={self.asin}, status={self.status}, profit={self.actual_profit})>"


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, database_url: str = "sqlite:///data/deals.db"):
        """Initialize database connection.

        Args:
            database_url: SQLAlchemy database URL
        """
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.create_tables()

    def create_tables(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Session:
        """Get a database session context manager."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_deal(self, deal_data: dict) -> Deal:
        """Add a new deal to the database.

        Args:
            deal_data: Dictionary containing deal information

        Returns:
            Created Deal object
        """
        with self.get_session() as session:
            deal = Deal(**deal_data)
            session.add(deal)
            session.flush()
            return deal

    def update_deal(self, asin: str, source: str, updates: dict) -> Optional[Deal]:
        """Update an existing deal.

        Args:
            asin: Product ASIN
            source: Deal source
            updates: Dictionary of fields to update

        Returns:
            Updated Deal object or None
        """
        with self.get_session() as session:
            deal = (
                session.query(Deal)
                .filter(Deal.asin == asin, Deal.source == source)
                .first()
            )
            if deal:
                for key, value in updates.items():
                    setattr(deal, key, value)
                deal.last_updated = datetime.utcnow()
                session.flush()
                return deal
            return None

    def get_active_deals(
        self, min_roi: float = 0, limit: int = 100
    ) -> List[Deal]:
        """Get active deals sorted by ROI.

        Args:
            min_roi: Minimum ROI percentage
            limit: Maximum number of deals to return

        Returns:
            List of Deal objects
        """
        with self.get_session() as session:
            deals = (
                session.query(Deal)
                .filter(Deal.status == "new", Deal.roi_percentage >= min_roi)
                .order_by(Deal.roi_percentage.desc())
                .limit(limit)
                .all()
            )
            return deals

    def add_price_history(self, price_data: dict):
        """Add price history entry.

        Args:
            price_data: Dictionary containing price information
        """
        with self.get_session() as session:
            price_entry = PriceHistory(**price_data)
            session.add(price_entry)

    def get_price_history(
        self, asin: str, days: int = 30
    ) -> List[PriceHistory]:
        """Get price history for a product.

        Args:
            asin: Product ASIN
            days: Number of days of history

        Returns:
            List of PriceHistory objects
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            history = (
                session.query(PriceHistory)
                .filter(
                    PriceHistory.asin == asin, PriceHistory.timestamp >= cutoff_date
                )
                .order_by(PriceHistory.timestamp.desc())
                .all()
            )
            return history

    def log_scan(self, log_data: dict) -> ScanLog:
        """Log a scan operation.

        Args:
            log_data: Dictionary containing scan log information

        Returns:
            Created ScanLog object
        """
        with self.get_session() as session:
            log = ScanLog(**log_data)
            session.add(log)
            session.flush()
            return log

    def cleanup_old_deals(self, days: int = 30):
        """Remove deals older than specified days.

        Args:
            days: Number of days to keep
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            session.query(Deal).filter(Deal.first_seen < cutoff_date).delete()


from datetime import timedelta
