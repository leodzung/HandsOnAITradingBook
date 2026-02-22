"""
DEX Screening Utilities
Shared functions for fetching and analyzing on-chain DEX data
"""

import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import requests

# Optional imports for production use
try:
    from web3 import Web3
except ImportError:
    Web3 = None  # Demo mode - will use mock data


@dataclass
class Token:
    """Represents a token with its metadata"""
    address: str
    symbol: str
    name: str
    chain: str
    decimals: int = 18

@dataclass
class LiquidityPool:
    """Represents a DEX liquidity pool"""
    address: str
    token0: Token
    token1: Token
    liquidity_usd: float
    volume_24h: float
    created_timestamp: int
    dex_name: str
    chain: str

@dataclass
class TokenMetrics:
    """Token safety and opportunity metrics"""
    token_address: str
    liquidity_usd: float
    volume_24h: float
    holder_count: int
    top_10_concentration: float  # % held by top 10 holders
    honeypot_risk: float  # 0-1 score
    contract_verified: bool
    buy_tax: float
    sell_tax: float
    liquidity_locked: bool
    creation_time: int
    price_change_1h: float
    price_change_24h: float
    listed_on_cex: bool = False  # Is token listed on major CEXs?
    cex_exchanges: list = None  # List of CEX names where listed

    def __post_init__(self):
        """Initialize mutable defaults"""
        if self.cex_exchanges is None:
            self.cex_exchanges = []


