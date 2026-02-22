"""
Quick Demo - Shows strategy ranking without delays
"""

from strategy_ranker import StrategyRanker
from strategy1_pool_scanner import PoolScannerStrategy, PoolOpportunity
from strategy2_smart_money import SmartMoneyTracker, CopyTradeOpportunity, WhaleWallet, WhaleTrade
from strategy3_anomaly_detector import AnomalyDetectorStrategy, TokenOpportunity, ScamIndicators, AnomalyScore
from dex_utils import TokenMetrics, Token, LiquidityPool
import time


def create_mock_pool_opportunity(score, token_symbol):
    """Create mock pool opportunity for demo"""
    metrics = TokenMetrics(
        token_address=f"0x{'1234'*10}",
        liquidity_usd=50000 + (score * 1000),
        volume_24h=30000 + (score * 500),
        holder_count=100 + int(score * 10),
        top_10_concentration=40 - (score * 0.1),
        honeypot_risk=0.1,
        contract_verified=True,
        buy_tax=2.0,
        sell_tax=2.0,
        liquidity_locked=True,
        creation_time=int(time.time() - 3600),
        price_change_1h=score * 0.5,
        price_change_24h=score * 0.8
    )

    pool = LiquidityPool(
        address=f"0x{'pool'*10}",
        token0=Token(metrics.token_address, token_symbol, token_symbol, "ethereum", 18),
        token1=Token("0x"+"0"*40, "WETH", "WETH", "ethereum", 18),
        liquidity_usd=metrics.liquidity_usd,
        volume_24h=metrics.volume_24h,
        created_timestamp=metrics.creation_time,
        dex_name="Uniswap",
        chain="ethereum"
    )

    return PoolOpportunity(
        pool=pool,
        metrics=metrics,
        safety_score=score - 10,
        opportunity_score=score - 5,
        composite_score=score,
        timestamp=int(time.time())
    )


def create_mock_whale_opportunity(score, token_symbol, whale_name):
    """Create mock whale opportunity for demo"""
    metrics = TokenMetrics(
        token_address=f"0x{'5678'*10}",
        liquidity_usd=75000 + (score * 1200),
        volume_24h=45000 + (score * 600),
        holder_count=150 + int(score * 8),
        top_10_concentration=35 - (score * 0.08),
        honeypot_risk=0.05,
        contract_verified=True,
        buy_tax=1.5,
        sell_tax=1.5,
        liquidity_locked=True,
        creation_time=int(time.time() - 7200),
        price_change_1h=score * 0.4,
        price_change_24h=score * 0.7
    )

    whale = WhaleWallet(
        address=f"0x{'whale'*8}",
        chain="ethereum",
        label=whale_name,
        historical_win_rate=0.70 + (score * 0.001),
        total_trades=200,
        avg_roi=2.5 + (score * 0.02),
        reputation_score=80 + (score * 0.1)
    )

    trade = WhaleTrade(
        wallet=whale,
        token_address=metrics.token_address,
        token_symbol=token_symbol,
        chain="ethereum",
        trade_type="buy",
        amount_usd=25000,
        timestamp=int(time.time() - 600),
        tx_hash=f"0x{'abcd'*16}"
    )

    return CopyTradeOpportunity(
        whale_trade=trade,
        token_metrics=metrics,
        whale_score=whale.reputation_score,
        safety_score=score - 8,
        opportunity_score=score - 3,
        composite_score=score,
        copy_recommended=True,
        reason="High-quality whale trade"
    )


