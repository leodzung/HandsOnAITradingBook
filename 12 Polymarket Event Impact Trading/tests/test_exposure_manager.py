"""
Unit tests for ExposureManager (src/core/exposure_manager.py).

Tests the 6-layer portfolio concentration defense system:
  Layer 1: Per-asset position count
  Layer 2: Per-asset capital exposure
  Layer 3: Directional balance (warn-only)
  Layer 4: Strike clustering (warn-only)
  Layer 5: Expiry concentration (warn-only)
  Layer 6: Total portfolio limits

Key API:
  ExposureManager(config: Dict)
  .analyze_exposure(positions, total_capital) -> Dict
  .can_open_position(new_position, existing_positions, total_capital) -> (bool, str, list)
  .get_rebalance_suggestions(positions, total_capital) -> list[str]
  .format_exposure_report(positions, total_capital) -> str
"""

import pytest
import json
from datetime import datetime, timezone, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.exposure_manager import ExposureManager


# ---- Helpers ----

def make_position(asset='BTC', size=50, side='YES', strike_price=100000,
                  expiry_date=None, metadata=None):
    """Create a test position dict matching PositionManager format."""
    if metadata is None:
        metadata = {
            'asset': asset,
            'strike_price': strike_price,
            'expiry_date': expiry_date,
        }
    return {
        'size': size,
        'side': side,
        'metadata': metadata,
    }


def make_new_position(asset='BTC', size=50, outcome='YES', strike_price=100000,
                      expiry_date=None):
    """Create a new_position dict for can_open_position()."""
    return {
        'asset': asset,
        'size': size,
        'outcome': outcome,
        'strike_price': strike_price,
        'expiry_date': expiry_date,
    }


# ---- Tests: analyze_exposure ----

class TestAnalyzeExposure:
    """Tests for ExposureManager.analyze_exposure()."""

    def test_empty_positions(self):
        em = ExposureManager()
        analysis = em.analyze_exposure([], 1000)
        assert analysis['total_positions'] == 0
        assert analysis['total_deployed'] == 0
        assert len(analysis['by_asset']) == 0

    def test_single_position(self):
        em = ExposureManager()
        positions = [make_position(asset='BTC', size=100, side='YES')]
        analysis = em.analyze_exposure(positions, 1000)
        assert analysis['total_positions'] == 1
        assert analysis['total_deployed'] == 100
        assert analysis['deployed_pct'] == 0.1
        assert analysis['by_asset']['BTC']['count'] == 1
        assert analysis['by_asset']['BTC']['capital'] == 100
        assert analysis['by_asset']['BTC']['bullish_count'] == 1
        assert analysis['by_asset']['BTC']['bearish_count'] == 0

    def test_multiple_positions_multiple_assets(self):
        em = ExposureManager()
        positions = [
            make_position(asset='BTC', size=100, side='YES'),
            make_position(asset='BTC', size=50, side='NO'),
            make_position(asset='ETH', size=200, side='YES'),
        ]
        analysis = em.analyze_exposure(positions, 1000)
        assert analysis['total_positions'] == 3
        assert analysis['total_deployed'] == 350
        assert analysis['by_asset']['BTC']['count'] == 2
        assert analysis['by_asset']['BTC']['bullish_count'] == 1
        assert analysis['by_asset']['BTC']['bearish_count'] == 1
        assert analysis['by_asset']['ETH']['count'] == 1

    def test_json_string_metadata(self):
        """Metadata stored as JSON string (from SQLite) should be parsed correctly."""
        em = ExposureManager()
        positions = [{
            'size': 75,
            'side': 'YES',
            'metadata': json.dumps({'asset': 'SOL', 'strike_price': 200}),
        }]
        analysis = em.analyze_exposure(positions, 1000)
        assert analysis['by_asset']['SOL']['count'] == 1

    def test_invalid_json_metadata_falls_back(self):
        """Invalid JSON metadata should not crash."""
        em = ExposureManager()
        positions = [{
            'size': 50,
            'side': 'YES',
            'metadata': 'not valid json {{{',
        }]
        analysis = em.analyze_exposure(positions, 1000)
        assert analysis['by_asset']['UNKNOWN']['count'] == 1

    def test_deployed_pct_calculation(self):
        em = ExposureManager()
        positions = [
            make_position(size=250),
            make_position(size=250),
        ]
        analysis = em.analyze_exposure(positions, 1000)
        assert analysis['deployed_pct'] == 0.5

    def test_expiry_week_grouping(self):
        em = ExposureManager()
        # Two positions expiring in the same week
        next_monday = datetime.now(timezone.utc) + timedelta(days=7)
        next_tuesday = next_monday + timedelta(days=1)
        positions = [
            make_position(expiry_date=next_monday.isoformat()),
            make_position(expiry_date=next_tuesday.isoformat()),
        ]
        analysis = em.analyze_exposure(positions, 1000)
        # Both should be in the same week key
        assert len(analysis['expiry_weeks']) == 1
        week_key = list(analysis['expiry_weeks'].keys())[0]
        assert analysis['expiry_weeks'][week_key] == 2

    def test_zero_capital_no_crash(self):
        """Zero capital should not cause division by zero."""
        em = ExposureManager()
        positions = [make_position(size=100)]
        analysis = em.analyze_exposure(positions, 0)
        assert analysis['total_positions'] == 1
        assert 'deployed_pct' not in analysis


