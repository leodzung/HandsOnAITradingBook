# Training Engine Usage Guide

Quick reference for using the centralized ML training engine.

---

## Basic Usage

### 1. Simple Training (Binary Classification)

```python
from ml.training_engine import ModelTrainer, ModelConfig
import pandas as pd

# Configure model
config = ModelConfig(
    model_type='gradient_boosting',
    n_estimators=200,
    learning_rate=0.05,
    max_depth=4,
    apply_calibration=True
)

# Create trainer
trainer = ModelTrainer(config)

# Split data
splits = trainer.split_data(X, y, test_size=0.15, val_size=0.15)

# Train
model, metrics = trainer.train(
    splits['X_train'], splits['y_train'],
    splits['X_val'], splits['y_val']
)

# Evaluate on test set
test_metrics = trainer.evaluate(model, splits['X_test'], splits['y_test'])

# Save
trainer.save_model(model, metrics, 'data/my_model.pkl')
```

---

## Available Model Types

```python
# Gradient Boosting (recommended for most cases)
config = ModelConfig(
    model_type='gradient_boosting',
    n_estimators=200,
    learning_rate=0.05,
    max_depth=4
)

# Random Forest
config = ModelConfig(
    model_type='random_forest',
    n_estimators=100,
    rf_max_depth=10
)

# Logistic Regression
config = ModelConfig(
    model_type='logistic',
    use_scaler=True  # Recommended for logistic
)

# SVM
config = ModelConfig(
    model_type='svm',
    use_scaler=True  # Recommended for SVM
)
```

---

## Calibration

```python
# With isotonic calibration (recommended)
config = ModelConfig(
    model_type='gradient_boosting',
    apply_calibration=True,
    calibration_method='isotonic'
)

# With sigmoid calibration
config = ModelConfig(
    model_type='gradient_boosting',
    apply_calibration=True,
    calibration_method='sigmoid'
)

# Without calibration
config = ModelConfig(
    model_type='gradient_boosting',
    apply_calibration=False
)
```

---

## Cross-Validation

```python
from ml.training_engine import ModelTrainer, ModelConfig
from models.cross_validation import UnifiedCrossValidator

# Configure model
config = ModelConfig(model_type='gradient_boosting')
trainer = ModelTrainer(config)

# Create CV validator
cv_validator = UnifiedCrossValidator(
    n_folds=5,
    val_period_days=30
)

# Run CV
validation_report = trainer.train_with_cv(
    X, y,
    cv_validator=cv_validator,
    date_column='entry_date'  # or None for synthetic dates
)

# Check results
print(f"Mean ROC-AUC: {validation_report.mean_roc_auc:.4f}")
print(f"Production Ready: {validation_report.production_ready}")
```

---

## Loading Models

```python
from ml.training_engine import ModelTrainer

# Load model
model, model_data = ModelTrainer.load_model('data/my_model.pkl')

# Check metadata
print(f"Features: {model_data['feature_names']}")
print(f"Trained: {model_data['trained_at']}")
print(f"Metrics: {model_data['metrics']}")

# Make predictions
predictions = model.predict(X_new)
probabilities = model.predict_proba(X_new)
```

---

## Migration from Legacy Code

### Event Bot (models.py → models_v2.py)

```python
# OLD
from models.models import PriceMovementPredictor
model = PriceMovementPredictor(model_type='random_forest')
metrics = model.train(X, y, validation_split=0.2)

# NEW (100% backward compatible)
from models.models_v2 import PriceMovementPredictor
model = PriceMovementPredictor(model_type='random_forest')
metrics = model.train(X, y, validation_split=0.2)
```

### Price-Level Bot (Direct Use)

```python
# OLD
from models.train_price_level_model import PriceLevelModelTrainer
trainer = PriceLevelModelTrainer(...)
trainer.run()

# NEW
from ml.training_engine import ModelTrainer, ModelConfig

config = ModelConfig(
    model_type='gradient_boosting',
    n_estimators=200,
    apply_calibration=True
)
trainer = ModelTrainer(config)

# Use standard API (see examples above)
```

---

## Common Patterns

### With Feature Scaling

```python
config = ModelConfig(
    model_type='logistic',
    use_scaler=True  # StandardScaler applied automatically
)
```

### Save with Custom Metadata

```python
trainer.save_model(
    model, metrics, 'model.pkl',
    metadata={
        'bot_name': 'price_level_bot',
        'version': '2.0',
        'data_source': 'real_markets_2024'
    }
)
```

### Multiclass Classification

