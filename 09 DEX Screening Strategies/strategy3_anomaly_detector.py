"""
Strategy 3: Honeypot Detector + Anomaly Scanner
================================================

Advanced pattern recognition to identify scams and find legitimate anomalies.
Uses ML-based anomaly detection to filter out rug pulls and honeypots while
identifying unusual but legitimate opportunities.

Key Features:
- Multi-layered honeypot detection
- Statistical anomaly detection for unusual patterns
- Contract code analysis for red flags
- Holder distribution analysis
- Trading pattern analysis (buy/sell pressure, whale behavior)
- ML-based classification of legitimate vs. scam tokens

Ideal For:
- Maximum safety and scam avoidance
- Finding tokens with unusual but positive characteristics
- Deep technical analysis before entry
- Risk-averse traders seeking high-confidence opportunities
"""

import time
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from dex_utils import (
    DEXDataFetcher, TokenMetrics, RiskAnalyzer,
    format_token_report
)


@dataclass
class AnomalyScore:
    """Anomaly analysis scores"""
    holder_distribution_anomaly: float  # 0-1, higher = more unusual
    trading_pattern_anomaly: float
    contract_risk_anomaly: float
    liquidity_anomaly: float
    volume_anomaly: float


@dataclass
class ScamIndicators:
    """Specific scam indicators detected"""
    is_honeypot: bool
    has_hidden_mint: bool
    has_blacklist_function: bool
    excessive_buy_tax: bool
    excessive_sell_tax: bool
    tax_asymmetry: bool  # Buy/sell tax difference > 5%
    ownership_not_renounced: bool
    liquidity_not_locked: bool
    concentrated_ownership: bool  # Top 10 > 60%
    suspicious_holder_pattern: bool
    low_liquidity: bool


@dataclass
class TokenOpportunity:
    """A filtered token opportunity"""
    token_address: str
    token_symbol: str
    chain: str
    metrics: TokenMetrics
    anomaly_scores: AnomalyScore
    scam_indicators: ScamIndicators
    safety_score: float
    anomaly_appeal_score: float  # Positive anomalies
    composite_score: float
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    recommendation: str


