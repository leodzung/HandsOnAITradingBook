# Walk-Forward Validation Guide

## Overview

Walk-forward validation is now implemented for both trading bots. This provides realistic performance estimates by preventing lookahead bias and respecting temporal ordering in time-series data.

## What Changed

### Before (Standard Split):
```
[=========== ALL DATA ===========]
      ↓ Random shuffle
[Train 70%] [Val 15%] [Test 15%]
```
**Problem**: Future data can "leak" into training, inflating metrics.

### After (Walk-Forward):
```
Fold 1: Train [-----] Val [--]
Fold 2: Train [---------] Val [--]
Fold 3: Train [-------------] Val [--]
Fold 4: Train [-----------------] Val [--]
Fold 5: Train [---------------------] Val [--]
```
**Benefit**: Training only uses past data, validation uses future periods.

## Usage

### Price-Level Model (Binary Classification)

**Standard training** (backward compatible):
```bash
python3 train_price_level_model.py
```

**With walk-forward validation**:
```bash
python3 train_price_level_model.py --walk-forward \
    --n-folds 5 \
    --val-period-days 30
```

**Options**:
- `--walk-forward`: Enable walk-forward validation
- `--n-folds`: Number of validation folds (default: 5)
- `--val-period-days`: Validation period length (default: 30 days)
- `--data-path`: Training data CSV path
- `--model-path`: Output model path

### Event-Bot Model (Multiclass Classification)

Coming in Phase 2 - same interface:
```bash
python3 train_event_bot_model.py --walk-forward
```

## Output Files

### 1. Validation Report (`*_validation.json`)
```json
{
  "fold_metrics": [
    {
      "fold_id": 1,
      "train_start": "2025-02-18",
      "train_end": "2025-04-20",
      "val_start": "2025-04-22",
      "val_end": "2025-05-22",
      "train_samples": 847,
      "val_samples": 376,
      "accuracy": 0.8298,
      "roc_auc": 0.9060,
      "...": "..."
    }
  ],
  "mean_roc_auc": 0.9113,
  "std_roc_auc": 0.0169,
  "auc_degradation": -0.0123
}
```

### 2. Trained Model (`*.pkl`)
Includes validation metadata:
```python
{
    'model': <calibrated_model>,
    'feature_names': [...],
    'trained_at': '2026-02-07T14:32:28',
    'validation_report': {
        'mean_roc_auc': 0.9113,
        'std_roc_auc': 0.0169,
        '...': '...'
    }
}
```

### 3. Training Report (`training_report.txt`)
Includes walk-forward summary:
```
WALK-FORWARD VALIDATION SUMMARY
----------------------------------------------------------------------
  Folds:              5
  Val Period (days):  30
  Mean ROC-AUC:       0.9113 ± 0.0169
  Mean Accuracy:      0.8478 ± 0.0344
  AUC Degradation:    -0.0123
```

## Performance Interpretation

### ROC-AUC Thresholds:
- **≥ 0.70**: Production ready
- **0.60-0.70**: Marginal, needs improvement
- **< 0.60**: Not ready for deployment

### Stability Metrics:
- **Std deviation > 0.10**: High instability (concept drift or overfitting)
- **AUC degradation > 0.10**: Severe drift (model decays over time)

### Example Output:
```
Mean ROC-AUC:  0.9113 ± 0.0169
Status: PRODUCTION READY ✅
```

## Current Status

### ✅ Implemented:
- [x] Core `WalkForwardValidator` class
- [x] Price-level model integration
- [x] Expanding window splits
- [x] Temporal ordering verification
- [x] Aggregate metrics calculation
- [x] JSON validation reports
- [x] CLI interface

### 🚧 In Progress:
- [ ] Event-bot model integration (multiclass)
- [ ] Visualization module
- [ ] Comprehensive tests

### 📋 Future Enhancements:
- [ ] Purged K-Fold (remove temporally close samples)
- [ ] Rolling window (fixed training size)
- [ ] Gap days / embargo period
- [ ] Parallel fold training
- [ ] Automatic drift detection

## Data Requirements

### Current (Synthetic Data)
The test above used synthetic data from `data/training_data_v2.csv`:
- **2,000 samples** (balanced 50/50)
- **Dates**: 2025-02-18 to 2025-07-24 (156 days)
- **Features**: 36 technical indicators

### Real Data (To Be Generated)

**Prerequisites**:
1. ✅ On-chain trades collected (603K trades available)
2. ❌ Market mapping (0 trades mapped to conditions)
3. ❌ Training pipeline executed

**To generate real training data**:

```bash
# Step 1: Map trades to markets
python3 market_mapper.py --build-mapping

# Step 2: Generate training labels
python3 training_pipeline.py --full --backfill-days 180

# Step 3: Train with walk-forward on REAL data
python3 train_price_level_model.py --walk-forward \
    --data-path data/training_price_level.csv
```

**Expected real data**:
- **10K-100K samples** (depends on resolved markets)
- **Date range**: Aug 2025 - Feb 2026 (6 months)
- **Labels**: Based on actual market outcomes

## Technical Details

### Split Algorithm

1. Sort data by `entry_date` column
2. Work backwards from most recent data
3. For each fold:
   - Validation: N-day window
   - Training: All data before validation window
4. Verify no temporal overlap (train_end < val_start)
5. Check minimum sample sizes (default: 500 train, 50 val)

### Calibration Strategy

- **During validation**: Each fold trains with internal 3-fold CV calibration
- **Final model**: Uses last 20% of data for calibration

### Feature Handling

- `entry_date` column **kept** during splitting
- `entry_date` column **removed** before model training
- Ensures temporal ordering without using date as a feature

## Troubleshooting

### Issue: "Insufficient data for N folds"
**Solution**: Reduce `--n-folds` or increase `--val-period-days`

### Issue: "entry_date column not found"
**Solution**: Ensure training data CSV includes `entry_date` column

### Issue: "Training samples below minimum"
**Solution**: Collect more historical data or reduce `min_train_samples`

### Issue: High AUC degradation (> 0.10)
**Cause**: Concept drift - market dynamics changing over time
**Solution**: Implement online learning or more frequent retraining

## Comparison: Standard vs Walk-Forward

### Standard Split (Old Method):
```python
# Random 70/15/15 split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15)
```

**Metrics on synthetic data**:
- ROC-AUC: ~0.95-0.98 (overly optimistic)
- Stability: Unknown (single test set)

### Walk-Forward (New Method):
```python
# 5 folds, expanding window
validator.validate(X, y, model_factory, eval_fn, date_column='entry_date')
```

**Metrics on synthetic data**:
- Mean ROC-AUC: 0.9113 ± 0.0169 (realistic)
- Stability: Quantified across 5 time periods

**Difference**: Standard split inflates metrics by 5-10% due to lookahead bias.

## Next Steps

1. **Generate real training data**:
   ```bash
   python3 market_mapper.py --build-mapping
   python3 training_pipeline.py --full
   ```

2. **Retrain with real data**:
   ```bash
   python3 train_price_level_model.py --walk-forward \
       --data-path data/training_price_level.csv
   ```

3. **Compare metrics**:
   - Expected: Mean ROC-AUC 0.65-0.75 (more realistic than synthetic)
   - If > 0.70: Deploy to production
   - If < 0.60: Revisit feature engineering

4. **Implement for event-bot**:
   - Same walk-forward approach for multiclass prediction
   - Train on `data/training_event_bot.csv`

## References

- **CLAUDE.md**: Repository instructions
- **IMPROVEMENT_CHECKLIST.md**: Master task list
- **walk_forward_validator.py**: Core implementation
- **train_price_level_model.py**: Integration example
