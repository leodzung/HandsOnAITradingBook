"""
Conditional Resolution Analyzer
Handles markets with 50-50 or other conditional resolution rules.
"""

import re
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AlternativeEvent:
    """Represents an alternative event that can trigger market resolution."""
    name: str
    expected_date: Optional[datetime]
    probability_before_expiry: float
    source: str


@dataclass
class ConditionalResolution:
    """Represents a market's conditional resolution structure."""
    has_5050_rule: bool
    alternative_event: Optional[AlternativeEvent]
    p_primary: float  # P(primary event, e.g., BTC hits $1M)
    p_alternative: float  # P(alternative event, e.g., GTA VI releases)
    p_neither: float  # P(neither happens by expiry)
    fair_yes: float  # Fair value of YES
    fair_no: float  # Fair value of NO


class ConditionalResolutionAnalyzer:
    """
    Analyzes markets for conditional resolution rules (50-50, etc.)
    and calculates fair values accounting for these rules.
    """

    # Known alternative events and their expected dates
    KNOWN_EVENTS = {
        'gta vi': {
            'name': 'GTA VI Release',
            'expected_date': datetime(2026, 11, 19, tzinfo=timezone.utc),
            'source': 'Rockstar Games announcement (Jan 2025)'
        },
        'gta 6': {
            'name': 'GTA VI Release',
            'expected_date': datetime(2026, 11, 19, tzinfo=timezone.utc),
            'source': 'Rockstar Games announcement (Jan 2025)'
        },
        'grand theft auto vi': {
            'name': 'GTA VI Release',
            'expected_date': datetime(2026, 11, 19, tzinfo=timezone.utc),
            'source': 'Rockstar Games announcement (Jan 2025)'
        },
    }

    # Patterns to detect 50-50 resolution rules
    FIFTY_FIFTY_PATTERNS = [
        r'resolve.*?50[/-]50',
        r'50[/-]50.*?resolv',
        r'neither.*?50[/-]50',
        r'split.*?50[/-]50',
    ]

    def __init__(self):
        """Initialize analyzer."""
        logger.info("ConditionalResolutionAnalyzer initialized")

    def analyze_market(self, market: Dict,
                      p_primary_event: float = 0.001) -> ConditionalResolution:
        """
        Analyze a market for conditional resolution rules.

        Args:
            market: Market dictionary from Polymarket API
            p_primary_event: Probability of the primary event (e.g., BTC hitting $1M)

        Returns:
            ConditionalResolution with analysis results
        """
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        full_text = f"{question} {description}"

        # Check for 50-50 rule
        has_5050 = self._detect_5050_rule(full_text)

        # Extract alternative event
        alt_event = self._extract_alternative_event(full_text, market)

        # Get market expiry
        expiry = self._get_expiry(market)

        # Calculate probabilities
        p_alternative = self._calculate_alternative_probability(alt_event, expiry)
        p_neither = max(0, 1 - p_primary_event - p_alternative)

        # Calculate fair values
        if has_5050:
            # YES wins if primary event happens, gets 0.50 if neither
            fair_yes = p_primary_event * 1.0 + p_neither * 0.50 + p_alternative * 0.0
            # NO wins if alternative happens, gets 0.50 if neither
            fair_no = p_alternative * 1.0 + p_neither * 0.50 + p_primary_event * 0.0
        else:
            # Standard binary market
            fair_yes = p_primary_event
            fair_no = 1 - p_primary_event

        return ConditionalResolution(
            has_5050_rule=has_5050,
            alternative_event=alt_event,
            p_primary=p_primary_event,
            p_alternative=p_alternative,
            p_neither=p_neither,
            fair_yes=fair_yes,
            fair_no=fair_no
        )

    def _detect_5050_rule(self, text: str) -> bool:
        """Detect if market has a 50-50 resolution rule."""
        for pattern in self.FIFTY_FIFTY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.info("Detected 50-50 resolution rule")
                return True
        return False

    def _extract_alternative_event(self, text: str,
                                   market: Dict) -> Optional[AlternativeEvent]:
        """Extract information about alternative events from market text."""
        # Check for known events
        for event_key, event_info in self.KNOWN_EVENTS.items():
            if event_key in text:
                return AlternativeEvent(
                    name=event_info['name'],
                    expected_date=event_info['expected_date'],
                    probability_before_expiry=0.0,  # Will be calculated separately
                    source=event_info['source']
                )

        # Check for generic "before X" patterns
        before_patterns = [
            r'before\s+([A-Z][a-zA-Z\s]+(?:release|launch|happen))',
            r'prior to\s+([A-Z][a-zA-Z\s]+)',
        ]

        for pattern in before_patterns:
            match = re.search(pattern, text)
            if match:
                event_name = match.group(1).strip()
                return AlternativeEvent(
                    name=event_name,
                    expected_date=None,
                    probability_before_expiry=0.5,  # Unknown, assume 50%
                    source='Extracted from market question'
                )

        return None

    def _get_expiry(self, market: Dict) -> Optional[datetime]:
        """Get market expiry date."""
        try:
            end_date_str = market.get('endDateIso') or market.get('endDate')
            if end_date_str and isinstance(end_date_str, str):
                return datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            pass
        return None

    def _calculate_alternative_probability(self,
                                          alt_event: Optional[AlternativeEvent],
                                          expiry: Optional[datetime]) -> float:
        """
        Calculate probability that alternative event happens before expiry.

        Args:
            alt_event: Alternative event info
            expiry: Market expiry date

        Returns:
            Probability (0-1)
        """
        if not alt_event:
            return 0.0

        if not expiry:
            return 0.5  # Unknown expiry, assume 50%

        if not alt_event.expected_date:
            return 0.5  # Unknown event date, assume 50%

        # Make expiry timezone-aware if needed
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        # If alternative event is expected AFTER expiry, low probability it happens early
        if alt_event.expected_date > expiry:
            # Event is scheduled after expiry
            # Estimate small chance of early release (5-10%)
            days_after = (alt_event.expected_date - expiry).days
            if days_after > 180:
                return 0.02  # Very unlikely to release 6+ months early
            elif days_after > 90:
                return 0.05  # 5% chance of 3-6 months early
            elif days_after > 30:
                return 0.10  # 10% chance of 1-3 months early
            else:
                return 0.30  # 30% chance if within a month
        else:
            # Event is scheduled BEFORE expiry
            days_until_event = (alt_event.expected_date - datetime.now(timezone.utc)).days
            if days_until_event < 0:
                return 0.95  # Event should have happened, very likely
            elif days_until_event < 30:
                return 0.85  # Within a month, very likely
            elif days_until_event < 90:
                return 0.70  # Within 3 months
            else:
                return 0.50  # Further out, more uncertainty

    def get_trading_recommendation(self,
                                   resolution: ConditionalResolution,
                                   current_yes_price: float,
                                   current_no_price: float) -> Dict:
        """
        Get trading recommendation based on conditional resolution analysis.

        Args:
            resolution: ConditionalResolution analysis
            current_yes_price: Current YES price
            current_no_price: Current NO price

        Returns:
            Trading recommendation dictionary
        """
        yes_edge = resolution.fair_yes - current_yes_price
        no_edge = resolution.fair_no - current_no_price

        # Determine best action
        if yes_edge > no_edge and yes_edge > 0.05:
            action = 'BUY_YES'
            edge = yes_edge
            reason = f"YES underpriced: fair={resolution.fair_yes:.2f}, market={current_yes_price:.2f}"
        elif no_edge > yes_edge and no_edge > 0.05:
            action = 'BUY_NO'
            edge = no_edge
            reason = f"NO underpriced: fair={resolution.fair_no:.2f}, market={current_no_price:.2f}"
        else:
            action = 'HOLD'
            edge = max(yes_edge, no_edge)
            reason = f"No significant edge (YES edge={yes_edge:.2%}, NO edge={no_edge:.2%})"

        return {
            'action': action,
            'edge': edge,
            'reason': reason,
            'fair_yes': resolution.fair_yes,
            'fair_no': resolution.fair_no,
            'yes_edge': yes_edge,
            'no_edge': no_edge,
            'p_primary': resolution.p_primary,
            'p_alternative': resolution.p_alternative,
            'p_neither': resolution.p_neither,
            'has_5050_rule': resolution.has_5050_rule,
            'alternative_event': resolution.alternative_event.name if resolution.alternative_event else None
        }


