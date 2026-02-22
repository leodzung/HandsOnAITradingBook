#!/bin/bash
# Quick test on 2023 data

echo "Testing strategy on 2023 data..."
echo ""

# Create a test version
cp simple_backtest_real_data.py test_2023.py

# Update dates to 2023
sed -i '' 's/datetime(2024, 1, 1)/datetime(2023, 1, 1)/g' test_2023.py
sed -i '' 's/datetime(2024, 10, 31)/datetime(2023, 12, 31)/g' test_2023.py

# Run backtest
python3 test_2023.py

# Rename results
mv simple_backtest_results.csv backtest_2023_results.csv

echo ""
echo "✅ 2023 backtest complete!"
echo "Results saved to backtest_2023_results.csv"
echo ""
echo "Compare to 2024:"
echo "  2024: +25.57% | Sharpe 1.72 | Max DD -10.59%"
echo "  2023: Check backtest_2023_results.csv"