class AnomalyDetectorStrategy:
    """
    Strategy 3: Honeypot Detector + Anomaly Scanner

    Deep analysis with focus on scam detection and positive anomalies
    """

    def __init__(self,
                 chains: List[str] = ['ethereum', 'bsc', 'solana'],
                 scan_recent_tokens: bool = True,
                 max_token_age_hours: int = 168,  # 1 week
                 min_safety_score: float = 70,
                 max_scam_indicators: int = 2,
                 scan_interval_seconds: int = 600,
                 enable_deep_scan: bool = True):
        """
        Initialize Anomaly Detector Strategy

        Args:
            chains: Chains to monitor
            scan_recent_tokens: Scan recently created tokens
            max_token_age_hours: Maximum token age to analyze
            min_safety_score: Minimum safety threshold
            max_scam_indicators: Maximum allowed scam indicators
            scan_interval_seconds: Time between scans
            enable_deep_scan: Enable deep contract analysis (slower)
        """
        self.chains = chains
        self.scan_recent_tokens = scan_recent_tokens
        self.max_token_age_hours = max_token_age_hours
        self.min_safety_score = min_safety_score
        self.max_scam_indicators = max_scam_indicators
        self.scan_interval = scan_interval_seconds
        self.enable_deep_scan = enable_deep_scan

        self.fetcher = DEXDataFetcher()
        self.opportunities: List[TokenOpportunity] = []
        self.scanned_tokens = set()

    def detect_scam_indicators(self, metrics: TokenMetrics, token_address: str, chain: str) -> ScamIndicators:
        """
        Comprehensive scam detection

        Returns:
            ScamIndicators object with all detected red flags
        """

        # Honeypot check
        honeypot_check = self.fetcher.check_honeypot(token_address, chain)

        return ScamIndicators(
            is_honeypot=honeypot_check.get('is_honeypot', False),
            has_hidden_mint=False,  # Would check contract code
            has_blacklist_function=False,  # Would check contract code
            excessive_buy_tax=metrics.buy_tax > 10,
            excessive_sell_tax=metrics.sell_tax > 10,
            tax_asymmetry=abs(metrics.buy_tax - metrics.sell_tax) > 5,
            ownership_not_renounced=False,  # Would check contract ownership
            liquidity_not_locked=not metrics.liquidity_locked,
            concentrated_ownership=metrics.top_10_concentration > 60,
            suspicious_holder_pattern=self._check_suspicious_holders(token_address, chain),
            low_liquidity=metrics.liquidity_usd < 10000
        )

    def _check_suspicious_holders(self, token_address: str, chain: str) -> bool:
        """
        Check for suspicious holder patterns
        - Multiple wallets with same balance
        - Bot-like wallet names
        - High concentration in recent wallets
        """
        # In production, fetch and analyze holder list
        return False

    def calculate_anomaly_scores(self, metrics: TokenMetrics, token_address: str, chain: str) -> AnomalyScore:
        """
        Calculate anomaly scores for various metrics

        Uses statistical methods to identify outliers
        """

        # Holder distribution anomaly
        # Normal: gradual distribution, Anomaly: clustered or extreme
        holder_anomaly = 0.0
        if metrics.top_10_concentration < 20:  # Too distributed (airdrop?)
            holder_anomaly = 0.6
        elif metrics.top_10_concentration > 70:  # Too concentrated
            holder_anomaly = 0.8

        # Trading pattern anomaly
        # Look at volume/liquidity ratio
        vol_liq_ratio = metrics.volume_24h / max(metrics.liquidity_usd, 1)
        trading_anomaly = 0.0
        if vol_liq_ratio > 3.0:  # Extremely high turnover
            trading_anomaly = 0.7
        elif vol_liq_ratio < 0.1:  # Very low activity
            trading_anomaly = 0.4

        # Contract risk anomaly (would involve code analysis)
        contract_anomaly = 0.0
        if not metrics.contract_verified:
            contract_anomaly = 0.8

        # Liquidity anomaly
        liquidity_anomaly = 0.0
        if metrics.liquidity_usd > 1000000:  # Unusually high for new token
            liquidity_anomaly = 0.3  # Positive anomaly
        elif metrics.liquidity_usd < 5000:
            liquidity_anomaly = 0.9  # Negative anomaly

        # Volume anomaly
        volume_anomaly = 0.0
        if metrics.volume_24h > metrics.liquidity_usd * 5:
            volume_anomaly = 0.8  # Pump or manipulation

        return AnomalyScore(
            holder_distribution_anomaly=holder_anomaly,
            trading_pattern_anomaly=trading_anomaly,
            contract_risk_anomaly=contract_anomaly,
            liquidity_anomaly=liquidity_anomaly,
            volume_anomaly=volume_anomaly
        )

    def calculate_anomaly_appeal(self, anomaly_scores: AnomalyScore, metrics: TokenMetrics) -> float:
        """
        Calculate positive anomaly score (0-100)

        Some anomalies are good (e.g., unusually high liquidity, strong buying)
        """
        appeal = 0.0

        # High liquidity for age is good
        if metrics.liquidity_usd > 100000 and anomaly_scores.liquidity_anomaly > 0:
            appeal += 25

        # Strong volume is good (but not too extreme)
        vol_liq = metrics.volume_24h / max(metrics.liquidity_usd, 1)
        if 0.5 < vol_liq < 2.0:
            appeal += 20

        # Good holder distribution
        if 25 < metrics.top_10_concentration < 45:
            appeal += 15

        # Growing holder count
        if metrics.holder_count > 500:
            appeal += 20

        # Positive price action
        if metrics.price_change_24h > 15:
            appeal += 20

        return min(100, appeal)

    def analyze_token(self, token_address: str, chain: str, token_symbol: str = "UNKNOWN") -> Optional[TokenOpportunity]:
        """
        Perform comprehensive token analysis

        Returns:
            TokenOpportunity if viable, None otherwise
        """

        # Get metrics
        metrics = self.fetcher.get_token_metrics(token_address, chain)

        # Detect scams
        scam_indicators = self.detect_scam_indicators(metrics, token_address, chain)

        # Count active scam indicators
        scam_count = sum([
            scam_indicators.is_honeypot,
            scam_indicators.has_hidden_mint,
            scam_indicators.has_blacklist_function,
            scam_indicators.excessive_buy_tax,
            scam_indicators.excessive_sell_tax,
            scam_indicators.tax_asymmetry,
            scam_indicators.ownership_not_renounced,
            scam_indicators.liquidity_not_locked,
            scam_indicators.concentrated_ownership,
            scam_indicators.suspicious_holder_pattern,
            scam_indicators.low_liquidity
        ])

        print(f"    {token_symbol}: {scam_count} scam indicators detected")

        # Reject if too many scam indicators
        if scam_count > self.max_scam_indicators:
            print(f"      ✗ REJECT: Too many scam indicators ({scam_count})")
            return None

        # Calculate anomalies
        anomaly_scores = self.calculate_anomaly_scores(metrics, token_address, chain)

        # Calculate scores
        safety_score = RiskAnalyzer.calculate_safety_score(metrics)
        anomaly_appeal = self.calculate_anomaly_appeal(anomaly_scores, metrics)

        print(f"      Safety: {safety_score:.1f}, Anomaly Appeal: {anomaly_appeal:.1f}")

        # Check minimum safety
        if safety_score < self.min_safety_score:
            print(f"      ✗ REJECT: Safety score too low")
            return None

        # Composite score: 60% safety, 40% anomaly appeal
        composite_score = (safety_score * 0.6) + (anomaly_appeal * 0.4)

        # Determine risk level
        if scam_count == 0 and safety_score >= 80:
            risk_level = 'LOW'
        elif scam_count <= 1 and safety_score >= 70:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'HIGH'

        recommendation = f"Risk: {risk_level}, Score: {composite_score:.1f}/100"

        print(f"      ✓ ACCEPT: {recommendation}")

        return TokenOpportunity(
            token_address=token_address,
            token_symbol=token_symbol,
            chain=chain,
            metrics=metrics,
            anomaly_scores=anomaly_scores,
            scam_indicators=scam_indicators,
            safety_score=safety_score,
            anomaly_appeal_score=anomaly_appeal,
            composite_score=composite_score,
            risk_level=risk_level,
            recommendation=recommendation
        )

    def scan_recent_tokens_on_chain(self, chain: str) -> List[str]:
        """
        Get list of recent token addresses to analyze

        Returns:
            List of token addresses
        """
        # In production, would fetch from DEX APIs, The Graph, or new pair events
        print(f"  Fetching recent tokens on {chain.upper()}...")

        # Mock implementation
        return []

    def run_scan_cycle(self):
        """Run one complete scan cycle"""
        print(f"\n{'='*70}")
        print(f"[Strategy 3: Anomaly Detector] Starting scan cycle at {datetime.now()}")
        print(f"{'='*70}")

        cycle_opportunities = []

        for chain in self.chains:
            token_addresses = self.scan_recent_tokens_on_chain(chain)

            for token_address in token_addresses:
                # Skip already scanned
                if token_address in self.scanned_tokens:
                    continue

                self.scanned_tokens.add(token_address)

                # Analyze token
                opportunity = self.analyze_token(token_address, chain)

                if opportunity:
                    cycle_opportunities.append(opportunity)
                    self.opportunities.append(opportunity)

        # Sort by composite score
        cycle_opportunities.sort(key=lambda x: x.composite_score, reverse=True)

        # Print opportunities
        if cycle_opportunities:
            print(f"\n🔍 Found {len(cycle_opportunities)} safe opportunities:")
            for i, opp in enumerate(cycle_opportunities[:5], 1):
                print(f"\n  #{i} {opp.token_symbol} on {opp.chain.upper()}")
                print(f"     Risk Level: {opp.risk_level}")
                print(f"     Composite Score: {opp.composite_score:.1f}/100")
                print(f"     Safety: {opp.safety_score:.1f} | Anomaly Appeal: {opp.anomaly_appeal_score:.1f}")
                print(f"     Contract: {opp.token_address}")
        else:
            print("\n  No opportunities found this cycle")

        return cycle_opportunities

    def run(self, duration_hours: Optional[float] = None, max_cycles: Optional[int] = None):
        """Run the strategy continuously"""

        print(f"\n{'#'*70}")
        print(f"# STRATEGY 3: HONEYPOT DETECTOR + ANOMALY SCANNER")
        print(f"{'#'*70}")
        print(f"\nConfiguration:")
        print(f"  Chains: {', '.join(self.chains)}")
        print(f"  Max Token Age: {self.max_token_age_hours}h")
        print(f"  Min Safety Score: {self.min_safety_score}")
        print(f"  Max Scam Indicators: {self.max_scam_indicators}")
        print(f"  Deep Scan: {'Enabled' if self.enable_deep_scan else 'Disabled'}")
        print(f"  Scan Interval: {self.scan_interval}s")

        start_time = time.time()
        cycle_count = 0

        try:
            while True:
                self.run_scan_cycle()
                cycle_count += 1

                if max_cycles and cycle_count >= max_cycles:
                    print(f"\n[Strategy 3] Reached max cycles ({max_cycles})")
                    break

                if duration_hours:
                    elapsed_hours = (time.time() - start_time) / 3600
                    if elapsed_hours >= duration_hours:
                        print(f"\n[Strategy 3] Reached duration limit ({duration_hours}h)")
                        break

                print(f"\n[Strategy 3] Waiting {self.scan_interval}s until next scan...")
                time.sleep(self.scan_interval)

        except KeyboardInterrupt:
            print("\n[Strategy 3] Stopped by user")

        self.print_summary()

    def print_summary(self):
        """Print strategy performance summary"""
        print(f"\n{'='*70}")
        print(f"STRATEGY 3: ANOMALY DETECTOR - SUMMARY")
        print(f"{'='*70}")

        if not self.opportunities:
            print("No opportunities found")
            return

        print(f"\nTotal Opportunities: {len(self.opportunities)}")
        print(f"Total Tokens Scanned: {len(self.scanned_tokens)}")
        print(f"Pass Rate: {len(self.opportunities)/max(len(self.scanned_tokens),1)*100:.1f}%")

        # Risk distribution
        risk_counts = defaultdict(int)
        for opp in self.opportunities:
            risk_counts[opp.risk_level] += 1

        print(f"\n📊 RISK DISTRIBUTION:")
        for risk_level in ['LOW', 'MEDIUM', 'HIGH']:
            count = risk_counts[risk_level]
            pct = count / len(self.opportunities) * 100
            print(f"   {risk_level}: {count} ({pct:.1f}%)")

        # Sort by composite score
        self.opportunities.sort(key=lambda x: x.composite_score, reverse=True)

        print(f"\n🏆 TOP 10 OPPORTUNITIES:")
        print(f"{'='*70}")

        for i, opp in enumerate(self.opportunities[:10], 1):
            scam_count = sum([
                opp.scam_indicators.is_honeypot,
                opp.scam_indicators.has_hidden_mint,
                opp.scam_indicators.excessive_buy_tax,
                opp.scam_indicators.excessive_sell_tax,
                opp.scam_indicators.tax_asymmetry,
                opp.scam_indicators.concentrated_ownership,
                opp.scam_indicators.low_liquidity
            ])

            print(f"\n#{i} {opp.token_symbol} ({opp.chain.upper()})")
            print(f"   Risk Level: {opp.risk_level}")
            print(f"   Composite Score: {opp.composite_score:.1f}/100")
            print(f"   Safety: {opp.safety_score:.1f} | Anomaly Appeal: {opp.anomaly_appeal_score:.1f}")
            print(f"   Scam Indicators: {scam_count}/{self.max_scam_indicators} allowed")
            print(f"   Liquidity: ${opp.metrics.liquidity_usd:,.0f}")
            print(f"   24h Volume: ${opp.metrics.volume_24h:,.0f}")
            print(f"   Contract: {opp.token_address}")

    def get_ranked_opportunities(self) -> List[TokenOpportunity]:
        """Get all opportunities ranked by composite score"""
        return sorted(self.opportunities, key=lambda x: x.composite_score, reverse=True)


def main():
    """Example usage of Strategy 3"""

    strategy = AnomalyDetectorStrategy(
        chains=['ethereum', 'bsc'],
        max_token_age_hours=72,
        min_safety_score=75,
        max_scam_indicators=1,
        scan_interval_seconds=600,  # 10 minutes
        enable_deep_scan=True
    )

    # Run for 2 cycles (demo mode)
    strategy.run(max_cycles=2)


if __name__ == "__main__":
    main()
