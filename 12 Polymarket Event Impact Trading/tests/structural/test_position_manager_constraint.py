"""
Structural tests for ARCH-002: PositionManager V2 is single source for position data

These tests enforce that all position operations use the unified PositionManager V2.
Direct SQLite access or separate implementations are FORBIDDEN.

Rationale:
    Eliminated 500+ lines of duplicate code across 3 bots (2026-02-14).
    V2 provides unified interface, backward compatibility, and consistent tracking.
"""

import pytest
import re
from pathlib import Path


class TestPositionManagerConstraint:
    """Structural tests enforcing PositionManager V2 usage"""

    # Files that MUST use PositionManager instead of direct SQLite
    REQUIRED_FILES = [
        "src/bots/trader.py",
        "src/bots/trader_price_levels.py",
        "src/bots/trader_short_expiry.py",
        "src/core/trade_executor.py",
    ]

    # Files ALLOWED to access SQLite directly
    ALLOWED_FILES = [
        "src/core/position_manager.py",
    ]

    def test_no_direct_sqlite_access_in_bots(self):
        """Verify bots don't access SQLite directly"""
        violations = []

        for file_path in self.REQUIRED_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()
                lines = content.split('\n')

                # Check for direct SQLite imports/usage
                forbidden_patterns = [
                    r"import sqlite3",
                    r"from sqlite3 import",
                    r"sqlite3\.connect",
                ]

                for pattern in forbidden_patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        line_content = lines[line_num - 1].strip()

                        # Skip comments
                        if line_content.startswith('#'):
                            continue

                        violations.append({
                            'file': str(file_path),
                            'line': line_num,
                            'pattern': match.group(0),
                            'context': line_content
                        })

        if violations:
            error_msg = "Found direct SQLite access (should use PositionManager):\n"
            for v in violations:
                error_msg += f"  {v['file']}:{v['line']} - {v['pattern']}\n"
                error_msg += f"    Context: {v['context']}\n"

            pytest.fail(error_msg)

    def test_bots_import_position_manager(self):
        """Verify all bots import PositionManager"""
        missing_imports = []

        for file_path in self.REQUIRED_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                # Check for PositionManager import (V2)
                has_import = (
                    'from src.core.position_manager_v2 import PositionManager' in content or
                    'from core.position_manager_v2 import PositionManager' in content or
                    'from position_manager_v2 import PositionManager' in content or
                    'import position_manager' in content
                )

                if not has_import:
                    # Only flag if file manages positions
                    if 'position' in content.lower():
                        missing_imports.append(str(file_path))

        if missing_imports:
            error_msg = "Files missing PositionManager import:\n"
            for file in missing_imports:
                error_msg += f"  {file}\n"

            pytest.fail(error_msg)

    def test_no_v1_position_manager_references(self):
        """Verify no references to old V1 position manager"""
        violations = []

        for file_path in self.REQUIRED_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                # Check for V1 references
                if 'position_manager_v1' in content:
                    violations.append(str(file_path))

        if violations:
            error_msg = "Files still reference position_manager_v1 (deprecated):\n"
            for file in violations:
                error_msg += f"  {file}\n"

            pytest.fail(error_msg)

    def test_v1_file_does_not_exist(self):
        """Verify old V1 file has been deleted"""
        v1_path = Path("src/core/position_manager_v1.py")
        assert not v1_path.exists(), \
            "Old position_manager_v1.py still exists (should be deleted)"

    def test_position_manager_v2_methods_used(self):
        """Verify bots use PositionManager V2 API (outcome instead of side)"""
        for file_path in self.REQUIRED_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                # If file saves positions, check for V2 API usage
                if 'save_position' in content:
                    # V2 uses 'outcome' parameter, V1 used 'side'
                    # Both are valid during migration, but outcome is preferred
                    assert 'PositionManager' in content, \
                        f"{file_path} saves positions but doesn't use PositionManager"

    def test_unified_position_manager_instance(self):
        """Verify bots instantiate PositionManager (without direct SQL)"""
        for file_path in self.REQUIRED_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                # If file uses PositionManager, just verify it's instantiated
                # (The import_linter already ensures no direct SQL access)
                if 'PositionManager(' in content:
                    # Ensure it's actually used (has assignment or call)
                    has_usage = (
                        'self.position_manager = PositionManager(' in content or
                        'position_manager = PositionManager(' in content
                    )
                    assert has_usage, \
                        f"{file_path} should properly instantiate PositionManager"

    def test_no_duplicate_position_logic(self):
        """Verify no duplicate position management code"""
        # Check for patterns that indicate duplicate implementation
        duplicate_patterns = [
            r"CREATE TABLE IF NOT EXISTS positions",  # Direct schema creation
            r"INSERT INTO positions",  # Direct SQL inserts
            r"UPDATE positions SET",  # Direct SQL updates
        ]

        violations = []

        for file_path in self.REQUIRED_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                for pattern in duplicate_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        violations.append({
                            'file': str(file_path),
                            'pattern': pattern
                        })

        if violations:
            error_msg = "Found duplicate position management logic:\n"
            for v in violations:
                error_msg += f"  {v['file']} - Pattern: {v['pattern']}\n"
            error_msg += "\nAll position logic should be in PositionManager"

            pytest.fail(error_msg)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