class DEXDataFetcher:
    """Fetches data from various DEX sources"""

    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """
        Initialize with API keys for various services
        api_keys: {
            'etherscan': 'key',
            'bscscan': 'key',
            'dexscreener': 'key',
            'moralis': 'key'
        }
        """
        self.api_keys = api_keys or {}
        self.session = requests.Session()

    def get_new_pools(self, chain: str = 'ethereum', min_liquidity: float = 10000,
                     max_age_hours: int = 24) -> List[LiquidityPool]:
        """
        Fetch newly created liquidity pools

        Args:
            chain: 'ethereum', 'bsc', or 'solana'
            min_liquidity: Minimum liquidity in USD
            max_age_hours: Maximum pool age in hours

        Returns:
            List of new liquidity pools
        """
        # In production, this would call DexScreener API, The Graph, or direct RPC
        # For now, return mock data structure

        pools = []

        # Mock implementation - in production use actual API calls
        print(f"[DEXDataFetcher] Fetching new pools on {chain} with min liquidity ${min_liquidity:,.0f}")

        # Example API endpoint (DexScreener-like):
        # url = f"https://api.dexscreener.com/latest/dex/search/?q={chain}"

        return pools

    def get_token_metrics(self, token_address: str, chain: str = 'ethereum') -> TokenMetrics:
        """
        Get comprehensive token safety and opportunity metrics

        Args:
            token_address: Token contract address
            chain: Blockchain network

        Returns:
            TokenMetrics object with all relevant data
        """
        # Mock implementation - in production call multiple APIs
        print(f"[DEXDataFetcher] Analyzing token {token_address[:8]}... on {chain}")

        # Would combine data from:
        # - Honeypot.is API for scam detection
        # - Etherscan/BSCScan for contract verification
        # - DEX APIs for liquidity/volume
        # - Token Sniffer for security score

        return TokenMetrics(
            token_address=token_address,
            liquidity_usd=0,
            volume_24h=0,
            holder_count=0,
            top_10_concentration=0,
            honeypot_risk=0,
            contract_verified=False,
            buy_tax=0,
            sell_tax=0,
            liquidity_locked=False,
            creation_time=int(time.time()),
            price_change_1h=0,
            price_change_24h=0,
            listed_on_cex=False,
            cex_exchanges=[]
        )

    def check_honeypot(self, token_address: str, chain: str = 'ethereum') -> Dict:
        """
        Check if token is a honeypot scam

        Returns:
            Dict with honeypot detection results
        """
        # In production, call honeypot.is API or similar
        # Example: https://api.honeypot.is/v2/IsHoneypot?address={token_address}&chainID={chain_id}

        return {
            'is_honeypot': False,
            'buy_tax': 0,
            'sell_tax': 0,
            'is_blacklisted': False,
            'can_sell': True
        }

    def get_whale_wallets(self, chain: str = 'ethereum', min_success_rate: float = 0.6) -> List[str]:
        """
        Get list of successful whale wallet addresses for smart money tracking

        Args:
            chain: Blockchain network
            min_success_rate: Minimum historical success rate (0-1)

        Returns:
            List of wallet addresses
        """
        # In production, would use:
        # - Nansen API for wallet labels
        # - Custom analytics on historical performance
        # - Arkham Intelligence API

        return []

    def get_wallet_transactions(self, wallet_address: str, chain: str = 'ethereum',
                               limit: int = 100) -> List[Dict]:
        """
        Get recent transactions for a wallet

        Returns:
            List of transaction objects
        """
        # In production use Etherscan API, Moralis, or direct RPC
        return []

    def get_token_price_history(self, token_address: str, chain: str = 'ethereum',
                                interval: str = '1h', limit: int = 168) -> List[Dict]:
        """
        Get historical price data for a token

        Args:
            interval: '1m', '5m', '1h', '1d'
            limit: Number of candles

        Returns:
            List of OHLCV candles
        """
        return []

    def check_cex_listing(self, token_address: str, chain: str = 'ethereum') -> Dict:
        """
        Check if token is listed on major centralized exchanges

        Uses CoinGecko API (free, no key required) to check listings

        Args:
            token_address: Token contract address
            chain: Blockchain network

        Returns:
            Dict with CEX listing information:
            {
                'listed_on_cex': bool,
                'exchanges': List[str],
                'major_cex_count': int
            }
        """
        major_exchanges = {
            'binance', 'coinbase', 'kraken', 'bitfinex', 'gemini',
            'bybit', 'okx', 'kucoin', 'huobi', 'crypto.com'
        }

        try:
            # Map chain to CoinGecko platform ID
            platform_mapping = {
                'ethereum': 'ethereum',
                'bsc': 'binance-smart-chain',
                'solana': 'solana'
            }

            platform_id = platform_mapping.get(chain.lower(), 'ethereum')

            # CoinGecko API endpoint (no key required for basic usage)
            url = f"https://api.coingecko.com/api/v3/coins/{platform_id}/contract/{token_address.lower()}"

            # Add delay to respect rate limits (50 calls/min for free tier)
            time.sleep(1.2)

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Get list of exchanges (tickers)
                tickers = data.get('tickers', [])

                # Extract unique exchange names
                exchanges = set()
                for ticker in tickers:
                    exchange_name = ticker.get('market', {}).get('identifier', '').lower()
                    if exchange_name:
                        exchanges.add(exchange_name)

                # Check for major CEX presence
                major_cex_found = exchanges.intersection(major_exchanges)

                return {
                    'listed_on_cex': len(major_cex_found) > 0,
                    'exchanges': list(exchanges),
                    'major_exchanges': list(major_cex_found),
                    'major_cex_count': len(major_cex_found)
                }

            elif response.status_code == 404:
                # Token not found in CoinGecko - likely DEX-only
                return {
                    'listed_on_cex': False,
                    'exchanges': [],
                    'major_exchanges': [],
                    'major_cex_count': 0
                }
            else:
                print(f"[CEX Check] API returned {response.status_code}")
                # Return conservative default
                return {
                    'listed_on_cex': False,
                    'exchanges': [],
                    'major_exchanges': [],
                    'major_cex_count': 0
                }

        except requests.exceptions.RequestException as e:
            print(f"[CEX Check] Request failed: {e}")
            # Return conservative default
            return {
                'listed_on_cex': False,
                'exchanges': [],
                'major_exchanges': [],
                'major_cex_count': 0
            }
        except Exception as e:
            print(f"[CEX Check] Unexpected error: {e}")
            return {
                'listed_on_cex': False,
                'exchanges': [],
                'major_exchanges': [],
                'major_cex_count': 0
            }


