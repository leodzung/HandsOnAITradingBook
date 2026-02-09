#!/usr/bin/env python3
"""
Helper script to set up cron job for collector monitoring.
Adds monitoring to crontab automatically.
"""

import os
import subprocess
import sys
from pathlib import Path

def get_current_crontab():
    """Get current crontab entries."""
    try:
        result = subprocess.run(
            ['crontab', '-l'],
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else ""
    except:
        return ""

def add_to_crontab(new_entry):
    """Add new entry to crontab."""
    current = get_current_crontab()

    # Check if already exists
    if 'monitor_collectors.py' in current:
        print("⚠️  Monitoring already in crontab")
        print("\nCurrent entry:")
        for line in current.split('\n'):
            if 'monitor_collectors.py' in line:
                print(f"  {line}")

        response = input("\nReplace with new entry? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled")
            return False

        # Remove old entry
        lines = [line for line in current.split('\n') if 'monitor_collectors.py' not in line]
        current = '\n'.join(lines)

    # Add new entry
    if current and not current.endswith('\n'):
        current += '\n'

    new_crontab = current + new_entry + '\n'

    # Write to crontab
    try:
        process = subprocess.Popen(
            ['crontab', '-'],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(input=new_crontab)

        if process.returncode == 0:
            print("✓ Monitoring added to crontab successfully!")
            return True
        else:
            print("✗ Failed to update crontab")
            return False
    except Exception as e:
        print(f"✗ Error updating crontab: {e}")
        return False

def main():
    print("=== Collector Monitoring Setup ===\n")

    # Get current directory
    current_dir = Path.cwd()

    # Check if monitor_collectors.py exists
    monitor_script = current_dir / "monitor_collectors.py"
    if not monitor_script.exists():
        print(f"✗ Error: monitor_collectors.py not found in {current_dir}")
        print("\nMake sure you're running this from the project directory:")
        print(f"  cd '{current_dir}'")
        sys.exit(1)

    print(f"Working directory: {current_dir}")
    print(f"Monitor script: {monitor_script}")
    print()

    # Check if telegram_config.json exists
    config_file = current_dir / "telegram_config.json"
    if not config_file.exists():
        print("⚠️  Warning: telegram_config.json not found")
        print("\nYou need to create it first:")
        print("  1. cp telegram_config.json.example telegram_config.json")
        print("  2. Edit telegram_config.json with your bot token and chat_id")
        print("  3. Test with: python3 monitor_collectors.py --test")
        print()

        response = input("Continue without config? (monitoring won't send alerts) (y/n): ")
        if response.lower() != 'y':
            print("\nCancelled. Set up telegram_config.json first.")
            sys.exit(1)

    # Create cron entry
    print("\nChoose monitoring frequency:")
    print("  1. Every 5 minutes (recommended)")
    print("  2. Every 10 minutes")
    print("  3. Every 15 minutes")
    print("  4. Custom interval")

    choice = input("\nChoice (1-4): ").strip()

    if choice == '1':
        interval = '*/5'
    elif choice == '2':
        interval = '*/10'
    elif choice == '3':
        interval = '*/15'
    elif choice == '4':
        custom = input("Enter interval in minutes: ").strip()
        try:
            minutes = int(custom)
            interval = f'*/{minutes}'
        except:
            print("Invalid interval, using default (5 minutes)")
            interval = '*/5'
    else:
        print("Invalid choice, using default (5 minutes)")
        interval = '*/5'

    # Escape spaces in path for cron
    escaped_path = str(current_dir).replace(' ', '\\ ')

    cron_entry = (
        f"{interval} * * * * "
        f"cd {escaped_path} && "
        f"python3 monitor_collectors.py >> monitoring.log 2>&1"
    )

    print("\nCron entry to be added:")
    print(f"  {cron_entry}")
    print()

    response = input("Add to crontab? (y/n): ")
    if response.lower() != 'y':
        print("\nCancelled")
        print("\nTo add manually:")
        print("  1. Run: crontab -e")
        print(f"  2. Add this line:\n     {cron_entry}")
        sys.exit(0)

    # Add to crontab
    if add_to_crontab(cron_entry):
        print("\n✓ Setup complete!")
        print("\nWhat happens now:")
        print(f"  - Monitoring runs every {interval.replace('*/', '')} minutes")
        print("  - Checks if collectors are running and healthy")
        print("  - Sends Telegram alerts if issues detected")
        print("  - Logs saved to monitoring.log")
        print("\nUseful commands:")
        print("  - View cron jobs:     crontab -l")
        print("  - Check logs:         tail -f monitoring.log")
        print("  - Test manually:      python3 monitor_collectors.py")
        print("  - Test alerts:        python3 monitor_collectors.py --test")
        print("  - Remove from cron:   crontab -e (then delete the line)")

        # Offer to run test
        print()
        response = input("Run test now? (y/n): ")
        if response.lower() == 'y':
            print("\nRunning test...")
            subprocess.run(['python3', 'monitor_collectors.py'])
    else:
        print("\n✗ Setup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
