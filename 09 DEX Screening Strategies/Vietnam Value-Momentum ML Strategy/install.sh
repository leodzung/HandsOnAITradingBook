#!/bin/bash

# Installation script for Vietnam Value-Momentum ML Strategy
# This script installs all required dependencies

echo "=========================================================================="
echo "  Vietnam Value-Momentum ML Strategy - Installation"
echo "=========================================================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
required_version="3.7"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.7 or higher required. You have Python $python_version"
    exit 1
fi

echo "✅ Python $python_version detected"
echo ""

# Install required packages
echo "Installing required packages..."
echo ""

packages=(
    "pandas>=1.3.0"
    "numpy>=1.21.0"
    "scikit-learn>=0.24.0"
    "vnstock3"
)

for package in "${packages[@]}"; do
    echo "Installing $package..."
    pip3 install "$package" --quiet
    if [ $? -eq 0 ]; then
        echo "✅ $package installed"
    else
        echo "❌ Failed to install $package"
        exit 1
    fi
done

echo ""
echo "Installing optional packages..."
pip3 install matplotlib --quiet 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ matplotlib installed (for charts)"
else
    echo "⚠️ matplotlib installation failed (optional, charts won't be generated)"
fi

echo ""
echo "=========================================================================="
echo "  Installation Complete!"
echo "=========================================================================="
echo ""
echo "Next steps:"
echo "1. Test the installation:"
echo "   python3 test_real_data.py"
echo ""
echo "2. Run your first backtest:"
echo "   python3 standalone_strategy_real_data.py"
echo ""
echo "3. Read the Quick Start guide:"
echo "   cat QUICKSTART.md"
echo ""
echo "Happy trading! 🇻🇳📈"
echo ""
