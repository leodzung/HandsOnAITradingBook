"""
Structural tests for ARCH-005: All position operations must go through TradeExecutor.

Verifies:
  1. No bot files call position_manager.close_position() directly
  2. No bot files call position_manager.save_position() directly
  3. All bot files import TradeExecutor
  4. All bot files call trade_executor.execute_trade() or execute_close_trade()
"""

import re
import pytest
from pathlib import Path


class TestTradeExecutorConstraint:
    """Structural tests enforcing TradeExecutor usage across all bots."""

    BOT_FILES = [
        "src/bots/trader.py",
        "src/bots/trader_price_levels.py",
        "src/bots/trader_short_expiry.py",
    ]

    FORBIDDEN_PATTERNS = [
        (r'position_manager\.close_position\(', 'position_manager.close_position()'),
        (r'position_manager\.save_position\(', 'position_manager.save_position()'),
    ]

    def test_no_direct_position_manager_close(self):
        """Bot files must NOT call position_manager.close_position() directly."""
        violations = []

        for file_path in self.BOT_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            content = path.read_text()
            lines = content.split('\n')

            for pattern, desc in self.FORBIDDEN_PATTERNS:
                for match in re.finditer(pattern, content):
                    line_num = content[:match.start()].count('\n') + 1
                    line_content = lines[line_num - 1].strip()

                    # Skip comments
                    if line_content.startswith('#'):
                        continue

                    violations.append(f"{file_path}:{line_num} - {desc}\n    {line_content}")

        if violations:
            pytest.fail(
                f"Found direct position_manager calls (should use TradeExecutor):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    def test_all_bots_import_trade_executor(self):
        """All bot files must import TradeExecutor."""
        missing = []

        for file_path in self.BOT_FILES:
            path = Path(file_path)
            if not path.exists():
                missing.append(f"{file_path} (file not found)")
                continue

            content = path.read_text()
            has_import = (
                'from core.trade_executor import' in content or
                'from src.core.trade_executor import' in content
            )
            if not has_import:
                missing.append(file_path)

        if missing:
            pytest.fail(
                f"Bot files missing TradeExecutor import:\n"
                + "\n".join(f"  - {f}" for f in missing)
            )

    def test_all_bots_use_trade_executor(self):
        """All bot files must call trade_executor methods for trades."""
        missing = []

        for file_path in self.BOT_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            content = path.read_text()
            uses_executor = (
                'trade_executor.execute_trade(' in content or
                'trade_executor.execute_close_trade(' in content
            )
            if not uses_executor:
                missing.append(file_path)

        if missing:
            pytest.fail(
                f"Bot files not using TradeExecutor for trades:\n"
                + "\n".join(f"  - {f}" for f in missing)
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
