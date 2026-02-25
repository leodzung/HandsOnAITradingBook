# ML Scripts Audit: 17 Model Files Review

**Date:** 2026-02-15
**Purpose:** Assess centralization opportunities for ML training pipeline
**Conclusion:** **HIGH duplication** - 60% of code can be centralized

---

## Executive Summary

### Key Findings
- **17 scripts, 6,661 total lines of code**
- **~4,000 lines (60%) can be centralized** into shared training engine
- **8 scripts duplicate core ML training logic**
- **2 duplicate backtesting frameworks**
- **3 duplicate class definitions** (Trade, ValidationResult)
- **5+ data generation workflows** with overlapping functionality

### Recommended Actions
1. **Create `src/ml/training_engine.py`** - Centralize GBM training, calibration, evaluation (~600 lines)
2. **Create `src/ml/backtesting.py`** - Unified backtesting framework (~400 lines)
3. **Consolidate data generators** - Single parameterized generator (~300 lines)
4. **Archive deprecated scripts** - Remove 7 obsolete files

**Estimated Code Reduction:** 60% (6,661 → ~2,500 lines)

---

## File-by-File Analysis

### Category 1: Core Model Training (8 files, 3,392 lines)

#### 🔴 **models.py** (658 lines) - Event Bot Model
**Purpose:** `PriceMovementPredictor` class for event-driven bot
**Status:** ACTIVELY USED by `trader.py`
**Functionality:**
- Multi-model support (RF, GBM, LogReg, SVM)
- Training with optional CV
- StandardScaler preprocessing
- Evaluation metrics

**Duplication Issues:**
- ML training loop: **DUPLICATES** `train_price_level_model.py` (lines 70-150)
- CV logic: **DUPLICATES** `cross_validation.py` (lines 89-120)
- Metrics: **DUPLICATES** 5 other files (accuracy, precision, recall, F1, ROC-AUC)

**Verdict:** ⚠️ KEEP but refactor to use `training_engine.py`

---

#### 🔴 **train_price_level_model.py** (603 lines) - Price-Level Bot Training
**Purpose:** Comprehensive GBM training with walk-forward validation
**Status:** ACTIVELY USED for price-level bot
**Functionality:**
- `PriceLevelModelTrainer` class
- GBM + isotonic calibration
- Walk-forward validation integration
- ROC/calibration/feature importance plots
- Train/val/test splits

**Duplication Issues:**
- GBM training: **DUPLICATES** `models.py` (lines 153-193)
- Calibration: **DUPLICATES** `label_and_retrain.py` (lines 180-190)
- Metrics: **DUPLICATES** `cv_utils.py`, `models.py`
- Plotting: **DUPLICATES** `validate_model_logic.py`

**Verdict:** ✅ **EXTRACT** core logic → `training_engine.py`

---

#### 🟡 **cross_validation.py** (296 lines) - CV Interface
**Purpose:** Wrapper for walk-forward validation
**Status:** USED by `models.py` and `train_price_level_model.py`
**Functionality:**
- `UnifiedCrossValidator` class
- Enforces k >= 5 folds
- Synthetic date injection for datasets without timestamps
- Standardized evaluation interface

**Duplication Issues:**
- CV logic: **DUPLICATES** `models.py` train_with_cv()
- Date injection: Unique feature (no duplication)
- Evaluation metrics: **DUPLICATES** 4 other files

**Verdict:** ✅ KEEP - good abstraction, minimal duplication

---

#### 🟡 **cv_utils.py** (437 lines) - CV Utilities
**Purpose:** Visualization and reporting for walk-forward validation
**Status:** USED by `cross_validation.py`
**Functionality:**
- `summarize_cv_results()` - Create summary DataFrame
- `plot_fold_performance()` - Per-fold performance charts
- `save_cv_summary()` - Export reports

**Duplication Issues:**
- Plotting logic: **DUPLICATES** `train_price_level_model.py` (ROC/calibration plots)
- Summary stats: Unique feature

**Verdict:** ✅ KEEP - useful utilities, but extract plotting to `visualization.py`

---

#### 🔴 **label_and_retrain.py** (406 lines) - Position-Based Training
**Purpose:** Train model on resolved positions from database
**Status:** LEGACY - Used for initial real data training
**Functionality:**
- Load positions from `positions.db`
- Extract features from tracked events
- Train RandomForest (simple, no calibration)
- Manual labeling of outcomes

