"""
Tests for ML Models
"""

import pytest
import numpy as np
import pandas as pd
import tempfile
from models import PriceMovementPredictor, EnsemblePredictor


class TestPriceMovementPredictor:
    """Test suite for PriceMovementPredictor."""

    def test_initialization(self):
        """Test model initialization."""
        model = PriceMovementPredictor(model_type='random_forest')

        assert model.model_type == 'random_forest'
        assert not model.is_trained

    def test_create_random_forest_model(self):
        """Test creating random forest model."""
        model = PriceMovementPredictor(model_type='random_forest')
        rf_model = model._create_model()

        from sklearn.ensemble import RandomForestClassifier
        assert isinstance(rf_model, RandomForestClassifier)

    def test_create_gradient_boost_model(self):
        """Test creating gradient boosting model."""
        model = PriceMovementPredictor(model_type='gradient_boost')
        gb_model = model._create_model()

        from sklearn.ensemble import GradientBoostingClassifier
        assert isinstance(gb_model, GradientBoostingClassifier)

    def test_create_logistic_model(self):
        """Test creating logistic regression model."""
        model = PriceMovementPredictor(model_type='logistic')
        lr_model = model._create_model()

        from sklearn.linear_model import LogisticRegression
        assert isinstance(lr_model, LogisticRegression)

    def test_train_model(self, sample_training_data):
        """Test training the model."""
        X, y = sample_training_data
        model = PriceMovementPredictor(model_type='random_forest')

        metrics = model.train(X, y, validation_split=0.2)

        assert model.is_trained
        assert 'train_accuracy' in metrics
        assert 'val_accuracy' in metrics
        assert 0 <= metrics['val_accuracy'] <= 1

    def test_predict(self, sample_training_data):
        """Test making predictions."""
        X, y = sample_training_data
        model = PriceMovementPredictor(model_type='random_forest')
        model.train(X, y)

        predictions = model.predict(X.head(5))

        assert len(predictions) == 5
        assert all(pred in [-1, 0, 1] for pred in predictions)

    def test_predict_proba(self, sample_training_data):
        """Test getting prediction probabilities."""
        X, y = sample_training_data
        model = PriceMovementPredictor(model_type='random_forest')
        model.train(X, y)

        probas = model.predict_proba(X.head(5))

        assert probas.shape == (5, 3)  # 5 samples, 3 classes
        assert np.allclose(probas.sum(axis=1), 1.0)  # Probabilities sum to 1

    def test_predict_without_training_raises_error(self, sample_training_data):
        """Test that predicting without training raises error."""
        X, y = sample_training_data
        model = PriceMovementPredictor(model_type='random_forest')

        with pytest.raises(ValueError, match='not trained'):
            model.predict(X)

    def test_feature_importance(self, sample_training_data):
        """Test getting feature importance."""
        X, y = sample_training_data
        model = PriceMovementPredictor(model_type='random_forest')
        model.train(X, y)

        importance_df = model.get_feature_importance()

        assert len(importance_df) == len(X.columns)
        assert 'feature' in importance_df.columns
        assert 'importance' in importance_df.columns
        # Check sorted by importance
        assert all(importance_df['importance'].iloc[i] >= importance_df['importance'].iloc[i+1]
                  for i in range(len(importance_df)-1))

    def test_save_and_load_model(self, sample_training_data):
        """Test saving and loading model."""
        X, y = sample_training_data
        model = PriceMovementPredictor(model_type='random_forest')
        model.train(X, y)

        # Save model
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            model_path = f.name
        model.save(model_path)

        # Load model
        loaded_model = PriceMovementPredictor()
        loaded_model.load(model_path)

        assert loaded_model.is_trained
        assert loaded_model.model_type == 'random_forest'
        assert loaded_model.feature_names == model.feature_names

        # Test predictions match
        pred_original = model.predict(X.head(5))
        pred_loaded = loaded_model.predict(X.head(5))
        assert np.array_equal(pred_original, pred_loaded)

    def test_model_handles_missing_features(self, sample_training_data):
        """Test that model reorders features correctly."""
        X, y = sample_training_data
        model = PriceMovementPredictor(model_type='random_forest')
        model.train(X, y)

        # Create test data with different column order
        X_reordered = X.head(5)[list(reversed(X.columns))]

        predictions = model.predict(X_reordered)
        assert len(predictions) == 5


