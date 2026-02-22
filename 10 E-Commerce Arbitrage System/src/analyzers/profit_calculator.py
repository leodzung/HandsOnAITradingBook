"""Profit calculator for Amazon arbitrage deals."""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class ProductSize(Enum):
    """Amazon FBA product size categories."""

    SMALL_STANDARD = "small_standard"
    LARGE_STANDARD = "large_standard"
    SMALL_OVERSIZE = "small_oversize"
    MEDIUM_OVERSIZE = "medium_oversize"
    LARGE_OVERSIZE = "large_oversize"
    SPECIAL_OVERSIZE = "special_oversize"


class ProductCategory(Enum):
    """Amazon product categories with different referral fees."""

    DEFAULT = "default"
    ELECTRONICS = "electronics"
    COMPUTERS = "computers"
    CAMERAS = "cameras"
    MUSICAL_INSTRUMENTS = "musical_instruments"
    TOYS_GAMES = "toys_games"
    BOOKS = "books"
    HOME_KITCHEN = "home_kitchen"
    SPORTS_OUTDOORS = "sports_outdoors"
    TOOLS = "tools"
    AUTOMOTIVE = "automotive"


# Amazon referral fee percentages by category
REFERRAL_FEES = {
    ProductCategory.DEFAULT: 0.15,
    ProductCategory.ELECTRONICS: 0.08,
    ProductCategory.COMPUTERS: 0.08,
    ProductCategory.CAMERAS: 0.08,
    ProductCategory.MUSICAL_INSTRUMENTS: 0.12,
    ProductCategory.TOYS_GAMES: 0.15,
    ProductCategory.BOOKS: 0.15,
    ProductCategory.HOME_KITCHEN: 0.15,
    ProductCategory.SPORTS_OUTDOORS: 0.15,
    ProductCategory.TOOLS: 0.15,
    ProductCategory.AUTOMOTIVE: 0.12,
}

# Amazon FBA fulfillment fees (2024 rates)
# Format: (weight_oz, length+girth): fee
FBA_FEES = {
    ProductSize.SMALL_STANDARD: {
        # Up to 10 oz, 15" L+W+H
        "6_oz": 3.22,
        "12_oz": 3.40,
    },
    ProductSize.LARGE_STANDARD: {
        # 10+ oz to 20 lbs, 18" L+W+H
        "4_oz": 3.86,
        "8_oz": 4.08,
        "12_oz": 4.24,
        "1_lb": 4.75,
        "1.5_lb": 5.40,
        "2_lb": 5.69,
        "2.5_lb": 6.10,
        "3_lb": 6.39,
        "20_lb": 9.73,
    },
    ProductSize.SMALL_OVERSIZE: {
        "70_lb": 9.73,
    },
    ProductSize.MEDIUM_OVERSIZE: {
        "150_lb": 19.05,
    },
    ProductSize.LARGE_OVERSIZE: {
        "150_lb": 89.98,
    },
}


@dataclass
class ProductDimensions:
    """Product physical dimensions."""

    length_inches: float
    width_inches: float
    height_inches: float
    weight_oz: float

    @property
    def weight_lbs(self) -> float:
        """Weight in pounds."""
        return self.weight_oz / 16

    @property
    def girth(self) -> float:
        """Calculate girth (L+W+H)."""
        return self.length_inches + self.width_inches + self.height_inches

    def get_size_tier(self) -> ProductSize:
        """Determine Amazon FBA size tier."""
        girth = self.girth

        if girth <= 15 and self.weight_oz <= 10:
            return ProductSize.SMALL_STANDARD
        elif girth <= 18 and self.weight_lbs <= 20:
            return ProductSize.LARGE_STANDARD
        elif girth <= 60 and self.weight_lbs <= 70:
            return ProductSize.SMALL_OVERSIZE
        elif girth <= 108 and self.weight_lbs <= 150:
            return ProductSize.MEDIUM_OVERSIZE
        elif self.weight_lbs <= 150:
            return ProductSize.LARGE_OVERSIZE
        else:
            return ProductSize.SPECIAL_OVERSIZE


