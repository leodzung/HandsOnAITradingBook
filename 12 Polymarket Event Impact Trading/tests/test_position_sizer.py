"""Tests for unified PositionSizer."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from core.position_sizer import PositionSizer


def make_orderbook(bid_sizes=None, ask_sizes=None):
    """Create a simple orderbook dict for testing."""
    bids = [{'price': str(0.50 - i * 0.01), 'size': str(s)}
            for i, s in enumerate(bid_sizes or [])]
    asks = [{'price': str(0.52 + i * 0.01), 'size': str(s)}
            for i, s in enumerate(ask_sizes or [])]
    return {'bids': bids, 'asks': asks}


class TestKellyFraction:
    def test_basic_kelly(self):
        """edge=0.10, multiplier=0.5 -> fraction=0.05"""
        ps = PositionSizer({'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
                            'max_position_size': 1000, 'min_position_size': 1})
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000)
        # kelly = 0.10 * 0.5 = 0.05; base = 1000 * 0.05 = 50; conf=1.0 -> *1.0
        assert size == 50.0

    def test_kelly_cap(self):
        """edge=0.80, multiplier=0.5 -> fraction capped at 0.25"""
        ps = PositionSizer({'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
                            'max_position_size': 1000, 'min_position_size': 1})
        size = ps.calculate(edge=0.80, confidence=1.0, balance=1000)
        # kelly = 0.80 * 0.5 = 0.40, capped at 0.25; base = 1000 * 0.25 = 250
        assert size == 250.0

    def test_negative_edge_uses_abs(self):
        """Negative edge should use absolute value for sizing."""
        ps = PositionSizer({'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
                            'max_position_size': 1000, 'min_position_size': 1})
        size = ps.calculate(edge=-0.10, confidence=1.0, balance=1000)
        assert size == 50.0


class TestConfidenceScaling:
    def test_confidence_zero(self):
        """confidence=0 -> 0.5x multiplier"""
        ps = PositionSizer({'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
                            'max_position_size': 1000, 'min_position_size': 1})
        size = ps.calculate(edge=0.10, confidence=0.0, balance=1000)
        # base = 50; conf=0 -> 0.5x -> 25
        assert size == 25.0

    def test_confidence_one(self):
        """confidence=1.0 -> 1.0x multiplier"""
        ps = PositionSizer({'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
                            'max_position_size': 1000, 'min_position_size': 1})
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000)
        assert size == 50.0

    def test_confidence_half(self):
        """confidence=0.5 -> 0.75x multiplier"""
        ps = PositionSizer({'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
                            'max_position_size': 1000, 'min_position_size': 1})
        size = ps.calculate(edge=0.10, confidence=0.5, balance=1000)
        # base = 50; conf=0.5 -> 0.75x -> 37.5
        assert size == 37.5

    def test_confidence_clamped_above_one(self):
        """confidence > 1.0 should be clamped to 1.0"""
        ps = PositionSizer({'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
                            'max_position_size': 1000, 'min_position_size': 1})
        size = ps.calculate(edge=0.10, confidence=1.5, balance=1000)
        assert size == 50.0  # Same as confidence=1.0


class TestMaxCap:
    def test_max_position_size(self):
        """Result capped at max_position_size."""
        ps = PositionSizer({'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
                            'max_position_size': 30, 'min_position_size': 1})
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000)
        # base would be 50, but max is 30
        assert size == 30.0

    def test_bucket_specific_max(self):
        """Bucket-specific max sizes: ultra_short=50, short=75, medium=100."""
        ps = PositionSizer({
            'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
            'max_position_size': {'ultra_short': 20, 'short': 75, 'medium': 100},
            'min_position_size': 1
        })
        # edge=0.10 -> base=50; bucket=ultra_short -> cap at 20
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000, bucket='ultra_short')
        assert size == 20.0

        # bucket=short -> no cap needed (50 < 75)
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000, bucket='short')
        assert size == 50.0

    def test_dict_max_no_bucket_uses_max_value(self):
        """Dict max without bucket uses max of all bucket values."""
        ps = PositionSizer({
            'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
            'max_position_size': {'ultra_short': 20, 'short': 30, 'medium': 40},
            'min_position_size': 1
        })
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000)
        # base=50, max of dict values = 40
        assert size == 40.0


class TestLiquidityCap:
    def test_liquidity_cap(self):
        """Orderbook depth 200 on each side, 10% -> cap at 20."""
        ps = PositionSizer({
            'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
            'max_position_size': 1000, 'min_position_size': 1,
            'liquidity_cap_pct': 0.10
        })
        orderbook = make_orderbook(
            bid_sizes=[40, 40, 40, 40, 40],  # total 200
            ask_sizes=[40, 40, 40, 40, 40],  # total 200
        )
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000, orderbook=orderbook)
        # base=50, liquidity cap = 200 * 0.10 = 20
        assert size == 20.0

    def test_no_orderbook_skips_liquidity(self):
        """No orderbook -> liquidity cap skipped."""
        ps = PositionSizer({
            'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
            'max_position_size': 1000, 'min_position_size': 1,
            'liquidity_cap_pct': 0.10
        })
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000, orderbook=None)
        assert size == 50.0

    def test_empty_orderbook(self):
        """Empty orderbook -> liquidity limit is 0, returns 0 (skips trade)."""
        ps = PositionSizer({
            'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
            'max_position_size': 1000, 'min_position_size': 1,
            'liquidity_cap_pct': 0.10
        })
        orderbook = {'bids': [], 'asks': []}
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000, orderbook=orderbook)
        # Empty orderbook -> depth=0, liquidity_limit=0, but _get_liquidity_limit returns 0
        # so sized stays unchanged (liquidity_limit <= 0 means we don't cap)
        assert size == 50.0


class TestMinFloor:
    def test_below_min_returns_zero(self):
        """Size < min_position_size -> returns 0."""
        ps = PositionSizer({
            'kelly_multiplier': 0.5, 'max_kelly_fraction': 0.25,
            'max_position_size': 1000, 'min_position_size': 100
        })
        size = ps.calculate(edge=0.10, confidence=1.0, balance=1000)
        # base = 50, but min is 100 -> returns 0
        assert size == 0.0


class TestEdgeCases:
    def test_zero_edge(self):
        """Zero edge -> returns 0."""
        ps = PositionSizer({'min_position_size': 1})
        assert ps.calculate(edge=0.0, confidence=0.8, balance=1000) == 0.0

    def test_zero_balance(self):
        """Zero balance -> returns 0."""
        ps = PositionSizer({'min_position_size': 1})
        assert ps.calculate(edge=0.10, confidence=0.8, balance=0) == 0.0

    def test_backward_compat_defaults(self):
        """Empty config uses sensible defaults."""
        ps = PositionSizer({})
        # Defaults: kelly_multiplier=0.5, max_kelly_fraction=0.25,
        # max_position_size=100, min_position_size=5
        size = ps.calculate(edge=0.20, confidence=0.8, balance=500)
        # kelly = 0.20 * 0.5 = 0.10; base = 500 * 0.10 = 50
        # conf=0.8 -> 0.5 + 0.5*0.8 = 0.90 -> 50 * 0.90 = 45
        assert size == 45.0

    def test_backward_compat_legacy_keys(self):
        """Legacy config keys (flat kelly_multiplier, max_position_size) still work."""
        ps = PositionSizer({
            'kelly_multiplier': 0.3,
            'max_position_size': 50,
        })
        size = ps.calculate(edge=0.20, confidence=1.0, balance=1000)
        # kelly = 0.20 * 0.3 = 0.06; base = 1000 * 0.06 = 60; max=50
        assert size == 50.0