def main():
    """Test the conditional resolution analyzer."""
    analyzer = ConditionalResolutionAnalyzer()

    # Test market
    test_market = {
        'question': 'Will bitcoin hit $1m before GTA VI?',
        'description': '''This market will resolve to "Yes" if any Binance 1 minute candle
        for Bitcoin (BTCUSDT) has a final "High" price of $1,000,000 or higher before
        Grand Theft Auto VI is officially released in the US. Otherwise, this market
        will resolve to "No". If neither occurs by July 31, 2026, 11:59 PM ET,
        this market will resolve to 50-50.''',
        'endDateIso': '2026-07-31T23:59:00Z'
    }

    print("=" * 70)
    print("CONDITIONAL RESOLUTION ANALYSIS")
    print("=" * 70)
    print(f"\nQuestion: {test_market['question']}")

    # Analyze with very low primary probability (BTC hitting $1M)
    resolution = analyzer.analyze_market(test_market, p_primary_event=0.001)

    print(f"\n50-50 Rule Detected: {resolution.has_5050_rule}")
    if resolution.alternative_event:
        print(f"Alternative Event: {resolution.alternative_event.name}")
        print(f"  Expected Date: {resolution.alternative_event.expected_date}")
        print(f"  Source: {resolution.alternative_event.source}")

    print(f"\nProbabilities:")
    print(f"  P(BTC hits $1M):     {resolution.p_primary:.1%}")
    print(f"  P(GTA VI releases):  {resolution.p_alternative:.1%}")
    print(f"  P(Neither by expiry): {resolution.p_neither:.1%}")

    print(f"\nFair Values:")
    print(f"  Fair YES: ${resolution.fair_yes:.3f}")
    print(f"  Fair NO:  ${resolution.fair_no:.3f}")

    # Get recommendation at current prices
    recommendation = analyzer.get_trading_recommendation(
        resolution,
        current_yes_price=0.50,
        current_no_price=0.50
    )

    print(f"\nTrading Recommendation (at YES=$0.50, NO=$0.50):")
    print(f"  Action: {recommendation['action']}")
    print(f"  Edge: {recommendation['edge']:.2%}")
    print(f"  Reason: {recommendation['reason']}")


if __name__ == '__main__':
    main()
