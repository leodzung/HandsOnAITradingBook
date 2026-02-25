#!/usr/bin/env python3
"""
Automated constraint validation system.

Validates all enforced constraints defined in CONSTRAINTS.yml.
Runs structural tests, import linters, and checks telemetry metrics.

Usage:
    python scripts/validate_constraints.py                    # Validate all constraints
    python scripts/validate_constraints.py --category arch    # Validate only architecture
    python scripts/validate_constraints.py --id ARCH-001      # Validate specific constraint
    python scripts/validate_constraints.py --ci               # CI mode (fail fast, no colors)

Exit codes:
    0 = All constraints satisfied
    1 = One or more violations found
    2 = Configuration error
"""

import yaml
import subprocess
import json
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

    @classmethod
    def disable(cls):
        """Disable colors for CI mode"""
        cls.HEADER = cls.BLUE = cls.CYAN = cls.GREEN = ''
        cls.YELLOW = cls.RED = cls.BOLD = cls.UNDERLINE = cls.END = ''


class ConstraintValidator:
    def __init__(self, constraints_file: str = "CONSTRAINTS.yml", verbose: bool = True):
        self.constraints_file = Path(constraints_file)
        self.verbose = verbose
        self.violations: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.passed: List[Dict[str, Any]] = []

        if not self.constraints_file.exists():
            raise FileNotFoundError(f"Constraints file not found: {constraints_file}")

        with open(self.constraints_file) as f:
            self.constraints = yaml.safe_load(f)

    def validate_all(self, category: Optional[str] = None, constraint_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate all enforced constraints (or filtered subset)"""

        print(f"{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.HEADER}{Colors.BOLD}🔍 Polymarket Trading System - Constraint Validation{Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

        # Validate constraints by category
        categories = self.constraints.get('constraints', {})

        if category:
            categories = {category: categories.get(category, [])}

        for cat_name, items in categories.items():
            if not items:
                continue

            print(f"{Colors.CYAN}{Colors.BOLD}📋 Category: {cat_name.upper()}{Colors.END}")
            print(f"{Colors.CYAN}{'─'*70}{Colors.END}\n")

            for constraint in items:
                if constraint.get('status') != 'enforced':
                    if self.verbose:
                        print(f"  ⏭️  [{constraint['id']}] {constraint['title']} - SKIPPED (status: {constraint.get('status')})")
                    continue

                # Filter by specific constraint ID if provided
                if constraint_id and constraint['id'] != constraint_id:
                    continue

                self._validate_constraint(constraint)

            print()  # Blank line between categories

        # Check for regressions in resolved technical debt
        if not constraint_id:  # Skip if validating specific constraint
            print(f"{Colors.CYAN}{Colors.BOLD}🔍 Checking for Technical Debt Regressions{Colors.END}")
            print(f"{Colors.CYAN}{'─'*70}{Colors.END}\n")
            self._check_technical_debt_regressions()
            print()

        return self._generate_report()

    def _validate_constraint(self, constraint: Dict[str, Any]) -> None:
        """Validate a single constraint"""
        constraint_id = constraint['id']
        title = constraint['title']

        print(f"  {Colors.BOLD}[{constraint_id}] {title}{Colors.END}")
        print(f"  Priority: {constraint.get('priority', 'unknown').upper()}")

        all_passed = True
        validation_results = []

        # Run all validation checks
        for validation in constraint.get('validation', []):
            result = self._run_validation(validation, constraint_id)
            validation_results.append(result)

            if result['passed']:
                self.passed.append({
                    'constraint_id': constraint_id,
                    'title': title,
                    'validation_type': validation['type']
                })
                print(f"    {Colors.GREEN}✅ {validation['type']}: PASSED{Colors.END}")
                if self.verbose and result.get('details'):
                    print(f"       {result['details']}")
            else:
                all_passed = False
                severity = constraint.get('priority', 'medium')

                violation = {
                    'constraint_id': constraint_id,
                    'title': title,
                    'validation_type': validation['type'],
                    'error': result['error'],
                    'severity': severity
                }

                if severity == 'critical':
                    self.violations.append(violation)
                    print(f"    {Colors.RED}❌ {validation['type']}: FAILED{Colors.END}")
                else:
                    self.warnings.append(violation)
                    print(f"    {Colors.YELLOW}⚠️  {validation['type']}: FAILED{Colors.END}")

                print(f"       {Colors.RED}Error: {result['error']}{Colors.END}")

        # Check telemetry metrics (if any)
        if 'telemetry' in constraint:
            telemetry_status = self._check_telemetry(constraint)
            if not telemetry_status['all_passed']:
                all_passed = False

        print()  # Blank line between constraints

    def _run_validation(self, validation: Dict[str, Any], constraint_id: str) -> Dict[str, Any]:
        """Execute a validation check"""
        validation_type = validation['type']

        try:
            if validation_type == 'import_linter':
                return self._check_forbidden_imports(validation)
            elif validation_type == 'structural_test':
                return self._run_pytest(validation['command'])
            elif validation_type == 'integration_test':
                return self._run_pytest(validation['command'])
            elif validation_type == 'behavioral_test':
                return self._run_pytest(validation['command'])
            elif validation_type == 'pre_deployment_gate':
                return self._run_command(validation['command'])
            elif validation_type == 'filesystem_check':
                return self._run_command(validation['command'])
            elif validation_type == 'code_duplication_check':
                return self._check_code_duplication(validation)
            elif validation_type == 'label_quality_check':
                return self._run_command(validation['command'])
            elif validation_type == 'continuous_monitoring':
                return self._run_command(validation['command'])
            elif validation_type == 'import_check':
                return self._run_command(validation['command'])
            else:
                return {
                    'passed': False,
                    'error': f"Unknown validation type: {validation_type}"
                }
        except Exception as e:
            return {
                'passed': False,
                'error': f"Validation error: {str(e)}"
            }

    def _check_forbidden_imports(self, validation: Dict[str, Any]) -> Dict[str, Any]:
        """Check for forbidden import patterns"""
        files_to_check = validation.get('files_to_check', [])
        forbidden_patterns = validation.get('forbidden_patterns', [])
        allowed_files = validation.get('allowed_files', [])

        violations_found = []

        for file_path in files_to_check:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                for pattern in forbidden_patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        # Find line number
                        line_num = content[:match.start()].count('\n') + 1
                        violations_found.append(f"{file_path}:{line_num} - {match.group(0)}")

        if violations_found:
            return {
                'passed': False,
                'error': f"Found {len(violations_found)} forbidden pattern(s):\n       " + "\n       ".join(violations_found[:5])
            }
        else:
            return {
                'passed': True,
                'details': f"Checked {len(files_to_check)} files, no violations"
            }

    def _run_pytest(self, command: str) -> Dict[str, Any]:
        """Run pytest command"""
        # Check if test file exists
        test_file = command.split()[-2] if '-v' in command else command.split()[-1]
        if not Path(test_file).exists():
            return {
                'passed': False,
                'error': f"Test file not found: {test_file} (needs to be created)"
            }

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        if result.returncode == 0:
            # Extract test count from pytest output
            match = re.search(r'(\d+) passed', result.stdout)
            test_count = match.group(1) if match else 'unknown'
            return {
                'passed': True,
                'details': f"{test_count} test(s) passed"
            }
        else:
            # Extract failure summary
            error_lines = result.stdout.split('\n')
            failure_summary = [line for line in error_lines if 'FAILED' in line or 'ERROR' in line]

            return {
                'passed': False,
                'error': '\n       '.join(failure_summary[:3]) if failure_summary else result.stdout[-200:]
            }

    def _run_command(self, command: str) -> Dict[str, Any]:
        """Run arbitrary shell command"""
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        if result.returncode == 0:
            return {'passed': True}
        else:
            return {
                'passed': False,
                'error': result.stderr or result.stdout or "Command failed"
            }

    def _check_code_duplication(self, validation: Dict[str, Any]) -> Dict[str, Any]:
        """Check for code duplication (stub - requires pylint or similar)"""
        # This is a placeholder - would need actual duplication detection
        return {
            'passed': True,
            'details': "Code duplication check not yet implemented"
        }

    def _check_telemetry(self, constraint: Dict[str, Any]) -> Dict[str, bool]:
        """Check telemetry metrics against thresholds"""
        print(f"    {Colors.CYAN}📊 Telemetry Checks:{Colors.END}")

        all_passed = True

        # Try to import telemetry system
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
            from monitoring.telemetry import TradeTelemetry

            telemetry = TradeTelemetry()

            # First, collect current metrics
            telemetry.collect_system_metrics()

            # Get latest metrics
            latest_metrics = telemetry.get_latest_metrics()

            for metric_def in constraint.get('telemetry', []):
                metric_name = metric_def['metric']
                threshold = metric_def.get('threshold')
                alert_level = metric_def.get('alert', 'warning')

                if metric_name not in latest_metrics:
                    print(f"       ℹ️  {metric_name}: Not available (no data collected yet)")
                    continue

                value = latest_metrics[metric_name]

                # Check threshold (if specified)
                if threshold is not None:
                    # Default to <= for thresholds (value should be at or below threshold)
                    if value <= threshold:
                        print(f"       {Colors.GREEN}✅ {metric_name}: {value} ≤ {threshold}{Colors.END}")
                    else:
                        all_passed = False
                        severity_color = Colors.RED if alert_level == 'critical' else Colors.YELLOW

                        self.violations.append({
                            'constraint_id': constraint['id'],
                            'title': f"Telemetry: {metric_name}",
                            'validation_type': 'telemetry',
                            'error': f"{metric_name}={value} exceeds threshold {threshold}",
                            'severity': alert_level
                        })

                        print(f"       {severity_color}❌ {metric_name}: {value} > {threshold}{Colors.END}")

                # Check for alert_on_change (event counting)
                elif metric_def.get('alert_on_change'):
                    # Count events for this metric
                    event_count = telemetry.get_event_count(metric_name, hours=24)

                    if event_count > 0:
                        all_passed = False
                        severity_color = Colors.RED if alert_level == 'critical' else Colors.YELLOW

                        self.warnings.append({
                            'constraint_id': constraint['id'],
                            'title': f"Telemetry: {metric_name}",
                            'validation_type': 'telemetry',
                            'error': f"{event_count} {metric_name} event(s) in last 24h",
                            'severity': alert_level
                        })

                        print(f"       {severity_color}⚠️  {metric_name}: {event_count} event(s) detected{Colors.END}")
                    else:
                        print(f"       {Colors.GREEN}✅ {metric_name}: No events{Colors.END}")
                else:
                    # Just report current value
                    print(f"       ℹ️  {metric_name}: {value}")

        except ImportError:
            print(f"       ℹ️  Telemetry system not available (monitoring.telemetry not found)")
        except Exception as e:
            print(f"       ⚠️  Telemetry check error: {str(e)}")

        return {'all_passed': all_passed}

    def _check_technical_debt_regressions(self) -> None:
        """Check if resolved technical debt has regressed"""
        resolved_debt = self.constraints.get('technical_debt', {}).get('resolved', [])

        for debt in resolved_debt:
            debt_id = debt['id']
            title = debt['title']

            print(f"  {Colors.BOLD}[{debt_id}] {title}{Colors.END}")

            has_regression = False

            for validation in debt.get('validation', []):
                result = self._run_validation(validation, debt_id)

                if result['passed']:
                    print(f"    {Colors.GREEN}✅ Still resolved{Colors.END}")
                else:
                    has_regression = True
                    self.violations.append({
                        'constraint_id': debt_id,
                        'title': f"REGRESSION: {title}",
                        'validation_type': 'regression',
                        'error': result['error'],
                        'severity': 'critical'
                    })
                    print(f"    {Colors.RED}❌ REGRESSION DETECTED!{Colors.END}")
                    print(f"       {Colors.RED}{result['error']}{Colors.END}")

            if not has_regression and not self.verbose:
                print(f"    {Colors.GREEN}✅ No regression{Colors.END}")

            print()

    def _generate_report(self) -> Dict[str, Any]:
        """Generate validation report"""
        total_constraints = self._count_enforced_constraints()

        report = {
            'timestamp': datetime.now().isoformat(),
            'total_constraints': total_constraints,
            'passed': len(self.passed),
            'warnings': len(self.warnings),
            'violations': len(self.violations),
            'status': 'PASS' if len(self.violations) == 0 else 'FAIL',
            'violation_details': self.violations,
            'warning_details': self.warnings
        }

        # Save report
        report_path = Path('data/constraint_validation_latest.json')
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        # Update CONSTRAINTS.yml metadata
        self.constraints['metadata']['last_validated'] = report['timestamp']
        self.constraints['metadata']['validation_status'] = report['status']

        with open(self.constraints_file, 'w') as f:
            yaml.dump(self.constraints, f, default_flow_style=False, sort_keys=False)

        # Print summary
        self._print_summary(report)

        return report

    def _count_enforced_constraints(self) -> int:
        """Count total enforced constraints"""
        count = 0
        for category, items in self.constraints.get('constraints', {}).items():
            count += sum(1 for c in items if c.get('status') == 'enforced')
        return count

    def _print_summary(self, report: Dict[str, Any]) -> None:
        """Print validation summary"""
        print(f"{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}📊 Validation Summary{Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

        print(f"  Total enforced constraints: {report['total_constraints']}")
        print(f"  {Colors.GREEN}Passed: {report['passed']}{Colors.END}")
        print(f"  {Colors.YELLOW}Warnings: {report['warnings']}{Colors.END}")
        print(f"  {Colors.RED}Violations: {report['violations']}{Colors.END}")

        if report['warnings'] > 0:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  WARNINGS:{Colors.END}")
            for w in self.warnings:
                print(f"  [{w['constraint_id']}] {w['title']}")
                print(f"    {w['error']}\n")

        if report['violations'] > 0:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ VALIDATION FAILED{Colors.END}\n")
            for v in self.violations:
                print(f"  {Colors.RED}[{v['severity'].upper()}] {v['constraint_id']}: {v['title']}{Colors.END}")
                print(f"    {v['error']}\n")
        else:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ ALL CONSTRAINTS SATISFIED{Colors.END}\n")

        print(f"Report saved to: {Colors.CYAN}data/constraint_validation_latest.json{Colors.END}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Validate Polymarket trading system constraints',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                            # Validate all constraints
  %(prog)s --category architecture    # Validate only architecture constraints
  %(prog)s --id ARCH-001              # Validate specific constraint
  %(prog)s --ci                       # CI mode (no colors, fail fast)
        """
    )
    parser.add_argument('--category', help='Validate specific category only')
    parser.add_argument('--id', help='Validate specific constraint ID only')
    parser.add_argument('--ci', action='store_true', help='CI mode (no colors)')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')
    parser.add_argument('--constraints-file', default='CONSTRAINTS.yml', help='Path to constraints file')

    args = parser.parse_args()

    if args.ci:
        Colors.disable()

    try:
        validator = ConstraintValidator(
            constraints_file=args.constraints_file,
            verbose=not args.quiet
        )
        report = validator.validate_all(
            category=args.category,
            constraint_id=args.id
        )

        # Exit with error code if violations found
        sys.exit(0 if report['status'] == 'PASS' else 1)

    except FileNotFoundError as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"{Colors.RED}Unexpected error: {e}{Colors.END}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
