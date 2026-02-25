# ML Training Pipeline Centralization - Quick Summary

## TL;DR
**17 scripts → 6 scripts + 4 new centralized modules**
**6,661 lines → 2,500 lines (60% reduction)**
**Estimated effort: 2-3 weeks**

---

## Current State vs. Proposed State

### BEFORE (17 scripts, 6,661 lines)

```
src/models/
├── 📊 TRAINING (8 files, 3,392 lines)
│   ├── models.py                          658 lines ✅ KEEP (refactor)
│   ├── train_price_level_model.py         603 lines ⚠️  EXTRACT LOGIC
│   ├── cross_validation.py                296 lines ✅ KEEP
│   ├── cv_utils.py                        437 lines ✅ KEEP
│   ├── label_and_retrain.py               406 lines 🗑️ ARCHIVE
│   ├── train_on_real_data.py              332 lines 🗑️ ARCHIVE
│   ├── create_manual_training_data.py     423 lines 🗑️ ARCHIVE
│   └── build_training_dataset.py          244 lines 🗑️ ARCHIVE
│
├── 🔄 DATA GENERATION (5 files, 1,547 lines)
│   ├── generate_synthetic_data.py         366 lines ⚠️  MERGE
│   ├── generate_real_training_data.py     300 lines ⚠️  MERGE
│   ├── generate_training_data_v2.py       354 lines 🗑️ ARCHIVE (merge improvements)
│   ├── create_real_dataset.py             262 lines 🗑️ ARCHIVE
│   └── build_historical_dataset.py        257 lines 🗑️ ARCHIVE
│
└── ✅ VALIDATION (4 files, 1,722 lines)
    ├── backtest_price_level_model.py      410 lines ⚠️  MERGE
    ├── backtester.py                      409 lines ⚠️  MERGE
    ├── validate_on_real_markets.py        498 lines ✅ KEEP
    └── validate_model_logic.py            406 lines ✅ KEEP
```

### AFTER (6 active + 4 new centralized)

```
src/ml/  (NEW - Centralized Services)
├── training_engine.py        ~600 lines  🆕 GBM, calibration, evaluation
├── backtesting.py            ~400 lines  🆕 Unified backtesting
├── data_generator.py         ~400 lines  🆕 Synthetic + real data
└── visualization.py          ~200 lines  🆕 Plotting utilities

src/models/  (REDUCED 17 → 6 files)
├── models.py                  400 lines  ✅ Event bot (uses training_engine)
├── cross_validation.py        296 lines  ✅ CV interface
├── cv_utils.py                437 lines  ✅ CV utilities
├── validate_on_real_markets.py 498 lines ✅ Real validation
└── validate_model_logic.py    406 lines  ✅ Logic validation

archive/deprecated_ml_scripts/
└── (7 archived files)           ~2,500 lines  🗑️
```

---

## Duplication Hotspots

### 🔴 HIGH Duplication (5+ occurrences)
| Code Pattern | Files | Lines | Solution |
|--------------|-------|-------|----------|
| GBM Training | 5 | ~800 | `training_engine.train_gbm()` |
| Evaluation Metrics | 8 | ~400 | `training_engine.evaluate_model()` |
| ROC/Calibration Plots | 4 | ~600 | `visualization.plot_*()` |
| Feature Extraction | 6 | ~900 | ✅ Already fixed (`common_features.py`) |

### 🟡 MEDIUM Duplication (2-4 occurrences)
| Code Pattern | Files | Lines | Solution |
|--------------|-------|-------|----------|
| Train/Val/Test Split | 6 | ~300 | `training_engine.split_data()` |
| Calibration | 3 | ~150 | `training_engine.calibrate_model()` |
| Historical Price Fetching | 3 | ~200 | `utils/price_history.py` |
| `Trade` class | 2 | ~80 | `backtesting.Trade` |
| `ValidationResult` class | 2 | ~60 | `validation.ValidationResult` |

---

## Implementation Phases