def create_mock_anomaly_opportunity(score, token_symbol, risk_level):
    """Create mock anomaly opportunity for demo"""
    metrics = TokenMetrics(
        token_address=f"0x{'9abc'*10}",
        liquidity_usd=100000 + (score * 1500),
        volume_24h=60000 + (score * 700),
        holder_count=200 + int(score * 12),
        top_10_concentration=30 - (score * 0.05),
        honeypot_risk=0.02,
        contract_verified=True,
        buy_tax=0.5,
        sell_tax=0.5,
        liquidity_locked=True,
        creation_time=int(time.time() - 10800),
        price_change_1h=score * 0.3,
        price_change_24h=score * 0.6
    )

    scam_indicators = ScamIndicators(
        is_honeypot=False,
        has_hidden_mint=False,
        has_blacklist_function=False,
        excessive_buy_tax=False,
        excessive_sell_tax=False,
        tax_asymmetry=False,
        ownership_not_renounced=False,
        liquidity_not_locked=False,
        concentrated_ownership=False,
        suspicious_holder_pattern=False,
        low_liquidity=False
    )

    anomaly_scores = AnomalyScore(
        holder_distribution_anomaly=0.2,
        trading_pattern_anomaly=0.3,
        contract_risk_anomaly=0.1,
        liquidity_anomaly=0.2,
        volume_anomaly=0.3
    )

    return TokenOpportunity(
        token_address=metrics.token_address,
        token_symbol=token_symbol,
        chain="ethereum",
        metrics=metrics,
        anomaly_scores=anomaly_scores,
        scam_indicators=scam_indicators,
        safety_score=score - 5,
        anomaly_appeal_score=score - 7,
        composite_score=score,
        risk_level=risk_level,
        recommendation=f"Risk: {risk_level}, Score: {score:.1f}/100"
    )


def main():
    """Quick demo with mock data"""

    print(f"\n{'#'*80}")
    print(f"# DEX SCREENING STRATEGIES - QUICK DEMO")
    print(f"# (Using mock data for demonstration)")
    print(f"{'#'*80}\n")

    # Create mock strategies with opportunities
    print("Creating mock strategies with sample opportunities...\n")

    # Strategy 1: Pool Scanner
    strategy1 = PoolScannerStrategy(chains=['ethereum'])
    strategy1.opportunities = [
        create_mock_pool_opportunity(85, "NEWTOK1"),
        create_mock_pool_opportunity(78, "LAUNCH2"),
        create_mock_pool_opportunity(72, "POOL3"),
        create_mock_pool_opportunity(68, "DEX4"),
        create_mock_pool_opportunity(81, "GEM5"),
    ]
    strategy1.scanned_pools = set([f"pool_{i}" for i in range(25)])

    # Strategy 2: Smart Money Tracker
    strategy2 = SmartMoneyTracker(chains=['ethereum'])
    strategy2.opportunities = [
        create_mock_whale_opportunity(88, "WHALETOK", "GemHunter"),
        create_mock_whale_opportunity(82, "SMARTM", "0xSmartMoney"),
        create_mock_whale_opportunity(79, "FOLLOW3", "MoonTracker"),
        create_mock_whale_opportunity(86, "COPY4", "WhaleWizard"),
        create_mock_whale_opportunity(75, "TRACK5", "TokenSniper"),
        create_mock_whale_opportunity(83, "WHALE6", "CryptoWhale"),
    ]
    strategy2.tracked_trades = set([f"trade_{i}" for i in range(30)])

    # Strategy 3: Anomaly Detector
    strategy3 = AnomalyDetectorStrategy(chains=['ethereum'])
    strategy3.opportunities = [
        create_mock_anomaly_opportunity(90, "SAFEGEM", "LOW"),
        create_mock_anomaly_opportunity(87, "VERIFIED", "LOW"),
        create_mock_anomaly_opportunity(82, "SECURE", "MEDIUM"),
        create_mock_anomaly_opportunity(78, "CLEAN", "MEDIUM"),
    ]
    strategy3.scanned_tokens = set([f"token_{i}" for i in range(50)])

    # Create ranker and analyze
    print("Analyzing strategies...\n")
    ranker = StrategyRanker()

    ranker.strategies_metrics[1] = ranker.analyze_strategy1(strategy1)
    ranker.strategies_metrics[2] = ranker.analyze_strategy2(strategy2)
    ranker.strategies_metrics[3] = ranker.analyze_strategy3(strategy3)

    ranker.calculate_rankings()

    # Print report
    ranker.print_comparison_report()

    # Export JSON
    ranker.export_report_json('dex_strategy_comparison.json')

    print(f"\n{'='*80}")
    print("DEMO COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
