# Forward-Validation Guide for Short Expiry Trader

## Overview

This guide explains how to use the walk-forward validation framework to train ML models for the short-expiry trading bot with realistic performance estimates.

## What is Forward-Validation?

**Forward-validation** (also called walk-forward validation) is a time-series cross-validation technique that:

1. **Prevents lookahead bias**: Only trains on past data to predict future outcomes
2. **Simulates production**: Uses an expanding window that mimics real-world retraining
3. **Detects concept drift**: Measures performance degradation over time
4. **Provides realistic estimates**: Out-of-sample metrics that reflect actual trading performance

### Example: 5-Fold Walk-Forward Validation

```
Timeline: Jan 1 ──────────────────────────────────────── Jun 30

Fold 1:  Train [Jan-Feb] │ Val [Mar 1-30]
Fold 2:  Train [Jan-Mar] │ Val [Apr 1-30]
Fold 3:  Train [Jan-Apr] │ Val [May 1-30]
Fold 4:  Train [Jan-May] │ Val [Jun 1-30]
Fold 5:  Train [Jan-Jun] │ Val [Jul 1-30] (future)
```

Each fold:
- Trains on ALL data before validation period
- Validates on 30 days of future data
- Training window expands (realistic for production)

## Prerequisites

### 1. Data Collection

The short-expiry bot must be running to collect market snapshots:

```bash
# Start the bot (if not already running)
nohup python3 trader_short_expiry.py >> short_expiry.out 2>&1 &
```

The bot automatically logs snapshots to `data/market_snapshots.db` via `MarketSnapshotCollector`.

### 2. Check Data Status

```bash
# View snapshot statistics
python3 -c "
from src.ml.snapshot_collector import MarketSnapshotCollector
collector = MarketSnapshotCollector('data/market_snapshots.db')
collector.print_statistics()
"
```

**Minimum Requirements:**
- 200+ labeled snapshots for robust validation
- Snapshots from at least 60 days (for 30-day validation windows)

## Workflow

### Step 1: Label Resolved Markets

After markets resolve, backfill outcomes:

```bash
# Preview what would be labeled (dry run)
python3 scripts/label_snapshots.py --dry-run

# Actually label resolved markets
python3 scripts/label_snapshots.py
```

This script:
- Fetches unlabeled snapshots from the database
- Checks if markets have resolved via Polymarket API
- Records YES/NO/INVALID outcomes
- Sends Telegram progress alerts

**Run periodically** (e.g., daily) to keep labeled data up-to-date.

### Step 2: Train Models with Forward-Validation

Once you have 200+ labeled samples:

```bash
# Train all buckets (ultra_short, short, medium)
python3 scripts/train_short_expiry_forward_validation.py --bucket all

# Or train individual bucket
python3 scripts/train_short_expiry_forward_validation.py --bucket short --n-folds 5
```

**Options:**
- `--bucket`: Which bucket to train (`ultra_short`, `short`, `medium`, or `all`)
- `--n-folds`: Number of validation folds (default: 5)
- `--val-period-days`: Validation window length in days (default: 30)
- `--gap-days`: Embargo period between train/val (default: 0)

**Output:**
- Trained models saved to `data/models/short_expiry_<bucket>_model.pkl`
- Validation reports saved to `data/validation_reports/short_expiry_<bucket>_wfv_<timestamp>.json`

### Step 3: Review Validation Results

The validation report contains:

```json
{
  "mean_roc_auc": 0.72,           // Average ROC-AUC across folds
  "std_roc_auc": 0.05,            // Stability metric
  "mean_accuracy": 0.68,
  "mean_f1": 0.65,
  "auc_degradation": -0.03,       // First fold vs last fold
  "n_folds": 5,
  "fold_metrics": [...]           // Per-fold details
}
```

**Performance Thresholds:**
- ✅ **Production Ready**: Mean ROC-AUC ≥ 0.70
- 🟡 **Marginal**: Mean ROC-AUC 0.60-0.70
- 🔴 **Not Ready**: Mean ROC-AUC < 0.60

**Warning Signs:**
- `std_roc_auc > 0.10`: High instability (model unreliable)
- `auc_degradation < -0.10`: Severe concept drift (model degrades over time)

### Step 4: Integrate Models into Bot

If validation metrics are acceptable:

