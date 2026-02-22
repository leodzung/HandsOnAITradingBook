"""
Real DEX Data Fetcher
=====================

Fetches actual token and pool data from live DEX APIs.
Supports multiple data sources with fallbacks.
"""

import requests
import json
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dex_utils import Token, LiquidityPool, TokenMetrics, DEXDataFetcher


class RealDEXFetcher:
    """
    Fetches real-time data from DEX APIs
    """

    def __init__(self, config_path: str = "config.json", check_cex: bool = True):
        """Initialize with configuration"""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Config file not found, using defaults")
            self.config = {"api_keys": {}}

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DEX-Screener/1.0'
        })

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds between requests

        # CEX checking
        self.check_cex = check_cex
        self.dex_data_fetcher = DEXDataFetcher() if check_cex else None

    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def get_latest_pools(self, chain: str = "ethereum", limit: int = 20) -> List[Dict]:
        """
        Fetch latest pools from DexScreener API (free, no auth required)

        Args:
            chain: "ethereum", "bsc", "solana"
            limit: Number of pools to fetch

        Returns:
            List of pool dictionaries
        """
        print(f"\n[RealDEXFetcher] Fetching latest pools on {chain.upper()}...")

        self._rate_limit()

        # Map chain names to DexScreener chain IDs
        chain_mapping = {
            "ethereum": "ethereum",
            "bsc": "bsc",
            "solana": "solana"
        }

        chain_id = chain_mapping.get(chain.lower(), "ethereum")

        try:
            # DexScreener search endpoint - search for popular base tokens
            # This gives us recent pairs with actual liquidity
            search_tokens = {
                'ethereum': 'WETH',
                'bsc': 'WBNB',
                'solana': 'SOL'
            }

            search_term = search_tokens.get(chain_id, 'WETH')
            url = f"https://api.dexscreener.com/latest/dex/search?q={search_term}"

            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if 'pairs' in data:
                    # Filter by chain
                    all_pools = data['pairs']
                    pools = [p for p in all_pools if p.get('chainId', '').lower() == chain_id.lower()][:limit]
                    print(f"  ✓ Found {len(pools)} pools on {chain_id}")
                    return pools
                else:
                    print(f"  ⚠️  No 'pairs' in response")
                    return []
            else:
                print(f"  ✗ API error: {response.status_code}")
                return []

        except requests.exceptions.RequestException as e:
            print(f"  ✗ Request failed: {e}")
            return []

    def get_new_pools_by_age(self, chain: str = "ethereum", max_age_hours: int = 24,
                             min_liquidity: float = 10000) -> List[LiquidityPool]:
        """
        Get recently created pools filtered by age and liquidity

        Args:
            chain: Blockchain network
            max_age_hours: Maximum pool age
            min_liquidity: Minimum liquidity in USD

        Returns:
            List of LiquidityPool objects
        """
        print(f"\n[RealDEXFetcher] Searching for new pools on {chain.upper()}...")
        print(f"  Filters: Age < {max_age_hours}h, Liquidity > ${min_liquidity:,.0f}")

        # Get latest pools
        raw_pools = self.get_latest_pools(chain, limit=50)

        if not raw_pools:
            print(f"  ⚠️  No pools fetched")
            return []

        filtered_pools = []
        cutoff_time = time.time() - (max_age_hours * 3600)

        for pool_data in raw_pools:
            try:
                # Parse pool data
                pair_created_at = pool_data.get('pairCreatedAt', 0) / 1000  # Convert ms to seconds
                liquidity_usd = float(pool_data.get('liquidity', {}).get('usd', 0))

                # Filter by age
                if pair_created_at < cutoff_time:
                    continue

                # Filter by liquidity
                if liquidity_usd < min_liquidity:
                    continue

                # Parse token data
                base_token = pool_data.get('baseToken', {})
                quote_token = pool_data.get('quoteToken', {})

                token0 = Token(
                    address=base_token.get('address', ''),
                    symbol=base_token.get('symbol', 'UNKNOWN'),
                    name=base_token.get('name', 'Unknown Token'),
                    chain=chain,
                    decimals=18
                )

                token1 = Token(
                    address=quote_token.get('address', ''),
                    symbol=quote_token.get('symbol', 'UNKNOWN'),
                    name=quote_token.get('name', 'Unknown Token'),
                    chain=chain,
                    decimals=18
                )

                # Create LiquidityPool object
                pool = LiquidityPool(
                    address=pool_data.get('pairAddress', ''),
                    token0=token0,
                    token1=token1,
                    liquidity_usd=liquidity_usd,
                    volume_24h=float(pool_data.get('volume', {}).get('h24', 0)),
                    created_timestamp=int(pair_created_at),
                    dex_name=pool_data.get('dexId', 'Unknown'),
                    chain=chain
                )

                filtered_pools.append(pool)

                # Print pool info
                age_hours = (time.time() - pair_created_at) / 3600
                print(f"  ✓ {token0.symbol}/{token1.symbol} - ${liquidity_usd:,.0f} - {age_hours:.1f}h old")

            except (KeyError, ValueError, TypeError) as e:
                print(f"  ⚠️  Error parsing pool: {e}")
                continue

        print(f"\n  Total filtered pools: {len(filtered_pools)}")
        return filtered_pools

    def get_token_info(self, token_address: str, chain: str = "ethereum") -> Optional[Dict]:
        """
        Get detailed token information

        Args:
            token_address: Token contract address
            chain: Blockchain network

        Returns:
            Token info dictionary or None
        """
        self._rate_limit()

        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if 'pairs' in data and len(data['pairs']) > 0:
                    return data['pairs'][0]  # Return first pair data

            return None

        except requests.exceptions.RequestException as e:
            print(f"  ✗ Failed to fetch token info: {e}")
            return None

    def create_token_metrics(self, pool_data: Dict, token_address: str) -> TokenMetrics:
        """
        Create TokenMetrics from pool data

        Args:
            pool_data: Raw pool data from API
            token_address: Token contract address

        Returns:
            TokenMetrics object
        """

        # Extract price changes
        price_change = pool_data.get('priceChange', {})
        price_change_1h = float(price_change.get('h1', 0))
        price_change_24h = float(price_change.get('h24', 0))

        # Extract liquidity and volume
        liquidity_usd = float(pool_data.get('liquidity', {}).get('usd', 0))
        volume_24h = float(pool_data.get('volume', {}).get('h24', 0))

        # Transaction data
        txns = pool_data.get('txns', {})
        h24_txns = txns.get('h24', {})
        buys = h24_txns.get('buys', 0)
        sells = h24_txns.get('sells', 0)

        # Estimate holder count (not always available)
        holder_count = 100  # Default estimate

        # Calculate holder concentration (not available from DexScreener)
        top_10_concentration = 35.0  # Default estimate

        # Creation time
        pair_created_at = pool_data.get('pairCreatedAt', int(time.time() * 1000)) / 1000

        # Tax info (not always available)
        buy_tax = 0.0
        sell_tax = 0.0

        # Security flags
        contract_verified = False  # Would need Etherscan API
        liquidity_locked = False   # Would need separate API

        # Check CEX listing status
        listed_on_cex = False
        cex_exchanges = []

        if self.check_cex and self.dex_data_fetcher:
            print(f"    Checking CEX listings for {token_address[:8]}...")
            cex_data = self.dex_data_fetcher.check_cex_listing(
                token_address=token_address,
                chain=pool_data.get('chainId', 'ethereum')
            )
            listed_on_cex = cex_data.get('listed_on_cex', False)
            cex_exchanges = cex_data.get('major_exchanges', [])

            if listed_on_cex:
                print(f"    ⚠️  Token is on {len(cex_exchanges)} major CEX(s): {', '.join(cex_exchanges[:3])}")
            else:
                print(f"    🎯 Token is DEX-ONLY - higher opportunity!")

        metrics = TokenMetrics(
            token_address=token_address,
            liquidity_usd=liquidity_usd,
            volume_24h=volume_24h,
            holder_count=holder_count,
            top_10_concentration=top_10_concentration,
            honeypot_risk=0.0,  # Would need honeypot.is API
            contract_verified=contract_verified,
            buy_tax=buy_tax,
            sell_tax=sell_tax,
            liquidity_locked=liquidity_locked,
            creation_time=int(pair_created_at),
            price_change_1h=price_change_1h,
            price_change_24h=price_change_24h,
            listed_on_cex=listed_on_cex,
            cex_exchanges=cex_exchanges
        )

        return metrics

    def check_token_security(self, token_address: str, chain: str = "ethereum") -> Dict:
        """
        Check token security using multiple sources

        NOTE: This requires API keys. For production, implement calls to:
        - Honeypot.is
        - GoPlus Security API
        - Token Sniffer

        Args:
            token_address: Token contract address
            chain: Blockchain network

        Returns:
            Security check results
        """

        # Placeholder - would call real security APIs
        return {
            'is_honeypot': False,
            'buy_tax': 0,
            'sell_tax': 0,
            'is_blacklisted': False,
            'can_sell': True,
            'verified': False,
            'proxy': False
        }


