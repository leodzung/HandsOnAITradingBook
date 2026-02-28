"""
Integration test for ML-004: Feature NaN/Inf handling.

Verifies that the MLPredictor correctly rejects predictions with invalid features.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
import pickle

from sklearn.ensemble import RandomForestClassifier


FEATURE_NAMES = ['trade_price', 'price_squared', 'price_distance_from_half']


class TestFeatureNanHandling:
    """Test MLPredictor rejects NaN/Inf features."""

    @pytest.fixture
    def mock_model_path(self, tmp_path):
        """Create a temporary model file for testing."""
        X = np.array([[0.5, 0.25, 0.1], [0.3, 0.09, 0.2], [0.7, 0.49, 0.3], [0.2, 0.04, 0.4]])
        y = np.array([1, 0, 1, 0])
        model = RandomForestClassifier(n_estimators=5, random_state=42)
        model.fit(X, y)

        model_info = {
            'model': model,
            'feature_names': FEATURE_NAMES,
            'metrics': {'accuracy': 0.75, 'roc_auc': 0.70},
        }
        model_path = tmp_path / 'test_model.pkl'
        with open(model_path, 'wb') as f:
            pickle.dump(model_info, f)
        return str(model_path)

    def test_predict_rejects_nan_features(self, mock_model_path):
        """MLPredictor.predict() must return False for NaN features."""
        from ml.ml_predictor import MLPredictor

        predictor = MLPredictor(mock_model_path)

        # Patch extract_features to return NaN values (simulates real data corruption)
        with patch.object(predictor, 'extract_features', return_value={
            'trade_price': float('nan'),
            'price_squared': float('nan'),
            'price_distance_from_half': 0.1,
        }):
            should_trade, confidence, reason = predictor.predict({'question': 'test'})
            assert not should_trade, f"Should reject NaN features but got should_trade={should_trade}"
            assert confidence == 0.0 or 'invalid' in reason.lower() or 'nan' in reason.lower()

    def test_predict_rejects_inf_features(self, mock_model_path):
        """MLPredictor.predict() must return False for Inf features."""
        from ml.ml_predictor import MLPredictor

        predictor = MLPredictor(mock_model_path)

        with patch.object(predictor, 'extract_features', return_value={
            'trade_price': 0.5,
            'price_squared': float('inf'),
            'price_distance_from_half': 0.0,
        }):
            should_trade, confidence, reason = predictor.predict({'question': 'test'})
            assert not should_trade, f"Should reject Inf features but got should_trade={should_trade}"

    def test_valid_features_produce_prediction(self, mock_model_path):
        """Valid features should produce a normal prediction."""
        from ml.ml_predictor import MLPredictor

        predictor = MLPredictor(mock_model_path)

        with patch.object(predictor, 'extract_features', return_value={
            'trade_price': 0.65,
            'price_squared': 0.4225,
            'price_distance_from_half': 0.15,
        }):
            should_trade, confidence, reason = predictor.predict({'question': 'test'})
            assert 0.0 <= confidence <= 1.0
            assert isinstance(reason, str)
            assert len(reason) > 0

    def test_mixed_nan_and_valid_features(self, mock_model_path):
        """Even one NaN feature should cause rejection."""
        from ml.ml_predictor import MLPredictor

        predictor = MLPredictor(mock_model_path)

        with patch.object(predictor, 'extract_features', return_value={
            'trade_price': 0.5,
            'price_squared': 0.25,
            'price_distance_from_half': float('nan'),
        }):
            should_trade, confidence, reason = predictor.predict({'question': 'test'})
            assert not should_trade, "Even one NaN feature should cause rejection"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
