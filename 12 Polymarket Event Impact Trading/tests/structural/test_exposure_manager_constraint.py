"""
Structural tests for RISK-011: ExposureManager enforced across all bots.

Verifies:
  1. All 3 bot files import ExposureManager
  2. All 3 config files have exposure_limits section
  3. All 3 bot files call can_open_position on exposure_manager
"""

import json
import pytest
from pathlib import Path


class TestExposureManagerConstraint:
    """Structural tests enforcing ExposureManager usage across all bots."""

    BOT_FILES = [
        "src/bots/trader.py",
        "src/bots/trader_price_levels.py",
        "src/bots/trader_short_expiry.py",
    ]

    CONFIG_FILES = [
        "config/config.json",
        "config/config_price_levels.json",
        "config/config_short_expiry.json",
    ]

    def test_all_bots_import_exposure_manager(self):
        """All 3 bot files must import ExposureManager."""
        missing = []
        for file_path in self.BOT_FILES:
            path = Path(file_path)
            if not path.exists():
                missing.append(f"{file_path} (file not found)")
                continue

            content = path.read_text()
            has_import = (
                'from core.exposure_manager import ExposureManager' in content or
                'from src.core.exposure_manager import ExposureManager' in content
            )
            if not has_import:
                missing.append(file_path)

        if missing:
            pytest.fail(
                f"Bot files missing ExposureManager import:\n"
                + "\n".join(f"  - {f}" for f in missing)
            )

    def test_all_configs_have_exposure_limits(self):
        """All 3 config files must have exposure_limits section."""
        missing = []
        for file_path in self.CONFIG_FILES:
            path = Path(file_path)
            if not path.exists():
                missing.append(f"{file_path} (file not found)")
                continue

            config = json.loads(path.read_text())
            if 'exposure_limits' not in config:
                missing.append(file_path)

        if missing:
            pytest.fail(
                f"Config files missing exposure_limits section:\n"
                + "\n".join(f"  - {f}" for f in missing)
            )

    def test_all_bots_call_exposure_check(self):
        """All 3 bot files must call exposure_manager.can_open_position."""
        missing = []
        for file_path in self.BOT_FILES:
            path = Path(file_path)
            if not path.exists():
                missing.append(f"{file_path} (file not found)")
                continue

            content = path.read_text()
            if 'exposure_manager.can_open_position' not in content:
                missing.append(file_path)

        if missing:
            pytest.fail(
                f"Bot files missing exposure_manager.can_open_position() call:\n"
                + "\n".join(f"  - {f}" for f in missing)
            )

    def test_exposure_limits_have_required_keys(self):
        """exposure_limits config must have the minimum required keys."""
        required_keys = [
            'max_positions_per_asset',
            'max_capital_per_asset_pct',
            'max_total_positions',
            'max_capital_deployed_pct',
        ]

        issues = []
        for file_path in self.CONFIG_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            config = json.loads(path.read_text())
            limits = config.get('exposure_limits', {})
            missing_keys = [k for k in required_keys if k not in limits]
            if missing_keys:
                issues.append(f"{file_path}: missing {missing_keys}")

        if issues:
            pytest.fail(
                f"Config files with incomplete exposure_limits:\n"
                + "\n".join(f"  - {i}" for i in issues)
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