def test_real_fetcher():
    """Test the real DEX fetcher"""

    print("\n" + "="*80)
    print("TESTING REAL DEX DATA FETCHER")
    print("="*80)

    fetcher = RealDEXFetcher()

    # Test 1: Get latest pools on Ethereum
    print("\n[TEST 1] Fetching latest Ethereum pools...")
    eth_pools = fetcher.get_new_pools_by_age(
        chain="ethereum",
        max_age_hours=48,
        min_liquidity=20000
    )

    if eth_pools:
        print(f"\n✓ Successfully fetched {len(eth_pools)} Ethereum pools")

        # Show first pool details
        if len(eth_pools) > 0:
            pool = eth_pools[0]
            print(f"\nSample Pool Details:")
            print(f"  Pair: {pool.token0.symbol}/{pool.token1.symbol}")
            print(f"  Address: {pool.address}")
            print(f"  Liquidity: ${pool.liquidity_usd:,.2f}")
            print(f"  24h Volume: ${pool.volume_24h:,.2f}")
            print(f"  DEX: {pool.dex_name}")
            age_hours = (time.time() - pool.created_timestamp) / 3600
            print(f"  Age: {age_hours:.1f} hours")
    else:
        print("\n⚠️  No pools found matching criteria")

    # Test 2: Get BSC pools
    print("\n[TEST 2] Fetching latest BSC pools...")
    bsc_pools = fetcher.get_new_pools_by_age(
        chain="bsc",
        max_age_hours=24,
        min_liquidity=10000
    )

    if bsc_pools:
        print(f"\n✓ Successfully fetched {len(bsc_pools)} BSC pools")
    else:
        print("\n⚠️  No BSC pools found")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    return eth_pools + bsc_pools


if __name__ == "__main__":
    test_real_fetcher()
