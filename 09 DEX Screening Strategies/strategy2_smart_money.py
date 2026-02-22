"""
Strategy 2: Smart Money Tracker
================================

Tracks successful whale wallets and copies their early token entries.
Monitors proven traders who consistently find gems before they pump.

Key Features:
- Curated list of successful whale wallets
- Real-time transaction monitoring
- Copy trading with configurable delay
- Historical performance tracking
- Multi-wallet scoring and ranking

Ideal For:
- Following proven winners into positions
- Reducing research burden by leveraging expert analysis
- Getting early entries based on smart money flows
- Piggybacking on wallets with strong track records
"""

import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from dex_utils import (
    DEXDataFetcher, TokenMetrics, RiskAnalyzer,
    format_token_report
)


@dataclass
class WhaleWallet:
    """Represents a tracked whale wallet"""
    address: str
    chain: str
    label: str  # e.g., "0xSmart", "GemHunter", etc.
    historical_win_rate: float  # 0-1
    total_trades: int
    avg_roi: float  # Average ROI per trade
    reputation_score: float  # 0-100


@dataclass
class WhaleTrade:
    """Represents a trade made by a whale"""
    wallet: WhaleWallet
    token_address: str
    token_symbol: str
    chain: str
    trade_type: str  # 'buy' or 'sell'
    amount_usd: float
    timestamp: int
    tx_hash: str


@dataclass
class CopyTradeOpportunity:
    """A potential copy trade opportunity"""
    whale_trade: WhaleTrade
    token_metrics: TokenMetrics
    whale_score: float  # Weighted score based on whale reputation
    safety_score: float
    opportunity_score: float
    composite_score: float
    copy_recommended: bool
    reason: str