class TestEnsemblePredictor:
    """Test suite for EnsemblePredictor."""

    def test_initialization(self):
        """Test ensemble initialization."""
        ensemble = EnsemblePredictor(model_types=['random_forest', 'logistic'])

        assert len(ensemble.models) == 2
        assert not ensemble.is_trained

    def test_train_ensemble(self, sample_training_data):
        """Test training ensemble of models."""
        X, y = sample_training_data
        ensemble = EnsemblePredictor(
            model_types=['random_forest', 'gradient_boost']
        )

        metrics = ensemble.train(X, y)

        assert ensemble.is_trained
        assert 'ensemble_accuracy' in metrics
        assert 'individual_accuracies' in metrics
        assert len(metrics['individual_accuracies']) == 2

    def test_ensemble_predictions(self, sample_training_data):
        """Test ensemble predictions."""
        X, y = sample_training_data
        ensemble = EnsemblePredictor()
        ensemble.train(X, y)

        predictions = ensemble.predict(X.head(10))

        assert len(predictions) == 10
        assert all(pred in [-1, 0, 1] for pred in predictions)

    def test_ensemble_weights_sum_to_one(self, sample_training_data):
        """Test that ensemble weights sum to 1."""
        X, y = sample_training_data
        ensemble = EnsemblePredictor()
        ensemble.train(X, y)

        assert ensemble.weights is not None
        assert np.isclose(sum(ensemble.weights), 1.0)

    def test_ensemble_better_than_worst_model(self, sample_training_data):
        """Test that ensemble performs at least as well as worst individual model."""
        X, y = sample_training_data
        ensemble = EnsemblePredictor()

        metrics = ensemble.train(X, y, validation_split=0.3)

        ensemble_acc = metrics['ensemble_accuracy']
        min_individual_acc = min(metrics['individual_accuracies'])

        # Ensemble should not be worse than worst model
        assert ensemble_acc >= min_individual_acc - 0.05  # Small tolerance


class TestModelIntegration:
    """Integration tests for model training pipeline."""

    def test_full_training_pipeline(self, sample_training_data):
        """Test complete training pipeline."""
        X, y = sample_training_data

        # Train model
        model = PriceMovementPredictor(model_type='random_forest')
        metrics = model.train(X, y, validation_split=0.2)

        # Save model
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            model_path = f.name
        model.save(model_path)

        # Load and predict
        loaded_model = PriceMovementPredictor()
        loaded_model.load(model_path)

        predictions = loaded_model.predict(X.head(10))
        probabilities = loaded_model.predict_proba(X.head(10))

        assert len(predictions) == 10
        assert probabilities.shape == (10, 3)

    def test_model_consistency(self, sample_training_data):
        """Test that model predictions are consistent."""
        X, y = sample_training_data
        model = PriceMovementPredictor(model_type='random_forest')
        model.train(X, y)

        # Same input should give same prediction
        pred1 = model.predict(X.head(5))
        pred2 = model.predict(X.head(5))

        assert np.array_equal(pred1, pred2)

    def test_different_model_types_all_work(self, sample_training_data):
        """Test that all model types can train and predict."""
        X, y = sample_training_data

        model_types = ['random_forest', 'gradient_boost', 'logistic', 'svm']

        for model_type in model_types:
            model = PriceMovementPredictor(model_type=model_type)
            model.train(X, y)

            predictions = model.predict(X.head(5))
            assert len(predictions) == 5
