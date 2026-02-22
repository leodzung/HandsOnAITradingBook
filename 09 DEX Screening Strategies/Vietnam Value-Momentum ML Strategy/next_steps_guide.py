"""
Interactive Guide: Next Steps After Your First Backtest

This script walks you through analyzing your results and testing robustness.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

def step_1_analyze_results():
    """Step 1: Analyze your backtest results in detail."""
    print("\n" + "="*70)
    print("STEP 1: ANALYZE YOUR BACKTEST RESULTS")
    print("="*70)

    # Load results
    if not os.path.exists('simple_backtest_results.csv'):
        print("❌ No results file found. Run simple_backtest_real_data.py first!")
        return False

    results = pd.read_csv('simple_backtest_results.csv')
    results['date'] = pd.to_datetime(results['date'])

    print(f"\n📊 Your Backtest Summary:")
    print(f"   Period: {results['date'].iloc[0].date()} to {results['date'].iloc[-1].date()}")
    print(f"   Trading days: {len(results)}")
    print(f"   Final return: {results['return'].iloc[-1]:.2f}%")

    # Monthly returns
    results['month'] = results['date'].dt.to_period('M')
    monthly_returns = results.groupby('month')['return'].last().diff()

    print(f"\n📅 Monthly Returns:")
    for month, ret in monthly_returns.items():
        if pd.notna(ret):
            emoji = "📈" if ret > 0 else "📉"
            print(f"   {month}: {emoji} {ret:+.2f}%")

    # Best and worst days
    results['daily_return'] = results['return'].diff()
    best_day = results.loc[results['daily_return'].idxmax()]
    worst_day = results.loc[results['daily_return'].idxmin()]

    print(f"\n🎯 Best Day: {best_day['date'].date()} (+{best_day['daily_return']:.2f}%)")
    print(f"⚠️  Worst Day: {worst_day['date'].date()} ({worst_day['daily_return']:.2f}%)")

    # Win rate
    winning_days = (results['daily_return'] > 0).sum()
    total_days = len(results['daily_return'].dropna())
    win_rate = winning_days / total_days * 100

    print(f"\n🎲 Win Rate: {win_rate:.1f}% ({winning_days}/{total_days} days)")

    return True


def step_2_test_different_periods():
    """Step 2: Test strategy on different time periods."""
    print("\n" + "="*70)
    print("STEP 2: TEST ON DIFFERENT TIME PERIODS")
    print("="*70)

    print("\n🔍 Why test different periods?")
    print("   - 2024 was a good year (bull market)")
    print("   - Strategy needs to work in different conditions")
    print("   - Avoid overfitting to recent data")

    test_periods = [
        ("Recent (2024)", datetime(2024, 1, 1), datetime(2024, 10, 31)),
        ("Full 2023", datetime(2023, 1, 1), datetime(2023, 12, 31)),
        ("COVID Recovery (2021)", datetime(2021, 1, 1), datetime(2021, 12, 31)),
        ("Bear Market (2022)", datetime(2022, 1, 1), datetime(2022, 12, 31)),
    ]

    print("\n📋 Suggested Test Periods:")
    for i, (name, start, end) in enumerate(test_periods, 1):
        print(f"   {i}. {name}: {start.date()} to {end.date()}")

    print("\n💡 How to test:")
    print("   1. Open simple_backtest_real_data.py")
    print("   2. Edit lines 21-22 to change dates")
    print("   3. Run: python3 simple_backtest_real_data.py")
    print("   4. Compare results across periods")

    return True


def step_3_experiment_with_parameters():
    """Step 3: Experiment with strategy parameters."""
    print("\n" + "="*70)
    print("STEP 3: EXPERIMENT WITH PARAMETERS")
    print("="*70)

    print("\n🔬 Parameters you can tune:")

    experiments = [
        {
            'name': 'Number of Stocks',
            'current': '3 stocks',
            'try': 'Change line 125: selected_stocks = [s for s, _ in sorted_preds[:5]]',
            'impact': 'More stocks = more diversification, less concentration'
        },
        {
            'name': 'Rebalancing Frequency',
            'current': '90 days (quarterly)',
            'try': 'Change line 104: rebalance_interval = 60 or 120',
            'impact': 'More frequent = higher costs, may capture trends better'
        },
        {
            'name': 'ML Prediction Horizon',
            'current': '60 days',
            'try': 'Change line 40: prediction_horizon_days=30 or 90',
            'impact': 'Shorter = more responsive, longer = more stable'
        },
        {
            'name': 'Universe Size',
            'current': '5 stocks (VNM, VCB, HPG, FPT, MSN)',
            'try': 'Change line 20: universe = [add more stocks]',
            'impact': 'Larger universe = more opportunities, slower execution'
        }
    ]

    for i, exp in enumerate(experiments, 1):
        print(f"\n{i}. {exp['name']}")
        print(f"   Current: {exp['current']}")
        print(f"   Try: {exp['try']}")
        print(f"   Impact: {exp['impact']}")

    print("\n💡 Best practice:")
    print("   - Change ONE parameter at a time")
    print("   - Document what you changed")
    print("   - Compare results to baseline (25.57%)")

    return True


def step_4_walk_forward_testing():
    """Step 4: Walk-forward validation (advanced)."""
    print("\n" + "="*70)
    print("STEP 4: WALK-FORWARD VALIDATION (Advanced)")
    print("="*70)

    print("\n🎓 What is walk-forward testing?")
    print("   - Train on past data (e.g., 2022)")
    print("   - Test on future data (e.g., 2023)")
    print("   - Retrain and test again (2024)")
    print("   - This simulates real trading more accurately")

    print("\n📅 Example walk-forward schedule:")
    print("   1. Train: 2021-2022 → Test: 2023 Q1")
    print("   2. Train: 2021-2023 Q1 → Test: 2023 Q2")
    print("   3. Train: 2021-2023 Q2 → Test: 2023 Q3")
    print("   4. And so on...")

    print("\n💡 Why do this?")
    print("   - Prevents look-ahead bias")
    print("   - More realistic performance estimate")
    print("   - Required before live trading")

    print("\n🛠️ Implementation:")
    print("   - Create a loop over time periods")
    print("   - Train ML model on each period")
    print("   - Test on next period")
    print("   - Aggregate results")

    return True


def step_5_prepare_for_paper_trading():
    """Step 5: Prepare for paper trading."""
    print("\n" + "="*70)
    print("STEP 5: PREPARE FOR PAPER TRADING")
    print("="*70)

    print("\n📝 Before you paper trade:")

    checklist = [
        ("✅ Strategy works on 3+ different time periods", False),
        ("✅ Tested with different parameters", False),
        ("✅ Understand why strategy makes money", False),
        ("✅ Know the risks and limitations", False),
        ("✅ Have a plan for when it underperforms", False),
        ("✅ Opened paper trading account", False),
    ]

    for item, checked in checklist:
        print(f"   {item}")

    print("\n🏦 Vietnamese brokers with paper trading:")
    print("   1. SSI (SSI iBoard) - https://www.ssi.com.vn")
    print("   2. VPS - https://www.vps.com.vn")
    print("   3. VNDIRECT - https://www.vndirect.com.vn")

    print("\n💡 Paper trading plan:")
    print("   - Start with virtual 100M VND")
    print("   - Trade for 2-3 quarters (6-9 months)")
    print("   - Compare to backtest expectations")
    print("   - Track all costs and slippage")
    print("   - Document what works and what doesn't")

    print("\n⚠️  Key differences from backtest:")
    print("   - Real market hours (9:00-11:30, 1:00-3:00 Vietnam time)")
    print("   - Price limits (±7% daily)")
    print("   - Foreign ownership limits (monitor room)")
    print("   - Execution delays and slippage")
    print("   - Your emotions! (Discipline is key)")

    return True


def create_comparison_template():
    """Create a template for comparing different runs."""
    print("\n" + "="*70)
    print("BONUS: COMPARISON TEMPLATE")
    print("="*70)

    template = """
