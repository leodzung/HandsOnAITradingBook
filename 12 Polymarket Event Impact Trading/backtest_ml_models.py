#!/usr/bin/env python3
"""
Backtest ML Models - Simulate trading with ML predictions.
Tests all three models and compares vs baseline strategies.
"""

import pandas as pd
import numpy as np
import pickle
import logging
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MLModelBacktester:
    """Backtest ML models with realistic trading simulation."""
    
    def __init__(self, data_path='data/REAL_labeled_from_alchemy.csv',
                 initial_balance=10000.0):
        self.data_path = data_path
        self.initial_balance = initial_balance
        self.models = {}
        
        logger.info(f"Loading data from {data_path}")
        self.df = pd.read_csv(data_path)
        self.df['timestamp'] = pd.to_datetime(self.df['block_timestamp'])
        
        # Sort by time
        self.df = self.df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"✅ Loaded {len(self.df):,} trades from {self.df['condition_id'].nunique():,} markets")
        
    def load_models(self):
        """Load all trained models."""
        logger.info("\n=== Loading Models ===")
        
        for bot_name in ['event', 'price_level', 'short_expiry']:
            model_path = f'data/models/{bot_name}_model.pkl'
            with open(model_path, 'rb') as f:
                model_info = pickle.load(f)
                self.models[bot_name] = {
                    'model': model_info['model'],
                    'features': model_info['feature_names'],
                    'metrics': model_info['metrics']
                }
            logger.info(f"✅ Loaded {bot_name} model")
    
    def engineer_features(self, df):
        """Engineer features for predictions."""
        df = df.copy()
        
        # Price features
        df['price_squared'] = df['trade_price'] ** 2
        df['price_cubed'] = df['trade_price'] ** 3
        df['log_price'] = np.log(df['trade_price'].clip(0.001, 0.999))
        df['price_distance_from_half'] = np.abs(df['trade_price'] - 0.5)
        df['betting_yes'] = (df['trade_price'] > 0.5).astype(int)
        df['betting_no'] = (df['trade_price'] < 0.5).astype(int)
        df['market_confidence'] = np.abs(df['trade_price'] - 0.5) * 2
        
        # Time features
        df['hour_of_day'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # Market features
        df['question_length'] = df['question'].str.len()
        df['question_words'] = df['question'].str.split().str.len()
        df['is_sports'] = df['question'].str.contains(
            'win|championship|bowl|playoff|coach|mvp|athlete',
            case=False, na=False
        ).astype(int)
        df['is_politics'] = df['question'].str.contains(
            'election|president|mayor|vote|poll',
            case=False, na=False
        ).astype(int)
        df['is_crypto'] = df['question'].str.contains(
            'bitcoin|btc|ethereum|eth|crypto|blockchain|fed|interest|rate',
            case=False, na=False
        ).astype(int)
        
        return df
    
    def backtest_strategy(self, df, model_name, confidence_threshold=0.6,
                         position_size=100.0, max_positions=10):
        """
        Backtest a trading strategy using ML predictions.
        
        Args:
            df: DataFrame with features and labels
            model_name: Which model to use
            confidence_threshold: Minimum confidence to trade
            position_size: $ amount per position
            max_positions: Maximum concurrent positions
        """
        model_info = self.models[model_name]
        model = model_info['model']
        feature_cols = model_info['features']
        
        # Get features
        X = df[feature_cols].fillna(0)
        
        # Get predictions
        logger.info(f"Generating predictions for {len(X):,} trades...")
        predictions = model.predict_proba(X)[:, 1]  # Probability of correct
        
        # Simulate trading
        balance = self.initial_balance
        positions = []
        trades_executed = 0
        trades_skipped = 0
        
        results = []
        
        for idx, (_, row) in enumerate(df.iterrows()):
            pred_confidence = predictions[idx]
            actual_correct = row['label'] == 1
            
            # Trading decision
            if pred_confidence >= confidence_threshold and len(positions) < max_positions:
                # Execute trade
                trades_executed += 1
                
                # Calculate P&L (simplified)
                if actual_correct:
                    # Win: Get back position_size + profit
                    # Assume 1:1 payout for simplicity
                    pnl = position_size
                else:
                    # Loss: Lose position_size
                    pnl = -position_size
                
                balance += pnl
                
                results.append({
                    'trade_num': trades_executed,
                    'timestamp': row['timestamp'],
                    'market': row['question'][:50],
                    'confidence': pred_confidence,
                    'predicted_correct': True,
                    'actual_correct': actual_correct,
                    'pnl': pnl,
                    'balance': balance,
                    'position_size': position_size
                })
            else:
                trades_skipped += 1
        
        results_df = pd.DataFrame(results)
        
        # Calculate metrics
        if len(results_df) > 0:
            total_trades = len(results_df)
            wins = (results_df['actual_correct'] == True).sum()
            losses = (results_df['actual_correct'] == False).sum()
            win_rate = wins / total_trades if total_trades > 0 else 0
            
            total_pnl = results_df['pnl'].sum()
            final_balance = balance
            roi = (final_balance - self.initial_balance) / self.initial_balance
            
            avg_win = results_df[results_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
            avg_loss = abs(results_df[results_df['pnl'] < 0]['pnl'].mean()) if losses > 0 else 0
            profit_factor = (wins * avg_win) / (losses * avg_loss) if losses > 0 else float('inf')
            
            # Drawdown
            results_df['cumulative_pnl'] = results_df['pnl'].cumsum()
            results_df['running_max'] = results_df['cumulative_pnl'].cummax()
            results_df['drawdown'] = results_df['running_max'] - results_df['cumulative_pnl']
            max_drawdown = results_df['drawdown'].max()
            
            metrics = {
                'total_trades': total_trades,
                'trades_skipped': trades_skipped,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'final_balance': final_balance,
                'roi': roi,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'avg_confidence': results_df['confidence'].mean()
            }
        else:
            metrics = {
                'total_trades': 0,
                'trades_skipped': trades_skipped,
                'error': 'No trades executed'
            }
        
        return metrics, results_df
    
    def compare_strategies(self, df):
        """Compare ML strategy vs baseline strategies."""
        logger.info("\n" + "="*70)
        logger.info("BACKTESTING ALL STRATEGIES")
        logger.info("="*70)
        
        # Use time-based split - test on most recent 30% of data
        # (simulates "what if we had the model earlier")
        split_idx = int(len(df) * 0.70)
        test_df = df.iloc[split_idx:].reset_index(drop=True)
        
        logger.info(f"\nTest period: {len(test_df):,} trades")
        logger.info(f"Date range: {test_df['timestamp'].min()} → {test_df['timestamp'].max()}")
        
        strategies = {}
        
        # Strategy 1: ML Model (60% confidence)
        logger.info("\n--- ML Strategy (60% threshold) ---")
        ml_metrics, ml_trades = self.backtest_strategy(
            test_df, 'event', confidence_threshold=0.60,
            position_size=100, max_positions=20
        )
        strategies['ML (60% confidence)'] = ml_metrics
        
        # Strategy 2: ML Model (70% confidence - more conservative)
        logger.info("\n--- ML Strategy (70% threshold) ---")
        ml_conservative, ml_conservative_trades = self.backtest_strategy(
            test_df, 'event', confidence_threshold=0.70,
            position_size=100, max_positions=20
        )
        strategies['ML (70% confidence)'] = ml_conservative
        
        # Strategy 3: ML Model (80% confidence - very conservative)
        logger.info("\n--- ML Strategy (80% threshold) ---")
        ml_very_conservative, _ = self.backtest_strategy(
            test_df, 'event', confidence_threshold=0.80,
            position_size=100, max_positions=20
        )
        strategies['ML (80% confidence)'] = ml_very_conservative
        
        # Strategy 4: Random baseline (trade all, 50/50 outcomes)
        logger.info("\n--- Random Baseline ---")
        random_balance = self.initial_balance
        random_trades = 0
        for idx, row in test_df.iterrows():
            if random_trades < 200:  # Match ML trade count roughly
                actual_correct = row['label'] == 1
                pnl = 100 if actual_correct else -100
                random_balance += pnl
                random_trades += 1
        
        random_roi = (random_balance - self.initial_balance) / self.initial_balance
        strategies['Random (baseline)'] = {
            'total_trades': random_trades,
            'win_rate': test_df['label'].mean(),
            'final_balance': random_balance,
            'roi': random_roi,
            'total_pnl': random_balance - self.initial_balance
        }
        
        # Print comparison
        self.print_comparison(strategies, ml_trades)
        
        return strategies, ml_trades
    
    def print_comparison(self, strategies, ml_trades):
        """Print strategy comparison table."""
        logger.info("\n" + "="*70)
        logger.info("STRATEGY COMPARISON")
        logger.info("="*70)
        
        print(f"\n{'Strategy':<25} {'Trades':<10} {'Win Rate':<12} {'ROI':<12} {'Final $':<12}")
        print("-" * 70)
        
        for name, metrics in strategies.items():
            if 'error' not in metrics:
                trades = metrics.get('total_trades', 0)
                win_rate = metrics.get('win_rate', 0)
                roi = metrics.get('roi', 0)
                final = metrics.get('final_balance', 0)
                
                print(f"{name:<25} {trades:<10} {win_rate*100:>6.2f}%     {roi*100:>6.2f}%     ${final:>10,.2f}")
        
        print("="*70)
        
        # Detailed ML metrics
        if len(ml_trades) > 0:
            ml_metrics = strategies['ML (60% confidence)']
            
            logger.info("\n=== ML Model (60%) Detailed Metrics ===")
            logger.info(f"Total Trades:      {ml_metrics['total_trades']:,}")
            logger.info(f"Trades Skipped:    {ml_metrics['trades_skipped']:,}")
            logger.info(f"Wins:              {ml_metrics['wins']:,}")
            logger.info(f"Losses:            {ml_metrics['losses']:,}")
            logger.info(f"Win Rate:          {ml_metrics['win_rate']*100:.2f}%")
            logger.info(f"Avg Confidence:    {ml_metrics['avg_confidence']*100:.1f}%")
            logger.info(f"Total P&L:         ${ml_metrics['total_pnl']:,.2f}")
            logger.info(f"Final Balance:     ${ml_metrics['final_balance']:,.2f}")
            logger.info(f"ROI:               {ml_metrics['roi']*100:.2f}%")
            logger.info(f"Profit Factor:     {ml_metrics['profit_factor']:.2f}x")
            logger.info(f"Max Drawdown:      ${ml_metrics['max_drawdown']:,.2f}")
            logger.info(f"Avg Win:           ${ml_metrics['avg_win']:.2f}")
            logger.info(f"Avg Loss:          ${ml_metrics['avg_loss']:.2f}")
            
            # Show best and worst trades
            logger.info("\n=== Best Trades (Top 5) ===")
            best = ml_trades.nlargest(5, 'pnl')
            for _, trade in best.iterrows():
                logger.info(f"  ${trade['pnl']:>6.0f} | {trade['confidence']*100:>5.1f}% conf | {trade['market']}")
            
            logger.info("\n=== Worst Trades (Bottom 5) ===")
            worst = ml_trades.nsmallest(5, 'pnl')
            for _, trade in worst.iterrows():
                logger.info(f"  ${trade['pnl']:>6.0f} | {trade['confidence']*100:>5.1f}% conf | {trade['market']}")
    
    def save_results(self, strategies, trades_df):
        """Save backtest results."""
        results_dir = Path('data/backtest_results')
        results_dir.mkdir(exist_ok=True)
        
        # Save trades
        if len(trades_df) > 0:
            trades_path = results_dir / 'ml_trades.csv'
            trades_df.to_csv(trades_path, index=False)
            logger.info(f"\n✅ Saved trade history: {trades_path}")
        
        # Save summary
        import json
        summary_path = results_dir / 'backtest_summary.json'
        
        # Convert to JSON-serializable format
        summary = {}
        for name, metrics in strategies.items():
            summary[name] = {k: float(v) if isinstance(v, (np.integer, np.floating)) else v 
                           for k, v in metrics.items() if k != 'error'}
        
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"✅ Saved summary: {summary_path}")
    
    def run_full_backtest(self):
        """Run complete backtest."""
        logger.info("\n" + "="*70)
        logger.info("ML MODEL BACKTEST")
        logger.info("="*70)
        logger.info(f"Initial Balance: ${self.initial_balance:,.2f}")
        logger.info(f"Dataset: {len(self.df):,} trades")
        
        # Load models
        self.load_models()
        
        # Engineer features
        logger.info("\nEngineering features...")
        df = self.engineer_features(self.df)
        
        # Run backtests
        strategies, trades = self.compare_strategies(df)
        
        # Save results
        self.save_results(strategies, trades)
        
        logger.info("\n" + "="*70)
        logger.info("✅ BACKTEST COMPLETE")
        logger.info("="*70)
        
        return strategies, trades


if __name__ == '__main__':
    backtester = MLModelBacktester(initial_balance=10000.0)
    strategies, trades = backtester.run_full_backtest()
