"""
Parameter search spaces for short-expiry trader optimization.

Defines moderate search ranges (±50-100% from current baseline values)
for all optimizable parameters across three time buckets.
"""

from skopt.space import Real, Integer

# Current baseline parameters
# NOTE: Slippage thresholds updated based on empirical analysis of 500K real trades
# which showed P75=10bps, P90=20bps, P95=37bps (was using synthetic 1500-3000bps)
BASELINE_PARAMS = {
    'ultra_short': {
        'take_profit_pct': 30,
        'stop_loss_pct': 10,
        'max_slippage_bps': 100,  # Updated from 3000 based on empirical data
        'max_position_size': 50,
        'max_spread_pct': 10.0,
        'min_volume': 100,
        'min_confidence': 0.55,
    },
    'short': {
        'take_profit_pct': 50,
        'stop_loss_pct': 15,
        'max_slippage_bps': 100,  # Updated from 2000 based on empirical data
        'max_position_size': 75,
        'max_spread_pct': 8.0,
        'min_volume': 200,
        'min_confidence': 0.55,
    },
    'medium': {
        'take_profit_pct': 75,
        'stop_loss_pct': 20,
        'max_slippage_bps': 100,  # Updated from 1500 based on empirical data
        'max_position_size': 100,
        'max_spread_pct': 6.0,
        'min_volume': 300,
        'min_confidence': 0.55,
    },
}

# Search space definitions (moderate ±50-100% ranges)
# NOTE: max_slippage_bps ranges updated to 50-300 bps based on empirical data
# (P95=37bps from actual trades, was using unrealistic 1500-5000bps)
SHORT_EXPIRY_SPACE = {
    'ultra_short': {
        'take_profit_pct': Real(15, 60, name='take_profit_pct'),  # ±50% from 30%
        'stop_loss_pct': Real(3, 15, name='stop_loss_pct'),  # -70% to +50% from 10%
        'max_slippage_bps': Integer(50, 300, name='max_slippage_bps'),  # -50% to +200% from 100bps
        'max_position_size': Real(25, 100, name='max_position_size'),  # -50% to +100% from $50
        'max_spread_pct': Real(6.0, 15.0, name='max_spread_pct'),  # -40% to +50% from 10%
        'min_volume': Integer(50, 200, name='min_volume'),  # -50% to +100% from 100
        'min_confidence': Real(0.50, 0.70, name='min_confidence'),  # -9% to +27% from 0.55
    },
    'short': {
        'take_profit_pct': Real(25, 100, name='take_profit_pct'),  # -50% to +100% from 50%
        'stop_loss_pct': Real(5, 25, name='stop_loss_pct'),  # -67% to +67% from 15%
        'max_slippage_bps': Integer(50, 300, name='max_slippage_bps'),  # -50% to +200% from 100bps
        'max_position_size': Real(40, 150, name='max_position_size'),  # -47% to +100% from $75
        'max_spread_pct': Real(4.0, 12.0, name='max_spread_pct'),  # -50% to +50% from 8%
        'min_volume': Integer(100, 400, name='min_volume'),  # -50% to +100% from 200
        'min_confidence': Real(0.50, 0.70, name='min_confidence'),  # -9% to +27% from 0.55
    },
    'medium': {
        'take_profit_pct': Real(40, 150, name='take_profit_pct'),  # -47% to +100% from 75%
        'stop_loss_pct': Real(8, 30, name='stop_loss_pct'),  # -60% to +50% from 20%
        'max_slippage_bps': Integer(50, 300, name='max_slippage_bps'),  # -50% to +200% from 100bps
        'max_position_size': Real(50, 200, name='max_position_size'),  # -50% to +100% from $100
        'max_spread_pct': Real(3.0, 10.0, name='max_spread_pct'),  # -50% to +67% from 6%
        'min_volume': Integer(150, 600, name='min_volume'),  # -50% to +100% from 300
        'min_confidence': Real(0.50, 0.70, name='min_confidence'),  # -9% to +27% from 0.55
    },
}

# Parameter names for each bucket (for consistent ordering)
PARAM_NAMES = [
    'take_profit_pct',
    'stop_loss_pct',
    'max_slippage_bps',
    'max_position_size',
    'max_spread_pct',
    'min_volume',
    'min_confidence',
]


def get_param_space(bucket: str):
    """
    Get the search space for a specific time bucket.

    Args:
        bucket: Time bucket name ('ultra_short', 'short', or 'medium')

    Returns:
        List of skopt space dimensions in consistent order
    """
    if bucket not in SHORT_EXPIRY_SPACE:
        raise ValueError(f"Invalid bucket: {bucket}. Must be one of {list(SHORT_EXPIRY_SPACE.keys())}")

    space_dict = SHORT_EXPIRY_SPACE[bucket]
    return [space_dict[name] for name in PARAM_NAMES]


def get_baseline_params(bucket: str):
    """
    Get baseline parameter values for a specific bucket.

    Args:
        bucket: Time bucket name ('ultra_short', 'short', or 'medium')

    Returns:
        Dictionary of baseline parameter values
    """
    if bucket not in BASELINE_PARAMS:
        raise ValueError(f"Invalid bucket: {bucket}. Must be one of {list(BASELINE_PARAMS.keys())}")

    return BASELINE_PARAMS[bucket].copy()


def params_list_to_dict(params_list: list, bucket: str = None):
    """
    Convert parameter list to dictionary.

    Args:
        params_list: List of parameter values in order of PARAM_NAMES
        bucket: Optional bucket name (for validation)

    Returns:
        Dictionary mapping parameter names to values
    """
    if len(params_list) != len(PARAM_NAMES):
        raise ValueError(f"Expected {len(PARAM_NAMES)} parameters, got {len(params_list)}")

    return dict(zip(PARAM_NAMES, params_list))


def params_dict_to_list(params_dict: dict):
    """
    Convert parameter dictionary to list.

    Args:
        params_dict: Dictionary of parameter values

    Returns:
        List of parameter values in order of PARAM_NAMES
    """
    return [params_dict[name] for name in PARAM_NAMES]


def validate_params(params_dict: dict):
    """
    Validate that parameters satisfy logical constraints.

    Args:
        params_dict: Dictionary of parameter values

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Take profit should be greater than stop loss
    if params_dict['take_profit_pct'] <= params_dict['stop_loss_pct']:
        return False, "take_profit_pct must be > stop_loss_pct"

    # Confidence must be between 0.5 and 1.0
    if not (0.5 <= params_dict['min_confidence'] <= 1.0):
        return False, "min_confidence must be between 0.5 and 1.0"

    # Position size must be positive
    if params_dict['max_position_size'] <= 0:
        return False, "max_position_size must be > 0"

    # Volume must be positive
    if params_dict['min_volume'] <= 0:
        return False, "min_volume must be > 0"

    # Slippage must be positive
    if params_dict['max_slippage_bps'] <= 0:
        return False, "max_slippage_bps must be > 0"

    # Spread must be positive
    if params_dict['max_spread_pct'] <= 0:
        return False, "max_spread_pct must be > 0"

    return True, None
