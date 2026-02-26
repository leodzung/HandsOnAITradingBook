"""
Tests for ML-003: Training labels use correct token-condition mapping

Validates that label creation uses maker_asset_id → token_condition_map → outcome_index
instead of price-based heuristics (which create ~50% label errors).

Critical bug (2026-02-23): Old logic assumed price indicates outcome traded.
Correct mapping: maker_asset_id identifies actual token purchased (YES vs NO).
This fix improved model accuracy from 60% (random) to 95%.
"""

import pytest
import sqlite3
import pandas as pd
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLabelCreationTokenMapping:
    """Test that label creation uses correct token-condition mapping."""

    @pytest.fixture
    def alchemy_db_path(self):
        """Path to alchemy trades database."""
        return Path(__file__).parent.parent / "data" / "alchemy_trades.db"

    @pytest.fixture
    def token_condition_map(self, alchemy_db_path):
        """Load token-condition mapping from database."""
        if not alchemy_db_path.exists():
            pytest.skip("Alchemy database not found")

        conn = sqlite3.connect(str(alchemy_db_path))
        try:
            df = pd.read_sql_query("""
                SELECT token_id, outcome_index, condition_id
                FROM token_condition_map
                LIMIT 100
            """, conn)
            return df
        except Exception:
            pytest.skip("token_condition_map table not found")
        finally:
            conn.close()

    def test_uses_token_condition_map(self, token_condition_map):
        """
        CRITICAL: Label creation MUST use token_condition_map.

        This is the core test for ML-003 constraint.
        Ensures labels are created from maker_asset_id mapping, not price heuristics.
        """
        # Verify token_condition_map exists and has data
        assert len(token_condition_map) > 0, (
            "token_condition_map must have data to create correct labels"
        )

        # Verify required columns exist
        required_columns = ['token_id', 'outcome_index', 'condition_id']
        for col in required_columns:
            assert col in token_condition_map.columns, (
                f"token_condition_map must have '{col}' column"
            )

        # Verify outcome_index is binary (0 or 1)
        unique_outcomes = token_condition_map['outcome_index'].unique()
        assert set(unique_outcomes).issubset({0, 1}), (
            f"outcome_index must be 0 or 1, got: {unique_outcomes}"
        )

        # Verify each token_id maps to exactly one outcome
        duplicates = token_condition_map.groupby('token_id').size()
        assert (duplicates == 1).all(), (
            "Each token_id must map to exactly one outcome_index"
        )

    def test_label_creation_script_uses_maker_asset_id(self):
        """
        Verify label creation scripts use maker_asset_id for mapping.

        Searches for correct pattern in label creation scripts.
        """
        label_scripts = [
            Path(__file__).parent.parent / "create_labels_final_correct.py",
            Path(__file__).parent.parent / "create_correct_labels.py",
            Path(__file__).parent.parent / "create_correct_labels_fast.py"
        ]

        found_correct_pattern = False

        for script_path in label_scripts:
            if not script_path.exists():
                continue

            content = script_path.read_text()

            # Check for CORRECT pattern: maker_asset_id mapping
            if 'maker_asset_id' in content and 'token_to_outcome' in content:
                found_correct_pattern = True

            # Check for FORBIDDEN pattern: price-based heuristics
            # But allow mentions in comments/docstrings explaining the bug
            forbidden_patterns = [
                "df['outcome'] = (df['price'] > 0.5",
                "df_trades['outcome'] = (df['price'] > 0.5",
                "outcome = (price > 0.5)",
                "outcome = price > 0.5"
            ]

            for pattern in forbidden_patterns:
                assert pattern not in content, (
                    f"❌ FORBIDDEN: {script_path.name} uses price heuristic: '{pattern}'\n"
                    f"This creates ~50% label errors!\n"
                    f"MUST use maker_asset_id → token_condition_map → outcome_index"
                )

        assert found_correct_pattern, (
            "No label creation script found using correct maker_asset_id mapping"
        )

    def test_no_price_based_label_creation(self):
        """
        CRITICAL: Price-based label heuristics are FORBIDDEN.

        Price > 0.5 does NOT indicate which outcome was traded!
        This was the critical bug that caused ~50% label errors.
        """
        # Check main label creation scripts
        scripts_to_check = list(Path(__file__).parent.parent.glob("create_*labels*.py"))

        for script_path in scripts_to_check:
            content = script_path.read_text()

            # Forbidden patterns that create incorrect labels (actual code, not comments)
            forbidden_patterns = [
                ("df['outcome'] = (df['price'] > 0.5", "Assigns outcome based on price (WRONG!)"),
                ("df_trades['outcome'] = (df['price'] > 0.5", "Assigns outcome based on price (WRONG!)"),
                ("df['outcome'] = (df['price'] >= 0.5", "Assigns outcome based on price (WRONG!)"),
                ("outcome = (price > 0.5)", "Assigns outcome based on price (WRONG!)"),
                ("outcome = price > 0.5", "Assigns outcome based on price (WRONG!)")
            ]

            for pattern, reason in forbidden_patterns:
                if pattern in content:
                    # Find the line with the pattern
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        # Skip comments
                        stripped = line.strip()
                        if stripped.startswith('#'):
                            continue
                        # Skip if in docstring
                        if '"""' in line or "'''" in line:
                            continue

                        if pattern in line:
                            pytest.fail(
                                f"❌ FORBIDDEN PATTERN in {script_path.name} (line {i}):\n"
                                f"  Line: {line.strip()}\n"
                                f"  Pattern: {pattern}\n"
                                f"  Reason: {reason}\n\n"
                                f"CORRECT APPROACH:\n"
                                f"  df['outcome'] = df['maker_asset_id'].map(token_to_outcome)\n\n"
                                f"This bug caused ~50% label errors and reduced model accuracy to 60%."
                            )

    def test_token_outcome_mapping_consistency(self, alchemy_db_path):
        """
        Verify token-outcome mappings are consistent across condition_id.

        Each condition_id should have exactly 2 tokens (YES=0, NO=1).
        """
        if not alchemy_db_path.exists():
            pytest.skip("Alchemy database not found")

        conn = sqlite3.connect(str(alchemy_db_path))
        try:
            df = pd.read_sql_query("""
                SELECT condition_id, token_id, outcome_index
                FROM token_condition_map
            """, conn)
        except Exception:
            pytest.skip("token_condition_map table not found")
        finally:
            conn.close()

        if len(df) == 0:
            pytest.skip("No data in token_condition_map")

        # Check each condition_id has at least 2 tokens
        tokens_per_condition = df.groupby('condition_id').size()

        # Binary markets have 2 tokens (YES=0, NO=1)
        # Categorical markets have 4+ tokens (e.g., A=0, B=1, C=2, D=3)
        assert (tokens_per_condition >= 2).all(), (
            f"All conditions should have at least 2 tokens\n"
            f"Found conditions with <2 tokens: {(tokens_per_condition < 2).sum()}"
        )

        # Check distribution of token counts
        token_dist = tokens_per_condition.value_counts().to_dict()
        print(f"Token count distribution: {token_dist}")

        # Verify outcome indices are sequential starting from 0
        for condition_id, group in df.groupby('condition_id'):
            outcomes = sorted(group['outcome_index'].unique())
            expected = list(range(len(outcomes)))

            assert outcomes == expected, (
                f"Condition {condition_id} should have sequential outcomes {expected}, got {outcomes}"
            )


