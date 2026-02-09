#!/usr/bin/env python3
"""
Exposure Manager - Portfolio correlation and concentration limits.
Prevents overexposure to single assets and correlated positions.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class ExposureManager:
    """Manages portfolio exposure and correlation limits."""

    def __init__(self, config: Dict = None):
        """
        Initialize exposure manager.

        Args:
            config: Exposure limit configuration
        """
        config = config or {}

        # Layer 1: Per-asset position limits
        self.max_positions_per_asset = config.get('max_positions_per_asset', 3)
        self.max_capital_per_asset_pct = config.get('max_capital_per_asset_pct', 0.40)

        # Layer 2: Directional balance
        self.max_same_direction_pct = config.get('max_same_direction_pct', 0.80)

        # Layer 3: Strike clustering (as % of current price)
        self.min_strike_distance_pct = config.get('min_strike_distance_pct', 0.10)

        # Layer 4: Expiry concentration
        self.max_positions_same_expiry_week = config.get('max_positions_same_expiry_week', 2)

        # Layer 5: Total portfolio limits
        self.max_total_positions = config.get('max_total_positions', 10)
        self.max_capital_deployed_pct = config.get('max_capital_deployed_pct', 0.50)

        # Soft mode: log warnings but don't block
        self.soft_mode = config.get('soft_mode', False)

        logger.info(f"ExposureManager initialized:")
        logger.info(f"  Max positions per asset: {self.max_positions_per_asset}")
        logger.info(f"  Max capital per asset: {self.max_capital_per_asset_pct:.0%}")
        logger.info(f"  Max same direction: {self.max_same_direction_pct:.0%}")
        logger.info(f"  Soft mode: {self.soft_mode}")

    def analyze_exposure(self, positions: List[Dict], total_capital: float) -> Dict:
        """
        Analyze current portfolio exposure.

        Args:
            positions: List of open positions
            total_capital: Total available capital

        Returns:
            Exposure analysis dictionary
        """
        analysis = {
            'total_positions': len(positions),
            'total_deployed': 0,
            'by_asset': defaultdict(lambda: {
                'count': 0,
                'capital': 0,
                'bullish_count': 0,
                'bearish_count': 0,
                'strikes': [],
                'expiries': []
            }),
            'expiry_weeks': defaultdict(int)
        }

        for pos in positions:
            # Extract position data
            metadata = pos.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            asset = metadata.get('asset', 'UNKNOWN')
            size = pos.get('size', 0)
            side = pos.get('side', 'YES')  # YES or NO
            strike = metadata.get('strike_price', 0)
            expiry = metadata.get('expiry_date')

            # Update totals
            analysis['total_deployed'] += size

            # Update per-asset stats
            asset_stats = analysis['by_asset'][asset]
            asset_stats['count'] += 1
            asset_stats['capital'] += size

            # Determine direction (bullish = YES on "hit $X", bearish = NO)
            # YES means betting price WILL hit strike (bullish for high strikes)
            # NO means betting price WON'T hit strike (bearish for high strikes)
            if side == 'YES':
                asset_stats['bullish_count'] += 1
            else:
                asset_stats['bearish_count'] += 1

            if strike:
                asset_stats['strikes'].append(strike)

            # Track expiry week
            if expiry:
                if isinstance(expiry, str):
                    try:
                        expiry = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                    except:
                        expiry = None

                if expiry:
                    # Get ISO week number
                    week_key = expiry.strftime('%Y-W%W')
                    analysis['expiry_weeks'][week_key] += 1
                    asset_stats['expiries'].append(expiry)

        # Calculate percentages
        if total_capital > 0:
            analysis['deployed_pct'] = analysis['total_deployed'] / total_capital
            for asset, stats in analysis['by_asset'].items():
                stats['capital_pct'] = stats['capital'] / total_capital
                total_dir = stats['bullish_count'] + stats['bearish_count']
                if total_dir > 0:
                    stats['bullish_pct'] = stats['bullish_count'] / total_dir
                    stats['bearish_pct'] = stats['bearish_count'] / total_dir

        return analysis

    def can_open_position(self, new_position: Dict,
                          existing_positions: List[Dict],
                          total_capital: float) -> Tuple[bool, str, List[str]]:
        """
        Check if opening a new position violates exposure limits.

        Args:
            new_position: Proposed new position
            existing_positions: List of current open positions
            total_capital: Total available capital

        Returns:
            (can_open, primary_reason, all_warnings)
        """
        warnings = []
        blocking_reason = None

        # Extract new position details
        new_asset = new_position.get('asset', 'UNKNOWN')
        new_size = new_position.get('size', 0)
        new_side = new_position.get('outcome', new_position.get('side', 'YES'))
        new_strike = new_position.get('strike_price', 0)
        new_expiry = new_position.get('expiry_date')

        # Get current exposure
        analysis = self.analyze_exposure(existing_positions, total_capital)

        # === Layer 1: Per-Asset Position Count ===
        asset_stats = analysis['by_asset'].get(new_asset, {'count': 0, 'capital': 0})
        if asset_stats['count'] >= self.max_positions_per_asset:
            msg = f"Max {new_asset} positions exceeded ({asset_stats['count']}/{self.max_positions_per_asset})"
            warnings.append(msg)
            if not blocking_reason:
                blocking_reason = msg

        # === Layer 2: Per-Asset Capital Exposure ===
        new_asset_capital = asset_stats.get('capital', 0) + new_size
        new_asset_capital_pct = new_asset_capital / total_capital if total_capital > 0 else 1

        if new_asset_capital_pct > self.max_capital_per_asset_pct:
            msg = f"{new_asset} capital exposure exceeded ({new_asset_capital_pct:.0%} > {self.max_capital_per_asset_pct:.0%})"
            warnings.append(msg)
            if not blocking_reason:
                blocking_reason = msg

        # === Layer 3: Directional Balance ===
        if asset_stats['count'] > 0:
            # Check if adding this position creates directional imbalance
            new_bullish = asset_stats.get('bullish_count', 0) + (1 if new_side == 'YES' else 0)
            new_bearish = asset_stats.get('bearish_count', 0) + (1 if new_side == 'NO' else 0)
            total_dir = new_bullish + new_bearish

            if total_dir > 0:
                max_dir_pct = max(new_bullish, new_bearish) / total_dir
                if max_dir_pct > self.max_same_direction_pct:
                    direction = 'bullish' if new_bullish > new_bearish else 'bearish'
                    msg = f"{new_asset} too {direction} ({max_dir_pct:.0%} > {self.max_same_direction_pct:.0%})"
                    warnings.append(msg)
                    # Don't block on direction, just warn

        # === Layer 4: Strike Clustering ===
        if new_strike and asset_stats.get('strikes'):
            for existing_strike in asset_stats['strikes']:
                if existing_strike > 0:
                    distance_pct = abs(new_strike - existing_strike) / existing_strike
                    if distance_pct < self.min_strike_distance_pct:
                        msg = f"Strike ${new_strike:,.0f} too close to existing ${existing_strike:,.0f} ({distance_pct:.0%} < {self.min_strike_distance_pct:.0%})"
                        warnings.append(msg)
                        # Don't block on strike clustering, just warn
                        break

        # === Layer 5: Expiry Concentration ===
        if new_expiry:
            if isinstance(new_expiry, str):
                try:
                    new_expiry = datetime.fromisoformat(new_expiry.replace('Z', '+00:00'))
                except:
                    new_expiry = None

            if new_expiry:
                week_key = new_expiry.strftime('%Y-W%W')
                current_in_week = analysis['expiry_weeks'].get(week_key, 0)
                if current_in_week >= self.max_positions_same_expiry_week:
                    msg = f"Too many positions expiring week {week_key} ({current_in_week + 1} > {self.max_positions_same_expiry_week})"
                    warnings.append(msg)
                    # Don't block on expiry, just warn

        # === Layer 6: Total Portfolio Limits ===
        if analysis['total_positions'] >= self.max_total_positions:
            msg = f"Max total positions exceeded ({analysis['total_positions']}/{self.max_total_positions})"
            warnings.append(msg)
            if not blocking_reason:
                blocking_reason = msg

        total_deployed = analysis['total_deployed'] + new_size
        deployed_pct = total_deployed / total_capital if total_capital > 0 else 1
        if deployed_pct > self.max_capital_deployed_pct:
            msg = f"Max capital deployed exceeded ({deployed_pct:.0%} > {self.max_capital_deployed_pct:.0%})"
            warnings.append(msg)
            if not blocking_reason:
                blocking_reason = msg

        # Log the check
        if warnings:
            logger.info(f"[EXPOSURE CHECK] {new_asset} ${new_strike:,.0f} {new_side}")
            for w in warnings:
                logger.warning(f"  {w}")

        # Determine result
        if blocking_reason and not self.soft_mode:
            logger.warning(f"  -> BLOCKED: {blocking_reason}")
            return False, blocking_reason, warnings
        elif warnings and self.soft_mode:
            logger.info(f"  -> ALLOWED (soft mode): {len(warnings)} warnings")
            return True, f"Soft mode: {len(warnings)} warnings", warnings
        elif warnings:
            # Has warnings but none are blocking
            return True, "OK with warnings", warnings
        else:
            return True, "OK", []

    def get_rebalance_suggestions(self, positions: List[Dict],
                                   total_capital: float) -> List[str]:
        """
        Get suggestions for rebalancing the portfolio.

        Args:
            positions: List of open positions
            total_capital: Total available capital

        Returns:
            List of suggestion strings
        """
        suggestions = []
        analysis = self.analyze_exposure(positions, total_capital)

        # Check for over-concentration
        for asset, stats in analysis['by_asset'].items():
            if stats['count'] > self.max_positions_per_asset:
                excess = stats['count'] - self.max_positions_per_asset
                suggestions.append(
                    f"Consider closing {excess} {asset} position(s) to allow diversification"
                )

            if stats.get('capital_pct', 0) > self.max_capital_per_asset_pct:
                suggestions.append(
                    f"Reduce {asset} exposure from {stats['capital_pct']:.0%} to <{self.max_capital_per_asset_pct:.0%}"
                )

        # Check for missing diversification
        assets_held = set(analysis['by_asset'].keys())
        if len(assets_held) == 1 and analysis['total_positions'] >= 3:
            only_asset = list(assets_held)[0]
            suggestions.append(
                f"Portfolio is 100% {only_asset}. Consider adding ETH, SOL, or other assets."
            )

        return suggestions

    def format_exposure_report(self, positions: List[Dict],
                                total_capital: float) -> str:
        """
        Generate a formatted exposure report.

        Args:
            positions: List of open positions
            total_capital: Total available capital

        Returns:
            Formatted report string
        """
        analysis = self.analyze_exposure(positions, total_capital)

        lines = [
            "=" * 50,
            "PORTFOLIO EXPOSURE REPORT",
            "=" * 50,
            f"Total Positions: {analysis['total_positions']} / {self.max_total_positions}",
            f"Capital Deployed: ${analysis['total_deployed']:.2f} / ${total_capital:.2f} "
            f"({analysis.get('deployed_pct', 0):.0%} / {self.max_capital_deployed_pct:.0%})",
            "",
            "BY ASSET:",
        ]

        for asset, stats in sorted(analysis['by_asset'].items()):
            status = "OK"
            if stats['count'] > self.max_positions_per_asset:
                status = "OVER LIMIT"
            elif stats.get('capital_pct', 0) > self.max_capital_per_asset_pct:
                status = "OVER LIMIT"

            lines.append(
                f"  {asset}: {stats['count']} positions, ${stats['capital']:.2f} "
                f"({stats.get('capital_pct', 0):.0%}) [{status}]"
            )

            # Direction breakdown
            if stats['count'] > 0:
                lines.append(
                    f"    Direction: {stats.get('bullish_pct', 0):.0%} bullish, "
                    f"{stats.get('bearish_pct', 0):.0%} bearish"
                )

        # Suggestions
        suggestions = self.get_rebalance_suggestions(positions, total_capital)
        if suggestions:
            lines.append("")
            lines.append("SUGGESTIONS:")
            for s in suggestions:
                lines.append(f"  - {s}")

        lines.append("=" * 50)

        return "\n".join(lines)
