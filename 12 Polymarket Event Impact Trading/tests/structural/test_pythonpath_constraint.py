"""
Structural test for TEST-001: All pytest commands must set PYTHONPATH=src.

Scans CONSTRAINTS.yml to verify every pytest command that references src/
includes PYTHONPATH=src prefix.
"""

import yaml
import pytest
from pathlib import Path


class TestPythonpathConstraint:
    """Verify all pytest commands in CONSTRAINTS.yml have PYTHONPATH=src."""

    def test_all_pytest_commands_have_pythonpath(self):
        """Every pytest command referencing src must set PYTHONPATH=src."""
        constraints_file = Path('CONSTRAINTS.yml')
        assert constraints_file.exists(), "CONSTRAINTS.yml not found"

        data = yaml.safe_load(constraints_file.read_text())
        violations = []

        for section in data.get('constraints', {}).values():
            if not isinstance(section, list):
                continue
            for constraint in section:
                for val in constraint.get('validation', []):
                    if val.get('type') in ['integration_test', 'structural_test']:
                        cmd = val.get('command', '')
                        if 'pytest' in cmd and 'src' in cmd and 'PYTHONPATH=src' not in cmd:
                            violations.append(
                                f"{constraint['id']}: {cmd[:60]}"
                            )

        if violations:
            pytest.fail(
                f"Missing PYTHONPATH=src in:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
