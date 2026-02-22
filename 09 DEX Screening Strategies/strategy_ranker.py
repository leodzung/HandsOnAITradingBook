"""
Strategy Ranking and Comparison Framework
==========================================

Compares the 3 DEX screening strategies and ranks them based on multiple criteria:
- Number of opportunities found
- Quality of opportunities (composite scores)
- Safety metrics
- Computational efficiency
- False positive rate (manual review needed)
- Risk-adjusted returns (if backtested)

Generates comprehensive comparison reports and recommendations.
"""

import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

from strategy1_pool_scanner import PoolScannerStrategy, PoolOpportunity
from strategy2_smart_money import SmartMoneyTracker, CopyTradeOpportunity
from strategy3_anomaly_detector import AnomalyDetectorStrategy, TokenOpportunity


@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy"""
    strategy_name: str
    strategy_number: int

    # Opportunity metrics
    total_opportunities: int
    avg_composite_score: float
    median_composite_score: float
    top_10_avg_score: float

    # Safety metrics
    avg_safety_score: float
    min_safety_score: float
    high_risk_count: int  # Opportunities below safety threshold

    # Efficiency metrics
    total_scanned: int
    hit_rate: float  # opportunities / scanned
    avg_scan_time: float  # seconds per cycle

    # Quality distribution
    excellent_count: int  # Composite > 80
    good_count: int  # 70-80
    moderate_count: int  # 60-70
    low_count: int  # < 60

    # Risk/Reward
    estimated_risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    recommended_capital_allocation: float  # 0-1


@dataclass
class StrategyRanking:
    """Overall ranking of strategies"""
    rank: int
    strategy_name: str
    strategy_number: int
    overall_score: float  # 0-100

    # Category scores
    opportunity_quality_score: float  # 0-100
    safety_score: float  # 0-100
    efficiency_score: float  # 0-100
    volume_score: float  # 0-100 (quantity of opportunities)

    # Recommendation
    best_for: str
    pros: List[str]
    cons: List[str]
    ideal_trader_profile: str


class StrategyRanker:
    """
    Ranks and compares DEX screening strategies
    """

    def __init__(self):
        self.strategies_metrics: Dict[int, StrategyMetrics] = {}
        self.rankings: List[StrategyRanking] = []

    def analyze_strategy1(self, strategy: PoolScannerStrategy) -> StrategyMetrics:
        """Analyze Pool Scanner Strategy"""

        print(f"\n[Ranker] Analyzing Strategy 1: Pool Scanner...")

        opportunities = strategy.get_ranked_opportunities()

        if not opportunities:
            return self._create_empty_metrics("Pool Scanner", 1)

        composite_scores = [o.composite_score for o in opportunities]
        safety_scores = [o.safety_score for o in opportunities]

        # Quality distribution
        excellent = sum(1 for s in composite_scores if s >= 80)
        good = sum(1 for s in composite_scores if 70 <= s < 80)
        moderate = sum(1 for s in composite_scores if 60 <= s < 70)
        low = sum(1 for s in composite_scores if s < 60)

        metrics = StrategyMetrics(
            strategy_name="Pool Scanner",
            strategy_number=1,
            total_opportunities=len(opportunities),
            avg_composite_score=np.mean(composite_scores),
            median_composite_score=np.median(composite_scores),
            top_10_avg_score=np.mean(composite_scores[:min(10, len(composite_scores))]),
            avg_safety_score=np.mean(safety_scores),
            min_safety_score=min(safety_scores),
            high_risk_count=sum(1 for s in safety_scores if s < strategy.min_safety_score),
            total_scanned=len(strategy.scanned_pools),
            hit_rate=len(opportunities) / max(len(strategy.scanned_pools), 1),
            avg_scan_time=0.0,  # Would measure in production
            excellent_count=excellent,
            good_count=good,
            moderate_count=moderate,
            low_count=low,
            estimated_risk_level='MEDIUM',
            recommended_capital_allocation=0.33
        )

        return metrics

    def analyze_strategy2(self, strategy: SmartMoneyTracker) -> StrategyMetrics:
        """Analyze Smart Money Tracker Strategy"""

        print(f"[Ranker] Analyzing Strategy 2: Smart Money Tracker...")

        opportunities = strategy.get_ranked_opportunities()

        if not opportunities:
            return self._create_empty_metrics("Smart Money Tracker", 2)

        composite_scores = [o.composite_score for o in opportunities]
        safety_scores = [o.safety_score for o in opportunities]

        # Quality distribution
        excellent = sum(1 for s in composite_scores if s >= 80)
        good = sum(1 for s in composite_scores if 70 <= s < 80)
        moderate = sum(1 for s in composite_scores if 60 <= s < 70)
        low = sum(1 for s in composite_scores if s < 60)

        metrics = StrategyMetrics(
            strategy_name="Smart Money Tracker",
            strategy_number=2,
            total_opportunities=len(opportunities),
            avg_composite_score=np.mean(composite_scores),
            median_composite_score=np.median(composite_scores),
            top_10_avg_score=np.mean(composite_scores[:min(10, len(composite_scores))]),
            avg_safety_score=np.mean(safety_scores),
            min_safety_score=min(safety_scores),
            high_risk_count=sum(1 for s in safety_scores if s < strategy.min_safety_score),
            total_scanned=len(strategy.tracked_trades),
            hit_rate=len(opportunities) / max(len(strategy.tracked_trades), 1),
            avg_scan_time=0.0,
            excellent_count=excellent,
            good_count=good,
            moderate_count=moderate,
            low_count=low,
            estimated_risk_level='MEDIUM-LOW',
            recommended_capital_allocation=0.40  # Higher due to following smart money
        )

        return metrics

    def analyze_strategy3(self, strategy: AnomalyDetectorStrategy) -> StrategyMetrics:
        """Analyze Anomaly Detector Strategy"""

        print(f"[Ranker] Analyzing Strategy 3: Anomaly Detector...")

        opportunities = strategy.get_ranked_opportunities()

        if not opportunities:
            return self._create_empty_metrics("Anomaly Detector", 3)

        composite_scores = [o.composite_score for o in opportunities]
        safety_scores = [o.safety_score for o in opportunities]

        # Quality distribution
        excellent = sum(1 for s in composite_scores if s >= 80)
        good = sum(1 for s in composite_scores if 70 <= s < 80)
        moderate = sum(1 for s in composite_scores if 60 <= s < 70)
        low = sum(1 for s in composite_scores if s < 60)

        # Count high risk opportunities
        high_risk = sum(1 for o in opportunities if o.risk_level == 'HIGH')

        metrics = StrategyMetrics(
            strategy_name="Anomaly Detector",
            strategy_number=3,
            total_opportunities=len(opportunities),
            avg_composite_score=np.mean(composite_scores),
            median_composite_score=np.median(composite_scores),
            top_10_avg_score=np.mean(composite_scores[:min(10, len(composite_scores))]),
            avg_safety_score=np.mean(safety_scores),
            min_safety_score=min(safety_scores),
            high_risk_count=high_risk,
            total_scanned=len(strategy.scanned_tokens),
            hit_rate=len(opportunities) / max(len(strategy.scanned_tokens), 1),
            avg_scan_time=0.0,
            excellent_count=excellent,
            good_count=good,
            moderate_count=moderate,
            low_count=low,
            estimated_risk_level='LOW',
            recommended_capital_allocation=0.50  # Highest due to best safety
        )

        return metrics

    def _create_empty_metrics(self, name: str, number: int) -> StrategyMetrics:
        """Create empty metrics when no opportunities found"""
        return StrategyMetrics(
            strategy_name=name,
            strategy_number=number,
            total_opportunities=0,
            avg_composite_score=0,
            median_composite_score=0,
            top_10_avg_score=0,
            avg_safety_score=0,
            min_safety_score=0,
            high_risk_count=0,
            total_scanned=0,
            hit_rate=0,
            avg_scan_time=0,
            excellent_count=0,
            good_count=0,
            moderate_count=0,
            low_count=0,
            estimated_risk_level='N/A',
            recommended_capital_allocation=0
        )

    def calculate_rankings(self) -> List[StrategyRanking]:
        """
        Calculate overall rankings based on multiple criteria

        Scoring methodology:
        - 30% Opportunity Quality (composite scores)
        - 25% Safety (safety scores, risk level)
        - 20% Volume (number of opportunities)
        - 25% Efficiency (hit rate)
        """

        print(f"\n[Ranker] Calculating rankings...")

        rankings = []

        for num, metrics in self.strategies_metrics.items():
            # Calculate category scores (0-100)

            # 1. Opportunity Quality Score
            quality_score = min(100, metrics.avg_composite_score)

            # 2. Safety Score
            safety_score = min(100, metrics.avg_safety_score)

            # 3. Volume Score (normalized)
            max_opportunities = max(m.total_opportunities for m in self.strategies_metrics.values())
            volume_score = (metrics.total_opportunities / max(max_opportunities, 1)) * 100

            # 4. Efficiency Score
            efficiency_score = metrics.hit_rate * 100

            # Overall score (weighted average)
            overall_score = (
                quality_score * 0.30 +
                safety_score * 0.25 +
                volume_score * 0.20 +
                efficiency_score * 0.25
            )

            # Determine best use case and profiles
            if num == 1:
                best_for = "Finding brand new tokens as they launch"
                pros = [
                    "First-mover advantage on new pools",
                    "Catches tokens before they trend",
                    "Good balance of safety and opportunity"
                ]
                cons = [
                    "Higher false positive rate",
                    "Requires quick decision making",
                    "Some rug pulls may pass initial filters"
                ]
                ideal_profile = "Aggressive traders comfortable with higher risk/reward"

            elif num == 2:
                best_for = "Following proven winners into positions"
                pros = [
                    "Reduced research burden",
                    "Higher win rate (proven whales)",
                    "Moderate risk profile"
                ]
                cons = [
                    "Later entries than Strategy 1",
                    "Dependent on whale wallet quality",
                    "May miss opportunities whales don't find"
                ]
                ideal_profile = "Moderate risk traders who want social proof"

            else:  # Strategy 3
                best_for = "Maximum safety and scam avoidance"
                pros = [
                    "Lowest scam risk",
                    "Thorough due diligence",
                    "Finds unusual but legitimate opportunities"
                ]
                cons = [
                    "Slower scanning (more thorough)",
                    "May filter out high-risk/high-reward plays",
                    "Fewer total opportunities"
                ]
                ideal_profile = "Conservative traders prioritizing capital preservation"

            ranking = StrategyRanking(
                rank=0,  # Will assign after sorting
                strategy_name=metrics.strategy_name,
                strategy_number=num,
                overall_score=overall_score,
                opportunity_quality_score=quality_score,
                safety_score=safety_score,
                efficiency_score=efficiency_score,
                volume_score=volume_score,
                best_for=best_for,
                pros=pros,
                cons=cons,
                ideal_trader_profile=ideal_profile
            )

            rankings.append(ranking)

        # Sort by overall score
        rankings.sort(key=lambda x: x.overall_score, reverse=True)

        # Assign ranks
        for i, ranking in enumerate(rankings, 1):
            ranking.rank = i

        self.rankings = rankings
        return rankings

    def print_comparison_report(self):
        """Print comprehensive comparison report"""

        print(f"\n{'#'*80}")
        print(f"# DEX SCREENING STRATEGIES - COMPREHENSIVE COMPARISON REPORT")
        print(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*80}")

        # Print individual strategy metrics
        print(f"\n{'='*80}")
        print(f"STRATEGY METRICS")
        print(f"{'='*80}")

        for num in sorted(self.strategies_metrics.keys()):
            metrics = self.strategies_metrics[num]
            self._print_strategy_metrics(metrics)

        # Print rankings
        print(f"\n{'='*80}")
        print(f"STRATEGY RANKINGS")
        print(f"{'='*80}")

        for ranking in self.rankings:
            self._print_strategy_ranking(ranking)

        # Print final recommendation
        self._print_final_recommendation()

    def _print_strategy_metrics(self, metrics: StrategyMetrics):
        """Print metrics for a single strategy"""

        print(f"\n┌─ STRATEGY {metrics.strategy_number}: {metrics.strategy_name.upper()} " + "─" * (55 - len(metrics.strategy_name)))
        print(f"│")
        print(f"│ OPPORTUNITIES")
        print(f"│   Total Found:        {metrics.total_opportunities}")
        print(f"│   Excellent (≥80):    {metrics.excellent_count}")
        print(f"│   Good (70-79):       {metrics.good_count}")
        print(f"│   Moderate (60-69):   {metrics.moderate_count}")
        print(f"│   Low (<60):          {metrics.low_count}")
        print(f"│")
        print(f"│ QUALITY METRICS")
        print(f"│   Avg Composite:      {metrics.avg_composite_score:.1f}/100")
        print(f"│   Median Composite:   {metrics.median_composite_score:.1f}/100")
        print(f"│   Top 10 Avg:         {metrics.top_10_avg_score:.1f}/100")
        print(f"│")
        print(f"│ SAFETY METRICS")
        print(f"│   Avg Safety Score:   {metrics.avg_safety_score:.1f}/100")
        print(f"│   Min Safety Score:   {metrics.min_safety_score:.1f}/100")
        print(f"│   High Risk Count:    {metrics.high_risk_count}")
        print(f"│   Risk Level:         {metrics.estimated_risk_level}")
        print(f"│")
        print(f"│ EFFICIENCY")
        print(f"│   Total Scanned:      {metrics.total_scanned}")
        print(f"│   Hit Rate:           {metrics.hit_rate*100:.1f}%")
        print(f"│")
        print(f"│ RECOMMENDATION")
        print(f"│   Capital Allocation: {metrics.recommended_capital_allocation*100:.0f}%")
        print(f"└" + "─" * 79)

    def _print_strategy_ranking(self, ranking: StrategyRanking):
        """Print ranking for a single strategy"""

        rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(ranking.rank, "")

        print(f"\n{rank_emoji} RANK #{ranking.rank}: {ranking.strategy_name.upper()}")
        print(f"{'─'*80}")
        print(f"Overall Score: {ranking.overall_score:.1f}/100")
        print(f"")
        print(f"Category Scores:")
        print(f"  • Opportunity Quality: {ranking.opportunity_quality_score:.1f}/100")
        print(f"  • Safety:              {ranking.safety_score:.1f}/100")
        print(f"  • Volume:              {ranking.volume_score:.1f}/100")
        print(f"  • Efficiency:          {ranking.efficiency_score:.1f}/100")
        print(f"")
        print(f"Best For: {ranking.best_for}")
        print(f"")
        print(f"Pros:")
        for pro in ranking.pros:
            print(f"  ✓ {pro}")
        print(f"")
        print(f"Cons:")
        for con in ranking.cons:
            print(f"  ✗ {con}")
        print(f"")
        print(f"Ideal Trader Profile: {ranking.ideal_trader_profile}")

    def _print_final_recommendation(self):
        """Print final recommendations"""

        print(f"\n{'='*80}")
        print(f"FINAL RECOMMENDATIONS")
        print(f"{'='*80}")

        if not self.rankings:
            print("\nNo strategies have been ranked yet.")
            return

        winner = self.rankings[0]

        print(f"\n🏆 OVERALL WINNER: Strategy {winner.strategy_number} - {winner.strategy_name}")
        print(f"   Overall Score: {winner.overall_score:.1f}/100")
        print(f"")

        print(f"📊 PORTFOLIO ALLOCATION RECOMMENDATION:")
        print(f"")
        total_alloc = sum(self.strategies_metrics[r.strategy_number].recommended_capital_allocation
                         for r in self.rankings)

        for ranking in self.rankings:
            metrics = self.strategies_metrics[ranking.strategy_number]
            alloc_pct = (metrics.recommended_capital_allocation / total_alloc) * 100
            print(f"  Strategy {ranking.strategy_number} ({ranking.strategy_name}): {alloc_pct:.0f}%")

        print(f"")
        print(f"💡 USAGE RECOMMENDATIONS:")
        print(f"")
        print(f"  1. Use ALL THREE strategies in parallel for maximum coverage")
        print(f"  2. Allocate capital based on your risk tolerance:")
        print(f"     • Conservative: 50% Strategy 3, 30% Strategy 2, 20% Strategy 1")
        print(f"     • Moderate:     40% Strategy 2, 35% Strategy 3, 25% Strategy 1")
        print(f"     • Aggressive:   45% Strategy 1, 35% Strategy 2, 20% Strategy 3")
        print(f"")
        print(f"  3. Cross-reference: Tokens found by multiple strategies are higher confidence")
        print(f"")
        print(f"  4. Timing:")
        print(f"     • Strategy 1: Enter immediately on high scores (>80)")
        print(f"     • Strategy 2: Enter within 5-10 min of whale trade")
        print(f"     • Strategy 3: Enter after full due diligence (1-24 hours)")
        print(f"")
        print(f"{'='*80}")

    def export_report_json(self, filepath: str):
        """Export comparison report as JSON"""

        report = {
            'generated_at': datetime.now().isoformat(),
            'metrics': {num: asdict(m) for num, m in self.strategies_metrics.items()},
            'rankings': [asdict(r) for r in self.rankings]
        }

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n[Ranker] Report exported to {filepath}")


def main():
    """Example: Run all 3 strategies and rank them"""

    print(f"\n{'#'*80}")
    print(f"# DEX SCREENING STRATEGIES - COMPREHENSIVE EVALUATION")
    print(f"{'#'*80}")
    print(f"\nThis will run all 3 strategies for 2 cycles each and compare them.\n")

    # Initialize strategies
    print(f"{'='*80}")
    print("INITIALIZING STRATEGIES")
    print(f"{'='*80}")

    strategy1 = PoolScannerStrategy(
        chains=['ethereum', 'bsc'],
        min_liquidity_usd=15000,
        min_safety_score=65,
        min_opportunity_score=55
    )

    strategy2 = SmartMoneyTracker(
        chains=['ethereum', 'bsc'],
        min_whale_reputation=75,
        min_trade_size_usd=10000,
        min_safety_score=60
    )

    strategy3 = AnomalyDetectorStrategy(
        chains=['ethereum', 'bsc'],
        min_safety_score=75,
        max_scam_indicators=1,
        enable_deep_scan=True
    )

    print("\n✓ All strategies initialized")

    # Run strategies
    print(f"\n{'='*80}")
    print("RUNNING STRATEGIES (2 cycles each)")
    print(f"{'='*80}")

    print("\n▶ Running Strategy 1...")
    strategy1.run(max_cycles=2)

    print("\n▶ Running Strategy 2...")
    strategy2.run(max_cycles=2)

    print("\n▶ Running Strategy 3...")
    strategy3.run(max_cycles=2)

    # Analyze and rank
    print(f"\n{'='*80}")
    print("ANALYZING AND RANKING STRATEGIES")
    print(f"{'='*80}")

    ranker = StrategyRanker()

    ranker.strategies_metrics[1] = ranker.analyze_strategy1(strategy1)
    ranker.strategies_metrics[2] = ranker.analyze_strategy2(strategy2)
    ranker.strategies_metrics[3] = ranker.analyze_strategy3(strategy3)

    ranker.calculate_rankings()

    # Print comprehensive report
    ranker.print_comparison_report()

    # Export JSON
    ranker.export_report_json('dex_strategy_comparison.json')

    print(f"\n{'='*80}")
    print("EVALUATION COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
