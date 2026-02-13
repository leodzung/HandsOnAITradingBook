#!/usr/bin/env python3
"""
Polymarket Arbitrage Bot

Implements arbitrage detection based on the IMDEA paper:
"Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets"
https://arxiv.org/abs/2508.03474

Three types of arbitrage:
1. Single-Condition: YES + NO < $1 (guaranteed profit)
2. NegRisk Rebalancing: Multi-outcome markets where sum < $1
3. Cross-Market (Combinatorial): Related markets with inconsistent pricing

References:
- Paper found $40M in arbitrage profits on Polymarket (Apr 2024 - Apr 2025)
- Single-condition: $10.58M across 7,051 conditions
- NegRisk rebalancing: $28.99M with 29x capital efficiency

Real-Time Mode:
- Uses WebSocket for live order book bid/ask spreads
- Detects true arbitrage from actual executable prices
- REST API only shows mid-prices (YES + NO always = $1)
"""

import sys
import os
# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import numpy as np

from core.polymarket_client import PolymarketClient

# Try to import WebSocket support
try:
    from orderbook_websocket import (
        OrderBookWebSocket,
        RealTimeArbitrageMonitor,
        ArbitrageSignal
    )
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity."""
    opportunity_id: str
    opportunity_type: str  # 'single_condition', 'negrisk', 'cross_market'
    timestamp: datetime

    # Market info
    market_id: str
    market_question: str

    # Prices
    yes_price: float = 0.0
    no_price: float = 0.0
    total_price: float = 0.0

    # For multi-outcome markets
    outcome_prices: List[float] = field(default_factory=list)
    outcome_names: List[str] = field(default_factory=list)

    # Profit calculation
    profit_per_dollar: float = 0.0
    profit_pct: float = 0.0
    min_profit_threshold: float = 0.02  # 2% minimum

    # Risk metrics
    volume_24h: float = 0.0
    liquidity: float = 0.0
    time_to_resolution: Optional[timedelta] = None
    risk_score: float = 0.0  # 0-1, lower is better

    # Execution info
    recommended_size: float = 0.0
    gas_estimate: float = 0.001  # ~$0.001 on Polygon

    # For cross-market arbitrage
    related_markets: List[Dict] = field(default_factory=list)
    relationship_type: str = ""  # 'contradictory', 'subset', 'complementary'

    def is_profitable(self) -> bool:
        """Check if opportunity meets profit threshold."""
        net_profit = self.profit_per_dollar - self.gas_estimate
        return net_profit >= self.min_profit_threshold

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return {
            'opportunity_id': self.opportunity_id,
            'type': self.opportunity_type,
            'timestamp': self.timestamp.isoformat(),
            'market_id': self.market_id,
            'question': self.market_question[:60],
            'yes_price': self.yes_price,
            'no_price': self.no_price,
            'total_price': self.total_price,
            'profit_pct': f"{self.profit_pct:.2%}",
            'risk_score': self.risk_score,
            'profitable': self.is_profitable()
        }


class SingleConditionDetector:
    """
    Detects single-condition arbitrage (YES + NO != $1).

    From the paper: This extracted $10.58M across 7,051 conditions.

    Two modes:
    1. REST mode: Uses mid-prices from outcomePrices (less accurate)
    2. WebSocket mode: Uses actual bid/ask from order book (accurate)
    """

    def __init__(self, min_profit_pct: float = 0.02, client: PolymarketClient = None):
        """
        Initialize detector.

        Args:
            min_profit_pct: Minimum profit percentage to flag (default 2%)
            client: PolymarketClient for fetching order books
        """
        self.min_profit_pct = min_profit_pct
        self.client = client

    def detect_from_orderbook(self, market: Dict) -> Optional[ArbitrageOpportunity]:
        """
        Detect arbitrage using actual order book bid/ask prices.

        This is more accurate than mid-prices because:
        - To BUY both: you pay the ASK prices
        - To SELL both: you receive the BID prices

        Real arbitrage exists when:
        - yes_ask + no_ask < 1.0 (buy both, guaranteed profit)
        - yes_bid + no_bid > 1.0 (sell both if you hold them)
        """
        if not self.client:
            return None

        # Get token IDs
        clob_tokens = market.get('clobTokenIds', '[]')
        if isinstance(clob_tokens, str):
            try:
                clob_tokens = json.loads(clob_tokens)
            except:
                return None

        if len(clob_tokens) != 2:
            return None

        yes_token_id, no_token_id = clob_tokens[0], clob_tokens[1]

        # Fetch order books
        yes_book = self.client.get_orderbook(yes_token_id)
        no_book = self.client.get_orderbook(no_token_id)

        # Extract best bid/ask
        yes_bids = yes_book.get('bids', [])
        yes_asks = yes_book.get('asks', [])
        no_bids = no_book.get('bids', [])
        no_asks = no_book.get('asks', [])

        if not (yes_bids and yes_asks and no_bids and no_asks):
            return None

        yes_best_bid = float(yes_bids[0]['price'])
        yes_best_ask = float(yes_asks[0]['price'])
        no_best_bid = float(no_bids[0]['price'])
        no_best_ask = float(no_asks[0]['price'])

        # Check BUY BOTH arbitrage: pay both asks, receive $1
        cost_to_buy_both = yes_best_ask + no_best_ask
        profit_buy_both = 1.0 - cost_to_buy_both

        # Check SELL BOTH arbitrage: receive both bids, owe $1
        value_if_sell_both = yes_best_bid + no_best_bid
        profit_sell_both = value_if_sell_both - 1.0

        # Determine best opportunity
        if profit_buy_both > self.min_profit_pct:
            profit_per_dollar = profit_buy_both
            profit_pct = profit_buy_both / cost_to_buy_both
            action = "BUY_BOTH"
            total_price = cost_to_buy_both
        elif profit_sell_both > self.min_profit_pct:
            profit_per_dollar = profit_sell_both
            profit_pct = profit_sell_both / 1.0
            action = "SELL_BOTH"
            total_price = value_if_sell_both
        else:
            return None

        volume = float(market.get('volume', 0) or 0)

        # Parse end date
        end_date_str = market.get('endDate')
        time_to_resolution = None
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                time_to_resolution = end_date - datetime.now(end_date.tzinfo)
            except:
                pass

        risk_score = self._calculate_risk_score(volume, time_to_resolution)

        opp = ArbitrageOpportunity(
            opportunity_id=f"sc_ob_{market.get('conditionId', '')}_{int(time.time())}",
            opportunity_type='single_condition_orderbook',
            timestamp=datetime.now(),
            market_id=market.get('conditionId', ''),
            market_question=market.get('question', ''),
            yes_price=yes_best_ask if action == "BUY_BOTH" else yes_best_bid,
            no_price=no_best_ask if action == "BUY_BOTH" else no_best_bid,
            total_price=total_price,
            profit_per_dollar=profit_per_dollar,
            profit_pct=profit_pct,
            volume_24h=volume,
            time_to_resolution=time_to_resolution,
            risk_score=risk_score,
            recommended_size=self._calculate_recommended_size(volume, profit_pct)
        )

        # Add order book details
        opp.related_markets = [{
            'yes_bid': yes_best_bid,
            'yes_ask': yes_best_ask,
            'no_bid': no_best_bid,
            'no_ask': no_best_ask,
            'action': action
        }]

        return opp

    def detect(self, market: Dict) -> Optional[ArbitrageOpportunity]:
        """
        Detect single-condition arbitrage in a binary market.

        Args:
            market: Market data from Polymarket API

        Returns:
            ArbitrageOpportunity if found, None otherwise
        """
        # Parse outcome prices
        outcome_prices_str = market.get('outcomePrices', '[]')
        try:
            if isinstance(outcome_prices_str, str):
                prices = json.loads(outcome_prices_str)
            else:
                prices = outcome_prices_str
        except:
            return None

        if len(prices) != 2:
            return None  # Not a binary market

        yes_price = float(prices[0])
        no_price = float(prices[1])
        total = yes_price + no_price

        # Check for arbitrage
        # Long arbitrage: total < 1 (buy both, guaranteed $1 payout)
        # Short arbitrage: total > 1 (sell both if you hold them)

        if abs(total - 1.0) < self.min_profit_pct:
            return None  # Not enough profit

        if total < 1.0:
            # Long arbitrage opportunity
            profit_per_dollar = 1.0 - total
            profit_pct = profit_per_dollar / total
            action = "BUY_BOTH"
        else:
            # Short arbitrage (requires existing holdings)
            profit_per_dollar = total - 1.0
            profit_pct = profit_per_dollar / 1.0
            action = "SELL_BOTH"

        if profit_pct < self.min_profit_pct:
            return None

        # Calculate risk score based on volume and time
        volume = float(market.get('volume', 0) or 0)

        # Parse end date for time to resolution
        end_date_str = market.get('endDate')
        time_to_resolution = None
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                time_to_resolution = end_date - datetime.now(end_date.tzinfo)
            except:
                pass

        # Risk score: lower volume and shorter time = higher risk
        risk_score = self._calculate_risk_score(volume, time_to_resolution)

        return ArbitrageOpportunity(
            opportunity_id=f"sc_{market.get('conditionId', '')}_{int(time.time())}",
            opportunity_type='single_condition',
            timestamp=datetime.now(),
            market_id=market.get('conditionId', ''),
            market_question=market.get('question', ''),
            yes_price=yes_price,
            no_price=no_price,
            total_price=total,
            profit_per_dollar=profit_per_dollar,
            profit_pct=profit_pct,
            volume_24h=volume,
            time_to_resolution=time_to_resolution,
            risk_score=risk_score,
            recommended_size=self._calculate_recommended_size(volume, profit_pct)
        )

    def _calculate_risk_score(self, volume: float,
                               time_to_resolution: Optional[timedelta]) -> float:
        """Calculate risk score 0-1 (lower is better)."""
        score = 0.0

        # Volume risk (low volume = higher risk)
        if volume < 1000:
            score += 0.4
        elif volume < 10000:
            score += 0.2
        elif volume < 100000:
            score += 0.1

        # Time risk (shorter time = higher risk of resolution)
        if time_to_resolution:
            days = time_to_resolution.total_seconds() / 86400
            if days < 1:
                score += 0.4
            elif days < 7:
                score += 0.2
            elif days < 30:
                score += 0.1

        return min(score, 1.0)

    def _calculate_recommended_size(self, volume: float, profit_pct: float) -> float:
        """Calculate recommended position size."""
        # Don't exceed 1% of 24h volume to avoid slippage
        max_from_volume = volume * 0.01

        # Scale by profit (higher profit = can use more)
        base_size = 100 * (profit_pct / 0.05)  # $100 base at 5% profit

        return min(base_size, max_from_volume, 1000)  # Cap at $1000


class NegRiskDetector:
    """
    Detects NegRisk rebalancing opportunities in multi-outcome markets.

    From the paper: This extracted $28.99M with 29x capital efficiency.

    NegRisk markets allow buying all outcomes for less than $1 when
    the sum of probabilities is less than 100%.
    """

    def __init__(self, min_profit_pct: float = 0.02):
        self.min_profit_pct = min_profit_pct

    def detect(self, market: Dict, related_conditions: List[Dict] = None) -> Optional[ArbitrageOpportunity]:
        """
        Detect NegRisk arbitrage in multi-outcome markets.

        Args:
            market: Primary market data
            related_conditions: Other conditions in the same market group

        Returns:
            ArbitrageOpportunity if found, None otherwise
        """
        # For NegRisk, we need multiple outcomes that should sum to 1
        # E.g., "Who will win the election?" with candidates A, B, C, D

        outcome_prices_str = market.get('outcomePrices', '[]')
        try:
            if isinstance(outcome_prices_str, str):
                prices = json.loads(outcome_prices_str)
            else:
                prices = outcome_prices_str
            prices = [float(p) for p in prices]
        except:
            return None

        # Need at least 3 outcomes for NegRisk to be interesting
        if len(prices) < 3:
            return None

        total = sum(prices)

        if total >= 1.0 - self.min_profit_pct:
            return None  # No arbitrage

        profit_per_dollar = 1.0 - total
        profit_pct = profit_per_dollar / total

        if profit_pct < self.min_profit_pct:
            return None

        # Parse outcome names
        outcomes_str = market.get('outcomes', '[]')
        try:
            if isinstance(outcomes_str, str):
                outcomes = json.loads(outcomes_str)
            else:
                outcomes = outcomes_str
        except:
            outcomes = [f"Outcome {i}" for i in range(len(prices))]

        volume = float(market.get('volume', 0) or 0)

        return ArbitrageOpportunity(
            opportunity_id=f"nr_{market.get('conditionId', '')}_{int(time.time())}",
            opportunity_type='negrisk',
            timestamp=datetime.now(),
            market_id=market.get('conditionId', ''),
            market_question=market.get('question', ''),
            outcome_prices=prices,
            outcome_names=outcomes,
            total_price=total,
            profit_per_dollar=profit_per_dollar,
            profit_pct=profit_pct,
            volume_24h=volume,
            risk_score=0.3,  # NegRisk generally lower risk
            recommended_size=min(volume * 0.01, 500)
        )


class CrossMarketDetector:
    """
    Detects cross-market (combinatorial) arbitrage using semantic analysis.

    From the paper: Uses embeddings to find related markets with
    inconsistent pricing.

    Example: "Will BTC hit $100k by Dec?" at 60% YES
             "Will BTC hit $150k by Dec?" at 50% YES
             These are inconsistent (can't have higher strike more likely)
    """

    def __init__(self, embedding_model: str = 'intfloat/e5-large-v2',
                 similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        self.embeddings_cache = {}
        self._model = None
        self._model_name = embedding_model

    def _get_model(self):
        """Lazy load embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                logger.info(f"Loaded embedding model: {self._model_name}")
            except ImportError:
                logger.warning("sentence-transformers not installed, using keyword matching")
                self._model = "keyword_fallback"
        return self._model

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding for text."""
        if text in self.embeddings_cache:
            return self.embeddings_cache[text]

        model = self._get_model()
        if model == "keyword_fallback":
            return None

        try:
            embedding = model.encode(text, normalize_embeddings=True)
            self.embeddings_cache[text] = embedding
            return embedding
        except:
            return None

    def find_related_markets(self, markets: List[Dict]) -> List[Tuple[Dict, Dict, float]]:
        """
        Find pairs of semantically related markets.

        Returns:
            List of (market1, market2, similarity_score) tuples
        """
        related_pairs = []

        # Group markets by likely topic (quick filter)
        topic_groups = self._group_by_topic(markets)

        for topic, group in topic_groups.items():
            if len(group) < 2:
                continue

            # Compare within group
            for i, m1 in enumerate(group):
                for m2 in group[i+1:]:
                    similarity = self._calculate_similarity(m1, m2)
                    if similarity >= self.similarity_threshold:
                        related_pairs.append((m1, m2, similarity))

        return related_pairs

    def _group_by_topic(self, markets: List[Dict]) -> Dict[str, List[Dict]]:
        """Quick grouping by keywords - stricter matching."""
        groups = defaultdict(list)

        # More specific topic groupings to avoid false matches
        topic_keywords = {
            'btc_price': ['bitcoin', 'btc'],  # Only BTC price markets
            'eth_price': ['ethereum', 'eth'],  # Only ETH price markets
            'sol_price': ['solana', 'sol'],
            'election_2024': ['2024 election', 'presidential election'],
            'trump': ['trump'],
            'fed_rates': ['federal reserve', 'interest rate', 'fomc', 'rate cut'],
            'tariffs': ['tariff'],
            'doge_cuts': ['doge cut', 'department of government efficiency'],
        }

        for market in markets:
            question = market.get('question', '').lower()
            matched = False

            for topic, keywords in topic_keywords.items():
                # Require more specific matching
                if any(kw in question for kw in keywords):
                    groups[topic].append(market)
                    matched = True
                    break

            # Don't add to 'other' - only group truly related markets
            # This prevents comparing unrelated markets

        return groups

    def _calculate_similarity(self, m1: Dict, m2: Dict) -> float:
        """Calculate semantic similarity between two markets."""
        q1 = m1.get('question', '')
        q2 = m2.get('question', '')

        # Try embedding similarity
        e1 = self._get_embedding(q1)
        e2 = self._get_embedding(q2)

        if e1 is not None and e2 is not None:
            return float(np.dot(e1, e2))

        # Fallback to keyword overlap
        words1 = set(q1.lower().split())
        words2 = set(q2.lower().split())

        if not words1 or not words2:
            return 0.0

        overlap = len(words1 & words2)
        return overlap / max(len(words1), len(words2))

    def detect_price_inconsistency(self, m1: Dict, m2: Dict) -> Optional[ArbitrageOpportunity]:
        """
        Detect if two related markets have inconsistent pricing.

        Examples:
        - "BTC > $100k" at 60% and "BTC > $150k" at 70% (impossible)
        - "A wins" at 60% and "B wins" at 50% when A and B are the only options
        """
        q1 = m1.get('question', '').lower()
        q2 = m2.get('question', '').lower()

        # Get YES prices
        p1 = self._get_yes_price(m1)
        p2 = self._get_yes_price(m2)

        if p1 is None or p2 is None:
            return None

        # First verify the markets are actually related (same subject)
        if not self._same_subject(q1, q2):
            return None

        # Check for price level inconsistency (higher strike should have lower probability)
        strike1 = self._extract_price_level(q1)
        strike2 = self._extract_price_level(q2)

        if strike1 and strike2 and strike1 != strike2:
            # Only flag if significant difference in strikes
            strike_diff_pct = abs(strike1 - strike2) / min(strike1, strike2)
            if strike_diff_pct < 0.1:  # Strikes too close, not useful
                return None

            # Higher strike should have lower YES probability
            # E.g., "BTC > $100k" should have higher prob than "BTC > $150k"
            if strike1 < strike2 and p1 < p2 - 0.05:  # Need 5% difference to matter
                # Inconsistency! Lower strike has lower probability
                logger.info(f"  Price inconsistency: ${strike1:,.0f}@{p1:.1%} vs ${strike2:,.0f}@{p2:.1%}")
                return self._create_cross_market_opportunity(
                    m1, m2, p1, p2, 'price_level_inconsistency'
                )
            elif strike1 > strike2 and p1 > p2 + 0.05:
                # Also inconsistent
                logger.info(f"  Price inconsistency: ${strike2:,.0f}@{p2:.1%} vs ${strike1:,.0f}@{p1:.1%}")
                return self._create_cross_market_opportunity(
                    m2, m1, p2, p1, 'price_level_inconsistency'
                )

        # Check for mutually exclusive events that sum > 1
        if self._are_mutually_exclusive(q1, q2):
            if p1 + p2 > 1.05:  # Sum > 105% is clearly wrong
                return self._create_cross_market_opportunity(
                    m1, m2, p1, p2, 'mutual_exclusion_violation'
                )

        return None

    def _same_subject(self, q1: str, q2: str) -> bool:
        """Check if two questions are about the same subject."""
        # Extract key subject indicators
        subjects = {
            'btc': ['bitcoin', 'btc'],
            'eth': ['ethereum', 'eth'],
            'sol': ['solana', 'sol'],
            'trump': ['trump'],
            'biden': ['biden'],
            'fed': ['federal reserve', 'fed ', 'fomc'],
        }

        q1_subjects = set()
        q2_subjects = set()

        for subject, keywords in subjects.items():
            if any(kw in q1 for kw in keywords):
                q1_subjects.add(subject)
            if any(kw in q2 for kw in keywords):
                q2_subjects.add(subject)

        # Must have at least one overlapping subject
        return bool(q1_subjects & q2_subjects)

    def _get_yes_price(self, market: Dict) -> Optional[float]:
        """Extract YES price from market."""
        prices_str = market.get('outcomePrices', '[]')
        try:
            if isinstance(prices_str, str):
                prices = json.loads(prices_str)
            else:
                prices = prices_str
            return float(prices[0]) if prices else None
        except:
            return None

    def _extract_price_level(self, question: str) -> Optional[float]:
        """Extract price level from question like 'Will BTC hit $100,000?'"""
        import re

        # Look for dollar amounts
        patterns = [
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*(?:k|K|thousand)?',
            r'([0-9,]+(?:\.[0-9]+)?)\s*(?:k|K|thousand)?\s*(?:dollars|USD)',
        ]

        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                value_str = match.group(1).replace(',', '')
                value = float(value_str)

                # Check for k/K suffix
                if 'k' in question[match.end():match.end()+2].lower():
                    value *= 1000

                return value

        return None

    def _are_mutually_exclusive(self, q1: str, q2: str) -> bool:
        """Check if two questions are about mutually exclusive events."""
        # Simple heuristic: same subject with different outcomes
        exclusive_patterns = [
            ('will win', 'will win'),  # Different candidates winning
            ('will be', 'will be'),     # Different outcomes
            ('first', 'first'),         # Race conditions
        ]

        for p1, p2 in exclusive_patterns:
            if p1 in q1 and p2 in q2:
                # Extract subject
                # This is a simplification - real implementation would use NER
                return True

        return False

    def _create_cross_market_opportunity(self, m1: Dict, m2: Dict,
                                          p1: float, p2: float,
                                          relationship: str) -> ArbitrageOpportunity:
        """Create a cross-market arbitrage opportunity."""
        # The profit depends on the specific inconsistency
        # For price-level inconsistency: buy the underpriced, sell the overpriced

        profit_estimate = abs(p1 - p2) * 0.5  # Conservative estimate

        return ArbitrageOpportunity(
            opportunity_id=f"cm_{m1.get('conditionId', '')[:8]}_{m2.get('conditionId', '')[:8]}_{int(time.time())}",
            opportunity_type='cross_market',
            timestamp=datetime.now(),
            market_id=m1.get('conditionId', ''),
            market_question=m1.get('question', ''),
            yes_price=p1,
            no_price=1.0 - p1,
            total_price=p1 + p2,
            profit_per_dollar=profit_estimate,
            profit_pct=profit_estimate / max(p1, p2),
            related_markets=[{
                'id': m2.get('conditionId', ''),
                'question': m2.get('question', ''),
                'yes_price': p2
            }],
            relationship_type=relationship,
            risk_score=0.6,  # Cross-market is higher risk
            recommended_size=50  # Conservative size for cross-market
        )


class ArbitrageLogger:
    """Persists arbitrage opportunities for analysis and execution."""

    def __init__(self, log_dir: str = 'data/arbitrage'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Separate files for each type
        self.files = {
            'single_condition': self.log_dir / 'single_condition.jsonl',
            'negrisk': self.log_dir / 'negrisk.jsonl',
            'cross_market': self.log_dir / 'cross_market.jsonl',
            'all': self.log_dir / 'all_opportunities.jsonl'
        }

    def log(self, opportunity: ArbitrageOpportunity):
        """Log an arbitrage opportunity."""
        data = opportunity.to_dict()
        data['logged_at'] = datetime.now().isoformat()

        # Log to type-specific file
        type_file = self.files.get(opportunity.opportunity_type, self.files['all'])
        with open(type_file, 'a') as f:
            f.write(json.dumps(data) + '\n')

        # Also log to combined file
        with open(self.files['all'], 'a') as f:
            f.write(json.dumps(data) + '\n')

    def get_recent(self, opportunity_type: str = None,
                   hours: int = 24) -> List[Dict]:
        """Get recent opportunities."""
        cutoff = datetime.now() - timedelta(hours=hours)
        results = []

        file_path = self.files.get(opportunity_type, self.files['all'])

        if not file_path.exists():
            return results

        with open(file_path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    logged_at = datetime.fromisoformat(data.get('logged_at', ''))
                    if logged_at >= cutoff:
                        results.append(data)
                except:
                    continue

        return results


class ArbitrageBot:
    """
    Main arbitrage bot that scans for opportunities.

    Based on the IMDEA paper methodology:
    1. Scan all markets periodically
    2. Detect single-condition arbitrage (YES + NO != $1)
    3. Detect NegRisk rebalancing (multi-outcome sum < $1)
    4. Detect cross-market inconsistencies (semantic analysis)
    5. Log opportunities for manual review or automated execution

    Two modes:
    - REST mode (default): Polls markets using REST API
    - WebSocket mode: Real-time order book monitoring for true bid/ask spreads
    """

    def __init__(self, config_path: str = 'config_arbitrage.json',
                 use_websocket: bool = True):
        """
        Initialize arbitrage bot.

        Args:
            config_path: Path to configuration file
            use_websocket: Enable WebSocket for real-time order book data
        """
        # Load config
        self.config = self._load_config(config_path)
        self.use_websocket = use_websocket and WEBSOCKET_AVAILABLE

        logger.info("=" * 60)
        logger.info("ARBITRAGE BOT INITIALIZING")
        logger.info("=" * 60)

        # Initialize components
        self.client = PolymarketClient()

        self.single_detector = SingleConditionDetector(
            min_profit_pct=self.config.get('min_profit_pct', 0.02),
            client=self.client  # Pass client for order book fetching
        )

        self.negrisk_detector = NegRiskDetector(
            min_profit_pct=self.config.get('min_profit_pct', 0.02)
        )

        self.cross_market_detector = CrossMarketDetector(
            embedding_model=self.config.get('embedding_model', 'intfloat/e5-large-v2'),
            similarity_threshold=self.config.get('similarity_threshold', 0.7)
        )

        self.logger = ArbitrageLogger(
            log_dir=self.config.get('log_dir', 'data/arbitrage')
        )

        # WebSocket monitor for real-time order book
        self.ws_monitor: Optional[RealTimeArbitrageMonitor] = None
        if self.use_websocket:
            logger.info("WebSocket mode ENABLED - using real-time order book data")
            self.ws_monitor = RealTimeArbitrageMonitor(
                min_profit_pct=self.config.get('min_profit_pct', 0.02),
                on_opportunity=self._on_ws_opportunity,
                signal_cooldown_seconds=self.config.get('websocket', {}).get('signal_cooldown_seconds', 30.0),
                min_price_change_pct=self.config.get('websocket', {}).get('min_price_change_pct', 0.01)
            )
        else:
            if not WEBSOCKET_AVAILABLE:
                logger.warning("WebSocket not available - install websocket-client")
            logger.info("REST mode - using mid-prices (less accurate)")

        # Statistics
        self.stats = {
            'scans': 0,
            'single_condition_found': 0,
            'single_condition_orderbook_found': 0,
            'negrisk_found': 0,
            'cross_market_found': 0,
            'websocket_opportunities': 0,
            'total_potential_profit': 0.0
        }

        logger.info(f"Min profit threshold: {self.config.get('min_profit_pct', 0.02):.1%}")
        logger.info(f"Scan interval: {self.config.get('scan_interval_seconds', 60)}s")
        logger.info(f"WebSocket enabled: {self.use_websocket}")
        logger.info("=" * 60)

    def _on_ws_opportunity(self, signal) -> None:
        """Handle real-time arbitrage signal from WebSocket."""
        self.stats['websocket_opportunities'] += 1

        # Convert to ArbitrageOpportunity for logging
        opp = ArbitrageOpportunity(
            opportunity_id=f"ws_{signal.condition_id}_{int(time.time())}",
            opportunity_type='websocket_realtime',
            timestamp=signal.timestamp,
            market_id=signal.condition_id,
            market_question=signal.market_question,
            yes_price=signal.yes_best_ask,
            no_price=signal.no_best_ask,
            total_price=signal.total_cost_to_buy,
            profit_per_dollar=signal.profit_if_buy_both,
            profit_pct=signal.profit_if_buy_both / signal.total_cost_to_buy if signal.total_cost_to_buy > 0 else 0,
            related_markets=[{
                'yes_bid': signal.yes_best_bid,
                'yes_ask': signal.yes_best_ask,
                'no_bid': signal.no_best_bid,
                'no_ask': signal.no_best_ask,
                'arb_type': signal.arb_type
            }]
        )

        self.logger.log(opp)

        logger.info(f"\n{'='*60}")
        logger.info("REAL-TIME ARBITRAGE DETECTED!")
        logger.info(f"Market: {signal.market_question[:50]}...")
        logger.info(f"YES: bid=${signal.yes_best_bid:.4f}, ask=${signal.yes_best_ask:.4f}")
        logger.info(f"NO:  bid=${signal.no_best_bid:.4f}, ask=${signal.no_best_ask:.4f}")
        logger.info(f"Buy both cost: ${signal.total_cost_to_buy:.4f}")
        logger.info(f"Profit: ${signal.profit_if_buy_both:.4f} ({signal.profit_if_buy_both*100:.2f}%)")
        logger.info(f"{'='*60}\n")

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration."""
        default_config = {
            'min_profit_pct': 0.02,  # 2% minimum profit
            'scan_interval_seconds': 60,
            'max_markets': 100,
            'embedding_model': 'intfloat/e5-large-v2',
            'similarity_threshold': 0.7,
            'log_dir': 'data/arbitrage',
            'paper_trading': True,
            'max_position_size': 100
        }

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                default_config.update(config)
        except FileNotFoundError:
            logger.info(f"Config not found at {config_path}, using defaults")
            # Save default config
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)

        return default_config

    def scan_markets(self) -> List[ArbitrageOpportunity]:
        """
        Scan all markets for arbitrage opportunities.

        Returns:
            List of found opportunities
        """
        opportunities = []

        logger.info("\n" + "=" * 60)
        logger.info(f"ARBITRAGE SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # Fetch markets
        try:
            markets = self.client.get_markets(
                limit=self.config.get('max_markets', 100),
                active=True
            )
            logger.info(f"Fetched {len(markets)} active markets")
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return opportunities

        # Update WebSocket subscriptions if enabled
        if self.ws_monitor:
            added = self.ws_monitor.add_markets_from_api(markets)
            logger.info(f"WebSocket tracking {added} markets for real-time arbitrage")

        # 1. Single-condition arbitrage (mid-price based - less accurate)
        logger.info("\n--- Single-Condition Scan (Mid-Price) ---")
        single_count = 0
        for market in markets:
            opp = self.single_detector.detect(market)
            if opp and opp.is_profitable():
                opportunities.append(opp)
                single_count += 1
                self.logger.log(opp)
                logger.info(f"  Found: {opp.market_question[:50]}...")
                logger.info(f"    YES=${opp.yes_price:.3f} + NO=${opp.no_price:.3f} = ${opp.total_price:.3f}")
                logger.info(f"    Profit: {opp.profit_pct:.2%}, Risk: {opp.risk_score:.2f}")

        logger.info(f"Single-condition (mid-price) opportunities: {single_count}")
        self.stats['single_condition_found'] += single_count

        # 1b. Single-condition with order book (more accurate)
        logger.info("\n--- Single-Condition Scan (Order Book) ---")
        orderbook_count = 0
        # Only scan top markets by volume to avoid rate limiting
        sorted_markets = sorted(markets, key=lambda m: float(m.get('volume', 0) or 0), reverse=True)
        top_markets = sorted_markets[:min(20, len(sorted_markets))]  # Top 20 by volume

        for market in top_markets:
            try:
                opp = self.single_detector.detect_from_orderbook(market)
                if opp and opp.is_profitable():
                    opportunities.append(opp)
                    orderbook_count += 1
                    self.logger.log(opp)
                    logger.info(f"  ORDERBOOK ARB: {opp.market_question[:50]}...")
                    if opp.related_markets:
                        details = opp.related_markets[0]
                        logger.info(f"    YES: bid=${details.get('yes_bid', 0):.4f}, ask=${details.get('yes_ask', 0):.4f}")
                        logger.info(f"    NO:  bid=${details.get('no_bid', 0):.4f}, ask=${details.get('no_ask', 0):.4f}")
                    logger.info(f"    Profit: {opp.profit_pct:.2%}, Action: {opp.related_markets[0].get('action', 'N/A') if opp.related_markets else 'N/A'}")
                time.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.debug(f"Error scanning orderbook for {market.get('conditionId', '')}: {e}")

        logger.info(f"Single-condition (order book) opportunities: {orderbook_count}")
        self.stats['single_condition_orderbook_found'] += orderbook_count

        # 2. NegRisk arbitrage (multi-outcome markets)
        logger.info("\n--- NegRisk Scan ---")
        negrisk_count = 0
        for market in markets:
            opp = self.negrisk_detector.detect(market)
            if opp and opp.is_profitable():
                opportunities.append(opp)
                negrisk_count += 1
                self.logger.log(opp)
                logger.info(f"  Found: {opp.market_question[:50]}...")
                logger.info(f"    Sum of outcomes: ${opp.total_price:.3f}")
                logger.info(f"    Profit: {opp.profit_pct:.2%}")

        logger.info(f"NegRisk opportunities: {negrisk_count}")
        self.stats['negrisk_found'] += negrisk_count

        # 3. Cross-market arbitrage
        logger.info("\n--- Cross-Market Scan ---")
        cross_count = 0

        # Find related market pairs
        related_pairs = self.cross_market_detector.find_related_markets(markets)
        logger.info(f"Found {len(related_pairs)} related market pairs")

        for m1, m2, similarity in related_pairs:
            opp = self.cross_market_detector.detect_price_inconsistency(m1, m2)
            if opp and opp.is_profitable():
                opportunities.append(opp)
                cross_count += 1
                self.logger.log(opp)
                logger.info(f"  Found: {opp.relationship_type}")
                logger.info(f"    M1: {opp.market_question[:40]}... @ {opp.yes_price:.3f}")
                logger.info(f"    M2: {opp.related_markets[0]['question'][:40]}... @ {opp.related_markets[0]['yes_price']:.3f}")

        logger.info(f"Cross-market opportunities: {cross_count}")
        self.stats['cross_market_found'] += cross_count

        # Summary
        total_profit = sum(o.profit_per_dollar * o.recommended_size for o in opportunities)
        self.stats['total_potential_profit'] += total_profit
        self.stats['scans'] += 1

        logger.info("\n" + "-" * 40)
        logger.info(f"SCAN SUMMARY:")
        logger.info(f"  Total opportunities: {len(opportunities)}")
        logger.info(f"  Potential profit: ${total_profit:.2f}")
        logger.info("-" * 40)

        return opportunities

    def run(self):
        """Run the arbitrage bot continuously."""
        logger.info("\n" + "=" * 60)
        logger.info("ARBITRAGE BOT STARTED")
        logger.info("=" * 60)

        scan_interval = self.config.get('scan_interval_seconds', 60)

        # Start WebSocket monitor if enabled
        if self.ws_monitor:
            logger.info("Starting WebSocket real-time monitor...")
            self.ws_monitor.start()
            if self.ws_monitor.wait_for_connection(timeout=15):
                logger.info("WebSocket connected - real-time arbitrage detection active")
            else:
                logger.warning("WebSocket connection failed - falling back to REST only")
                self.ws_monitor = None

        try:
            while True:
                try:
                    opportunities = self.scan_markets()

                    # Check WebSocket opportunities
                    ws_opportunities = []
                    if self.ws_monitor:
                        ws_opportunities = self.ws_monitor.scan_all()
                        if ws_opportunities:
                            logger.info(f"\nWebSocket found {len(ws_opportunities)} real-time opportunities")
                            for signal in ws_opportunities:
                                logger.info(f"  {signal.market_question[:40]}... profit={signal.profit_if_buy_both:.4f}")

                    # In paper trading mode, just log
                    if self.config.get('paper_trading', True):
                        total_opps = len(opportunities) + len(ws_opportunities)
                        if total_opps > 0:
                            logger.info(f"\n[PAPER MODE] Would execute {total_opps} trades")
                    else:
                        # TODO: Implement live execution
                        pass

                    # Log WebSocket stats
                    if self.ws_monitor:
                        ws_stats = self.ws_monitor.get_stats()
                        logger.info(f"\nWebSocket stats: {ws_stats['messages_received']} msgs, "
                                   f"{ws_stats['book_updates']} book updates, "
                                   f"{ws_stats['unique_opportunities']} unique opportunities "
                                   f"({ws_stats['total_signals']} total signals, "
                                   f"{ws_stats['avg_signals_per_opportunity']:.1f} avg/opportunity)")

                    logger.info(f"\nNext scan in {scan_interval} seconds...")
                    time.sleep(scan_interval)

                except Exception as e:
                    logger.error(f"Error in scan cycle: {e}", exc_info=True)
                    time.sleep(30)

        except KeyboardInterrupt:
            logger.info("\nShutting down...")
            if self.ws_monitor:
                self.ws_monitor.stop()
            self._print_stats()

    def _print_stats(self):
        """Print session statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("SESSION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total scans: {self.stats['scans']}")
        logger.info(f"Single-condition (mid-price): {self.stats['single_condition_found']}")
        logger.info(f"Single-condition (order book): {self.stats['single_condition_orderbook_found']}")
        logger.info(f"NegRisk opportunities: {self.stats['negrisk_found']}")
        logger.info(f"Cross-market opportunities: {self.stats['cross_market_found']}")
        logger.info(f"WebSocket real-time: {self.stats['websocket_opportunities']}")
        logger.info(f"Total potential profit: ${self.stats['total_potential_profit']:.2f}")

        if self.ws_monitor:
            ws_stats = self.ws_monitor.get_stats()
            logger.info("\nWebSocket Statistics:")
            logger.info(f"  Messages received: {ws_stats['messages_received']}")
            logger.info(f"  Book updates: {ws_stats['book_updates']}")
            logger.info(f"  Markets tracked: {ws_stats['monitored_markets']}")
            logger.info(f"  Unique opportunities: {ws_stats.get('unique_opportunities', 0)}")
            logger.info(f"  Total signals: {ws_stats.get('total_signals', 0)}")
            logger.info(f"  Avg signals/opportunity: {ws_stats.get('avg_signals_per_opportunity', 0):.1f}")
            logger.info(f"  Reconnects: {ws_stats.get('reconnects', 0)}")

        logger.info("=" * 60)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Polymarket Arbitrage Bot')
    parser.add_argument('--config', default='config_arbitrage.json',
                       help='Path to config file')
    parser.add_argument('--no-websocket', action='store_true',
                       help='Disable WebSocket (use REST only)')
    parser.add_argument('--rest-only', action='store_true',
                       help='Same as --no-websocket')

    args = parser.parse_args()

    use_websocket = not (args.no_websocket or args.rest_only)

    bot = ArbitrageBot(
        config_path=args.config,
        use_websocket=use_websocket
    )
    bot.run()


if __name__ == '__main__':
    main()
