"""RISK-009: Config validation at startup.

Validates that SlippageEstimator rejects invalid config types at init,
preventing runtime TypeErrors (e.g., float > dict comparisons).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.slippage_estimator import SlippageEstimator


class TestConfigTypeValidation:
    """Config values must be numeric or dict-of-numeric, nothing else."""

    def test_scalar_config_accepted(self):
        """Scalar (int/float) config values should work."""
        est = SlippageEstimator({
            'max_slippage_bps': 250,
            'max_slippage_dollars': 5.0,
            'warn_threshold_bps': 100,
        })
        assert est.max_slippage_bps == 250

    def test_per_bucket_dict_config_accepted(self):
        """Per-bucket dict config values should work."""
        est = SlippageEstimator({
            'max_slippage_bps': {'ultra_short': 3000, 'short': 2000, 'medium': 1500},
            'max_slippage_dollars': {'ultra_short': 15.0, 'short': 20.0, 'medium': 25.0},
            'warn_threshold_bps': {'ultra_short': 2000, 'short': 1500, 'medium': 1000},
        })
        assert isinstance(est.max_slippage_bps, dict)

    def test_string_config_rejected(self):
        """String config values must raise ValueError."""
        with pytest.raises(ValueError, match="must be numeric or dict-of-numeric"):
            SlippageEstimator({'max_slippage_bps': "high"})

    def test_list_config_rejected(self):
        """List config values must raise ValueError."""
        with pytest.raises(ValueError, match="must be numeric or dict-of-numeric"):
            SlippageEstimator({'max_slippage_dollars': [5.0, 10.0]})

    def test_nested_dict_with_non_numeric_rejected(self):
        """Dict with non-numeric values must raise ValueError."""
        with pytest.raises(ValueError, match="must be numeric"):
            SlippageEstimator({
                'max_slippage_bps': {'ultra_short': 'high', 'short': 2000}
            })

    def test_none_config_rejected(self):
        """None config values must raise ValueError."""
        with pytest.raises(ValueError, match="must be numeric or dict-of-numeric"):
            SlippageEstimator({'warn_threshold_bps': None})


class TestConfigRangeValidation:
    """Config values should be within sane ranges (warnings, not errors)."""

    def test_bps_within_range_no_warning(self, caplog):
        """Values within range should not warn."""
        import logging
        with caplog.at_level(logging.WARNING):
            SlippageEstimator({'max_slippage_bps': 250})
        assert 'outside recommended range' not in caplog.text

    def test_bps_too_low_warns(self, caplog):
        """max_slippage_bps < 50 should warn."""
        import logging
        with caplog.at_level(logging.WARNING):
            SlippageEstimator({'max_slippage_bps': 10})
        assert 'outside recommended range' in caplog.text

    def test_bps_too_high_warns(self, caplog):
        """max_slippage_bps > 5000 should warn."""
        import logging
        with caplog.at_level(logging.WARNING):
            SlippageEstimator({'max_slippage_bps': 12000})
        assert 'outside recommended range' in caplog.text

    def test_per_bucket_range_warns(self, caplog):
        """Per-bucket values outside range should warn per bucket."""
        import logging
        with caplog.at_level(logging.WARNING):
            SlippageEstimator({
                'max_slippage_bps': {'ultra_short': 3000, 'short': 10}  # short too low
            })
        assert 'max_slippage_bps[short]' in caplog.text


class TestAllBotConfigs:
    """Verify all 3 bot configs pass validation."""

    @pytest.mark.parametrize("config_file", [
        'config/config.json',
        'config/config_price_levels.json',
        'config/config_short_expiry.json',
    ])
    def test_bot_config_passes_validation(self, config_file):
        """Each bot's slippage config must pass type validation."""
        import json
        config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', config_file
        )
        with open(config_path) as f:
            config = json.load(f)

        slippage_config = config.get('slippage_estimation', {})
        # Should not raise
        est = SlippageEstimator(slippage_config)
        assert est.enabled is True