# Strategy Comparison Template

| Run | Period | Stocks | Rebal | Return | Sharpe | Max DD | Notes |
|-----|--------|--------|-------|--------|--------|--------|-------|
| 1   | 2024   | 3      | 90d   | 25.57% | 1.72   | -10.6% | Baseline |
| 2   |        |        |       |        |        |        |        |
| 3   |        |        |       |        |        |        |        |
| 4   |        |        |       |        |        |        |        |

## Best Configuration:
-

## Lessons Learned:
-

## Next Actions:
-
"""

    with open('strategy_comparison.md', 'w') as f:
        f.write(template)

    print("\n✅ Created strategy_comparison.md")
    print("   Use this to track your experiments!")


def main():
    """Run the interactive guide."""
    print("\n" + "="*70)
    print("🚀 NEXT STEPS GUIDE - Vietnamese Stock Strategy")
    print("="*70)

    print("\nYou've completed your first successful backtest!")
    print("Return: +25.57% | Sharpe: 1.72 | Max DD: -10.59%")

    print("\nNow let's make sure this is robust before live trading.")
    print("We'll walk through 5 key validation steps:\n")

    steps = [
        ("Analyze Your Results", step_1_analyze_results),
        ("Test Different Time Periods", step_2_test_different_periods),
        ("Experiment with Parameters", step_3_experiment_with_parameters),
        ("Walk-Forward Validation", step_4_walk_forward_testing),
        ("Prepare for Paper Trading", step_5_prepare_for_paper_trading),
    ]

    for i, (name, func) in enumerate(steps, 1):
        print(f"{i}. {name}")

    print("\n" + "="*70)
    input("\nPress Enter to start Step 1...")

    # Run each step
    for i, (name, func) in enumerate(steps, 1):
        try:
            success = func()

            if i < len(steps):
                input(f"\nPress Enter to continue to Step {i+1}...")
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")

    # Create comparison template
    create_comparison_template()

    # Final summary
    print("\n" + "="*70)
    print("🎉 NEXT STEPS GUIDE COMPLETE!")
    print("="*70)

    print("\n📋 Your Action Plan:")
    print("   1. ✅ Analyze results (just completed)")
    print("   2. 🔄 Test on 2023 data (change dates, run again)")
    print("   3. 🔄 Test on 2022 data (bear market test)")
    print("   4. 🔬 Experiment with 5 stocks instead of 3")
    print("   5. 📊 Compare all results in strategy_comparison.md")
    print("   6. 🎯 If consistent, move to paper trading")

    print("\n💡 Remember:")
    print("   - Don't rush to live trading")
    print("   - Test thoroughly on different periods")
    print("   - Understand WHY the strategy works")
    print("   - Paper trade for at least 6 months")

    print("\n🚀 Quick Commands:")
    print("   Run on 2023: Edit simple_backtest_real_data.py lines 21-22")
    print("   Try 5 stocks: Edit simple_backtest_real_data.py line 125")
    print("   Add stocks: Edit simple_backtest_real_data.py line 20")

    print("\n📚 Need Help?")
    print("   - Read RESULTS_SUMMARY.md for detailed analysis")
    print("   - Check STRATEGY_DESIGN.md for methodology")
    print("   - Review code comments for understanding")

    print("\nGood luck! 🇻🇳📈\n")


if __name__ == '__main__':
    main()
