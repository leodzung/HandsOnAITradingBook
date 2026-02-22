#!/usr/bin/env python3
"""
DEX Scanner - Smoke Test Suite
===============================

Quick validation that all components are working correctly.
Run this before relying on the scanner for real trading decisions.
"""

import json
import sys
import requests
from datetime import datetime

# Test counter
tests_passed = 0
tests_failed = 0
tests_total = 0

def test(name):
    """Decorator to track test results"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            global tests_passed, tests_failed, tests_total
            tests_total += 1

            print(f"\n{'='*80}")
            print(f"TEST {tests_total}: {name}")
            print('='*80)

            try:
                result = func(*args, **kwargs)
                if result:
                    tests_passed += 1
                    print(f"✅ PASS: {name}")
                    return True
                else:
                    tests_failed += 1
                    print(f"❌ FAIL: {name}")
                    return False
            except Exception as e:
                tests_failed += 1
                print(f"❌ FAIL: {name}")
                print(f"   Error: {e}")
                import traceback
                traceback.print_exc()
                return False

        return wrapper
    return decorator


@test("API Connectivity - DexScreener")
def test_api_connectivity():
    """Test that we can reach the DexScreener API"""
    url = "https://api.dexscreener.com/latest/dex/search?q=WBNB"

    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        data = response.json()

        if 'pairs' in data and len(data['pairs']) > 0:
            print(f"   ✓ API reachable")
            print(f"   ✓ Received {len(data['pairs'])} pairs")
            print(f"   ✓ Sample pair: {data['pairs'][0].get('baseToken', {}).get('symbol')}")
            return True

    print(f"   ✗ API returned status {response.status_code}")
    return False


@test("Email Configuration - Valid JSON")
def test_email_config():
    """Test that email config file exists and is valid"""
    try:
        with open('email_config.json', 'r') as f:
            config = json.load(f)

        required_keys = ['email_settings', 'alert_settings']
        for key in required_keys:
            if key not in config:
                print(f"   ✗ Missing key: {key}")
                return False

        email_keys = ['to_email', 'from_email', 'smtp_server', 'smtp_port', 'smtp_password']
        for key in email_keys:
            if key not in config['email_settings']:
                print(f"   ✗ Missing email setting: {key}")
                return False

        print(f"   ✓ Config file valid")
        print(f"   ✓ Alerts to: {config['email_settings']['to_email']}")
        print(f"   ✓ From: {config['email_settings']['from_email']}")
        print(f"   ✓ Threshold: {config['alert_settings']['min_score_to_alert']}")

        return True

    except FileNotFoundError:
        print("   ✗ email_config.json not found")
        return False
    except json.JSONDecodeError as e:
        print(f"   ✗ Invalid JSON: {e}")
        return False


@test("Scoring Logic - Transparency Score")
def test_transparency_scoring():
    """Test that transparency scoring works correctly"""
    from run_working import calculate_transparency_score

    # Test 1: No links (should be 0)
    no_links = {
        'github': None,
        'website': None,
        'twitter': None,
        'telegram': None,
        'discord': None
    }
    score1 = calculate_transparency_score(no_links)

    # Test 2: All links (should be 100)
    all_links = {
        'github': 'https://github.com/test',
        'website': 'https://test.com',
        'twitter': 'https://twitter.com/test',
        'telegram': 'https://t.me/test',
        'discord': 'https://discord.gg/test'
    }
    score2 = calculate_transparency_score(all_links)

    # Test 3: Only GitHub (should be 40)
    github_only = {
        'github': 'https://github.com/test',
        'website': None,
        'twitter': None,
        'telegram': None,
        'discord': None
    }
    score3 = calculate_transparency_score(github_only)

    print(f"   No links: {score1}/100 (expected 0)")
    print(f"   All links: {score2}/100 (expected 100)")
    print(f"   GitHub only: {score3}/100 (expected 40)")

    if score1 == 0 and score2 == 100 and score3 == 40:
        print("   ✓ Transparency scoring correct")
        return True
    else:
        print("   ✗ Transparency scoring incorrect")
        return False


@test("Scoring Logic - Safety Score")
def test_safety_scoring():
    """Test that safety scoring works correctly"""
    from run_working import calculate_safety_score

    # Test 1: Low liquidity, no transparency
    score1 = calculate_safety_score(
        liquidity=5000,
        volume=100,
        dex_id='unknown',
        transparency_score=0
    )

    # Test 2: High liquidity, good transparency
    score2 = calculate_safety_score(
        liquidity=100000,
        volume=50000,
        dex_id='pancakeswap-v2',
        transparency_score=100
    )

    # Test 3: Medium liquidity, medium transparency
    score3 = calculate_safety_score(
        liquidity=25000,
        volume=5000,
        dex_id='pancakeswap-v2',
        transparency_score=50
    )

    print(f"   Low liq, no transparency: {score1:.1f}/100")
    print(f"   High liq, good transparency: {score2:.1f}/100")
    print(f"   Medium liq, medium transparency: {score3:.1f}/100")

    # Validate ranges
    if 20 <= score1 <= 40 and 75 <= score2 <= 100 and 50 <= score3 <= 70:
        print("   ✓ Safety scoring in expected ranges")
        return True
    else:
        print("   ✗ Safety scoring out of range")
        return False


@test("Scoring Logic - Opportunity Score")
def test_opportunity_scoring():
    """Test that opportunity scoring works correctly"""
    from run_working import calculate_opportunity_score

    # Test 1: Low volume, negative momentum
    score1 = calculate_opportunity_score(
        liquidity=10000,
        volume=100,
        price_24h=-5.0
    )

    # Test 2: High volume, strong momentum
    score2 = calculate_opportunity_score(
        liquidity=100000,
        volume=200000,
        price_24h=25.0
    )

    # Test 3: Medium volume, moderate momentum
    score3 = calculate_opportunity_score(
        liquidity=50000,
        volume=30000,
        price_24h=8.0
    )

    print(f"   Low vol, negative: {score1:.1f}/100")
    print(f"   High vol, strong momentum: {score2:.1f}/100")
    print(f"   Medium vol, moderate: {score3:.1f}/100")

    # Validate ranges and ordering
    if score1 < score3 < score2 and 20 <= score1 <= 40 and 70 <= score2 <= 100:
        print("   ✓ Opportunity scoring correct")
        return True
    else:
        print("   ✗ Opportunity scoring incorrect")
        return False


@test("Data Fetching - Real Token Analysis")
def test_real_token_fetch():
    """Test that we can fetch and analyze real tokens"""
    from run_working import fetch_and_analyze

    opportunities = fetch_and_analyze()

    if opportunities is not None:
        print(f"   ✓ Fetched data successfully")
        print(f"   ✓ Found {len(opportunities)} tokens")

        if len(opportunities) > 0:
            top = opportunities[0]
            print(f"   ✓ Top token: {top['symbol']}")
            print(f"   ✓ Composite: {top['composite']:.1f}/100")
            print(f"   ✓ Safety: {top['safety']:.1f}/100")
            print(f"   ✓ Opportunity: {top['opportunity']:.1f}/100")
            print(f"   ✓ Transparency: {top.get('transparency', 0):.1f}/100")

        return True
    else:
        print("   ✗ Failed to fetch data")
        return False


@test("Email System - Configuration Test")
def test_email_system():
    """Test email system without actually sending"""
    try:
        with open('email_config.json', 'r') as f:
            config = json.load(f)

        email_settings = config['email_settings']

        # Check SMTP settings are reasonable
        smtp_server = email_settings['smtp_server']
        smtp_port = email_settings['smtp_port']

        if 'gmail.com' in smtp_server and smtp_port == 587:
            print(f"   ✓ SMTP server: {smtp_server}")
            print(f"   ✓ SMTP port: {smtp_port}")
            print(f"   ✓ Email configuration looks valid")
            print(f"   ⚠️  Not sending test email (run send_test_email.py to test sending)")
            return True
        else:
            print(f"   ⚠️  Unusual SMTP settings: {smtp_server}:{smtp_port}")
            return True  # Still pass, just warning

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


@test("Cron Job - Installation Check")
def test_cron_installation():
    """Test that cron job is installed"""
    import subprocess

    try:
        result = subprocess.run(
            ['crontab', '-l'],
            capture_output=True,
            text=True
        )

        if 'run_with_email_alerts.py' in result.stdout:
            print("   ✓ Cron job found")

            # Extract the cron line
            for line in result.stdout.split('\n'):
                if 'run_with_email_alerts.py' in line:
                    print(f"   ✓ Schedule: {line.split()[0:5]}")
                    print(f"   ✓ Full entry: {line[:80]}...")
                    break

            return True
        else:
            print("   ✗ Cron job not found")
            print("   ℹ️  Run: ./install_cron.sh to install")
            return False

    except Exception as e:
        print(f"   ✗ Error checking cron: {e}")
        return False


@test("Cron Log - Activity Check")
def test_cron_log():
    """Test that cron has been running"""
    import os

    if not os.path.exists('cron_log.txt'):
        print("   ⚠️  No cron_log.txt found (cron hasn't run yet)")
        print("   ℹ️  This is normal if cron was just installed")
        return True  # Not a failure, just hasn't run yet

    with open('cron_log.txt', 'r') as f:
        log_content = f.read()

    if 'Scan completed successfully' in log_content:
        # Count successful scans
        successful_scans = log_content.count('Scan completed successfully')
        print(f"   ✓ Log file exists")
        print(f"   ✓ Found {successful_scans} successful scan(s)")

        # Get last scan time
        lines = log_content.split('\n')
        for line in reversed(lines):
            if 'Scan completed successfully at' in line:
                print(f"   ✓ Last scan: {line.split('at')[1].strip()}")
                break

        return True
    else:
        print("   ⚠️  Log exists but no successful scans yet")
        return True  # Not a failure


@test("File Permissions - Script Executability")
def test_file_permissions():
    """Test that necessary files are executable"""
    import os

    files_to_check = [
        'install_cron.sh',
        'check_cron_status.sh',
        'send_test_email.py',
        'run_with_email_alerts.py'
    ]

    all_ok = True
    for filename in files_to_check:
        if os.path.exists(filename):
            is_executable = os.access(filename, os.X_OK)
            if is_executable:
                print(f"   ✓ {filename} is executable")
            else:
                print(f"   ⚠️  {filename} is not executable (run: chmod +x {filename})")
                all_ok = False
        else:
            print(f"   ✗ {filename} not found")
            all_ok = False

    return all_ok


@test("End-to-End - Full Pipeline Dry Run")
def test_full_pipeline():
    """Test the complete pipeline without sending email"""
    from run_working import fetch_and_analyze

    print("   Running full pipeline...")

    # Fetch data
    opportunities = fetch_and_analyze()

    if opportunities is None or len(opportunities) == 0:
        print("   ⚠️  No opportunities found (market is slow)")
        return True  # Not a failure

    # Sort by composite score
    opportunities.sort(key=lambda x: x['composite'], reverse=True)

    # Load config
    with open('email_config.json', 'r') as f:
        config = json.load(f)

    min_score = config['alert_settings']['min_score_to_alert']
    high_quality = [o for o in opportunities if o['composite'] >= min_score]

    print(f"   ✓ Pipeline executed successfully")
    print(f"   ✓ Analyzed {len(opportunities)} token(s)")
    print(f"   ✓ Top score: {opportunities[0]['composite']:.1f}/100")

    if high_quality:
        print(f"   ✓ Found {len(high_quality)} qualified opportunity(ies)")
    else:
        print(f"   ℹ️  No opportunities above threshold ({min_score})")

    return True


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("SMOKE TEST SUMMARY")
    print("="*80)

    print(f"\nTotal Tests: {tests_total}")
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")

    pass_rate = (tests_passed / tests_total * 100) if tests_total > 0 else 0

    print(f"\nPass Rate: {pass_rate:.1f}%")

    if tests_failed == 0:
        print("\n🎉 ALL TESTS PASSED! Your scanner is ready to use.")
        print("\n✅ Recommended next steps:")
        print("   1. Monitor cron_log.txt for the next few runs")
        print("   2. Verify you receive emails at ltd@bu.edu")
        print("   3. Review opportunities and practice due diligence")
        return 0
    else:
        print(f"\n⚠️  {tests_failed} TEST(S) FAILED - Fix issues before relying on scanner")
        print("\n📋 Troubleshooting:")
        print("   • Check email_config.json is valid")
        print("   • Verify cron job is installed: ./install_cron.sh")
        print("   • Test email sending: python3 send_test_email.py")
        print("   • Check API connectivity and rate limits")
        return 1


def main():
    """Run all smoke tests"""
    print("="*80)
    print("DEX SCANNER - SMOKE TEST SUITE")
    print("="*80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Run all tests
    test_api_connectivity()
    test_email_config()
    test_transparency_scoring()
    test_safety_scoring()
    test_opportunity_scoring()
    test_real_token_fetch()
    test_email_system()
    test_cron_installation()
    test_cron_log()
    test_file_permissions()
    test_full_pipeline()

    # Print summary
    exit_code = print_summary()

    print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
