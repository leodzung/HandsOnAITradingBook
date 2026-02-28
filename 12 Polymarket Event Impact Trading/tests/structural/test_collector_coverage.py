"""
Structural test for TEST-002: Collector test coverage.

Verifies that test files exist for all collector modules.
"""

import pytest
from pathlib import Path


# All collector modules that MUST have corresponding test files
COLLECTOR_MODULES = {
    'src/collectors/alchemy_collector.py': 'tests/integration/test_alchemy_collector.py',
    'src/collectors/gdelt_collector.py': 'tests/integration/test_gdelt_collector.py',
    'src/collectors/data_collector.py': 'tests/integration/test_data_collector.py',
}


class TestCollectorCoverage:
    """Verify test files exist for all collector modules."""

    def test_all_collectors_have_tests(self):
        """Every collector module must have a corresponding test file."""
        missing = []

        for collector, test_file in COLLECTOR_MODULES.items():
            collector_path = Path(collector)
            test_path = Path(test_file)

            if collector_path.exists() and not test_path.exists():
                missing.append(f"{collector} -> missing {test_file}")

        if missing:
            pytest.fail(
                f"TEST-002 violation: {len(missing)} collector(s) without tests:\n"
                + "\n".join(f"  - {m}" for m in missing)
            )

    def test_collector_tests_are_not_empty(self):
        """Test files must contain at least one test class or function."""
        for test_file in COLLECTOR_MODULES.values():
            path = Path(test_file)
            if not path.exists():
                continue

            content = path.read_text()
            has_tests = ('def test_' in content or 'class Test' in content)
            assert has_tests, f"{test_file} exists but contains no test functions"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