### ✅ Phase 0: Preparation (Week 0)
- [x] Audit all 17 scripts (DONE - see ML_SCRIPTS_AUDIT.md)
- [ ] Review audit findings
- [ ] Decide on phase priorities
- [ ] Write tests for existing functionality

### 🚧 Phase 1: Training Engine (Week 1)
**Goal:** Extract core training logic into `src/ml/training_engine.py`

**Files to extract from:**
- `train_price_level_model.py` (GBM + calibration)
- `models.py` (multi-model training)
- `label_and_retrain.py` (simple training loop)

**Deliverables:**
```python
class ModelTrainer:
    def train_gbm(X, y, config) -> CalibratedModel
    def train_random_forest(X, y, config) -> Model
    def calibrate_model(model, X_cal, y_cal) -> CalibratedModel
    def evaluate_model(model, X, y) -> Dict[str, float]
    def save_model(model, metadata, path)
    def load_model(path) -> Tuple[Model, Dict]
```

**Migration:**
1. Event bot (`models.py`) → Uses `training_engine`
2. Price-level bot (`train_price_level_model.py`) → Uses `training_engine`
3. Validate identical results

**Success Criteria:**
- [ ] All bots train successfully
- [ ] Model metrics unchanged (ROC-AUC ±0.01)
- [ ] 100% test coverage for `training_engine.py`

---

### 🚧 Phase 2: Backtesting Framework (Week 1-2)
**Goal:** Merge duplicate backtesting logic

**Files to merge:**
- `backtester.py` (generic framework)
- `backtest_price_level_model.py` (price-level specific)

**Deliverables:**
```python
@dataclass
class Trade:
    """Unified trade representation (no more duplicates!)"""

class Portfolio:
    """Portfolio state management"""

class Backtester:
    def run_backtest(model, data, strategy) -> BacktestReport
```

**Success Criteria:**
- [ ] Both bot backtests use same framework
- [ ] Backtest results match legacy scripts
- [ ] Portfolio P&L calculations verified

---

### 🚧 Phase 3: Data Generation (Week 2)
**Goal:** Merge 3 data generators into 1

**Files to merge:**
- `generate_synthetic_data.py`
- `generate_real_training_data.py`
- `generate_training_data_v2.py` (extract improvements)

**Deliverables:**
```python
class DataGenerator:
    def __init__(self, mode: str = 'synthetic'):
        # mode: 'synthetic' or 'real'

    def generate_dataset(assets, config) -> pd.DataFrame
```

**Success Criteria:**
- [ ] Generates identical datasets to legacy scripts
- [ ] Both synthetic and real modes tested
- [ ] Historical price fetching centralized

---

### 🚧 Phase 4: Visualization (Week 2-3)
**Goal:** Extract duplicate plotting code

**Files to extract from:**
- `train_price_level_model.py` (ROC, calibration, feature importance)
- `cv_utils.py` (fold performance)
- `validate_model_logic.py` (calibration analysis)

**Deliverables:**
```python
def plot_roc_curve(y_true, y_prob, save_path)
def plot_calibration_curve(y_true, y_prob, save_path)
def plot_feature_importance(model, features, save_path)
def plot_backtest_results(trades, equity, save_path)
def plot_cv_folds(validation_report, save_path)
```

**Success Criteria:**
- [ ] All plots generated from centralized functions
- [ ] Visual output identical to legacy scripts
- [ ] Plotting code not duplicated anywhere

---

### 🚧 Phase 5: Archive & Cleanup (Week 3)
**Goal:** Remove deprecated scripts

**Actions:**
1. Move 7 files to `archive/deprecated_ml_scripts/`
2. Update documentation
3. Add deprecation notices
4. Clean up imports in remaining files

**Files to archive:**
- `label_and_retrain.py`
- `train_on_real_data.py`
- `create_manual_training_data.py`
- `build_training_dataset.py`
- `create_real_dataset.py`
- `build_historical_dataset.py`
- `generate_training_data_v2.py`

---

## Success Metrics

