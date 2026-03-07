"""
Structural tests for ARCH-017: Position loop must use .get() for all DB-derived fields.

Rationale:
    Direct dict access (pos['entry_time']) crashes if a column was added later or a row
    is missing data. Using .get() and validating for None before use prevents KeyError
    crashes in _check_positions().
"""

import re
from pathlib import Path


BOT_FILE = Path("src/bots/trader_short_expiry.py")


def _get_check_positions_source() -> str:
    content = BOT_FILE.read_text()
    match = re.search(
        r"def _check_positions\(self\).*?(?=\n    def |\Z)",
        content,
        re.DOTALL,
    )
    assert match, "_check_positions method not found in trader_short_expiry.py"
    return match.group(0)


class TestPositionLoopFieldAccess:
    """Verify _check_positions() uses .get() for DB-derived fields."""

    def test_entry_time_uses_get(self):
        """ARCH-017: entry_time must be read with .get(), not direct access."""
        source = _get_check_positions_source()
        assert "pos.get('entry_time')" in source or 'pos.get("entry_time")' in source, (
            "_check_positions must use pos.get('entry_time') to avoid KeyError"
        )

    def test_entry_time_none_check_skips(self):
        """ARCH-017: entry_time=None must log a warning and skip the position."""
        source = _get_check_positions_source()
        # Should check if entry_time is None
        assert "entry_time is None" in source, (
            "_check_positions must validate entry_time is not None before using it"
        )

    def test_hours_to_expiry_uses_get(self):
        """ARCH-017: hours_to_expiry_at_entry must be read with .get()."""
        source = _get_check_positions_source()
        assert (
            "pos.get('hours_to_expiry_at_entry')" in source
            or 'pos.get("hours_to_expiry_at_entry")' in source
        ), (
            "_check_positions must use pos.get('hours_to_expiry_at_entry') to avoid KeyError"
        )

    def test_hours_to_expiry_none_triggers_force_close(self):
        """ARCH-017: hours_to_expiry=None must force-close, not skip silently."""
        source = _get_check_positions_source()
        assert "hours_to_expiry is None" in source, (
            "_check_positions must check hours_to_expiry is not None"
        )
        # Should call _execute_close, not just continue
        # Find the block after the None check
        none_check_idx = source.find("hours_to_expiry is None")
        block_after = source[none_check_idx:none_check_idx + 300]
        assert "_execute_close" in block_after, (
            "When hours_to_expiry is None, _check_positions must call _execute_close, not just skip"
        )

    def test_size_uses_get(self):
        """ARCH-017: size must be validated before use in P&L calculations."""
        source = _get_check_positions_source()
        assert (
            "pos.get('size')" in source
            or 'pos.get("size")' in source
        ), (
            "_check_positions must use pos.get('size') to safely read position size"
        )

    def test_no_direct_bracket_access_for_critical_fields(self):
        """ARCH-017: Critical fields must not use direct bracket access in position loop."""
        source = _get_check_positions_source()

        # These fields should use .get(), not direct access
        forbidden_patterns = [
            r"pos\['entry_time'\]",
            r'pos\["entry_time"\]',
            r"pos\['hours_to_expiry_at_entry'\]",
            r'pos\["hours_to_expiry_at_entry"\]',
        ]
        violations = []
        for pattern in forbidden_patterns:
            if re.search(pattern, source):
                violations.append(pattern)

        assert not violations, (
            f"_check_positions uses direct dict access for critical fields: {violations}\n"
            "These must use .get() to avoid KeyError on missing columns."
        )