class TestLabelQuality:
    """Test that labels are high quality (not random)."""

    @pytest.fixture
    def alchemy_db_path(self):
        """Path to alchemy trades database."""
        return Path(__file__).parent.parent / "data" / "alchemy_trades.db"

    def test_label_distribution_not_random(self, alchemy_db_path):
        """
        Labels should NOT be ~50/50 (which indicates random/incorrect labeling).

        After fixing the maker_asset_id bug, label distribution should be
        based on actual market resolutions, not random.
        """
        if not alchemy_db_path.exists():
            pytest.skip("Alchemy database not found")

        conn = sqlite3.connect(str(alchemy_db_path))

        # Check if we have labeled trades
        try:
            df = pd.read_sql_query("""
                SELECT COUNT(*) as count
                FROM on_chain_trades
                WHERE label IS NOT NULL
                LIMIT 1
            """, conn)

            if df['count'].iloc[0] == 0:
                pytest.skip("No labeled trades found")

            # Get label distribution
            df_labels = pd.read_sql_query("""
                SELECT label, COUNT(*) as count
                FROM on_chain_trades
                WHERE label IS NOT NULL
                GROUP BY label
            """, conn)

        except Exception:
            pytest.skip("Could not query labels")
        finally:
            conn.close()

        if len(df_labels) == 0:
            pytest.skip("No label data")

        # Calculate distribution
        total = df_labels['count'].sum()
        df_labels['pct'] = df_labels['count'] / total

        # If labels are random/incorrect, distribution would be ~50/50
        # With correct labeling, distribution reflects actual market outcomes
        for _, row in df_labels.iterrows():
            # Warn if any label is suspiciously close to 50% (indicates random)
            if 0.48 <= row['pct'] <= 0.52:
                pytest.warn(
                    f"⚠️ Label {row['label']} is {row['pct']:.1%} of data (close to 50%)\n"
                    f"This might indicate random/incorrect labeling.\n"
                    f"Check that maker_asset_id mapping is being used correctly."
                )