# ---- Tests: can_open_position ----

class TestCanOpenPosition:
    """Tests for ExposureManager.can_open_position()."""

    def test_allows_first_position(self):
        em = ExposureManager()
        new_pos = make_new_position(asset='BTC', size=50)
        can_open, reason, warnings = em.can_open_position(new_pos, [], 1000)
        assert can_open is True
        assert reason == "OK"
        assert warnings == []

    def test_blocks_per_asset_count(self):
        """Layer 1: Block when max positions per asset reached."""
        em = ExposureManager({'max_positions_per_asset': 2})
        existing = [
            make_position(asset='BTC', size=50),
            make_position(asset='BTC', size=50),
        ]
        new_pos = make_new_position(asset='BTC', size=50)
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 1000)
        assert can_open is False
        assert 'Max BTC positions' in reason

    def test_blocks_per_asset_capital(self):
        """Layer 2: Block when capital per asset exceeded."""
        em = ExposureManager({'max_capital_per_asset_pct': 0.30})
        existing = [make_position(asset='BTC', size=250)]
        new_pos = make_new_position(asset='BTC', size=100)
        # 350/1000 = 35% > 30%
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 1000)
        assert can_open is False
        assert 'capital exposure' in reason.lower()

    def test_warns_directional_imbalance(self):
        """Layer 3: Directional imbalance warns but does NOT block."""
        em = ExposureManager({'max_same_direction_pct': 0.50,
                              'max_positions_per_asset': 10,
                              'max_capital_per_asset_pct': 1.0})
        existing = [
            make_position(asset='BTC', size=50, side='YES'),
            make_position(asset='BTC', size=50, side='YES'),
        ]
        new_pos = make_new_position(asset='BTC', size=50, outcome='YES')
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 10000)
        # Should allow (Layer 3 is warn-only) but produce warning
        assert can_open is True
        assert any('bullish' in w.lower() or 'bearish' in w.lower() for w in warnings)

    def test_warns_strike_clustering(self):
        """Layer 4: Strike clustering warns but does NOT block."""
        em = ExposureManager({
            'min_strike_distance_pct': 0.10,
            'max_positions_per_asset': 10,
            'max_capital_per_asset_pct': 1.0,
        })
        existing = [make_position(asset='BTC', size=50, strike_price=100000)]
        new_pos = make_new_position(asset='BTC', size=50, strike_price=105000)
        # 5% distance < 10% threshold -> warning
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 10000)
        assert can_open is True
        assert any('close to' in w.lower() or 'strike' in w.lower() for w in warnings)

    def test_warns_expiry_concentration(self):
        """Layer 5: Expiry concentration warns but does NOT block."""
        em = ExposureManager({
            'max_positions_same_expiry_week': 1,
            'max_positions_per_asset': 10,
            'max_capital_per_asset_pct': 1.0,
        })
        expiry = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        existing = [make_position(asset='BTC', size=50, expiry_date=expiry)]
        new_pos = make_new_position(asset='BTC', size=50, expiry_date=expiry)
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 10000)
        assert can_open is True
        assert any('expir' in w.lower() for w in warnings)

    def test_blocks_total_positions(self):
        """Layer 6: Block when max total positions reached."""
        em = ExposureManager({'max_total_positions': 2,
                              'max_positions_per_asset': 10,
                              'max_capital_per_asset_pct': 1.0})
        existing = [
            make_position(asset='BTC', size=10),
            make_position(asset='ETH', size=10),
        ]
        new_pos = make_new_position(asset='SOL', size=10)
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 10000)
        assert can_open is False
        assert 'total positions' in reason.lower()

    def test_blocks_total_capital_deployed(self):
        """Layer 6: Block when max capital deployed exceeded."""
        em = ExposureManager({
            'max_capital_deployed_pct': 0.50,
            'max_positions_per_asset': 10,
            'max_capital_per_asset_pct': 1.0,
            'max_total_positions': 100,
        })
        existing = [make_position(asset='BTC', size=400)]
        new_pos = make_new_position(asset='ETH', size=200)
        # 600/1000 = 60% > 50%
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 1000)
        assert can_open is False
        assert 'capital deployed' in reason.lower()

    def test_soft_mode_allows_blocked(self):
        """Soft mode logs warnings but does not block."""
        em = ExposureManager({
            'max_positions_per_asset': 1,
            'soft_mode': True,
        })
        existing = [make_position(asset='BTC', size=50)]
        new_pos = make_new_position(asset='BTC', size=50)
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 1000)
        assert can_open is True
        assert 'soft mode' in reason.lower()
        assert len(warnings) > 0

    def test_none_strike_price_no_crash(self):
        """Regression: strike_price=None should not cause TypeError."""
        em = ExposureManager()
        existing = [make_position(asset='EVENT', size=50, strike_price=None)]
        new_pos = make_new_position(asset='EVENT', size=50, strike_price=None)
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 1000)
        assert can_open is True  # Should not crash

    def test_none_expiry_no_crash(self):
        """None expiry should be handled gracefully."""
        em = ExposureManager()
        new_pos = make_new_position(asset='BTC', size=50, expiry_date=None)
        can_open, reason, warnings = em.can_open_position(new_pos, [], 1000)
        assert can_open is True

    def test_zero_capital_blocked(self):
        """Zero total capital should be blocked with clear reason."""
        em = ExposureManager()
        new_pos = make_new_position(asset='BTC', size=50)
        can_open, reason, warnings = em.can_open_position(new_pos, [], 0)
        assert can_open is False
        assert 'capital' in reason.lower()

    def test_negative_capital_blocked(self):
        """Negative total capital should be blocked."""
        em = ExposureManager()
        new_pos = make_new_position(asset='BTC', size=50)
        can_open, reason, warnings = em.can_open_position(new_pos, [], -100)
        assert can_open is False

    def test_allows_different_assets(self):
        """Different assets should not trigger per-asset limits."""
        em = ExposureManager({'max_positions_per_asset': 1})
        existing = [make_position(asset='BTC', size=50)]
        new_pos = make_new_position(asset='ETH', size=50)
        can_open, reason, warnings = em.can_open_position(new_pos, existing, 10000)
        assert can_open is True