### Code Quality
| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Total lines | 6,661 | ~2,500 | 60% reduction ✅ |
| Number of files | 17 | 10 | 41% reduction ✅ |
| Duplicate classes | 3 | 0 | Zero duplication ✅ |
| Training logic files | 8 | 1 | Centralized ✅ |

### Functionality
| Test | Status |
|------|--------|
| Event bot model unchanged | ⏳ Pending |
| Price-level bot model unchanged | ⏳ Pending |
| Short-expiry bot ready for ML | ⏳ Pending |
| Backtest results match legacy | ⏳ Pending |
| Data generation identical | ⏳ Pending |

### Testing
| Coverage Target | Status |
|-----------------|--------|
| `training_engine.py` | 100% ⏳ |
| `backtesting.py` | 100% ⏳ |
| `data_generator.py` | 100% ⏳ |
| Integration tests (all bots) | ✅ ⏳ |

---

## Risk Mitigation

### Risk: Breaking Existing Bots
**Mitigation:**
- Parallel run old + new code during migration
- Validate identical model metrics (ROC-AUC, calibration)
- Keep old scripts until validation complete

### Risk: Model Performance Degradation
**Mitigation:**
- Write comprehensive tests BEFORE refactoring
- Track model metrics in validation reports
- Automated alerts if metrics deviate >1%

### Risk: Timeline Slippage
**Mitigation:**
- Incremental migration (one bot at a time)
- Each phase is independently deliverable
- Can pause/resume between phases

---

## Comparison to `common_features.py` Success

### Previous Centralization (2026-02-14)
- **Scope:** Feature extraction across 3 bots
- **Reduction:** 35% code reduction
- **Files:** Created 1 new file (`common_features.py`)
- **Tests:** 27/27 passing ✅
- **Duration:** ~1 week
- **Outcome:** SUCCESS ✅

### This Centralization (Proposed)
- **Scope:** ML training, backtesting, data generation
- **Reduction:** 60% code reduction (larger!)
- **Files:** Create 4 new files
- **Tests:** TBD (estimate 50+ tests needed)
- **Duration:** 2-3 weeks
- **Outcome:** TBD

**Confidence Level:** HIGH (based on proven success with `common_features.py`)

---

## Decision Point

### Option A: Proceed with Full Centralization ✅ RECOMMENDED
**Pros:**
- 60% code reduction
- Proven template (`common_features.py`)
- Prevents future duplication
- Easier to add short-expiry ML (Phase 2)

**Cons:**
- 2-3 week effort
- Requires comprehensive testing
- Risk of breaking existing bots

**Recommendation:** Proceed incrementally, one phase at a time

---

### Option B: Partial Centralization (Training Only)
**Pros:**
- Smaller scope (1 week)
- Lower risk
- Still eliminates biggest duplication

**Cons:**
- Leaves backtesting/data generation duplicated
- Will need to do Phase 2-4 eventually anyway

**Recommendation:** Only if timeline is critical

---

### Option C: Status Quo (No Centralization)
**Pros:**
- Zero risk
- No effort required

**Cons:**
- Duplication will worsen (short-expiry bot adds more!)
- Harder to maintain 17 scripts
- Slower development velocity

**Recommendation:** ❌ NOT RECOMMENDED (technical debt too high)

---

## Next Steps

1. **Review audit findings** (ML_SCRIPTS_AUDIT.md)
2. **Decide on approach** (Option A, B, or C)
3. **If Option A:**
   - Prioritize phases (which first?)
   - Create detailed Phase 1 implementation plan
   - Write tests for existing functionality
   - Start migration (event bot first)
4. **If Option B:**
   - Focus on Phase 1 only (training_engine.py)
   - Revisit Phases 2-4 later
5. **If Option C:**
   - Document decision (for future reference)
   - Accept technical debt

---

**Recommendation:** **Option A** - Proceed with full centralization, following the proven `common_features.py` template. The 60% code reduction and consistency benefits outweigh the 2-3 week effort.