**Duplication Issues:**
- Model training: **DUPLICATES** `models.py`, `train_price_level_model.py`
- Feature extraction: Outdated (doesn't use `common_features.py`)
- DB queries: Unique

**Verdict:** 🗑️ **ARCHIVE** - Replaced by `training_pipeline.py`

---

#### 🔴 **train_on_real_data.py** (332 lines) - Real Data Training
**Purpose:** Train on real Polymarket outcomes
**Status:** PARTIALLY USED - Data loading still relevant
**Functionality:**
- `load_real_dataset()` - Load from CSV
- `create_synthetic_labels()` - Generate labels (WHY?)
- Train/evaluate GBM

**Duplication Issues:**
- Model training: **DUPLICATES** `train_price_level_model.py` (100% overlap)
- Labeling: Contradicts "real data" purpose (synthetic labels?)

**Verdict:** 🗑️ **ARCHIVE** - Obsolete, replaced by `training_pipeline.py`

---

#### 🔴 **create_manual_training_data.py** (423 lines) - Manual Dataset
**Purpose:** Create training data from manual annotations
**Status:** LEGACY - One-time use
**Functionality:**
- Hardcoded market scenarios
- Manual feature engineering
- CSV export

**Duplication Issues:**
- Feature engineering: **DUPLICATES** `feature_extractor.py`
- Data format: Incompatible with current pipeline

**Verdict:** 🗑️ **ARCHIVE** - Historical artifact, no longer used

---

#### 🔴 **build_training_dataset.py** (244 lines) - Synthetic Dataset Builder
**Purpose:** Match events to markets, create labeled samples
**Status:** LEGACY - Pre-dates `training_pipeline.py`
**Functionality:**
- Load markets from CSV
- Create synthetic training samples
- Simple feature extraction

**Duplication Issues:**
- Dataset building: **REPLACED** by `training_pipeline.py` (lines 223-336)
- Feature extraction: Outdated

**Verdict:** 🗑️ **ARCHIVE** - Superseded by centralized pipeline

---

### Category 2: Data Generation (5 files, 1,547 lines)

#### 🟡 **generate_synthetic_data.py** (366 lines) - Synthetic Data Generator
**Purpose:** Generate training data from historical spot prices
**Status:** ACTIVELY USED for initial model training
**Functionality:**
- `SyntheticDataGenerator` class
- Download historical OHLCV from CoinGecko/YFinance
- Simulate price-level markets
- Generate features + labels

**Duplication Issues:**
- Feature extraction: **DUPLICATES** `price_level_features.py`
- Historical data fetching: **DUPLICATES** `external_data.py`
- Label generation: **DUPLICATES** `generate_real_training_data.py`

**Verdict:** ✅ KEEP but merge with `generate_real_training_data.py` → `data_generator.py`

---

#### 🟡 **generate_real_training_data.py** (300 lines) - Real Data Generator
**Purpose:** Generate training data from actual Polymarket outcomes
**Status:** ACTIVELY USED
**Functionality:**
- `RealDataGenerator` class
- Load resolved markets from API/CSV
- Extract features at market creation time
- Label with actual outcomes

**Duplication Issues:**
- Feature extraction: **DUPLICATES** `generate_synthetic_data.py` (~80% overlap)
- Data source: Different (real vs synthetic) but same interface

**Verdict:** ✅ MERGE with `generate_synthetic_data.py` → unified `DataGenerator(mode='synthetic'|'real')`

---

#### 🟡 **generate_training_data_v2.py** (354 lines) - V2 Generator
**Purpose:** Improved data generation with additional features
**Status:** UNCLEAR - May be experimental
**Functionality:**
- `TrainingDataGeneratorV2` class
- Enhanced feature engineering
- Better market filtering

**Duplication Issues:**
- Entire file: **DUPLICATES** `generate_real_training_data.py` (90% overlap)
- "V2" suggests iteration, not replacement

**Verdict:** ⚠️ INVESTIGATE - Merge improvements into unified generator, then archive

---

#### 🔴 **create_real_dataset.py** (262 lines) - Real Dataset Creator
**Purpose:** Build dataset from news + markets
**Status:** LEGACY
**Functionality:**
- Load news from JSON
- Match news to markets (keyword-based)
- Extract features

**Duplication Issues:**
- News matching: **REPLACED** by `event_matcher.py` (vector embeddings)
- Feature extraction: Outdated

**Verdict:** 🗑️ **ARCHIVE** - Replaced by `training_pipeline.py` event matching

---

#### 🔴 **build_historical_dataset.py** (257 lines) - Historical Dataset Builder
**Purpose:** Build dataset from historical on-chain trades
**Status:** LEGACY
**Functionality:**
- `HistoricalDatasetBuilder` class
- Load from Alchemy data
- Create training samples

**Duplication Issues:**
- On-chain data loading: **REPLACED** by `training_pipeline.py` Alchemy integration

**Verdict:** 🗑️ **ARCHIVE** - Superseded by centralized pipeline

---

### Category 3: Validation & Backtesting (4 files, 1,722 lines)

#### 🟡 **backtest_price_level_model.py** (410 lines) - Price-Level Backtester
**Purpose:** Backtest price-level model on historical data
**Status:** USED for model evaluation
**Functionality:**
- `PriceLevelBacktester` class
- Simulate trades based on model signals
- Calculate P&L, win rate, Sharpe
- `Trade` dataclass

**Duplication Issues:**
- `Trade` class: **DUPLICATES** `backtester.py` (same name, similar structure)
- Backtesting logic: **DUPLICATES** `backtester.py` (~60% overlap)

**Verdict:** ✅ MERGE with `backtester.py` → `src/ml/backtesting.py`

---

#### 🟡 **backtester.py** (409 lines) - Generic Backtester
**Purpose:** General-purpose backtesting framework
**Status:** USED by event bot
**Functionality:**
- `Trade` class
- `Portfolio` class
- `Backtester` class
- Equity curve tracking

**Duplication Issues:**
- `Trade` class: **DUPLICATES** `backtest_price_level_model.py`
- Portfolio management: Unique (not in price-level backtester)

**Verdict:** ✅ **EXTRACT** to `src/ml/backtesting.py` as unified framework

---

#### 🟡 **validate_on_real_markets.py** (498 lines) - Real Market Validator
**Purpose:** Validate model predictions against resolved Polymarket outcomes
**Status:** ACTIVELY USED for model validation
**Functionality:**
- `RealMarketValidator` class
- Load resolved markets from CSV
- Fetch historical spot prices (CoinGecko)
- Calculate model accuracy on real outcomes
- `ValidationResult` dataclass

**Duplication Issues:**
- Historical price fetching: **DUPLICATES** `generate_synthetic_data.py`
- `ValidationResult` class: **DUPLICATES** `validate_model_logic.py`
- Evaluation metrics: **DUPLICATES** 5+ other files

**Verdict:** ✅ KEEP - unique validation logic, but extract price fetching to shared util

---

#### 🟡 **validate_model_logic.py** (406 lines) - Logic Validator
**Purpose:** Validate model's internal logic and calibration
**Status:** USED for model diagnostics
**Functionality:**
- `ValidationResult` dataclass (DUPLICATE!)
- Calibration curve analysis
- Probability distribution checks
- Edge case testing

**Duplication Issues:**
- `ValidationResult` class: **DUPLICATES** `validate_on_real_markets.py`
- Calibration plots: **DUPLICATES** `train_price_level_model.py`

**Verdict:** ✅ KEEP but merge `ValidationResult` classes, extract plotting

---

## Duplication Matrix

| Function/Class | Files | Total Lines | Centralized Lines |
|----------------|-------|-------------|-------------------|
| GBM Training | 5 | ~800 | 150 |
| Calibration | 3 | ~150 | 40 |
| Evaluation Metrics | 8 | ~400 | 80 |
| Train/Val/Test Split | 6 | ~300 | 50 |
| ROC/Calibration Plots | 4 | ~600 | 120 |
| `Trade` class | 2 | ~80 | 40 |
| `ValidationResult` class | 2 | ~60 | 30 |
| Feature Extraction | 6 | ~900 | Covered by `common_features.py` ✅ |
| Historical Price Fetching | 3 | ~200 | 60 |
| CV Logic | 3 | ~400 | Covered by `cross_validation.py` ✅ |

**Total Duplication:** ~3,890 lines → **Can centralize to ~570 lines**

---

## Recommended Centralization Plan

### Phase 1: Core Training Engine (Week 1)
**Create `src/ml/training_engine.py` (~600 lines)**

```python
class ModelTrainer:
    """Unified training engine for all bots."""

    def train_gbm(X, y, config) -> CalibratedModel:
        """Standard GBM training with calibration."""

    def evaluate_model(model, X, y) -> Dict[str, float]:
        """Unified evaluation metrics."""

    def walk_forward_validate(X, y, model_factory, config) -> ValidationReport:
        """Walk-forward CV wrapper."""

    def save_model(model, metadata, path):
        """Standardized model persistence."""
```

**Files to extract from:**
- `train_price_level_model.py` (lines 153-193, 195-240)
- `models.py` (lines 70-150, 200-250)
- `label_and_retrain.py` (lines 180-220)

---

### Phase 2: Backtesting Framework (Week 1)
**Create `src/ml/backtesting.py` (~400 lines)**

```python
@dataclass
class Trade:
    """Unified trade representation."""

class Portfolio:
    """Portfolio state management."""

class Backtester:
    """Generic backtesting framework."""

    def run_backtest(model, data, strategy, config) -> BacktestReport:
        """Execute backtest and return metrics."""
```

**Files to merge:**
- `backtester.py` (Portfolio logic)
- `backtest_price_level_model.py` (Price-level strategy)

---

### Phase 3: Data Generation (Week 2)
**Create `src/ml/data_generator.py` (~400 lines)**

```python
class DataGenerator:
    """Unified data generation for synthetic and real datasets."""

    def __init__(self, mode: str = 'synthetic'):
        self.mode = mode  # 'synthetic' or 'real'

    def generate_dataset(assets, config) -> pd.DataFrame:
        """Generate training dataset."""
```

**Files to merge:**
- `generate_synthetic_data.py`
- `generate_real_training_data.py`
- `generate_training_data_v2.py` (extract improvements)

---

### Phase 4: Utilities & Visualization (Week 2)
**Create `src/ml/visualization.py` (~200 lines)**

```python
def plot_roc_curve(y_true, y_prob, save_path):
def plot_calibration_curve(y_true, y_prob, save_path):
def plot_feature_importance(model, feature_names, save_path):
def plot_backtest_results(trades, equity_curve, save_path):
```

**Files to extract from:**
- `train_price_level_model.py` (plotting methods)
- `cv_utils.py` (fold performance plots)
- `validate_model_logic.py` (calibration analysis)

---

### Phase 5: Archive Deprecated Scripts (Week 3)
**Move to `archive/deprecated_ml_scripts/`:**
1. `label_and_retrain.py` - Replaced by `training_pipeline.py`
2. `train_on_real_data.py` - Replaced by `training_engine.py`
3. `create_manual_training_data.py` - One-time use
4. `build_training_dataset.py` - Replaced by `training_pipeline.py`
5. `create_real_dataset.py` - Replaced by `event_matcher.py`
6. `build_historical_dataset.py` - Replaced by `training_pipeline.py`
7. `generate_training_data_v2.py` - Merge improvements, then archive

---

## Final Architecture

```
src/ml/
├── training_engine.py       # Centralized GBM training, calibration, evaluation
├── backtesting.py           # Unified backtesting framework
├── data_generator.py        # Synthetic + real data generation
├── visualization.py         # Plotting utilities
└── model_registry.py        # Model versioning (NEW)

src/models/  (REDUCED FROM 17 → 6 FILES)
├── models.py               # Event bot model wrapper (uses training_engine)
├── cross_validation.py     # CV interface (KEEP)
├── cv_utils.py             # CV utilities (KEEP)
├── validate_on_real_markets.py  # Real outcome validation (KEEP)
└── validate_model_logic.py      # Logic validation (KEEP)

archive/deprecated_ml_scripts/  (7 archived files)
```

---

## Impact Assessment

### Benefits
- **60% code reduction** (6,661 → 2,500 lines)
- **Single source of truth** for training logic
- **Easier testing** - Test 1 training engine vs 8 scripts
- **Consistent model quality** - All bots use same calibration/validation
- **Faster iteration** - Update 1 file vs 5+ files
- **Better documentation** - Centralized API docs

### Risks
- **Breaking existing workflows** - Need careful migration
- **Testing burden** - Must validate all 3 bots after migration
- **Short-term velocity hit** - 2-3 weeks of refactoring

### Mitigation
- **Incremental migration** - One bot at a time
- **Parallel run** - Keep old scripts during transition
- **Comprehensive tests** - Add tests BEFORE refactoring
- **Performance validation** - Ensure no model degradation

---

## Success Metrics

### Code Quality
- [ ] Reduce total lines from 6,661 → ~2,500 (60% reduction)
- [ ] Eliminate all duplicate class definitions
- [ ] Zero ML training logic outside `training_engine.py`

### Functionality
- [ ] All 3 bots use `training_engine.py`
- [ ] Model performance unchanged (ROC-AUC ±0.01)
- [ ] Walk-forward validation results match exactly

### Testing
- [ ] 100% test coverage for `training_engine.py`
- [ ] Integration tests for all 3 bots
- [ ] Backtesting results match legacy scripts

---

## Next Steps

1. **Review this audit** with team
2. **Prioritize phases** - Which phase first?
3. **Create detailed implementation plan** for Phase 1
4. **Write tests** for `training_engine.py` BEFORE implementing
5. **Start migration** - Event bot first (simplest)

---

**Recommendation:** Proceed with centralization. The duplication level (60%) justifies the effort, and recent success with `common_features.py` (35% reduction, 27/27 tests passing) provides a proven template.
