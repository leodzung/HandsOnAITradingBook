"""
Market Parser for Price-Level Markets
Parses Polymarket market questions to extract asset, strike price, and expiry date.
"""

import re
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceLevelMarketParser:
    """Parse price-level market questions to extract structured data."""

    # Regex patterns for detecting price-level markets by asset
    # Group 1: number, Group 2: optional suffix (k/m/b) - must be followed by word boundary
    PATTERNS = {
        'BTC': [
            r'bitcoin.*?\$?([0-9,]+)\s*([kmb])?\b',
            r'btc.*?\$?([0-9,]+)\s*([kmb])?\b',
            r'\$([0-9,]+)\s*([kmb])?\b.*?bitcoin',
        ],
        'ETH': [
            r'ethereum.*?\$?([0-9,]+)\s*([kmb])?\b',
            r'eth\b.*?\$?([0-9,]+)\s*([kmb])?\b',
            r'\$([0-9,]+)\s*([kmb])?\b.*?ethereum',
        ],
        'GOLD': [
            r'gold.*?\$?([0-9,]+)\s*([kmb])?\b',
            r'xau.*?\$?([0-9,]+)\s*([kmb])?\b',
            r'\$([0-9,]+)\s*([kmb])?\b.*?gold',
        ]
    }

    # Multipliers for price suffixes
    SUFFIX_MULTIPLIERS = {
        'k': 1_000,
        'm': 1_000_000,
        'b': 1_000_000_000,
    }

    # Keywords that indicate price-level markets
    PRICE_LEVEL_KEYWORDS = [
        'reach', 'break', 'hit', 'exceed', 'above', 'below', 'close',
        'price', 'value', 'worth', 'trade', 'dip', 'drop', 'fall'
    ]

    def __init__(self):
        """Initialize parser."""
        logger.info("PriceLevelMarketParser initialized")

    def parse_market(self, market: Dict) -> Optional[Dict]:
        """
        Parse market question to extract structured data.

        Args:
            market: Market dictionary from Polymarket API

        Returns:
            Dictionary with parsed data or None if not a price-level market:
            {
                'asset': 'BTC' | 'ETH' | 'GOLD',
                'strike_price': float,
                'expiry_date': datetime,
                'direction': 'ABOVE' | 'BELOW',
                'days_to_expiry': int,
                'conditionId': str,
                'token_id': str,
                'question': str,
                'market_type': 'threshold' | 'race',
                'race_prices': [float, float] (only for race markets)
            }
        """
        question = market.get('question', '')
        if not question:
            return None

        question_lower = question.lower()

        # Check if it's a price-level market
        if not any(keyword in question_lower for keyword in self.PRICE_LEVEL_KEYWORDS):
            return None

        # Detect asset
        asset = self._detect_asset(question_lower)
        if not asset:
            return None

        # Check if it's a "race" market (e.g., "hit $80k or $150k first")
        is_race, race_prices = self._detect_race_market(question_lower, asset)

        # Extract strike price
        strike_price = self._extract_strike_price(question_lower, asset)
        if strike_price is None:
            return None

        # Extract expiry from endDateIso
        expiry_date, days_to_expiry = self._extract_expiry(market)
        if expiry_date is None:
            return None

        # Detect direction (most markets are "Will X reach Y?" which is ABOVE)
        direction = self._detect_direction(question_lower)

        # Parse token_id from clobTokenIds
        token_id = self._extract_token_id(market)
        if not token_id:
            logger.warning(f"No token_id for market {market.get('conditionId')}")
            return None

        result = {
            'asset': asset,
            'strike_price': strike_price,
            'expiry_date': expiry_date,
            'direction': direction,
            'days_to_expiry': days_to_expiry,
            'conditionId': market.get('conditionId'),
            'token_id': token_id,
            'question': question,
            'market_type': 'race' if is_race else 'threshold'
        }

        if is_race:
            result['race_prices'] = race_prices

        return result

    def _detect_race_market(self, question_lower: str, asset: str) -> tuple[bool, list]:
        """
        Detect if market is a "race" type (e.g., "hit $80k or $150k first").

        Race markets have different semantics - YES means the FIRST price is hit first,
        which for a price BELOW current spot is actually a bearish bet.

        Args:
            question_lower: Lowercased question
            asset: Asset symbol

        Returns:
            Tuple of (is_race, [price1, price2])
        """
        import re

        # Patterns for race markets
        race_patterns = [
            r'hit\s+\$?([\d,]+)([kmb])?\s+or\s+\$?([\d,]+)([kmb])?\s+first',
            r'reach\s+\$?([\d,]+)([kmb])?\s+or\s+\$?([\d,]+)([kmb])?\s+first',
            r'\$?([\d,]+)([kmb])?\s+or\s+\$?([\d,]+)([kmb])?\s+first',
        ]

        for pattern in race_patterns:
            match = re.search(pattern, question_lower)
            if match:
                try:
                    price1_str = match.group(1).replace(',', '')
                    price1 = float(price1_str)
                    suffix1 = match.group(2)
                    if suffix1:
                        price1 *= self.SUFFIX_MULTIPLIERS.get(suffix1.lower(), 1)

                    price2_str = match.group(3).replace(',', '')
                    price2 = float(price2_str)
                    suffix2 = match.group(4)
                    if suffix2:
                        price2 *= self.SUFFIX_MULTIPLIERS.get(suffix2.lower(), 1)

                    return True, sorted([price1, price2])
                except (ValueError, IndexError):
                    continue

        return False, []

    def _detect_asset(self, question_lower: str) -> Optional[str]:
        """
        Detect which asset the market is about.

        Args:
            question_lower: Lowercased question

        Returns:
            'BTC', 'ETH', 'GOLD', or None
        """
        # Check for each asset
        if any(keyword in question_lower for keyword in ['bitcoin', 'btc']):
            return 'BTC'
        elif any(keyword in question_lower for keyword in ['ethereum', 'eth']):
            return 'ETH'
        elif any(keyword in question_lower for keyword in ['gold', 'xau']):
            return 'GOLD'

        return None

    def _extract_strike_price(self, question_lower: str, asset: str) -> Optional[float]:
        """
        Extract strike price from question.

        Args:
            question_lower: Lowercased question
            asset: Asset symbol ('BTC', 'ETH', 'GOLD')

        Returns:
            Strike price as float or None
        """
        patterns = self.PATTERNS.get(asset, [])

        for pattern in patterns:
            match = re.search(pattern, question_lower)
            if match:
                price_str = match.group(1).replace(',', '')

                try:
                    price = float(price_str)

                    # Handle suffix (k/m/b) from capture group 2
                    suffix = match.group(2) if len(match.groups()) > 1 else None
                    if suffix:
                        multiplier = self.SUFFIX_MULTIPLIERS.get(suffix.lower(), 1)
                        price = price * multiplier

                    # Sanity checks (adjusted for larger values with m/b suffixes)
                    if asset == 'BTC' and (price < 1000 or price > 10_000_000):
                        continue  # Unrealistic BTC price
                    elif asset == 'ETH' and (price < 100 or price > 1_000_000):
                        continue  # Unrealistic ETH price
                    elif asset == 'GOLD' and (price < 500 or price > 100_000):
                        continue  # Unrealistic Gold price

                    return price

                except ValueError:
                    continue

        return None

    def _extract_expiry(self, market: Dict) -> tuple[Optional[datetime], Optional[int]]:
        """
        Extract expiry date from market.

        Args:
            market: Market dictionary

        Returns:
            Tuple of (expiry_date, days_to_expiry)
        """
        try:
            # Try endDateIso first (ISO format)
            end_date_str = market.get('endDateIso') or market.get('endDate')
            if end_date_str and isinstance(end_date_str, str):
                # Handle ISO date format (e.g., "2026-07-31T00:00:00Z")
                expiry_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                days_to_expiry = (expiry_date - datetime.now(expiry_date.tzinfo)).days
                return expiry_date, days_to_expiry

            # Fallback to endDate as Unix timestamp (if numeric)
            end_date_unix = market.get('endDate')
            if end_date_unix and isinstance(end_date_unix, (int, float)):
                expiry_date = datetime.fromtimestamp(int(end_date_unix))
                days_to_expiry = (expiry_date - datetime.now()).days
                return expiry_date, days_to_expiry

        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Error parsing expiry: {e}")

        return None, None

    def _detect_direction(self, question_lower: str) -> str:
        """
        Detect if market is betting on price going ABOVE or BELOW a level.

        Args:
            question_lower: Lowercased question

        Returns:
            'ABOVE' or 'BELOW'
        """
        below_keywords = ['below', 'under', 'less than', 'drop', 'fall', 'decline']
        if any(keyword in question_lower for keyword in below_keywords):
            return 'BELOW'

        # Default to ABOVE (most markets are "Will X reach Y?")
        return 'ABOVE'

    def _extract_token_id(self, market: Dict) -> Optional[str]:
        """
        Extract token_id from market clobTokenIds.

        WARNING: This returns token_ids[0] which is NOT guaranteed to be the YES token!
        For live trading, use PolymarketClient.identify_yes_token() to verify.

        Args:
            market: Market dictionary

        Returns:
            Token ID string or None
        """
        token_ids_str = market.get('clobTokenIds')
        if not token_ids_str:
            return None

        try:
            # Parse JSON string
            if isinstance(token_ids_str, str):
                token_ids = json.loads(token_ids_str)
            else:
                token_ids = token_ids_str

            # Return first token (for binary markets)
            # NOTE: This assumes token[0] = YES which may not always be true!
            if token_ids and len(token_ids) > 0:
                return token_ids[0]

        except (json.JSONDecodeError, TypeError, IndexError) as e:
            logger.debug(f"Error parsing token IDs: {e}")

        return None

    def _extract_both_token_ids(self, market: Dict) -> tuple:
        """
        Extract both token IDs from market.

        Args:
            market: Market dictionary

        Returns:
            Tuple of (token_id_0, token_id_1) or (None, None)
        """
        token_ids_str = market.get('clobTokenIds')
        if not token_ids_str:
            return (None, None)

        try:
            if isinstance(token_ids_str, str):
                token_ids = json.loads(token_ids_str)
            else:
                token_ids = token_ids_str

            if len(token_ids) >= 2:
                return (token_ids[0], token_ids[1])
            elif len(token_ids) == 1:
                return (token_ids[0], None)

        except (json.JSONDecodeError, TypeError, IndexError) as e:
            logger.debug(f"Error parsing token IDs: {e}")

        return (None, None)

    def filter_price_level_markets(self, markets: List[Dict],
                                   assets: Optional[List[str]] = None) -> List[Dict]:
        """
        Filter markets to only price-level markets for specified assets.

        Args:
            markets: List of market dictionaries
            assets: List of assets to filter for (default: ['BTC', 'ETH', 'GOLD'])

        Returns:
            List of parsed price-level markets
        """
        if assets is None:
            assets = ['BTC', 'ETH', 'GOLD']

        parsed_markets = []

        for market in markets:
            parsed = self.parse_market(market)
            if parsed and parsed['asset'] in assets:
                parsed_markets.append(parsed)

        logger.info(f"Filtered {len(parsed_markets)} price-level markets from {len(markets)} total")

        return parsed_markets


