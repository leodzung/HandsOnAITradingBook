# Cross-Validation Implementation

## Overview

Comprehensive k-fold cross-validation system (k≥5) for all model training paths in the Polymarket trading system. Implements walk-forward validation for time-series data with production readiness checks.

## Key Features

✅ **Enforces k≥5 minimum folds** - Ensures robust performance estimates
✅ **Walk-forward validation** - Time-series aware, prevents lookahead bias
✅ **Automatic date injection** - Works with datasets that lack temporal columns
✅ **Production readiness checks** - Gates deployments based on performance criteria
✅ **Comprehensive metrics** - ROC-AUC, accuracy, F1, Brier score, degradation
✅ **Visualization** - Automatic plotting of fold performance
✅ **Backward compatible** - Existing code works without changes

## Architecture

### Core Components

1. **`cross_validation.py`** - Unified CV interface
   - `UnifiedCrossValidator` class
   - Wraps `WalkForwardValidator` with standardized API
   - Enforces k≥5 minimum
   - Handles datasets without dates

2. **`cv_utils.py`** - CV utilities
   - `check_production_readiness()` - Production criteria assessment
   - `plot_fold_performance()` - Visualization
   - `save_cv_summary()` - JSON export
   - `compare_cv_reports()` - Multi-model comparison

3. **`models.py`** - Enhanced with CV support
   - `train_with_cv()` method added to `PriceMovementPredictor`
   - Backward compatible `train()` method
   - Optional CV via `use_cv=True` parameter

4. **`label_and_retrain.py`** - Fixed critical production issue
   - Now uses CV by default (was training on full dataset with NO validation)
   - Production readiness check blocks bad deployments
   - User override option for marginal models

5. **`train_on_real_data.py`** - Uses proper walk-forward CV
   - Replaced `cross_val_score` with walk-forward validation
   - Compares multiple models with CV
   - Generates comparison plots

## Usage

### Basic Usage (models.py)

```python
from models import PriceMovementPredictor
import pandas as pd

# Create model
model = PriceMovementPredictor('random_forest')

# Option 1: Simple training (backward compatible)
metrics = model.train(X, y, validation_split=0.2)

# Option 2: Training with CV (recommended)
cv_metrics = model.train(X, y, use_cv=True, cv_n_folds=5)

print(f"Mean ROC-AUC: {cv_metrics['mean_roc_auc']:.3f}")
print(f"Production Ready: {cv_metrics['production_ready']}")
```

### Advanced Usage (direct CV interface)

```python
from cross_validation import UnifiedCrossValidator
from sklearn.ensemble import RandomForestClassifier

# Create validator
cv = UnifiedCrossValidator(
    n_folds=5,
    val_period_days=30,
    min_samples_per_fold=50
)

# Define model factory
def model_factory():
    return RandomForestClassifier(n_estimators=100, random_state=42)

# Run validation
report = cv.validate_sklearn_model(X, y, model_factory, date_column='entry_date')

# Check production readiness
from cv_utils import check_production_readiness
readiness = check_production_readiness(report)

if readiness['is_production_ready']:
    print("✓ Model ready for production!")
else:
    print("✗ Model needs improvement:")
    for issue in readiness['issues']:
        print(f"  - {issue}")
```

### Production Retraining (label_and_retrain.py)

```python
# Retrain with CV (default behavior)
model = retrain_model(df, use_cv=True)  # Will block if not production ready

# Skip CV (not recommended for production)
model = retrain_model(df, use_cv=False)
```

## Production Readiness Criteria

Models are assessed against three criteria:

1. **Mean ROC-AUC ≥ 0.70** - Performance threshold
   - ✓ Production ready: AUC ≥ 0.70
   - ⚠️ Marginal: AUC 0.60-0.70
   - ✗ Not ready: AUC < 0.60

2. **Std ROC-AUC < 0.10** - Stability across folds
   - High variance indicates unstable model

3. **|AUC Degradation| < 0.10** - Concept drift detection
   - Degradation = (Last fold AUC - First fold AUC)
   - Large degradation indicates non-stationary data

### Example Assessment

```
======================================================================
PRODUCTION READINESS ASSESSMENT
======================================================================
✓ Mean ROC-AUC: 0.7500 (>= 0.70)
✓ Std ROC-AUC: 0.0500 (< 0.10)
✓ AUC Degradation: -0.0200 (|val| < 0.10)

Additional Metrics:
  Mean Accuracy: 0.7200 ± 0.0400
  Mean F1:       0.7100 ± 0.0450
  Folds:         5

======================================================================
✅ PRODUCTION READY
Model meets all production readiness criteria.
======================================================================
```

## Output Files

When training with CV, the following files are generated:

### JSON Reports

```
data/{model_type}_cv_report.json       # Full ValidationReport
data/{model_type}_cv_summary.json      # Summary with readiness assessment
```

Example structure:
```json
{
  "validation_report": {
    "n_folds": 5,
    "mean_roc_auc": 0.75,
    "std_roc_auc": 0.05,
    "auc_degradation": -0.02,
    "fold_metrics": [...]
  },
  "production_readiness": {
    "is_production_ready": true,
    "issues": [],
    "warnings": []
  }
}
```

### Visualizations

```
data/{model_type}_cv_folds.png         # Performance across folds
data/model_comparison.png              # Multi-model comparison
```

## Testing

### Run Unit Tests