```python
# In trader_short_expiry.py, add model loading:

import pickle
from pathlib import Path

class ShortExpiryTrader:
    def __init__(self, config_path: str):
        # ... existing initialization ...

        # Load ML models
        self.models = {}
        models_dir = Path('data/models')

        for bucket in ['ultra_short', 'short', 'medium']:
            model_path = models_dir / f'short_expiry_{bucket}_model.pkl'
            if model_path.exists():
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.models[bucket] = model_data['model']
                    logger.info(f"Loaded {bucket} model: {model_data['metadata']}")

    def _generate_signal(self, features: pd.DataFrame, market: Dict, bucket: str) -> Dict:
        """Generate signal using ML model (if available) or rules."""

        # Try ML model first
        if bucket in self.models:
            model = self.models[bucket]
            feature_cols = [col for col in features.columns if col != 'label']

            # Get model prediction
            model_prob = model.predict_proba(features[feature_cols])[0][1]
            model_pred = model.predict(features[feature_cols])[0]

            # Convert to trading signal
            if model_pred == 1 and model_prob > 0.65:  # High confidence YES
                return {
                    'action': 'BUY',
                    'outcome': 'YES',
                    'edge': model_prob - 0.5,
                    'confidence': model_prob,
                    'reason': 'ml_model'
                }
            elif model_pred == 0 and model_prob < 0.35:  # High confidence NO
                return {
                    'action': 'BUY',
                    'outcome': 'NO',
                    'edge': 0.5 - model_prob,
                    'confidence': 1.0 - model_prob,
                    'reason': 'ml_model'
                }

        # Fallback to rule-based signals
        # ... existing rule-based logic ...
```

### Step 5: A/B Testing (Optional)

Compare ML vs rule-based performance:

```python
# Track signal source in metadata
self.position_manager.save_position(
    # ... other params ...
    metadata={
        'signal_source': 'ml_model' if bucket in self.models else 'rules',
        'model_prob': model_prob if bucket in self.models else None
    }
)

# Later: analyze performance by signal source
# SELECT AVG(pnl) FROM positions WHERE metadata->>'signal_source' = 'ml_model';
```

## Retraining Cadence

**Recommended Schedule:**

1. **Daily**: Run `label_snapshots.py` to backfill resolved markets
2. **Weekly**: Check if labeled count increased by 50+ samples
3. **Monthly**: Retrain models if:
   - Labeled data increased by 200+ samples
   - Win rate degraded significantly
   - New market patterns emerged

**Retraining Script:**

```bash
#!/bin/bash
# retrain_short_expiry.sh

# Label resolved markets
python3 scripts/label_snapshots.py

# Check if enough new data
LABELED_COUNT=$(sqlite3 data/market_snapshots.db \
  "SELECT COUNT(*) FROM market_snapshots WHERE labeled=1 AND bot_type='short_expiry'")

if [ "$LABELED_COUNT" -lt 200 ]; then
  echo "Insufficient data: $LABELED_COUNT labeled samples (need 200+)"
  exit 0
fi

# Retrain all buckets
python3 scripts/train_short_expiry_forward_validation.py --bucket all

echo "Retraining complete! Review validation reports before deploying."
```

## Infrastructure Reuse

This framework reuses **all existing infrastructure**:

| Component | Purpose | Location |
|-----------|---------|----------|
| **WalkForwardValidator** | Temporal cross-validation | `src/utils/walk_forward_validator.py` |
| **ModelTrainer** | Centralized training engine | `src/ml/training_engine.py` |
| **MarketSnapshotCollector** | Training data collection | `src/ml/snapshot_collector.py` |
| **TelegramNotifier** | Progress alerts | `src/monitoring/telegram_notifier.py` |
| **ModelConfig** | Hyperparameter management | `src/ml/training_engine.py` |

**No code duplication** - all scripts leverage shared components.

## Troubleshooting

### "Insufficient data" Error

**Problem:** Less than 200 labeled samples

**Solution:**
1. Run bot longer to collect more snapshots
2. Check labeling progress: `python3 scripts/label_snapshots.py --dry-run`
3. Wait for markets to resolve (short-expiry = 0-7 days)

### "No valid splits generated" Error

**Problem:** Data doesn't span enough time for validation windows

**Solution:**
- Reduce `--val-period-days` (e.g., try 14 days instead of 30)
- Reduce `--n-folds` (e.g., try 3 folds instead of 5)
- Collect data over longer period

### Poor Validation Metrics (ROC-AUC < 0.60)

**Problem:** Model not learning meaningful patterns

**Possible Causes:**
- Insufficient training data
- Feature engineering issues
- Market regime change (concept drift)
- Random/efficient markets (unpredictable)

**Solutions:**
1. Collect more data (500+ samples recommended)
2. Review feature importance (check `model_data['feature_importance']`)
3. Add domain-specific features
4. Consider ensemble with rule-based signals

### High Instability (std_roc_auc > 0.10)

**Problem:** Model performance varies significantly across folds

**Solutions:**
- Increase training data
- Regularize model (reduce `max_depth`, increase `min_samples_leaf`)
- Add feature selection (drop noisy features)
- Use ensemble methods (multiple models)

## Next Steps

1. ✅ Collect 200+ labeled snapshots
2. ✅ Train initial models with validation
3. ✅ Review metrics and feature importance
4. ⏭️ Integrate best-performing models into bot
5. ⏭️ A/B test ML vs rule-based signals
6. ⏭️ Monitor live performance
7. ⏭️ Retrain monthly or when performance degrades

## References

- Walk-Forward Validation: `src/utils/walk_forward_validator.py`
- Training Engine: `src/ml/training_engine.py`
- Snapshot Collector: `src/ml/snapshot_collector.py`
- Improvement Checklist: `IMPROVEMENT_CHECKLIST.md`
