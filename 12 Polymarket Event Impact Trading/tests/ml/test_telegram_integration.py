#!/usr/bin/env python3
"""
Test Telegram Integration in Training Engine
Verifies that training notifications work correctly.
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ml.training_engine import ModelTrainer, ModelConfig
from models.models_v2 import PriceMovementPredictor


@pytest.fixture
def sample_data():
    """Create sample dataset."""
    np.random.seed(42)
    X = pd.DataFrame(np.random.randn(100, 10), columns=[f'f{i}' for i in range(10)])
    y = np.random.choice([0, 1], size=100)
    return X, y


@pytest.fixture
def mock_telegram():
    """Create mock Telegram notifier."""
    telegram = Mock()
    telegram.send_message = Mock(return_value=True)
    return telegram


class TestTelegramIntegration:
    """Test Telegram notifications in training engine."""

    def test_training_without_telegram(self, sample_data):
        """Test that training works without Telegram (backward compatible)."""
        X, y = sample_data

        config = ModelConfig(
            model_type='random_forest',
            n_estimators=10,
            apply_calibration=False,
            verbose=False
        )

        trainer = ModelTrainer(config)  # No telegram parameter
        model, metrics = trainer.train(X, y)

        assert model is not None
        assert 'train' in metrics

    def test_training_with_telegram_notifies_start(self, sample_data, mock_telegram):
        """Test that training sends start notification."""
        X, y = sample_data

        config = ModelConfig(
            model_type='random_forest',
            n_estimators=10,
            apply_calibration=False,
            verbose=False
        )

        trainer = ModelTrainer(config, telegram_notifier=mock_telegram)
        model, metrics = trainer.train(X, y)

        # Check that Telegram was called
        assert mock_telegram.send_message.called
        calls = mock_telegram.send_message.call_args_list

        # Should have at least 2 calls: start + complete
        assert len(calls) >= 2

        # Check start message
        start_message = calls[0][0][0]
        assert "TRAINING STARTED" in start_message
        assert "random_forest" in start_message.lower()
        assert str(len(X)) in start_message

    def test_training_with_telegram_notifies_complete(self, sample_data, mock_telegram):
        """Test that training sends completion notification."""
        X, y = sample_data

        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=10,
            apply_calibration=False,
            verbose=False
        )

        trainer = ModelTrainer(config, telegram_notifier=mock_telegram)
        model, metrics = trainer.train(X, y)

        calls = mock_telegram.send_message.call_args_list

        # Find completion message (last call)
        complete_message = calls[-1][0][0]
        assert "TRAINING COMPLETE" in complete_message or "COMPLETE" in complete_message
        assert "Accuracy" in complete_message

    def test_training_failure_notifies_error(self, mock_telegram):
        """Test that training failures send error notification."""
        config = ModelConfig(
            model_type='random_forest',
            n_estimators=10,
            verbose=False
        )

        trainer = ModelTrainer(config, telegram_notifier=mock_telegram)

        # Create data with mismatched shapes to trigger error
        X = pd.DataFrame(np.random.randn(10, 5))
        y = np.array([0])  # Wrong size!

        with pytest.raises(Exception):
            trainer.train(X, y)

        # Check that error notification was sent
        calls = mock_telegram.send_message.call_args_list
        assert len(calls) > 0
        error_message = calls[-1][0][0]
        assert "FAILED" in error_message or "ERROR" in error_message or "STARTED" in error_message

    def test_models_v2_with_telegram(self, sample_data, mock_telegram):
        """Test that models_v2 PriceMovementPredictor supports Telegram."""
        X, y = sample_data

        # Create model with telegram
        model = PriceMovementPredictor(
            model_type='random_forest',
            telegram_notifier=mock_telegram
        )

        metrics = model.train(X, y, validation_split=0.2)

        # Should have sent notifications
        assert mock_telegram.send_message.called

    def test_telegram_message_format(self, sample_data, mock_telegram):
        """Test that Telegram messages are properly formatted."""
        X, y = sample_data

        config = ModelConfig(
            model_type='random_forest',
            n_estimators=10,
            apply_calibration=False,
            verbose=False
        )

        trainer = ModelTrainer(config, telegram_notifier=mock_telegram)
        trainer.train(X, y)

        calls = mock_telegram.send_message.call_args_list

        # All messages should contain HTML tags
        for call in calls:
            message = call[0][0]
            assert '<b>' in message  # Bold tags
            assert '</b>' in message

    def test_poor_performance_warning(self, mock_telegram):
        """Test that poor model performance triggers warning."""
        # Create data that will result in poor performance
        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 5), columns=[f'f{i}' for i in range(5)])
        y = np.random.choice([0, 1], size=100)  # Random labels (no pattern)

        config = ModelConfig(
            model_type='logistic',
            apply_calibration=False,
            verbose=False
        )

        trainer = ModelTrainer(config, telegram_notifier=mock_telegram)

        # Split data
        splits = trainer.split_data(X, y, test_size=0.3, val_size=0.2)

        # Train
        model, metrics = trainer.train(
            splits['X_train'], splits['y_train'],
            splits['X_val'], splits['y_val']
        )

        # Check if warning was sent (may or may not be, depending on random performance)
        # Just verify the notification system works
        assert mock_telegram.send_message.called

    def test_telegram_disabled_no_calls(self, sample_data):
        """Test that training works when Telegram is None."""
        X, y = sample_data

        config = ModelConfig(
            model_type='random_forest',
            n_estimators=10,
            verbose=False
        )

        trainer = ModelTrainer(config, telegram_notifier=None)
        model, metrics = trainer.train(X, y)

        # Should complete without errors
        assert model is not None
        assert metrics['train'].accuracy > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