class SmartMoneyTracker:
    """
    Strategy 2: Smart Money Tracker

    Monitors and copies successful whale wallets
    """

    def __init__(self,
                 chains: List[str] = ['ethereum', 'bsc', 'solana'],
                 min_whale_reputation: float = 70,
                 min_trade_size_usd: float = 5000,
                 max_trade_age_minutes: int = 60,
                 min_safety_score: float = 55,
                 scan_interval_seconds: int = 180,
                 copy_delay_minutes: int = 5):
        """
        Initialize Smart Money Tracker

        Args:
            chains: Chains to monitor
            min_whale_reputation: Minimum whale reputation score (0-100)
            min_trade_size_usd: Minimum trade size to consider
            max_trade_age_minutes: Only copy trades this recent
            min_safety_score: Minimum token safety score
            scan_interval_seconds: Time between scans
            copy_delay_minutes: Delay before copying (to allow for better entry)
        """
        self.chains = chains
        self.min_whale_reputation = min_whale_reputation
        self.min_trade_size_usd = min_trade_size_usd
        self.max_trade_age_minutes = max_trade_age_minutes
        self.min_safety_score = min_safety_score
        self.scan_interval = scan_interval_seconds
        self.copy_delay = copy_delay_minutes * 60

        self.fetcher = DEXDataFetcher()
        self.whale_wallets: List[WhaleWallet] = []
        self.opportunities: List[CopyTradeOpportunity] = []
        self.tracked_trades = set()  # Track trades we've already seen

        # Load whale wallets
        self._load_whale_wallets()

    def _load_whale_wallets(self):
        """Load curated list of whale wallets to track"""
        print(f"[Strategy 2] Loading whale wallets...")

        # In production, load from database or API
        # For demo, create mock whales

        mock_whales = [
            WhaleWallet(
                address="0x1234567890abcdef1234567890abcdef12345678",
                chain="ethereum",
                label="GemSniper",
                historical_win_rate=0.73,
                total_trades=245,
                avg_roi=3.2,
                reputation_score=88
            ),
            WhaleWallet(
                address="0xabcdef1234567890abcdef1234567890abcdef12",
                chain="bsc",
                label="MoonHunter",
                historical_win_rate=0.65,
                total_trades=189,
                avg_roi=2.8,
                reputation_score=79
            ),
            WhaleWallet(
                address="0x9876543210fedcba9876543210fedcba98765432",
                chain="ethereum",
                label="0xSmartMoney",
                historical_win_rate=0.81,
                total_trades=312,
                avg_roi=4.1,
                reputation_score=94
            ),
        ]

        # Filter by reputation
        self.whale_wallets = [
            w for w in mock_whales
            if w.reputation_score >= self.min_whale_reputation
        ]

        print(f"  Loaded {len(self.whale_wallets)} high-reputation whales")
        for whale in self.whale_wallets:
            print(f"    {whale.label} ({whale.chain}): {whale.reputation_score:.0f} rep, {whale.historical_win_rate*100:.0f}% win rate")

    def scan_whale_transactions(self, whale: WhaleWallet) -> List[WhaleTrade]:
        """Scan recent transactions for a whale wallet"""

        transactions = self.fetcher.get_wallet_transactions(
            wallet_address=whale.address,
            chain=whale.chain,
            limit=50
        )

        trades = []

        # In production, parse transactions and identify token buys
        # For demo, return mock data
        print(f"  Scanning {whale.label}... (found 0 new trades)")

        return trades

    def analyze_whale_trade(self, trade: WhaleTrade) -> Optional[CopyTradeOpportunity]:
        """
        Analyze a whale trade and determine if we should copy it

        Returns:
            CopyTradeOpportunity if worth copying, None otherwise
        """

        # Get token metrics
        metrics = self.fetcher.get_token_metrics(trade.token_address, trade.chain)

        # Calculate scores
        safety_score = RiskAnalyzer.calculate_safety_score(metrics)
        opportunity_score = RiskAnalyzer.calculate_opportunity_score(metrics)

        # Whale score (based on reputation and trade size)
        whale_score = trade.wallet.reputation_score
        if trade.amount_usd > 50000:
            whale_score += 5  # Bonus for high conviction trades

        # Composite score: 40% whale, 35% safety, 25% opportunity
        composite_score = (
            whale_score * 0.40 +
            safety_score * 0.35 +
            opportunity_score * 0.25
        )

        print(f"    {trade.token_symbol}: Whale={whale_score:.1f}, Safety={safety_score:.1f}, Opp={opportunity_score:.1f}, Composite={composite_score:.1f}")

        # Decision logic
        copy_recommended = True
        reason = "High-quality whale trade"

        if safety_score < self.min_safety_score:
            copy_recommended = False
            reason = f"Safety score too low ({safety_score:.1f})"
            print(f"      ✗ REJECT: {reason}")
            return None

        # Check honeypot
        honeypot_check = self.fetcher.check_honeypot(trade.token_address, trade.chain)
        if honeypot_check['is_honeypot']:
            copy_recommended = False
            reason = "Honeypot detected"
            print(f"      ✗ REJECT: {reason}")
            return None

        # Check trade age
        trade_age = time.time() - trade.timestamp
        if trade_age > self.max_trade_age_minutes * 60:
            copy_recommended = False
            reason = f"Trade too old ({trade_age/60:.0f}m)"
            print(f"      ✗ REJECT: {reason}")
            return None

        print(f"      ✓ ACCEPT: {reason}")

        return CopyTradeOpportunity(
            whale_trade=trade,
            token_metrics=metrics,
            whale_score=whale_score,
            safety_score=safety_score,
            opportunity_score=opportunity_score,
            composite_score=composite_score,
            copy_recommended=copy_recommended,
            reason=reason
        )

    def run_scan_cycle(self):
        """Run one complete scan cycle"""
        print(f"\n{'='*70}")
        print(f"[Strategy 2: Smart Money] Starting scan cycle at {datetime.now()}")
        print(f"{'='*70}")

        cycle_opportunities = []

        for whale in self.whale_wallets:
            trades = self.scan_whale_transactions(whale)

            for trade in trades:
                # Skip if already tracked
                trade_id = f"{trade.tx_hash}"
                if trade_id in self.tracked_trades:
                    continue

                self.tracked_trades.add(trade_id)

                # Only analyze buys
                if trade.trade_type != 'buy':
                    continue

                # Check minimum trade size
                if trade.amount_usd < self.min_trade_size_usd:
                    continue

                # Analyze the trade
                opportunity = self.analyze_whale_trade(trade)

                if opportunity and opportunity.copy_recommended:
                    cycle_opportunities.append(opportunity)
                    self.opportunities.append(opportunity)

        # Sort by composite score
        cycle_opportunities.sort(key=lambda x: x.composite_score, reverse=True)

        # Print opportunities
        if cycle_opportunities:
            print(f"\n🐋 Found {len(cycle_opportunities)} copy trade opportunities:")
            for i, opp in enumerate(cycle_opportunities[:5], 1):
                print(f"\n  #{i} {opp.whale_trade.token_symbol} on {opp.whale_trade.chain.upper()}")
                print(f"     Followed by: {opp.whale_trade.wallet.label}")
                print(f"     Composite Score: {opp.composite_score:.1f}/100")
                print(f"     Trade Size: ${opp.whale_trade.amount_usd:,.0f}")
                print(f"     Contract: {opp.whale_trade.token_address}")
        else:
            print("\n  No copy opportunities found this cycle")

        return cycle_opportunities

    def run(self, duration_hours: Optional[float] = None, max_cycles: Optional[int] = None):
        """Run the strategy continuously"""

        print(f"\n{'#'*70}")
        print(f"# STRATEGY 2: SMART MONEY TRACKER")
        print(f"{'#'*70}")
        print(f"\nConfiguration:")
        print(f"  Chains: {', '.join(self.chains)}")
        print(f"  Tracked Whales: {len(self.whale_wallets)}")
        print(f"  Min Whale Reputation: {self.min_whale_reputation}")
        print(f"  Min Trade Size: ${self.min_trade_size_usd:,.0f}")
        print(f"  Max Trade Age: {self.max_trade_age_minutes}m")
        print(f"  Min Safety Score: {self.min_safety_score}")
        print(f"  Scan Interval: {self.scan_interval}s")
        print(f"  Copy Delay: {self.copy_delay/60:.0f}m")

        start_time = time.time()
        cycle_count = 0

        try:
            while True:
                self.run_scan_cycle()
                cycle_count += 1

                if max_cycles and cycle_count >= max_cycles:
                    print(f"\n[Strategy 2] Reached max cycles ({max_cycles})")
                    break

                if duration_hours:
                    elapsed_hours = (time.time() - start_time) / 3600
                    if elapsed_hours >= duration_hours:
                        print(f"\n[Strategy 2] Reached duration limit ({duration_hours}h)")
                        break

                print(f"\n[Strategy 2] Waiting {self.scan_interval}s until next scan...")
                time.sleep(self.scan_interval)

        except KeyboardInterrupt:
            print("\n[Strategy 2] Stopped by user")

        self.print_summary()

    def print_summary(self):
        """Print strategy performance summary"""
        print(f"\n{'='*70}")
        print(f"STRATEGY 2: SMART MONEY TRACKER - SUMMARY")
        print(f"{'='*70}")

        if not self.opportunities:
            print("No copy opportunities found")
            return

        print(f"\nTotal Copy Opportunities: {len(self.opportunities)}")
        print(f"Total Trades Scanned: {len(self.tracked_trades)}")

        # Whale performance
        whale_stats = defaultdict(int)
        for opp in self.opportunities:
            whale_stats[opp.whale_trade.wallet.label] += 1

        print(f"\n🐋 WHALE PERFORMANCE:")
        for whale_label, count in sorted(whale_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"   {whale_label}: {count} opportunities")

        # Sort by composite score
        self.opportunities.sort(key=lambda x: x.composite_score, reverse=True)

        print(f"\n🏆 TOP 10 COPY TRADE OPPORTUNITIES:")
        print(f"{'='*70}")

        for i, opp in enumerate(self.opportunities[:10], 1):
            print(f"\n#{i} {opp.whale_trade.token_symbol} ({opp.whale_trade.chain.upper()})")
            print(f"   Whale: {opp.whale_trade.wallet.label} (Rep: {opp.whale_trade.wallet.reputation_score:.0f})")
            print(f"   Composite Score: {opp.composite_score:.1f}/100")
            print(f"   Whale Score: {opp.whale_score:.1f} | Safety: {opp.safety_score:.1f} | Opp: {opp.opportunity_score:.1f}")
            print(f"   Trade Size: ${opp.whale_trade.amount_usd:,.0f}")
            print(f"   Liquidity: ${opp.token_metrics.liquidity_usd:,.0f}")
            print(f"   Contract: {opp.whale_trade.token_address}")
            print(f"   Time: {datetime.fromtimestamp(opp.whale_trade.timestamp).strftime('%Y-%m-%d %H:%M:%S')}")

    def get_ranked_opportunities(self) -> List[CopyTradeOpportunity]:
        """Get all opportunities ranked by composite score"""
        return sorted(self.opportunities, key=lambda x: x.composite_score, reverse=True)


def main():
    """Example usage of Strategy 2"""

    strategy = SmartMoneyTracker(
        chains=['ethereum', 'bsc'],
        min_whale_reputation=75,
        min_trade_size_usd=10000,
        max_trade_age_minutes=30,
        min_safety_score=60,
        scan_interval_seconds=180,  # 3 minutes
        copy_delay_minutes=5
    )

    # Run for 2 cycles (demo mode)
    strategy.run(max_cycles=2)


if __name__ == "__main__":
    main()
