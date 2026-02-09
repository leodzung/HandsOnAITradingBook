# Test Suite for Polymarket Event Impact Trading

Comprehensive test suite covering all components of the Polymarket trading bots.

## Overview

This test suite provides extensive coverage of:
- **Unit Tests**: Individual component testing
- **Integration Tests**: Multi-component interaction testing
- **End-to-End Tests**: Complete workflow testing

## Test Structure

```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                    # Shared pytest fixtures
├── test_polymarket_client.py      # PolymarketClient and MarketFilter tests
├── test_position_manager.py       # Position persistence tests
├── test_price_tracker.py          # Price tracking and labeling tests
├── test_models.py                 # ML model tests
├── test_feature_extractor.py      # Feature engineering tests
├── test_event_detector.py         # Event detection tests
├── test_trader.py                 # Main trader tests
├── test_integration.py            # End-to-end integration tests
└── README.md                      # This file
```

## Quick Start

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_polymarket_client.py

# Run specific test
pytest tests/test_models.py::TestPriceMovementPredictor::test_train_model
```

### Run Tests by Category

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Fast tests only (exclude slow tests)
pytest -m "not slow"

# Database tests
pytest -m db

# Model tests
pytest -m models
```

## Test Coverage

Generate HTML coverage report:

```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html  # View report
```

View coverage in terminal:

```bash
pytest --cov=. --cov-report=term-missing
```

## Key Test Fixtures

The `conftest.py` file provides shared fixtures:

- `temp_db`: Temporary SQLite database for testing
- `temp_json_file`: Temporary JSON file for configuration
- `sample_market`: Mock Polymarket market data
- `sample_event`: Mock news event
- `sample_orderbook`: Mock orderbook data
- `sample_historical_prices`: Mock price history
- `sample_features`: Mock feature dictionary
- `mock_polymarket_client`: Mocked API client
- `sample_config`: Complete bot configuration
- `sample_training_data`: ML training dataset

## Writing New Tests

### Basic Test Structure

```python
import pytest

class TestMyComponent:
    """Test suite for MyComponent."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        # Arrange
        component = MyComponent()

        # Act
        result = component.do_something()

        # Assert
        assert result is not None
```

### Using Fixtures

```python
def test_with_fixtures(self, temp_db, sample_market):
    """Test using shared fixtures."""
    manager = PositionManager(db_path=temp_db)
    # Use sample_market for testing
```

### Mocking External Dependencies

```python
from unittest.mock import patch, Mock

@patch('trader.PolymarketClient')
def test_with_mock(self, mock_client_class):
    """Test with mocked dependencies."""
    mock_client = Mock()
    mock_client.get_markets.return_value = []
    mock_client_class.return_value = mock_client

    # Test code here
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pip install -r requirements-test.txt
      - run: pytest --cov=.
```

## Test Best Practices

1. **Isolation**: Each test should be independent
2. **Naming**: Use descriptive test names that explain what is being tested
3. **AAA Pattern**: Arrange, Act, Assert
4. **Fixtures**: Use fixtures for common setup
5. **Mocking**: Mock external dependencies (APIs, databases)
6. **Coverage**: Aim for >80% code coverage
7. **Speed**: Keep tests fast (use markers for slow tests)

## Common Test Scenarios

### Testing Database Operations

```python
def test_database_operation(self, temp_db):
    """Test database persistence."""
    manager = PositionManager(db_path=temp_db)

    # Save data
    manager.save_position(...)

    # Verify persistence
    positions = manager.load_positions()
    assert len(positions) == 1
```

### Testing API Calls

```python
@patch('module.requests.get')
def test_api_call(self, mock_get):
    """Test API interaction."""
    mock_response = Mock()
    mock_response.json.return_value = {'data': 'value'}
    mock_get.return_value = mock_response

    # Test code
```

### Testing Error Handling

```python
def test_error_handling(self):
    """Test error handling."""
    with pytest.raises(ValueError, match='error message'):
        # Code that should raise ValueError
        pass
```

### Testing Time-Dependent Code

```python
from freezegun import freeze_time

@freeze_time("2026-01-15 12:00:00")
def test_time_dependent(self):
    """Test time-dependent behavior."""
    # Time is frozen at 2026-01-15 12:00:00
    pass
```

## Debugging Failed Tests

### Run Failed Tests Only

```bash
pytest --lf  # Run last failed tests
pytest --ff  # Run failed first, then others
```

### Show Print Statements

```bash
pytest -s  # Show print() output
pytest --capture=no  # Disable all output capturing
```

### Run with PDB Debugger

```bash
pytest --pdb  # Drop into debugger on failure
pytest -x --pdb  # Stop on first failure and debug
```

### Verbose Output

```bash
pytest -vv  # Extra verbose
pytest -vv --tb=long  # Full traceback
```

## Performance Testing

Run performance benchmarks:

```bash
pytest tests/test_performance.py --benchmark-only
```

## Parallel Test Execution

Speed up tests by running in parallel:

```bash
pytest -n auto  # Auto-detect CPU count
pytest -n 4     # Use 4 workers
```

## Test Reports

Generate HTML test report:

```bash
pytest --html=report.html --self-contained-html
```

Generate Allure report:

```bash
pytest --alluredir=./allure-results
allure serve ./allure-results
```

## Troubleshooting

### Import Errors

Make sure you're running tests from the project root:

```bash
cd /path/to/12 Polymarket Event Impact Trading
pytest
```

### Database Locked Errors

SQLite may have locking issues with parallel tests. Use `pytest-xdist` carefully or disable parallel execution for database tests.

### Missing Dependencies

Install all test dependencies:

```bash
pip install -r requirements-test.txt
```

## Contact

For questions or issues with the test suite, refer to the main project documentation or create an issue in the repository.
