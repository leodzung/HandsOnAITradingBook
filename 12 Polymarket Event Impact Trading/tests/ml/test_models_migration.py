#!/usr/bin/env python3
"""
Test backward compatibility of models_v2.py with models.py

Ensures the new centralized training engine maintains
the exact same interface as the legacy code.
"""

import pytest
import numpy as np
import pandas as pd
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from models.models_v2 import PriceMovementPredictor, create_model


@pytest.fixture
def sample_data():
    """Create sample classification dataset."""
    np.random.seed(42)

    n_samples = 300
    n_features = 10

    # Generate features
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f'feature_{i}' for i in range(n_features)]
    )

    # Generate labels (ternary classification: -1, 0, 1)
    # Create some signal
    signal = X['feature_0'] + X['feature_1']
    y = np.where(signal > 0.5, 1, np.where(signal < -0.5, -1, 0))

    return X, y


class TestBackwardCompatibility:
    """Test backward compatibility with legacy models.py interface."""

    def test_initialization_rf(self):
        """Test RandomForest initialization."""
        model = PriceMovementPredictor(model_type='random_forest')

        assert model.model_type == 'random_forest'
        assert model.model is None
        assert model.is_trained is False
        assert model.feature_names == []

    def test_initialization_gb(self):
        """Test GradientBoosting initialization (legacy name)."""
        model = PriceMovementPredictor(model_type='gradient_boost')

        assert model.model_type == 'gradient_boost'
        assert model.is_trained is False

    def test_create_model_function(self):
        """Test legacy create_model() function."""
        model = create_model('random_forest')

        assert isinstance(model, PriceMovementPredictor)
        assert model.model_type == 'random_forest'

    def test_train_basic(self, sample_data):
        """Test basic training (legacy interface)."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        # Train using legacy interface
        metrics = model.train(X, y, validation_split=0.2)

        # Check legacy metrics format
        assert 'train_accuracy' in metrics
        assert 'val_accuracy' in metrics
        assert 'train_f1' in metrics
        assert 'val_f1' in metrics

        # Check model is trained
        assert model.is_trained is True
        assert model.model is not None
        assert model.feature_names == list(X.columns)

    def test_predict_after_training(self, sample_data):
        """Test predict() method."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        model.train(X, y, validation_split=0.2)

        # Predict
        predictions = model.predict(X)

        assert len(predictions) == len(X)
        assert predictions.dtype == np.int64 or predictions.dtype == np.int32

    def test_predict_proba_after_training(self, sample_data):
        """Test predict_proba() method."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        model.train(X, y, validation_split=0.2)

        # Predict probabilities
        proba = model.predict_proba(X)

        assert proba.shape[0] == len(X)
        assert proba.shape[1] == len(np.unique(y))  # Number of classes
        assert np.allclose(proba.sum(axis=1), 1.0)  # Probabilities sum to 1

    def test_predict_before_training_raises(self, sample_data):
        """Test that predict() raises error before training."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        with pytest.raises(ValueError, match="Model not trained"):
            model.predict(X)

    def test_predict_proba_before_training_raises(self, sample_data):
        """Test that predict_proba() raises error before training."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        with pytest.raises(ValueError, match="Model not trained"):
            model.predict_proba(X)

    def test_save_and_load(self, sample_data):
        """Test save() and load() methods."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        # Train
        model.train(X, y, validation_split=0.2)

        # Save
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_model.pkl')

            model.save(filepath)

            # Check file exists
            assert os.path.exists(filepath)

            # Load into new model
            model2 = PriceMovementPredictor(model_type='random_forest')
            model2.load(filepath)

            # Check loaded model works
            assert model2.is_trained is True
            assert model2.feature_names == model.feature_names

            # Verify predictions match
            pred1 = model.predict(X)
            pred2 = model2.predict(X)
            np.testing.assert_array_equal(pred1, pred2)

    def test_save_before_training_raises(self):
        """Test that save() raises error before training."""
        model = PriceMovementPredictor(model_type='random_forest')

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_model.pkl')

            with pytest.raises(ValueError, match="Cannot save untrained model"):
                model.save(filepath)

    def test_feature_importance(self, sample_data):
        """Test get_feature_importance() method."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        model.train(X, y, validation_split=0.2)

        # Get feature importance
        importance = model.get_feature_importance(top_n=5)

        assert isinstance(importance, dict)
        assert len(importance) == 5
        assert all(isinstance(v, (float, np.float32, np.float64)) for v in importance.values())

    def test_feature_importance_before_training_raises(self):
        """Test that get_feature_importance() raises error before training."""
        model = PriceMovementPredictor(model_type='random_forest')

        with pytest.raises(ValueError, match="Model not trained"):
            model.get_feature_importance()


class TestModelTypes:
    """Test different model types."""

    @pytest.mark.parametrize("model_type", [
        'random_forest',
        'gradient_boost',
        'logistic',
        'svm'
    ])
    def test_all_model_types(self, sample_data, model_type):
        """Test all supported model types."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type=model_type)

        # Train
        metrics = model.train(X, y, validation_split=0.2)

        # Check training worked
        assert model.is_trained is True
        assert 'train_accuracy' in metrics
        assert 'val_accuracy' in metrics

        # Check predictions work
        predictions = model.predict(X)
        assert len(predictions) == len(X)

        probabilities = model.predict_proba(X)
        assert probabilities.shape[0] == len(X)


class TestMetricsCompatibility:
    """Test that metrics match legacy format."""

    def test_metrics_format(self, sample_data):
        """Test that returned metrics match legacy format."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        metrics = model.train(X, y, validation_split=0.2)

        # Legacy format has these exact keys
        required_keys = ['train_accuracy', 'val_accuracy', 'train_f1', 'val_f1']

        for key in required_keys:
            assert key in metrics
            assert isinstance(metrics[key], (float, np.float32, np.float64))
            assert 0 <= metrics[key] <= 1

    def test_metrics_values_reasonable(self, sample_data):
        """Test that metrics are in reasonable ranges."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        metrics = model.train(X, y, validation_split=0.2)

        # Train accuracy should be high (overfitting expected with trees)
        assert metrics['train_accuracy'] > 0.5

        # Val accuracy should be reasonable
        assert metrics['val_accuracy'] > 0.3  # Better than random for 3-class


class TestFeatureOrdering:
    """Test that feature ordering is preserved."""

    def test_feature_ordering_predict(self, sample_data):
        """Test that predict() handles feature ordering correctly."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        model.train(X, y, validation_split=0.2)

        # Predict with features in original order
        pred1 = model.predict(X)

        # Predict with features in different order (should reorder internally)
        X_reordered = X[list(reversed(X.columns))]
        pred2 = model.predict(X_reordered)

        # Predictions should be identical
        np.testing.assert_array_equal(pred1, pred2)

    def test_feature_ordering_predict_proba(self, sample_data):
        """Test that predict_proba() handles feature ordering correctly."""
        X, y = sample_data
        model = PriceMovementPredictor(model_type='random_forest')

        model.train(X, y, validation_split=0.2)

        # Get probabilities with original order
        proba1 = model.predict_proba(X)

        # Get probabilities with reordered features
        X_reordered = X[list(reversed(X.columns))]
        proba2 = model.predict_proba(X_reordered)

        # Probabilities should be identical
        np.testing.assert_array_almost_equal(proba1, proba2)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