# Example usage
if __name__ == '__main__':
    parser = PriceLevelMarketParser()

    # Test cases
    test_markets = [
        {
            'question': 'Will Bitcoin reach $150,000 by December 31, 2025?',
            'conditionId': '0xabc123',
            'endDateIso': '2025-12-31',
            'clobTokenIds': '["123456789", "987654321"]'
        },
        {
            'question': 'Will BTC break $100k before 2026?',
            'conditionId': '0xdef456',
            'endDateIso': '2025-12-31',
            'clobTokenIds': '["111111111", "222222222"]'
        },
        {
            'question': 'Will Ethereum hit $10,000 by December 31?',
            'conditionId': '0xghi789',
            'endDateIso': '2025-12-31',
            'clobTokenIds': '["333333333", "444444444"]'
        },
        {
            'question': 'Will Gold close above $3,000 at end of 2025?',
            'conditionId': '0xjkl012',
            'endDateIso': '2025-12-31',
            'clobTokenIds': '["555555555", "666666666"]'
        },
        {
            'question': 'Will Trump win 2024 election?',  # Not a price-level market
            'conditionId': '0xmno345',
            'endDateIso': '2024-11-05',
            'clobTokenIds': '["777777777", "888888888"]'
        },
        {
            'question': 'Will Bitcoin drop below $50,000 in 2025?',
            'conditionId': '0xpqr678',
            'endDateIso': '2025-12-31',
            'clobTokenIds': '["999999999", "000000000"]'
        }
    ]

    print("\n=== Testing Market Parser ===\n")

    for market in test_markets:
        print(f"Question: {market['question']}")
        parsed = parser.parse_market(market)

        if parsed:
            print(f"  ✓ MATCHED")
            print(f"    Asset: {parsed['asset']}")
            print(f"    Strike: ${parsed['strike_price']:,.2f}")
            print(f"    Direction: {parsed['direction']}")
            print(f"    Expiry: {parsed['expiry_date']}")
            print(f"    Days to expiry: {parsed['days_to_expiry']}")
            print(f"    Token ID: {parsed['token_id'][:20]}...")
        else:
            print(f"  ✗ NOT A PRICE-LEVEL MARKET")

        print()

    # Test filter function
    print("\n=== Testing Filter Function ===")
    parsed_markets = parser.filter_price_level_markets(test_markets)
    print(f"Found {len(parsed_markets)} price-level markets")
    for pm in parsed_markets:
        print(f"  - {pm['asset']} @ ${pm['strike_price']:,.0f} ({pm['direction']})")
