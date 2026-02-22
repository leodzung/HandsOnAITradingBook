#!/usr/bin/env python3
"""Interactive setup script for E-Commerce Arbitrage System."""

import os
import sys
import shutil
from pathlib import Path


class Colors:
    """Terminal colors."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")


def print_success(text):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def check_python_version():
    """Check Python version."""
    print_header("Step 1: Checking Python Version")

    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error("Python 3.8 or higher is required")
        return False

    print_success("Python version is compatible")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    print_header("Step 2: Checking Dependencies")

    required_packages = [
        'requests',
        'yaml',
        'pandas',
        'sqlalchemy',
    ]

    optional_packages = {
        'keepa': 'For Keepa API integration (highly recommended)',
        'telegram': 'For Telegram notifications',
        'playwright': 'For web scraping (optional)',
    }

    missing_required = []
    missing_optional = []

    for package in required_packages:
        try:
            __import__(package)
            print_success(f"{package} is installed")
        except ImportError:
            print_error(f"{package} is NOT installed")
            missing_required.append(package)

    print("\nOptional packages:")
    for package, description in optional_packages.items():
        try:
            __import__(package)
            print_success(f"{package} is installed - {description}")
        except ImportError:
            print_warning(f"{package} is NOT installed - {description}")
            missing_optional.append(package)

    if missing_required:
        print_error(f"\nMissing required packages: {', '.join(missing_required)}")
        print_info("Run: pip install -r requirements.txt")
        return False

    if missing_optional:
        print_warning(f"\nOptional packages not installed: {', '.join(missing_optional)}")
        print_info("These can be installed later as needed")

    return True


def create_directories():
    """Create necessary directories."""
    print_header("Step 3: Creating Directories")

    directories = ['data', 'logs', 'config']

    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created {directory}/ directory")
        else:
            print_info(f"{directory}/ already exists")

    return True


def setup_config_file():
    """Set up configuration file."""
    print_header("Step 4: Configuration File Setup")

    config_path = Path('config/config.yaml')
    example_path = Path('config/config.example.yaml')

    if config_path.exists():
        print_warning("config.yaml already exists")
        response = input("Do you want to overwrite it? (yes/no): ").lower()
        if response not in ['yes', 'y']:
            print_info("Keeping existing config.yaml")
            return True

    if example_path.exists():
        shutil.copy(example_path, config_path)
        print_success("Created config/config.yaml from template")
        print_warning("You need to edit config/config.yaml with your API credentials")
        return True
    else:
        print_error("config.example.yaml not found")
        return False


def setup_env_file():
    """Set up environment file."""
    print_header("Step 5: Environment File Setup")

    env_path = Path('.env')
    example_path = Path('.env.example')

    if env_path.exists():
        print_warning(".env already exists")
        response = input("Do you want to overwrite it? (yes/no): ").lower()
        if response not in ['yes', 'y']:
            print_info("Keeping existing .env")
            return True

    if example_path.exists():
        shutil.copy(example_path, env_path)
        print_success("Created .env from template")
        print_warning("You need to edit .env with your credentials")
        return True
    else:
        print_error(".env.example not found")
        return False


def test_database():
    """Test database connection."""
    print_header("Step 6: Testing Database")

    try:
        from src.utils.database import DatabaseManager

        db = DatabaseManager("sqlite:///data/deals.db")
        print_success("Database initialized successfully")
        print_info("Database location: data/deals.db")
        return True
    except Exception as e:
        print_error(f"Database test failed: {e}")
        return False


def print_next_steps():
    """Print next steps."""
    print_header("Setup Complete! Next Steps:")

    print(f"{Colors.BOLD}1. Configure API Credentials{Colors.END}")
    print("   Edit config/config.yaml and add your API keys:")
    print("   - Amazon SP-API credentials (required)")
    print("   - Keepa API key (highly recommended)")
    print("   - Email SMTP settings (for alerts)")
    print()

    print(f"{Colors.BOLD}2. Get API Credentials{Colors.END}")
    print()
    print("   Amazon SP-API:")
    print("   • Go to: https://sellercentral.amazon.com")
    print("   • Navigate to: Apps & Services > Develop Apps")
    print("   • Create a new app and get credentials")
    print()
    print("   Keepa API:")
    print("   • Go to: https://keepa.com")
    print("   • Sign up and subscribe to API access ($19-149/month)")
    print("   • Get your API key from account settings")
    print()
    print("   Email (Gmail example):")
    print("   • Enable 2FA on Google account")
    print("   • Create App Password: https://myaccount.google.com/apppasswords")
    print("   • Use app password in config")
    print()

    print(f"{Colors.BOLD}3. Test the System{Colors.END}")
    print("   python main.py --show-deals")
    print()

    print(f"{Colors.BOLD}4. Run Your First Scan{Colors.END}")
    print("   python main.py --scanner amazon")
    print()

    print(f"{Colors.BOLD}5. View Documentation{Colors.END}")
    print("   README.md - Full documentation")
    print("   QUICKSTART.md - Quick start guide")
    print()

    print(f"{Colors.GREEN}{Colors.BOLD}Need help? Check the documentation or run:{Colors.END}")
    print(f"{Colors.GREEN}python main.py --help{Colors.END}")


def main():
    """Run setup."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║     E-Commerce Arbitrage System - Interactive Setup              ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")

    steps = [
        ("Checking Python version", check_python_version),
        ("Checking dependencies", check_dependencies),
        ("Creating directories", create_directories),
        ("Setting up config file", setup_config_file),
        ("Setting up environment file", setup_env_file),
        ("Testing database", test_database),
    ]

    failed_steps = []

    for step_name, step_func in steps:
        if not step_func():
            failed_steps.append(step_name)

    if failed_steps:
        print_header("Setup Incomplete")
        print_error("The following steps failed:")
        for step in failed_steps:
            print(f"  - {step}")
        print()
        print_warning("Please fix the errors and run setup again")
        return 1

    print_next_steps()
    return 0


if __name__ == "__main__":
    sys.exit(main())
