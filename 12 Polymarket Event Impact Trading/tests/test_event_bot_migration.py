#!/usr/bin/env python3
"""
Test Event Bot Migration to models_v2.py
Verifies that trader.py works correctly with the new centralized training engine.
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from models.models_v2 import (
    PriceMovementPredictor,
    TradingSignalGenerator,
    ModelPerformanceTracker,
    ConfidenceFilter
)


class TestEventBotMigration:
    """Test that event bot components work with models_v2."""

    def test_import_success(self):
        """Test that all required classes can be imported."""
        # If this test passes, imports are working
        assert PriceMovementPredictor is not None
        assert TradingSignalGenerator is not None
        assert ModelPerformanceTracker is not None
        assert ConfidenceFilter is not None

    def test_price_movement_predictor(self):
        """Test PriceMovementPredictor works as expected."""
        np.random.seed(42)

        # Create sample data
        X = pd.DataFrame(np.random.randn(100, 10), columns=[f'f{i}' for i in range(10)])
        y = np.random.choice([-1, 0, 1], size=100)

        # Create and train model
        model = PriceMovementPredictor(model_type='random_forest')
        metrics = model.train(X, y, validation_split=0.2)

        # Check model is trained
        assert model.is_trained
        assert 'train_accuracy' in metrics
        assert 'val_accuracy' in metrics

        # Check prediction works
        predictions = model.predict(X[:5])
        assert len(predictions) == 5
        assert all(p in [-1, 0, 1] for p in predictions)

        # Check predict_proba works
        proba = model.predict_proba(X[:5])
        assert proba.shape == (5, 3)  # 3 classes
        assert np.allclose(proba.sum(axis=1), 1.0)

    def test_trading_signal_generator(self):
        """Test TradingSignalGenerator works with models_v2."""
        np.random.seed(42)

        # Create and train model
        X = pd.DataFrame(np.random.randn(100, 10), columns=[f'f{i}' for i in range(10)])
        y = np.random.choice([-1, 0, 1], size=100)

        model = PriceMovementPredictor(model_type='random_forest')
        model.train(X, y, validation_split=0.2)

        # Create signal generator
        signal_gen = TradingSignalGenerator(
            model=model,
            min_confidence=0.4,  # Low for testing
            min_expected_return=0.01
        )

        # Generate signal
        features = X.iloc[0:1]
        signal = signal_gen.generate_signal(features, current_price=0.5)

        # Check signal structure
        assert 'action' in signal
        assert 'confidence' in signal
        assert signal['action'] in ['BUY', 'SELL', 'HOLD']

    def test_confidence_filter(self):
        """Test ConfidenceFilter works."""
        conf_filter = ConfidenceFilter(min_confidence=0.7)

        predictions = np.array([1, -1, 0, 1, -1])
        probabilities = np.array([
            [0.1, 0.1, 0.8],  # High confidence (0.8)
            [0.6, 0.2, 0.2],  # Low confidence (0.6 < 0.7)
            [0.3, 0.4, 0.3],  # Low confidence
            [0.1, 0.2, 0.7],  # High confidence
            [0.9, 0.05, 0.05] # High confidence
        ])

        filtered, confidences = conf_filter.filter_predictions(predictions, probabilities)

        assert len(filtered) == 5
        assert len(confidences) == 5
        assert confidences[0] == 0.8  # Max prob from first row

    def test_model_performance_tracker(self):
        """Test ModelPerformanceTracker works."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'performance.json')

            tracker = ModelPerformanceTracker(filepath=filepath)

            # Record some predictions
            tracker.record_prediction(1, 1, 0.8, 'market1')  # Correct
            tracker.record_prediction(-1, 1, 0.7, 'market2')  # Wrong
            tracker.record_prediction(1, 1, 0.9, 'market3')  # Correct

            # Check accuracy
            accuracy = tracker.get_accuracy()
            assert accuracy == 2/3  # 2 correct out of 3

            # Check statistics
            stats = tracker.get_statistics()
            assert stats['total_predictions'] == 3
            assert stats['overall_accuracy'] == 2/3

            # Check save/load
            assert os.path.exists(filepath)

            # Load into new tracker
            tracker2 = ModelPerformanceTracker(filepath=filepath)
            assert len(tracker2.performance_history) == 3

    def test_end_to_end_workflow(self):
        """Test complete workflow like trader.py uses it."""
        np.random.seed(42)

        # 1. Create and train model
        X = pd.DataFrame(np.random.randn(200, 10), columns=[f'f{i}' for i in range(10)])
        y = np.random.choice([-1, 0, 1], size=200)

        model = PriceMovementPredictor(model_type='random_forest')
        metrics = model.train(X, y, validation_split=0.2)

        assert model.is_trained

        # 2. Create signal generator
        signal_gen = TradingSignalGenerator(
            model=model,
            min_confidence=0.5,
            min_expected_return=0.02
        )

        # 3. Generate signals
        features = X.iloc[0:1]
        signal = signal_gen.generate_signal(features, current_price=0.6)

        assert signal['action'] in ['BUY', 'SELL', 'HOLD']

        # 4. Track performance
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'perf.json')
            tracker = ModelPerformanceTracker(filepath=filepath)

            tracker.record_prediction(1, 1, 0.8, 'market1')
            assert tracker.get_accuracy() == 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
