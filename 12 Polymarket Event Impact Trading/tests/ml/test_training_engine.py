#!/usr/bin/env python3
"""
Tests for Centralized Training Engine
Ensures training_engine.py matches behavior of legacy scripts.
"""

import pytest
import numpy as np
import pandas as pd
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ml.training_engine import (
    ModelTrainer, ModelConfig, TrainingMetrics,
    create_trainer_from_legacy_config
)


@pytest.fixture
def sample_data():
    """Create sample classification dataset."""
    np.random.seed(42)

    n_samples = 500
    n_features = 10

    # Generate features
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f'feature_{i}' for i in range(n_features)]
    )

    # Generate labels (binary classification)
    # Create some signal: label = 1 if feature_0 + feature_1 > 0
    y = ((X['feature_0'] + X['feature_1']) > 0).astype(int).values

    return X, y


@pytest.fixture
def model_config():
    """Default model configuration for tests."""
    return ModelConfig(
        model_type='gradient_boosting',
        n_estimators=50,  # Smaller for faster tests
        learning_rate=0.1,
        max_depth=3,
        apply_calibration=True,
        verbose=False
    )


class TestModelConfig:
    """Test ModelConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ModelConfig()

        assert config.model_type == 'gradient_boosting'
        assert config.n_estimators == 200
        assert config.learning_rate == 0.05
        assert config.apply_calibration is True
        assert config.calibration_method == 'isotonic'

    def test_custom_config(self):
        """Test custom configuration."""
        config = ModelConfig(
            model_type='random_forest',
            n_estimators=100,
            apply_calibration=False
        )

        assert config.model_type == 'random_forest'
        assert config.n_estimators == 100
        assert config.apply_calibration is False


class TestModelTrainer:
    """Test ModelTrainer core functionality."""

    def test_initialization(self, model_config):
        """Test trainer initialization."""
        trainer = ModelTrainer(model_config)

        assert trainer.config == model_config
        assert trainer.feature_names == []
        assert trainer.scaler is None  # Not using scaler by default

    def test_initialization_with_scaler(self):
        """Test trainer initialization with scaler."""
        config = ModelConfig(use_scaler=True, verbose=False)
        trainer = ModelTrainer(config)

        assert trainer.scaler is not None

    def test_create_base_model_gbm(self, model_config):
        """Test GBM model creation."""
        trainer = ModelTrainer(model_config)
        model = trainer._create_base_model()

        from sklearn.ensemble import GradientBoostingClassifier
        assert isinstance(model, GradientBoostingClassifier)
        assert model.n_estimators == 50
        assert model.learning_rate == 0.1
        assert model.max_depth == 3

    def test_create_base_model_rf(self):
        """Test RandomForest model creation."""
        config = ModelConfig(
            model_type='random_forest',
            n_estimators=100,
            rf_max_depth=5,
            verbose=False
        )
        trainer = ModelTrainer(config)
        model = trainer._create_base_model()

        from sklearn.ensemble import RandomForestClassifier
        assert isinstance(model, RandomForestClassifier)
        assert model.n_estimators == 100
        assert model.max_depth == 5

    def test_create_base_model_logistic(self):
        """Test LogisticRegression model creation."""
        config = ModelConfig(model_type='logistic', verbose=False)
        trainer = ModelTrainer(config)
        model = trainer._create_base_model()

        from sklearn.linear_model import LogisticRegression
        assert isinstance(model, LogisticRegression)

    def test_create_base_model_svm(self):
        """Test SVM model creation."""
        config = ModelConfig(model_type='svm', verbose=False)
        trainer = ModelTrainer(config)
        model = trainer._create_base_model()

        from sklearn.svm import SVC
        assert isinstance(model, SVC)
        assert model.probability is True  # Required for predict_proba

    def test_create_base_model_invalid(self):
        """Test error on invalid model type."""
        config = ModelConfig(model_type='invalid_model', verbose=False)
        trainer = ModelTrainer(config)

        with pytest.raises(ValueError, match="Unknown model type"):
            trainer._create_base_model()


class TestTraining:
    """Test model training functionality."""

    def test_train_basic(self, sample_data, model_config):
        """Test basic training without validation set."""
        X, y = sample_data
        trainer = ModelTrainer(model_config)

        model, metrics = trainer.train(X, y)

        # Check model is trained
        assert model is not None
        assert hasattr(model, 'predict')
        assert hasattr(model, 'predict_proba')

        # Check metrics
        assert 'train' in metrics
        assert isinstance(metrics['train'], TrainingMetrics)
        assert 0 <= metrics['train'].accuracy <= 1
        assert 0 <= metrics['train'].roc_auc <= 1

        # Check feature names stored
        assert trainer.feature_names == list(X.columns)

    def test_train_with_validation(self, sample_data, model_config):
        """Test training with validation set."""
        X, y = sample_data
        trainer = ModelTrainer(model_config)

        # Split data
        splits = trainer.split_data(X, y, test_size=0.2, val_size=0.2)

        model, metrics = trainer.train(
            splits['X_train'], splits['y_train'],
            splits['X_val'], splits['y_val']
        )

        # Check both train and val metrics
        assert 'train' in metrics
        assert 'val' in metrics
        assert isinstance(metrics['train'], TrainingMetrics)
        assert isinstance(metrics['val'], TrainingMetrics)

    def test_train_with_calibration(self, sample_data):
        """Test training with calibration."""
        X, y = sample_data

        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            apply_calibration=True,
            calibration_method='isotonic',
            verbose=False
        )
        trainer = ModelTrainer(config)

        # Split for calibration
        splits = trainer.split_data(X, y)

        model, metrics = trainer.train(
            splits['X_train'], splits['y_train'],
            splits['X_val'], splits['y_val']
        )

        # Check model is calibrated
        from sklearn.calibration import CalibratedClassifierCV
        assert isinstance(model, CalibratedClassifierCV)

    def test_train_without_calibration(self, sample_data):
        """Test training without calibration."""
        X, y = sample_data

        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            apply_calibration=False,
            verbose=False
        )
        trainer = ModelTrainer(config)

        model, metrics = trainer.train(X, y)

        # Check model is NOT calibrated
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.calibration import CalibratedClassifierCV
        assert isinstance(model, GradientBoostingClassifier)
        assert not isinstance(model, CalibratedClassifierCV)


class TestEvaluation:
    """Test model evaluation functionality."""

    def test_evaluate(self, sample_data, model_config):
        """Test model evaluation."""
        X, y = sample_data
        trainer = ModelTrainer(model_config)

        # Train model
        splits = trainer.split_data(X, y)
        model, _ = trainer.train(splits['X_train'], splits['y_train'])

        # Evaluate on test set
        test_metrics = trainer.evaluate(
            model, splits['X_test'], splits['y_test'],
            dataset_name='test'
        )

        # Check metrics structure
        assert isinstance(test_metrics, TrainingMetrics)
        assert 0 <= test_metrics.accuracy <= 1
        assert 0 <= test_metrics.precision <= 1
        assert 0 <= test_metrics.recall <= 1
        assert 0 <= test_metrics.f1 <= 1
        assert 0 <= test_metrics.roc_auc <= 1
        assert 0 <= test_metrics.brier_score <= 1

        # Check confusion matrix
        assert len(test_metrics.confusion_matrix) == 2
        assert len(test_metrics.confusion_matrix[0]) == 2

    def test_metrics_to_dict(self, sample_data, model_config):
        """Test TrainingMetrics to_dict conversion."""
        X, y = sample_data
        trainer = ModelTrainer(model_config)

        splits = trainer.split_data(X, y)
        model, _ = trainer.train(splits['X_train'], splits['y_train'])

        metrics = trainer.evaluate(model, splits['X_test'], splits['y_test'])
        metrics_dict = metrics.to_dict()

        assert isinstance(metrics_dict, dict)
        assert 'accuracy' in metrics_dict
        assert 'roc_auc' in metrics_dict
        assert 'confusion_matrix' in metrics_dict


class TestDataSplitting:
    """Test data splitting functionality."""

    def test_split_data_basic(self, sample_data, model_config):
        """Test basic data splitting."""
        X, y = sample_data
        trainer = ModelTrainer(model_config)

        splits = trainer.split_data(X, y, test_size=0.2, val_size=0.2)

        # Check all splits present
        assert 'X_train' in splits
        assert 'y_train' in splits
        assert 'X_val' in splits
        assert 'y_val' in splits
        assert 'X_test' in splits
        assert 'y_test' in splits

        # Check split sizes
        total_samples = len(X)
        train_samples = len(splits['X_train'])
        val_samples = len(splits['X_val'])
        test_samples = len(splits['X_test'])

        assert train_samples + val_samples + test_samples == total_samples
        assert test_samples == pytest.approx(total_samples * 0.2, abs=5)

    def test_split_data_stratified(self, sample_data, model_config):
        """Test stratified splitting."""
        X, y = sample_data
        trainer = ModelTrainer(model_config)

        splits = trainer.split_data(X, y, stratify=True)

        # Check class distribution is preserved
        train_ratio = splits['y_train'].mean()
        val_ratio = splits['y_val'].mean()
        test_ratio = splits['y_test'].mean()
        overall_ratio = y.mean()

        # All ratios should be close to overall ratio
        assert train_ratio == pytest.approx(overall_ratio, abs=0.1)
        assert val_ratio == pytest.approx(overall_ratio, abs=0.1)
        assert test_ratio == pytest.approx(overall_ratio, abs=0.1)


class TestModelPersistence:
    """Test model saving and loading."""

    def test_save_and_load_model(self, sample_data, model_config):
        """Test model save and load."""
        X, y = sample_data
        trainer = ModelTrainer(model_config)

        # Train model
        splits = trainer.split_data(X, y)
        model, metrics = trainer.train(splits['X_train'], splits['y_train'])

        # Save model
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_model.pkl')

            trainer.save_model(model, metrics, filepath)

            # Check file exists
            assert os.path.exists(filepath)

            # Load model
            loaded_model, model_data = ModelTrainer.load_model(filepath)

            # Check loaded model works
            assert loaded_model is not None
            assert hasattr(loaded_model, 'predict')

            # Check metadata
            assert 'feature_names' in model_data
            assert 'config' in model_data
            assert 'metrics' in model_data
            assert 'trained_at' in model_data

            # Verify predictions match
            original_pred = model.predict_proba(splits['X_test'])
            loaded_pred = loaded_model.predict_proba(splits['X_test'])

            np.testing.assert_array_almost_equal(original_pred, loaded_pred)

    def test_save_model_with_metadata(self, sample_data, model_config):
        """Test saving model with custom metadata."""
        X, y = sample_data
        trainer = ModelTrainer(model_config)

        model, metrics = trainer.train(X, y)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test_model.pkl')

            custom_metadata = {
                'bot_name': 'test_bot',
                'version': '1.0',
                'notes': 'Test model'
            }

            trainer.save_model(model, metrics, filepath, metadata=custom_metadata)

            # Load and check metadata
            _, model_data = ModelTrainer.load_model(filepath)

            assert 'metadata' in model_data
            assert model_data['metadata']['bot_name'] == 'test_bot'
            assert model_data['metadata']['version'] == '1.0'


class TestLegacyCompatibility:
    """Test backward compatibility with legacy code."""

    def test_create_trainer_from_legacy_config(self):
        """Test legacy config conversion."""
        trainer = create_trainer_from_legacy_config(
            legacy_model_type='random_forest',
            apply_calibration=True,
            n_estimators=150
        )

        assert trainer.config.model_type == 'random_forest'
        assert trainer.config.apply_calibration is True
        assert trainer.config.n_estimators == 150

    def test_gradient_boost_legacy_name(self):
        """Test 'gradient_boost' legacy name mapping."""
        trainer = create_trainer_from_legacy_config(
            legacy_model_type='gradient_boost'
        )

        assert trainer.config.model_type == 'gradient_boosting'


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_training_pipeline(self, sample_data):
        """Test complete training pipeline."""
        X, y = sample_data

        # Create config
        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            apply_calibration=True,
            verbose=False
        )

        # Create trainer
        trainer = ModelTrainer(config)

        # Split data
        splits = trainer.split_data(X, y, test_size=0.15, val_size=0.15)

        # Train
        model, train_metrics = trainer.train(
            splits['X_train'], splits['y_train'],
            splits['X_val'], splits['y_val']
        )

        # Evaluate on test set
        test_metrics = trainer.evaluate(
            model, splits['X_test'], splits['y_test'],
            dataset_name='test'
        )

        # Save
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'model.pkl')
            trainer.save_model(model, train_metrics, filepath)

            # Load
            loaded_model, model_data = ModelTrainer.load_model(filepath)

            # Verify
            assert loaded_model is not None
            assert model_data['feature_names'] == list(X.columns)

        # Check test performance is reasonable
        assert test_metrics.roc_auc > 0.5  # Better than random


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