# ---- Tests: get_rebalance_suggestions ----

class TestRebalanceSuggestions:
    """Tests for ExposureManager.get_rebalance_suggestions()."""

    def test_over_concentration_suggests_closing(self):
        em = ExposureManager({'max_positions_per_asset': 2})
        positions = [
            make_position(asset='BTC', size=50),
            make_position(asset='BTC', size=50),
            make_position(asset='BTC', size=50),
        ]
        suggestions = em.get_rebalance_suggestions(positions, 1000)
        assert any('closing' in s.lower() and 'BTC' in s for s in suggestions)

    def test_single_asset_diversification(self):
        em = ExposureManager()
        positions = [
            make_position(asset='BTC', size=50),
            make_position(asset='BTC', size=50),
            make_position(asset='BTC', size=50),
        ]
        suggestions = em.get_rebalance_suggestions(positions, 1000)
        assert any('100% BTC' in s for s in suggestions)
        # Should NOT contain hardcoded "ETH, SOL"
        assert not any('ETH, SOL' in s for s in suggestions)

    def test_balanced_portfolio_no_suggestions(self):
        em = ExposureManager()
        positions = [
            make_position(asset='BTC', size=50),
            make_position(asset='ETH', size=50),
        ]
        suggestions = em.get_rebalance_suggestions(positions, 1000)
        assert len(suggestions) == 0


# ---- Tests: format_exposure_report ----

class TestFormatReport:
    """Tests for ExposureManager.format_exposure_report()."""

    def test_report_with_positions(self):
        em = ExposureManager()
        positions = [
            make_position(asset='BTC', size=100, side='YES'),
            make_position(asset='ETH', size=200, side='NO'),
        ]
        report = em.format_exposure_report(positions, 1000)
        assert 'PORTFOLIO EXPOSURE REPORT' in report
        assert 'BTC' in report
        assert 'ETH' in report
        assert 'Total Positions: 2' in report

    def test_report_empty_portfolio(self):
        em = ExposureManager()
        report = em.format_exposure_report([], 1000)
        assert 'Total Positions: 0' in report


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
