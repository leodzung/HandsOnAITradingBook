"""
Structural test for TEST-001: All pytest commands must set PYTHONPATH=src.

Scans CONSTRAINTS.yml to verify every pytest command includes PYTHONPATH=src prefix.
"""

import yaml
import pytest
from pathlib import Path

# Validation types that can contain pytest commands
PYTEST_VALIDATION_TYPES = [
    'integration_test', 'structural_test', 'behavioral_test',
    'label_quality_check', 'pre_deployment_gate',
]


class TestPythonpathConstraint:
    """Verify all pytest commands in CONSTRAINTS.yml have PYTHONPATH=src."""

    def test_all_pytest_commands_have_pythonpath(self):
        """Every pytest command must set PYTHONPATH=src."""
        constraints_file = Path('CONSTRAINTS.yml')
        assert constraints_file.exists(), "CONSTRAINTS.yml not found"

        data = yaml.safe_load(constraints_file.read_text())
        violations = []

        def scan_validations(validations, constraint_id):
            for val in validations:
                cmd = val.get('command', '')
                if 'pytest' in cmd and 'PYTHONPATH=src' not in cmd:
                    violations.append(
                        f"{constraint_id}: {cmd[:80]}"
                    )

        for section in data.get('constraints', {}).values():
            if not isinstance(section, list):
                continue
            for constraint in section:
                scan_validations(
                    constraint.get('validation', []),
                    constraint.get('id', 'UNKNOWN')
                )

        # Also check technical_debt resolved/active sections
        for debt_section in ['resolved', 'active']:
            for item in data.get('technical_debt', {}).get(debt_section, []):
                scan_validations(
                    item.get('validation', []),
                    item.get('id', 'UNKNOWN')
                )

        # Also check operations section (top-level list)
        for item in data.get('operations', []):
            scan_validations(
                item.get('validation', []),
                item.get('id', 'UNKNOWN')
            )

        if violations:
            pytest.fail(
                f"Missing PYTHONPATH=src in {len(violations)} command(s):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