```bash
cd "12 Polymarket Event Impact Trading"
python3 -m pytest tests/test_cross_validation.py -v
```

**Test Coverage:**
- ✓ 15 unit tests
- ✓ Initialization requirements (k≥5)
- ✓ CV with temporal data
- ✓ Synthetic date injection
- ✓ Production readiness checks
- ✓ CV utilities
- ✓ Pipeline factories
- ✓ Full integration workflow

### Run Integration Test

```bash
python3 test_cv_integration.py
```

**Tests:**
- ✓ Backward compatibility (simple training)
- ✓ CV integration (k=5 folds)
- ✓ Production readiness assessment
- ✓ Output file generation
- ✓ Predictions with trained model

## Migration Guide

### For Existing Code

**No changes required!** The system is backward compatible:

```python
# This still works exactly as before
model = PriceMovementPredictor('random_forest')
metrics = model.train(X, y, validation_split=0.2)
```

### To Enable CV

Simply add `use_cv=True`:

```python
# Enable CV (recommended)
model = PriceMovementPredictor('random_forest')
cv_metrics = model.train(X, y, use_cv=True, cv_n_folds=5)
```

### For Production Retraining

**CRITICAL:** `label_and_retrain.py` now uses CV by default:

```python
# OLD BEHAVIOR (dangerous - no validation):
model = retrain_model(df)  # Trained on FULL dataset

# NEW BEHAVIOR (safe - validates before deployment):
model = retrain_model(df, use_cv=True)  # Default: uses CV, blocks if not ready
```

**User override:** If model fails production readiness, user will be prompted:

```
⚠️  WARNING: MODEL FAILED PRODUCTION READINESS CRITERIA

Issues identified:
  ✗ Marginal performance: AUC 0.650 in 0.60-0.70 range

Deploy anyway? (yes/no):
```

## Walk-Forward Validation Details

### Expanding Window Approach

```
Fold 1: Train [-----]       Gap [] Val [--]
Fold 2: Train [---------]   Gap [] Val [--]
Fold 3: Train [-------------] Gap [] Val [--]
Fold 4: Train [-----------------] Gap [] Val [--]
Fold 5: Train [---------------------] Gap [] Val [--]
```

### Key Properties

1. **Temporal ordering** - Training always precedes validation
2. **No lookahead bias** - Future data never used for past predictions
3. **Expanding window** - Realistic for production (accumulating data)
4. **Optional gap** - Embargo period between train/val (default: 0 days)

### Parameters

```python
cv = UnifiedCrossValidator(
    n_folds=5,              # Number of folds (must be >= 5)
    val_period_days=30,     # Validation period length
    gap_days=0,             # Embargo between train/val
    min_samples_per_fold=50 # Minimum samples per fold
)
```

## Performance Impact

### Before

- Simple train/val split (may overfit)
- Production retraining with NO validation ⚠️
- No production readiness criteria
- No tracking of model stability

### After

- Rigorous k-fold CV (k≥5)
- Time-series aware (walk-forward)
- Production readiness gates
- Comprehensive metrics tracking
- Mean ± std reported for all metrics
- Visualization of performance across folds

### Computational Cost

- **Simple split:** ~2x training time (train + val)
- **5-fold CV:** ~6x training time (5 folds + final model)

**Recommendation:** Use simple split for rapid prototyping, CV for production.

## Troubleshooting

### Error: "n_folds must be >= 5"

```python
# ✗ This will fail
cv = UnifiedCrossValidator(n_folds=3)

# ✓ Use k=5 minimum
cv = UnifiedCrossValidator(n_folds=5)
```

### Error: "Insufficient samples for CV"

Increase dataset size or reduce `min_samples_per_fold`:

```python
# Option 1: Collect more data
# Option 2: Reduce minimum
cv = UnifiedCrossValidator(n_folds=5, min_samples_per_fold=30)
```

### Error: "No valid splits generated"

Check temporal span of data:

```python
# Dataset must span: n_folds * val_period_days + buffer
# For k=5, val_period=30: need ~210 days of data

# Option 1: Reduce val_period_days
cv = UnifiedCrossValidator(n_folds=5, val_period_days=15)

# Option 2: Reduce n_folds (if >= 5)
cv = UnifiedCrossValidator(n_folds=5, val_period_days=30)
```

### Warning: "Model not production ready"

**DO NOT deploy!** Options:

1. Collect more training data
2. Improve feature engineering
3. Try different model architectures
4. Check for data quality issues
5. User override (not recommended)

## Future Enhancements

Potential improvements:

- [ ] Nested CV for hyperparameter tuning
- [ ] Stratified sampling for imbalanced classes
- [ ] Custom metrics support
- [ ] Parallel fold execution
- [ ] Real-time drift detection in production
- [ ] Automatic retraining triggers

## References

- **Walk-Forward Validation:** Pardo, R. (2008). "The Evaluation and Optimization of Trading Strategies"
- **Time-Series CV:** Bergmeir & Benítez (2012). "On the use of cross-validation for time series predictor evaluation"
- **Production ML:** Breck et al. (2017). "The ML Test Score: A Rubric for ML Production Readiness"

## Support

For issues or questions:

1. Check this documentation
2. Review `test_cv_integration.py` for examples
3. Run unit tests: `pytest tests/test_cross_validation.py -v`
4. Check IMPROVEMENT_CHECKLIST.md for known issues