```python
# Automatically detected (e.g., y has values -1, 0, 1)
config = ModelConfig(model_type='gradient_boosting')
trainer = ModelTrainer(config)

# Metrics automatically use 'weighted' average for precision/recall/f1
model, metrics = trainer.train(X_train, y_train)
```

---

## Metrics Format

```python
# TrainingMetrics object
metrics = trainer.evaluate(model, X_test, y_test)

print(metrics.accuracy)       # 0.85
print(metrics.precision)      # 0.83
print(metrics.recall)         # 0.87
print(metrics.f1)             # 0.85
print(metrics.roc_auc)        # 0.91 (binary only)
print(metrics.brier_score)    # 0.12 (binary only)
print(metrics.confusion_matrix)  # [[100, 10], [5, 85]]

# Convert to dict
metrics_dict = metrics.to_dict()
```

---

## Best Practices

### 1. Always Split Data
```python
# Use trainer's built-in splitting
splits = trainer.split_data(X, y, test_size=0.15, val_size=0.15, stratify=True)

# Ensures consistent random_state from config
```

### 2. Use Calibration for Probability Estimates
```python
# If you need reliable probabilities, use calibration
config = ModelConfig(
    model_type='gradient_boosting',
    apply_calibration=True  # Better probability estimates
)
```

### 3. Save Models with Metadata
```python
# Include version info for tracking
trainer.save_model(model, metrics, filepath, metadata={
    'version': '1.0',
    'data_date': '2026-02-15',
    'notes': 'Added new features: spread, depth'
})
```

### 4. Validate on Held-Out Test Set
```python
# Train on train+val, evaluate on test
splits = trainer.split_data(X, y)

model, train_metrics = trainer.train(
    splits['X_train'], splits['y_train'],
    splits['X_val'], splits['y_val']
)

# Final evaluation on unseen test data
test_metrics = trainer.evaluate(model, splits['X_test'], splits['y_test'])

if test_metrics.roc_auc < 0.7:
    print("Model not ready for production")
```

---

## Troubleshooting

### Issue: "Target is multiclass but average='binary'"
**Solution:** Already fixed! Training engine auto-detects multiclass and uses weighted average.

### Issue: "Model not trained yet"
**Solution:** Call `trainer.train()` before `model.predict()`.

### Issue: sklearn deprecation warnings
**Solution:** Update sklearn to 1.8+ when released, or ignore for now (doesn't affect functionality).

### Issue: Feature names don't match
**Solution:** Training engine automatically reorders features to match training order.

---

## Examples by Use Case

### Use Case 1: Quick Prototype
```python
from ml.training_engine import ModelTrainer, ModelConfig

# Simplest possible usage
config = ModelConfig(model_type='random_forest', verbose=True)
trainer = ModelTrainer(config)

model, metrics = trainer.train(X, y)
print(f"Accuracy: {metrics['train'].accuracy:.2f}")
```

### Use Case 2: Production Model with CV
```python
from ml.training_engine import ModelTrainer, ModelConfig
from models.cross_validation import UnifiedCrossValidator

# Full production pipeline
config = ModelConfig(
    model_type='gradient_boosting',
    n_estimators=200,
    apply_calibration=True,
    verbose=True
)

trainer = ModelTrainer(config)
cv = UnifiedCrossValidator(n_folds=5)

# Validate first
report = trainer.train_with_cv(X, y, cv_validator=cv)

if not report.production_ready:
    print("Model failed production readiness check")
    print(f"Mean ROC-AUC: {report.mean_roc_auc:.4f}")
    exit(1)

# Train final model
splits = trainer.split_data(X, y)
model, metrics = trainer.train(
    splits['X_train'], splits['y_train'],
    splits['X_val'], splits['y_val']
)

# Evaluate and save
test_metrics = trainer.evaluate(model, splits['X_test'], splits['y_test'])
trainer.save_model(model, {'train': metrics['train'], 'val': metrics['val'], 'test': test_metrics}, 'model.pkl')
```

### Use Case 3: Legacy Bot Migration
```python
# Change ONE line
# from models.models import PriceMovementPredictor
from models.models_v2 import PriceMovementPredictor

# Everything else stays the same!
model = PriceMovementPredictor(model_type='random_forest')
metrics = model.train(X, y, validation_split=0.2)
predictions = model.predict(X_new)
```

---

## Questions?

- See `PHASE_1_COMPLETE.md` for full migration guide
- See `tests/ml/test_training_engine.py` for more examples
- See `src/ml/training_engine.py` for API documentation
