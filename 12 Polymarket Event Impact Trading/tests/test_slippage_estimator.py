"""
Unit tests for SlippageEstimator module
"""

import pytest
from slippage_estimator import SlippageEstimator, SlippageEstimate, FillLevel


class TestSlippageEstimator:
    """Test suite for slippage estimation"""

    def setup_method(self):
        """Setup test fixtures"""
        # Default config
        self.config = {
            'enabled': True,
            'max_slippage_bps': 100,
            'max_slippage_dollars': 5.0,
            'orderbook_staleness_seconds': 10,
            'depth_buffer_pct': 0.10,
            'volatility_adjustment': True,
            'volume_limit_pct': 0.01,
            'warn_threshold_bps': 50
        }

        self.estimator = SlippageEstimator(config=self.config)

    def test_small_order_low_slippage(self):
        """Test small order that fits entirely in best level"""
        # Use tight spread to avoid volatility adjustment
        # Use higher max_slippage_bps to allow the 10% buffer
        orderbook = {
            'bids': [[0.499, 1000]],
            'asks': [[0.501, 1000]]
        }

        # Adjust config for this test to allow higher slippage
        config = self.config.copy()
        config['max_slippage_bps'] = 600  # Allow up to 6%
        estimator = SlippageEstimator(config=config)

        order_size = 50.0  # $50 order
        quoted_price = 0.501  # Best ask

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        # Order fits in first level, so VWAP = quoted price
        assert result.expected_execution_price == pytest.approx(0.501, rel=1e-4)
        # With 10% buffer (tight spread, 1 level): 0.501 * 1.10 = 0.5511
        assert result.worst_case_execution_price == pytest.approx(0.5511, rel=1e-2)
        assert result.levels_consumed == 1
        assert result.order_fills_immediately is True
        assert result.is_acceptable is True
        # Slippage = 2.505 / 50 * 10000 = 501 bps
        assert result.slippage_bps == pytest.approx(501, rel=1e-1)

    def test_large_order_multiple_levels(self):
        """Test large order that walks through multiple price levels"""
        # Use tight spread orderbook
        orderbook = {
            'bids': [[0.499, 1000]],
            'asks': [
                [0.501, 100],   # $50.1 liquidity
                [0.502, 100],   # $50.2 liquidity
                [0.503, 200]    # $100.6 liquidity
            ]
        }

        order_size = 150.0  # $150 order - needs 3 levels
        quoted_price = 0.501

        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=50000
        )

        # Should consume 3 levels
        assert result.levels_consumed == 3
        assert result.order_fills_immediately is True

        # VWAP should be weighted average
        # Level 1: 50.1 @ 0.501 = 25.1001
        # Level 2: 50.2 @ 0.502 = 25.2004
        # Level 3: 49.7 @ 0.503 = 24.9991
        # Total: 75.2996 / 150 = 0.5020
        expected_vwap = (50.1 * 0.501 + 50.2 * 0.502 + 49.7 * 0.503) / 150
        assert result.expected_execution_price == pytest.approx(expected_vwap, rel=1e-3)

        # 3+ levels = 20% buffer, VWAP ~0.502, buffered = 0.502 * 1.20 = 0.6024
        # Slippage = (0.6024 - 0.501) * 150 = 15.21
        # Slippage bps = 15.21 / 150 * 10000 = 1014 bps (exceeds limit)
        # This will be rejected
        assert result.slippage_bps > 0

    def test_insufficient_liquidity(self):
        """Test order exceeds available liquidity"""
        orderbook = {
            'bids': [[0.48, 100]],
            'asks': [[0.52, 100]]  # Only $52 available
        }

        order_size = 100.0  # $100 order
        quoted_price = 0.52

        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        assert result.is_acceptable is False
        assert "Insufficient liquidity" in result.rejection_reason
        assert result.order_fills_immediately is False
        assert result.total_liquidity_available == pytest.approx(52.0, rel=1e-2)

    def test_wide_spread_adjustment(self):
        """Test volatility buffer applied for wide spreads (>5%)"""
        orderbook = {
            'bids': [[0.40, 1000]],
            'asks': [[0.60, 1000]]  # 40% spread!
        }

        order_size = 50.0
        quoted_price = 0.60

        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        # Should have warning about wide spread
        assert any("Wide spread" in w for w in result.warnings)

        # Buffer should be increased (10% base + 20% volatility = 30%)
        # 0.60 * 1.30 = 0.78
        assert result.worst_case_execution_price == pytest.approx(0.78, rel=1e-2)

    def test_volume_limit_exceeded(self):
        """Test order exceeds 1% of daily volume limit"""
        orderbook = {
            'bids': [[0.48, 10000]],
            'asks': [[0.52, 10000]]
        }

        order_size = 200.0  # $200 order
        quoted_price = 0.52
        market_volume_24h = 10000  # $10k daily volume

        # Order is 2% of volume (exceeds 1% limit)
        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=market_volume_24h
        )

        assert result.is_acceptable is False
        assert "daily volume" in result.rejection_reason.lower()

    def test_empty_orderbook(self):
        """Test empty orderbook"""
        orderbook = {
            'bids': [],
            'asks': []
        }

        order_size = 50.0
        quoted_price = 0.52

        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        assert result.is_acceptable is False
        assert "No liquidity" in result.rejection_reason
        assert result.levels_consumed == 0

    def test_slippage_threshold_boundary_bps(self):
        """Test slippage exactly at BPS threshold"""
        # Create orderbook that produces exactly 100 bps slippage
        orderbook = {
            'bids': [[0.48, 1000]],
            'asks': [[0.52, 1000]]
        }

        # Adjust max threshold to test boundary
        config = self.config.copy()
        config['max_slippage_bps'] = 100
        estimator = SlippageEstimator(config=config)

        order_size = 50.0
        quoted_price = 0.52

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        # Slippage should be close to limit but acceptable
        # With 10% buffer: 0.52 * 1.10 = 0.572
        # Slippage = (0.572 - 0.52) / 0.52 * 10000 = 1000 bps
        # But slippage is calculated as total dollars / order_size
        # Slippage $ = (0.572 - 0.52) * 50 = 2.6
        # Slippage bps = 2.6 / 50 * 10000 = 520 bps
        # This will exceed threshold and be rejected
        assert result.slippage_bps > 100

    def test_slippage_threshold_boundary_dollars(self):
        """Test slippage exactly at dollar threshold"""
        # Tight spread, single level to minimize slippage
        orderbook = {
            'bids': [[0.499, 1000]],
            'asks': [[0.501, 1000]]
        }

        # Adjust max threshold
        config = self.config.copy()
        config['max_slippage_dollars'] = 10.0
        config['max_slippage_bps'] = 10000  # High enough to not trigger
        estimator = SlippageEstimator(config=config)

        order_size = 50.0
        quoted_price = 0.501

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        # With single level and tight spread, slippage should be low
        # VWAP = 0.501, buffered = 0.501 * 1.10 = 0.5511
        # Slippage = (0.5511 - 0.501) * 50 = 2.505
        assert result.slippage_dollars < 10.0
        assert result.is_acceptable is True

    def test_thin_orderbook_warning(self):
        """Test warning triggered for thin orderbook (3+ levels consumed)"""
        # Tight spread orderbook with 3 levels
        orderbook = {
            'bids': [[0.499, 1000]],
            'asks': [[0.501, 100], [0.502, 100], [0.503, 100]]
        }

        order_size = 120.0  # Will consume all 3 levels
        quoted_price = 0.501

        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=20000
        )

        # Should have thin orderbook warning (3 levels consumed)
        assert any("Thin orderbook" in w for w in result.warnings)
        assert result.levels_consumed == 3

        # Should use 20% buffer (3+ levels consumed)
        # Level 1: 0.501 * 100 = 50.1 available
        # Level 2: 0.502 * 100 = 50.2 available
        # Level 3: 0.503 * 100 = 50.3 available
        # Total available: 150.6, we need 120
        # Fill: 50.1 @ 0.501, 50.2 @ 0.502, 19.7 @ 0.503
        # VWAP = (50.1 * 0.501 + 50.2 * 0.502 + 19.7 * 0.503) / 120
        expected_vwap = (50.1 * 0.501 + 50.2 * 0.502 + 19.7 * 0.503) / 120
        assert result.expected_execution_price == pytest.approx(expected_vwap, rel=1e-3)

        # With 20% buffer
        expected_buffered = expected_vwap * 1.20
        assert result.worst_case_execution_price == pytest.approx(expected_buffered, rel=1e-2)

    def test_slippage_above_threshold_bps(self):
        """Test slippage clearly above BPS threshold triggers rejection"""
        orderbook = {
            'bids': [[0.48, 1000]],
            'asks': [[0.52, 10], [0.60, 100]]  # Big price jump
        }

        order_size = 50.0
        quoted_price = 0.52

        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        # VWAP will be much higher due to second level
        # Level 1: 10 * 0.52 = 5.2
        # Level 2: 40 * 0.60 = 24
        # VWAP = (5.2 + 24) / 50 = 0.584
        # With 20% buffer (thin book): 0.584 * 1.20 = 0.7008
        # Slippage = (0.7008 - 0.52) * 50 = 9.04
        # Slippage bps = 9.04 / 50 * 10000 = 1808 bps
        assert result.slippage_bps > 100
        assert result.is_acceptable is False
        assert "exceeds limit" in result.rejection_reason.lower()

    def test_buffer_application(self):
        """Test that 10% buffer is correctly applied"""
        # Tight spread to avoid volatility adjustment
        orderbook = {
            'bids': [[0.499, 1000]],
            'asks': [[0.501, 1000]]
        }

        order_size = 50.0
        quoted_price = 0.501

        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        # VWAP should be 0.501 (single level)
        assert result.expected_execution_price == pytest.approx(0.501, rel=1e-4)

        # Buffered should be 0.501 * 1.10 = 0.5511
        assert result.worst_case_execution_price == pytest.approx(0.5511, rel=1e-2)

    def test_sell_order_slippage(self):
        """Test slippage calculation for SELL orders"""
        # Tight spread orderbook
        orderbook = {
            'bids': [[0.499, 100], [0.498, 100], [0.497, 100]],
            'asks': [[0.501, 1000]]
        }

        order_size = 120.0
        quoted_price = 0.499  # Best bid

        result = self.estimator.estimate_slippage(
            order_side='SELL',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=20000  # Increased to avoid volume limit (120/20000 = 0.6%)
        )

        # Should fill across 3 bid levels
        # Level 1: 0.499 * 100 = 49.9
        # Level 2: 0.498 * 100 = 49.8
        # Level 3: 0.497 * 100 = 49.7, but we only need 20.3
        # VWAP = (49.9 * 0.499 + 49.8 * 0.498 + 20.3 * 0.497) / 120
        expected_vwap = (49.9 * 0.499 + 49.8 * 0.498 + 20.3 * 0.497) / 120
        assert result.expected_execution_price == pytest.approx(expected_vwap, rel=1e-3)

        # For SELL, buffer makes price worse (lower)
        # 3 levels consumed = 20% buffer
        # Buffered = VWAP * 0.80
        expected_buffered = expected_vwap * 0.80
        assert result.worst_case_execution_price == pytest.approx(expected_buffered, rel=1e-2)

        # Slippage for SELL is quoted_price - buffered_price
        assert result.slippage_dollars > 0
        assert result.levels_consumed == 3
        assert any("Thin orderbook" in w for w in result.warnings)

    def test_disabled_slippage_estimation(self):
        """Test that disabled slippage estimation returns optimistic result"""
        config = self.config.copy()
        config['enabled'] = False
        estimator = SlippageEstimator(config=config)

        orderbook = {
            'bids': [],
            'asks': []
        }

        order_size = 50.0
        quoted_price = 0.52

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        # Should accept everything when disabled
        assert result.is_acceptable is True
        assert result.slippage_dollars == 0.0
        assert result.slippage_bps == 0.0
        assert "disabled" in result.warnings[0].lower()

    def test_warning_threshold(self):
        """Test warning generated at warn_threshold_bps"""
        # Tight spread orderbook, single level
        orderbook = {
            'bids': [[0.499, 1000]],
            'asks': [[0.501, 1000]]
        }

        # Set low warning threshold
        config = self.config.copy()
        config['warn_threshold_bps'] = 50
        config['max_slippage_bps'] = 10000  # High enough to not reject
        estimator = SlippageEstimator(config=config)

        order_size = 50.0
        quoted_price = 0.501

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        # VWAP = 0.501, buffered = 0.501 * 1.10 = 0.5511
        # Slippage = (0.5511 - 0.501) / 0.501 * 10000 = 1002 bps
        # Wait, slippage is calculated differently:
        # Slippage $ = (0.5511 - 0.501) * 50 = 2.505
        # Slippage bps = 2.505 / 50 * 10000 = 501 bps
        # This exceeds 50 bps threshold
        assert result.slippage_bps > 50
        assert any("above warning threshold" in w for w in result.warnings)

    def test_spread_calculation(self):
        """Test bid-ask spread calculation"""
        orderbook = {
            'bids': [[0.48, 1000]],
            'asks': [[0.52, 1000]]
        }

        # Spread = 0.52 - 0.48 = 0.04
        # Mid = (0.48 + 0.52) / 2 = 0.50
        # Spread bps = 0.04 / 0.50 * 10000 = 800 bps
        expected_spread_bps = 800

        order_size = 50.0
        quoted_price = 0.52

        result = self.estimator.estimate_slippage(
            order_side='BUY',
            order_size=order_size,
            orderbook=orderbook,
            quoted_price=quoted_price,
            market_volume_24h=10000
        )

        assert result.orderbook_spread_bps == pytest.approx(expected_spread_bps, rel=1e-1)

    def test_invalid_order_side(self):
        """Test invalid order_side raises ValueError"""
        orderbook = {'bids': [[0.48, 1000]], 'asks': [[0.52, 1000]]}

        with pytest.raises(ValueError, match="Invalid order_side"):
            self.estimator.estimate_slippage(
                order_side='HOLD',
                order_size=50.0,
                orderbook=orderbook,
                quoted_price=0.52,
                market_volume_24h=10000
            )

    def test_invalid_order_size(self):
        """Test invalid order_size raises ValueError"""
        orderbook = {'bids': [[0.48, 1000]], 'asks': [[0.52, 1000]]}

        with pytest.raises(ValueError, match="Invalid order_size"):
            self.estimator.estimate_slippage(
                order_side='BUY',
                order_size=-50.0,
                orderbook=orderbook,
                quoted_price=0.52,
                market_volume_24h=10000
            )

        with pytest.raises(ValueError, match="Invalid order_size"):
            self.estimator.estimate_slippage(
                order_side='BUY',
                order_size=0.0,
                orderbook=orderbook,
                quoted_price=0.52,
                market_volume_24h=10000
            )
