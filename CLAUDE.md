# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the code repository for the book "Hands-On AI Trading with Python, QuantConnect, and AWS". It contains practical examples of AI-driven algorithmic trading strategies implemented on the QuantConnect platform.

## Architecture

### Project Structure

The repository is organized into three main sections:

1. **00 Libraries/** - Shared utility libraries
   - `backtestlib/` - Backtesting utilities for rough equity curve estimation
   - `tearsheet/` - Performance analysis and visualization tools

2. **06 Applied Machine Learning/** - 19 complete ML trading strategy examples
   - Each example is a self-contained folder with `main.py` (algorithm) and/or `research.ipynb` (analysis)
   - Some examples include custom Python modules for ML models (e.g., `temporalcnn.py`, `symboldata.py`)

3. **07 Better Hedging with Reinforcement Learning/** - RL-based hedging strategies

4. **08 AI for Risk Management and Optimization/** - Portfolio optimization and risk management examples

### QuantConnect Platform Integration

All strategies are designed to run on the **QuantConnect** platform, which uses the LEAN algorithmic trading engine:

- **main.py** - Contains the `QCAlgorithm` class that runs live/backtests
- **research.ipynb** - Jupyter notebooks for research and analysis using `QuantBook`
- All algorithms import from `AlgorithmImports` which provides access to QuantConnect's API

### Common Pattern: Algorithm Structure

QuantConnect algorithms follow this pattern:

```python
from AlgorithmImports import *

class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        # Set dates, cash, universe, schedule
        self.set_start_date(...)
        self.set_end_date(...)
        self.set_cash(...)

    def on_data(self, data):
        # Handle incoming market data
        pass
```

Research notebooks use `QuantBook` (qb) for historical analysis:
```python
qb = QuantBook()
history = qb.history(symbols, start, end, resolution)
```

## Development Workflow

### Running Code

**On QuantConnect Cloud/Local Platform:**
1. Copy `main.py` and/or `research.ipynb` from an example folder
2. Paste into your QuantConnect project files
3. Run backtest or open research notebook

**Using LEAN CLI:**
1. Clone this repo
2. Move `main.py`/`research.ipynb` to a project in your organization workspace
3. Run: `lean backtest <project-name>` or `lean research <project-name>`
4. Note: Local execution requires the appropriate datasets

### Using the backtestlib Library

To use `backtestlib` functionality (rough equity curve backtesting):

1. Create a library called `backtestlib` in your QuantConnect workspace
2. Copy the contents of `00 Libraries/backtestlib/backtestlib.py` into it
3. Add the library to your project

The library provides `rough_daily_backtest(qb, portfolio_weights)` which calculates equity curves for portfolio weights.

## Key Technical Details

### ML Model Persistence

Many examples use the **Object Store** to save/load trained models:

- `self.object_store.save_bytes(key, data)` - Save serialized models
- `self.object_store.read(key)` - Load serialized models
- Common in `live_mode` to avoid retraining models

### Data Handling

- **DataNormalizationMode.RAW** is commonly used to prevent split/dividend adjustments from affecting raw price data
- **Resolution.DAILY** is the most common resolution
- History is accessed via `security.history` or `self.history()`

### Universe Selection

Examples use dynamic universes (e.g., ETF constituents):
```python
self.add_universe(self.universe.etf(etf_symbol, universe_filter_func=self._select_assets))
```

### Scheduling

Trading logic is typically scheduled using:
```python
self.schedule.on(date_rule, time_rule, callback)
self.train(date_rule, time_rule, training_callback)  # For ML model training
```

### ML Libraries Used

Common imports across examples:
- **sklearn** - Standard ML models (RandomForest, SVM, DecisionTree, etc.)
- **tensorflow/keras** - Deep learning (CNN, Neural Networks)
- **MLFinLab** - Financial ML techniques (trend scanning)
- **hmmlearn** - Hidden Markov Models
- **PyWavelets** - Wavelet decomposition
- **transformers** - Pre-trained models (FinBERT, Amazon Chronos)
- **OpenAI API** - GPT-4 for news sentiment analysis

## Testing

There are no formal test suites. Validation is done through:
- Running backtests and verifying equity curves
- Analyzing results in research notebooks
- Comparing benchmark vs. candidate strategies

## Important Notes

- **Datasets**: Running locally requires access to QuantConnect datasets for the symbols used
- **Object Store**: Used extensively for sharing data between `main.py` and `research.ipynb`
- **Parameters**: Algorithms often use `self.get_parameter()` for configurable values
- **Live Mode**: Many algorithms check `self.live_mode` to load pre-trained models instead of training from scratch