@dataclass
class DealMetrics:
    """Calculated deal metrics."""

    # Prices
    source_price: float
    amazon_price: float

    # Fees
    referral_fee: float
    fba_fee: float
    storage_fee: float
    shipping_to_amazon: float
    prep_fee: float
    sales_tax: float

    # Totals
    total_cost: float
    total_fees: float
    net_profit: float

    # Metrics
    roi_percentage: float
    profit_margin: float

    # Additional
    breakeven_price: float

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "source_price": round(self.source_price, 2),
            "amazon_price": round(self.amazon_price, 2),
            "referral_fee": round(self.referral_fee, 2),
            "fba_fee": round(self.fba_fee, 2),
            "storage_fee": round(self.storage_fee, 2),
            "shipping_to_amazon": round(self.shipping_to_amazon, 2),
            "prep_fee": round(self.prep_fee, 2),
            "sales_tax": round(self.sales_tax, 2),
            "total_cost": round(self.total_cost, 2),
            "total_fees": round(self.total_fees, 2),
            "net_profit": round(self.net_profit, 2),
            "roi_percentage": round(self.roi_percentage, 2),
            "profit_margin": round(self.profit_margin, 2),
            "breakeven_price": round(self.breakeven_price, 2),
        }


class ProfitCalculator:
    """Calculates profit metrics for arbitrage deals."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize profit calculator.

        Args:
            config: Configuration dictionary with fee settings
        """
        self.config = config or {}

        # Default costs (can be overridden by config)
        self.default_shipping_to_amazon = self.config.get(
            "shipping_to_amazon_per_item", 2.50
        )
        self.default_prep_fee = self.config.get("prep_fee_per_item", 0.50)
        self.default_sales_tax = self.config.get("sales_tax_percent", 0.0)
        self.default_storage_monthly = self.config.get(
            "storage_per_cubic_ft_monthly", 0.83
        )

        # Return rate for expected value calculation
        self.average_return_rate = self.config.get("average_return_rate_percent", 2.0)

    def calculate_referral_fee(
        self, sale_price: float, category: ProductCategory = ProductCategory.DEFAULT
    ) -> float:
        """Calculate Amazon referral fee.

        Args:
            sale_price: Expected sale price on Amazon
            category: Product category

        Returns:
            Referral fee amount
        """
        fee_percentage = REFERRAL_FEES.get(category, REFERRAL_FEES[ProductCategory.DEFAULT])
        fee = sale_price * fee_percentage

        # Minimum referral fee is $0.30
        return max(fee, 0.30)

    def estimate_fba_fee(
        self, dimensions: Optional[ProductDimensions] = None, weight_oz: float = 16
    ) -> float:
        """Estimate FBA fulfillment fee.

        Args:
            dimensions: Product dimensions
            weight_oz: Weight in ounces (if dimensions not provided)

        Returns:
            Estimated FBA fee
        """
        if dimensions:
            size_tier = dimensions.get_size_tier()
            weight = dimensions.weight_lbs
        else:
            # Estimate based on weight only
            if weight_oz <= 10:
                return 3.40  # Small standard average
            elif weight_oz <= 16:
                return 4.75  # Large standard 1 lb
            elif weight_oz <= 32:
                return 5.69  # Large standard 2 lb
            else:
                # Rough estimate for heavier items
                return 4.75 + (weight_oz / 16 - 1) * 1.50

        # Get fee based on size tier and weight
        if size_tier == ProductSize.SMALL_STANDARD:
            return 3.40  # Average
        elif size_tier == ProductSize.LARGE_STANDARD:
            if weight <= 1:
                return 4.75
            elif weight <= 2:
                return 5.69
            elif weight <= 3:
                return 6.39
            else:
                return 9.73
        elif size_tier == ProductSize.SMALL_OVERSIZE:
            return 9.73
        elif size_tier == ProductSize.MEDIUM_OVERSIZE:
            return 19.05
        elif size_tier == ProductSize.LARGE_OVERSIZE:
            return 89.98
        else:
            return 100.00  # Special oversize estimate

    def estimate_storage_fee(
        self, dimensions: Optional[ProductDimensions] = None, months: int = 1
    ) -> float:
        """Estimate monthly storage fee.

        Args:
            dimensions: Product dimensions
            months: Number of months to store

        Returns:
            Estimated storage fee
        """
        if not dimensions:
            # Assume small item (0.5 cubic feet)
            cubic_feet = 0.5
        else:
            cubic_feet = (
                dimensions.length_inches
                * dimensions.width_inches
                * dimensions.height_inches
            ) / 1728  # Convert cubic inches to cubic feet

        monthly_fee = cubic_feet * self.default_storage_monthly
        return monthly_fee * months

    def calculate_profit(
        self,
        source_price: float,
        amazon_price: float,
        category: ProductCategory = ProductCategory.DEFAULT,
        dimensions: Optional[ProductDimensions] = None,
        weight_oz: float = 16,
        shipping_to_amazon: Optional[float] = None,
        prep_fee: Optional[float] = None,
        sales_tax: Optional[float] = None,
        storage_months: int = 1,
    ) -> DealMetrics:
        """Calculate comprehensive profit metrics.

        Args:
            source_price: Purchase price from source
            amazon_price: Expected selling price on Amazon
            category: Product category
            dimensions: Product dimensions
            weight_oz: Weight in ounces
            shipping_to_amazon: Shipping cost to Amazon warehouse
            prep_fee: Prep/labeling fee
            sales_tax: Sales tax on purchase
            storage_months: Expected months in storage

        Returns:
            DealMetrics object with all calculations
        """
        # Calculate fees
        referral_fee = self.calculate_referral_fee(amazon_price, category)
        fba_fee = self.estimate_fba_fee(dimensions, weight_oz)
        storage_fee = self.estimate_storage_fee(dimensions, storage_months)

        # Use defaults if not provided
        shipping = (
            shipping_to_amazon
            if shipping_to_amazon is not None
            else self.default_shipping_to_amazon
        )
        prep = prep_fee if prep_fee is not None else self.default_prep_fee

        if sales_tax is None:
            sales_tax = source_price * (self.default_sales_tax / 100)

        # Calculate totals
        total_cost = source_price + shipping + prep + sales_tax
        total_fees = referral_fee + fba_fee + storage_fee
        net_profit = amazon_price - total_cost - total_fees

        # Calculate metrics
        if total_cost > 0:
            roi_percentage = (net_profit / total_cost) * 100
        else:
            roi_percentage = 0

        if amazon_price > 0:
            profit_margin = (net_profit / amazon_price) * 100
        else:
            profit_margin = 0

        # Calculate breakeven price
        breakeven_price = total_cost + total_fees

        return DealMetrics(
            source_price=source_price,
            amazon_price=amazon_price,
            referral_fee=referral_fee,
            fba_fee=fba_fee,
            storage_fee=storage_fee,
            shipping_to_amazon=shipping,
            prep_fee=prep,
            sales_tax=sales_tax,
            total_cost=total_cost,
            total_fees=total_fees,
            net_profit=net_profit,
            roi_percentage=roi_percentage,
            profit_margin=profit_margin,
            breakeven_price=breakeven_price,
        )

    def is_profitable(
        self, metrics: DealMetrics, min_roi: float = 30.0, min_profit: float = 5.0
    ) -> bool:
        """Check if deal meets profitability thresholds.

        Args:
            metrics: Calculated deal metrics
            min_roi: Minimum ROI percentage
            min_profit: Minimum absolute profit

        Returns:
            True if deal is profitable
        """
        return metrics.roi_percentage >= min_roi and metrics.net_profit >= min_profit

    def calculate_expected_value(self, metrics: DealMetrics) -> float:
        """Calculate expected value accounting for return rate.

        Args:
            metrics: Calculated deal metrics

        Returns:
            Expected profit after accounting for returns
        """
        return_rate = self.average_return_rate / 100
        success_rate = 1 - return_rate

        # Expected value = (probability of success * profit) - (probability of return * cost)
        expected_profit = (success_rate * metrics.net_profit) - (
            return_rate * metrics.total_cost
        )

        return expected_profit
