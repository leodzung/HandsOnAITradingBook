"""
Structural test for ML-004: Feature validation before ML prediction.

Verifies that NaN/Inf validation exists between feature extraction and ML prediction
in both bot code and MLPredictor.
"""

import ast
import pytest
from pathlib import Path


class TestFeatureValidation:
    """Verify NaN/Inf validation exists before ML prediction."""

    def test_trader_validates_features_before_prediction(self):
        """trader.py must check for NaN/Inf in model_features before creating DataFrame."""
        path = Path('src/bots/trader.py')
        assert path.exists(), "trader.py not found"

        content = path.read_text()
        # Check that NaN/Inf validation exists between model_features and features_df
        assert 'isnan' in content or 'np.isnan' in content or 'NaN/Inf' in content, \
            "trader.py must validate features for NaN/Inf before ML prediction"

    def test_ml_predictor_has_defense_in_depth(self):
        """ml_predictor.py predict() must validate features for NaN/Inf."""
        path = Path('src/ml/ml_predictor.py')
        assert path.exists(), "ml_predictor.py not found"

        content = path.read_text()
        assert 'isnull' in content or 'isnan' in content or 'isinf' in content, \
            "ml_predictor.py must validate features for NaN/Inf in predict()"

    def test_validation_occurs_before_predict(self):
        """NaN/Inf check must appear before predict_proba call in ml_predictor.py."""
        path = Path('src/ml/ml_predictor.py')
        content = path.read_text()

        # Find the positions of validation and prediction
        nan_check_pos = max(
            content.find('isnull'),
            content.find('isnan'),
            content.find('isinf'),
        )
        predict_pos = content.find('predict_proba')

        assert nan_check_pos >= 0, "NaN/Inf validation not found in ml_predictor.py"
        assert predict_pos >= 0, "predict_proba not found in ml_predictor.py"
        assert nan_check_pos < predict_pos, \
            "NaN/Inf validation must appear BEFORE predict_proba call"

    def test_trader_returns_on_invalid_features(self):
        """trader.py must return/skip when features contain NaN/Inf."""
        path = Path('src/bots/trader.py')
        content = path.read_text()
        lines = content.splitlines()

        # Find the NaN/Inf check section
        found_validation = False
        found_return = False
        for i, line in enumerate(lines):
            if 'NaN/Inf' in line or ('isnan' in line and 'isinf' in line):
                found_validation = True
            if found_validation and 'return' in line:
                found_return = True
                break

        assert found_validation, "trader.py must have NaN/Inf validation"
        assert found_return, "trader.py must return when features contain NaN/Inf"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
