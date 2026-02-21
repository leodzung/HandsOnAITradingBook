"""
Parameter optimization module for Polymarket trading bots.

This module provides tools for systematic parameter optimization using
Bayesian optimization with walk-forward validation.

Components:
- param_spaces: Search space definitions for optimization
- objective_functions: Composite scoring functions for evaluation
- realistic_backtester: Backtester with realistic slippage, fees, and constraints
- parameter_optimizer: Main Bayesian optimization engine
"""

from .param_spaces import SHORT_EXPIRY_SPACE, get_param_space
from .objective_functions import composite_score, calculate_metrics
from .realistic_backtester import RealisticBacktester
from .parameter_optimizer import ParameterOptimizer

__all__ = [
    'SHORT_EXPIRY_SPACE',
    'get_param_space',
    'composite_score',
    'calculate_metrics',
    'RealisticBacktester',
    'ParameterOptimizer',
]
