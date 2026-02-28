"""
Structural test for OPS-005: Database integrity check at startup.

Verifies that critical-path DB initialization methods include PRAGMA integrity_check.
"""

import pytest
from pathlib import Path


# Critical-path DB files that MUST have integrity checks
CRITICAL_DB_FILES = [
    'src/core/position_manager_v2.py',
]


class TestDbIntegrityCheck:
    """Verify PRAGMA integrity_check exists in critical-path DB init methods."""

    def test_position_manager_has_integrity_check(self):
        """position_manager_v2.py must run PRAGMA integrity_check at init."""
        path = Path('src/core/position_manager_v2.py')
        assert path.exists(), "position_manager_v2.py not found"

        content = path.read_text()
        assert 'integrity_check' in content, \
            "position_manager_v2.py must include PRAGMA integrity_check"

    def test_integrity_check_in_create_table(self):
        """Integrity check must be in _create_table method (called at init)."""
        path = Path('src/core/position_manager_v2.py')
        content = path.read_text()

        # Find _create_table method and verify integrity_check is inside it
        in_create_table = False
        found_integrity_check = False

        for line in content.splitlines():
            if 'def _create_table' in line:
                in_create_table = True
            elif in_create_table and line.strip().startswith('def '):
                break  # Hit next method
            elif in_create_table and 'integrity_check' in line:
                found_integrity_check = True
                break

        assert found_integrity_check, \
            "_create_table must contain PRAGMA integrity_check"

    def test_integrity_check_raises_on_failure(self):
        """Integrity check failure must raise an exception (refuse to start)."""
        path = Path('src/core/position_manager_v2.py')
        content = path.read_text()

        # After integrity_check, there should be a raise statement
        lines = content.splitlines()
        in_integrity_section = False
        found_raise = False

        for line in lines:
            if 'integrity_check' in line:
                in_integrity_section = True
            elif in_integrity_section:
                if 'raise' in line:
                    found_raise = True
                    break
                if line.strip().startswith('def '):
                    break  # Hit next method

        assert found_raise, \
            "Integrity check failure must raise an exception"

    def test_integrity_check_with_corrupted_db(self, tmp_path):
        """PositionManager must detect corrupted database."""
        import sqlite3

        # Create a valid DB first
        db_path = str(tmp_path / 'test_positions.db')
        conn = sqlite3.connect(db_path)
        conn.execute('CREATE TABLE test (id INTEGER PRIMARY KEY)')
        conn.close()

        # Now corrupt it by writing garbage
        with open(db_path, 'r+b') as f:
            f.seek(100)
            f.write(b'\x00\x00\x00\x00' * 50)

        # PositionManager should detect corruption
        from core.position_manager_v2 import PositionManager
        with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
            PositionManager(db_path=db_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