class RiskAnalyzer:
    """Analyzes token safety and risk metrics"""

    @staticmethod
    def calculate_safety_score(metrics: TokenMetrics) -> float:
        """
        Calculate overall safety score (0-100)

        Higher score = safer token
        """
        score = 100.0

        # Deduct points for risk factors
        if not metrics.contract_verified:
            score -= 20

        if metrics.honeypot_risk > 0.5:
            score -= 30

        if metrics.buy_tax > 10 or metrics.sell_tax > 10:
            score -= 15

        if metrics.top_10_concentration > 50:
            score -= 20

        if not metrics.liquidity_locked:
            score -= 15

        if metrics.liquidity_usd < 50000:
            score -= 10

        return max(0, score)

    @staticmethod
    def calculate_opportunity_score(metrics: TokenMetrics) -> float:
        """
        Calculate opportunity score (0-100)

        Higher score = better potential opportunity
        """
        score = 0.0

        # Add points for positive indicators
        if metrics.price_change_1h > 5:
            score += 15

        if metrics.price_change_24h > 10:
            score += 20

        if metrics.volume_24h > metrics.liquidity_usd * 0.5:
            score += 25  # Good volume/liquidity ratio

        if metrics.holder_count > 100:
            score += 10

        # Recent creation bonus (within 48 hours)
        age_hours = (time.time() - metrics.creation_time) / 3600
        if age_hours < 48:
            score += 20

        # Moderate concentration is good (not too centralized, not too distributed)
        if 20 < metrics.top_10_concentration < 40:
            score += 10

        # DEX-ONLY BONUS - Major opportunity indicator
        # Tokens not yet on CEXs have higher upside potential
        if not metrics.listed_on_cex:
            score += 30  # Significant bonus for DEX-only gems
        else:
            # Penalize tokens already on major CEXs
            score -= (len(metrics.cex_exchanges) * 5)  # -5 per CEX listing

        return min(100, max(0, score))

    @staticmethod
    def is_viable_opportunity(metrics: TokenMetrics, min_safety: float = 50,
                            min_opportunity: float = 60) -> Tuple[bool, str]:
        """
        Determine if token meets minimum thresholds

        Returns:
            (is_viable, reason)
        """
        safety = RiskAnalyzer.calculate_safety_score(metrics)
        opportunity = RiskAnalyzer.calculate_opportunity_score(metrics)

        if safety < min_safety:
            return False, f"Safety score too low: {safety:.1f} < {min_safety}"

        if opportunity < min_opportunity:
            return False, f"Opportunity score too low: {opportunity:.1f} < {min_opportunity}"

        if metrics.honeypot_risk > 0.7:
            return False, "High honeypot risk detected"

        return True, f"Viable (Safety: {safety:.1f}, Opportunity: {opportunity:.1f})"


def format_token_report(metrics: TokenMetrics) -> str:
    """Format a human-readable token analysis report"""

    safety = RiskAnalyzer.calculate_safety_score(metrics)
    opportunity = RiskAnalyzer.calculate_opportunity_score(metrics)
    viable, reason = RiskAnalyzer.is_viable_opportunity(metrics)

    report = f"""
{'='*70}
TOKEN ANALYSIS REPORT
{'='*70}

Address: {metrics.token_address}
Created: {datetime.fromtimestamp(metrics.creation_time).strftime('%Y-%m-%d %H:%M:%S')}

LIQUIDITY & VOLUME
  Liquidity (USD):     ${metrics.liquidity_usd:,.2f}
  24h Volume:          ${metrics.volume_24h:,.2f}
  Volume/Liquidity:    {(metrics.volume_24h/max(metrics.liquidity_usd,1)*100):.1f}%

PRICE MOVEMENT
  1h Change:           {metrics.price_change_1h:+.2f}%
  24h Change:          {metrics.price_change_24h:+.2f}%

HOLDER DISTRIBUTION
  Total Holders:       {metrics.holder_count}
  Top 10 Ownership:    {metrics.top_10_concentration:.1f}%

SAFETY CHECKS
  Contract Verified:   {'✓' if metrics.contract_verified else '✗'}
  Liquidity Locked:    {'✓' if metrics.liquidity_locked else '✗'}
  Buy Tax:             {metrics.buy_tax:.1f}%
  Sell Tax:            {metrics.sell_tax:.1f}%
  Honeypot Risk:       {metrics.honeypot_risk*100:.1f}%

CEX LISTING STATUS
  Listed on CEX:       {'✗ DEX-ONLY 🎯' if not metrics.listed_on_cex else '✓ On CEX'}
  Major Exchanges:     {', '.join(metrics.cex_exchanges[:5]) if metrics.cex_exchanges else 'None'}
  CEX Count:           {len(metrics.cex_exchanges)}

SCORES
  Safety Score:        {safety:.1f}/100
  Opportunity Score:   {opportunity:.1f}/100

VERDICT: {'✓ VIABLE' if viable else '✗ REJECT'} - {reason}
{'='*70}
"""
    return report
