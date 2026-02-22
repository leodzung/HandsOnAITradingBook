#!/usr/bin/env python3
"""Interactive setup script for Agentic Portfolio Manager MVP"""
import os
import sys
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_step(num, text):
    print(f"\n{'='*60}")
    print(f"STEP {num}: {text}")
    print(f"{'='*60}\n")

def check_python():
    """Check Python version"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"❌ Python 3.9+ required. You have: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """Check if dependencies are installed"""
    required = ['openai', 'alpaca_trade_api', 'pandas', 'yfinance', 'rich', 'dotenv']
    missing = []

    for package in required:
        try:
            __import__(package if package != 'dotenv' else 'dotenv')
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing.append(package)

    return len(missing) == 0, missing

def install_dependencies():
    """Install dependencies"""
    print("\n📦 Installing dependencies...")
    print("This may take 1-2 minutes...\n")

    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✅ Dependencies installed successfully!")
        return True
    else:
        print(f"❌ Installation failed:\n{result.stderr}")
        return False

def setup_env_file():
    """Guide user through .env setup"""
    env_path = Path('.env')

    if env_path.exists():
        response = input("\n⚠️  .env file already exists. Overwrite? (y/n): ").lower()
        if response != 'y':
            print("Keeping existing .env file.")
            return True

    print("\n📝 Setting up .env file...")
    print("\nYou'll need:")
    print("  1. Alpaca API Key (from https://alpaca.markets)")
    print("  2. Alpaca Secret Key")
    print("  3. OpenAI API Key (from https://platform.openai.com)")

    print("\n" + "─" * 60)
    print("ALPACA SETUP")
    print("─" * 60)
    print("\nIf you don't have an Alpaca account yet:")
    print("  1. Go to: https://alpaca.markets")
    print("  2. Sign up (free)")
    print("  3. Enable paper trading")
    print("  4. Get your API keys from the dashboard")
    input("\nPress Enter when you have your Alpaca keys ready...")

    alpaca_key = input("\nEnter Alpaca API Key: ").strip()
    alpaca_secret = input("Enter Alpaca Secret Key: ").strip()

    print("\n" + "─" * 60)
    print("OPENAI SETUP")
    print("─" * 60)
    print("\nIf you don't have an OpenAI account yet:")
    print("  1. Go to: https://platform.openai.com/signup")
    print("  2. Sign up and add payment method")
    print("  3. Create an API key")
    print("  4. Add $5-10 credits for testing")
    input("\nPress Enter when you have your OpenAI key ready...")

    openai_key = input("\nEnter OpenAI API Key: ").strip()

    # Write .env file
    env_content = f"""# Agentic Portfolio Manager MVP - Configuration

# Alpaca API (Paper Trading - SAFE)
ALPACA_API_KEY={alpaca_key}
ALPACA_SECRET_KEY={alpaca_secret}
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# OpenAI API
OPENAI_API_KEY={openai_key}
OPENAI_MODEL=gpt-4-turbo-preview

# Risk Management Settings
MAX_POSITION_SIZE_PCT=0.10
MAX_PORTFOLIO_VOLATILITY=0.15
MIN_CASH_RESERVE_PCT=0.05

# Analysis Settings
LOOKBACK_DAYS=60
MOMENTUM_THRESHOLD=0.05
"""

    with open('.env', 'w') as f:
        f.write(env_content)

    print("\n✅ .env file created!")
    return True

def test_connections():
    """Test API connections"""
    print_step("TEST", "Testing Connections")

    # Test config loading
    print("Loading configuration...")
    try:
        import config
        config.validate_config()
        print("✅ Configuration loaded")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

    # Test Alpaca
    print("\nTesting Alpaca connection...")
    try:
        from alpaca_client import AlpacaClient
        alpaca = AlpacaClient()
        portfolio = alpaca.get_portfolio()
        print(f"✅ Connected to Alpaca")
        print(f"   Cash: ${portfolio.cash:,.2f}")
        print(f"   Portfolio Value: ${portfolio.portfolio_value:,.2f}")
    except Exception as e:
        print(f"❌ Alpaca connection failed: {e}")
        print("\nCheck:")
        print("  - Are your Alpaca API keys correct?")
        print("  - Did you enable paper trading?")
        print("  - Try regenerating your keys")
        return False

    # Test OpenAI
    print("\nTesting OpenAI connection...")
    try:
        from llm_client import LLMClient
        llm = LLMClient()
        response = llm.complete(
            system_prompt="You are a helpful assistant.",
            user_message="Say 'Connection successful' and nothing else."
        )
        if response:
            print(f"✅ Connected to OpenAI")
            print(f"   Response: {response[:50]}...")
        else:
            print("❌ OpenAI returned empty response")
            return False
    except Exception as e:
        print(f"❌ OpenAI connection failed: {e}")
        print("\nCheck:")
        print("  - Is your OpenAI API key correct?")
        print("  - Do you have credits in your account?")
        print("  - Check: https://platform.openai.com/account/billing")
        return False

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    return True

def main():
    """Main setup flow"""
    print_header("🤖 Agentic Portfolio Manager - Setup")

    print("This script will help you set up the MVP.\n")
    print("You'll need:")
    print("  ✓ Internet connection")
    print("  ✓ Alpaca account (free paper trading)")
    print("  ✓ OpenAI account (~$5-10 for testing)")

    input("\nPress Enter to begin setup...")

    # Step 1: Check Python
    print_step(1, "Checking Python")
    if not check_python():
        print("\n❌ Please install Python 3.9 or higher")
        print("   Visit: https://www.python.org/downloads/")
        sys.exit(1)

    # Step 2: Check/Install Dependencies
    print_step(2, "Checking Dependencies")
    deps_ok, missing = check_dependencies()

    if not deps_ok:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        response = input("\nInstall now? (y/n): ").lower()
        if response == 'y':
            if not install_dependencies():
                print("\n❌ Setup failed. Please install manually:")
                print("   pip3 install -r requirements.txt")
                sys.exit(1)
        else:
            print("\n❌ Cannot continue without dependencies")
            sys.exit(1)

    # Step 3: Setup .env
    print_step(3, "Configuring API Keys")
    if not setup_env_file():
        print("\n❌ Setup cancelled")
        sys.exit(1)

    # Step 4: Test connections
    if not test_connections():
        print("\n❌ Connection tests failed")
        print("\nPlease fix the errors and run setup again:")
        print("   python3 setup.py")
        sys.exit(1)

    # Success!
    print("\n" + "=" * 60)
    print("✅ SETUP COMPLETE!")
    print("=" * 60)
    print("\nYou're ready to run the MVP!")
    print("\nTo start:")
    print("   python3 main.py")
    print("\nFirst time? Try this:")
    print("   1. Select option '1' (Run AI Analysis)")
    print("   2. Wait 30-60 seconds for agents to analyze")
    print("   3. Review the recommendations")
    print("   4. Decide if you want to execute trades")
    print("\nGood luck! 🚀\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)
