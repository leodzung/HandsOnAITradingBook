"""
Diagnostic script to understand why short expiry bot is not opening positions.
"""
import json
import logging
import sys
import os
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.polymarket_client import PolymarketClient, MarketFilter
from core.price_fetcher import PriceFetcher
from features.short_expiry_features import ShortExpiryFeatureExtractor
from bots.trader_short_expiry import ShortExpiryRiskManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Load config
    with open('config/config_short_expiry.json') as f:
        config = json.load(f)

    # Initialize components
    client = PolymarketClient()
    price_fetcher = PriceFetcher(client)
    feature_extractor = ShortExpiryFeatureExtractor()
    risk_manager = ShortExpiryRiskManager(config)

    # Discover short markets
    logger.info("Discovering SHORT bucket markets (24-72h)...")
    short_markets = MarketFilter.discover_markets(
        client=client,
        category='crypto',
        min_hours_to_expiry=24,
        max_hours_to_expiry=72,
        min_volume=200,
        min_liquidity=100,
        max_pages=3,
        include_crypto_events=True,
        crypto_event_days_ahead=3,
        logger=logger
    )

    logger.info(f"Found {len(short_markets)} raw markets")

    # Filter tradeable
    tradeable = MarketFilter.filter_by_quality(
        markets=short_markets,
        price_fetcher=price_fetcher,
        min_price=config['discovery']['min_price'],
        max_price=config['discovery']['max_price'],
        max_spread_pct=config['discovery']['max_spread_pct']['short'],
        check_last_trade=True,
        logger=logger
    )

    logger.info(f"Found {len(tradeable)} tradeable markets after quality filter")

    if not tradeable:
        logger.warning("No tradeable markets found!")
        return

    # Test signal generation on first 5 markets
    logger.info("\n" + "="*80)
    logger.info("TESTING SIGNAL GENERATION ON FIRST 5 MARKETS")
    logger.info("="*80 + "\n")

    for i, market in enumerate(tradeable[:5]):
        logger.info(f"\n--- Market {i+1} ---")
        logger.info(f"Question: {market.get('question', 'N/A')[:80]}")
        logger.info(f"Market ID: {market.get('conditionId', 'N/A')[:16]}...")

        # Extract features
        try:
            features = feature_extractor.extract_all_features(market, 'short')
            logger.info(f"Features extracted: {len(features.columns)} columns")
            logger.info(f"  - Market price: {features['market_probability'].iloc[0]:.4f}")
            logger.info(f"  - Hours to expiry: {features['hours_to_expiry'].iloc[0]:.1f}")
            logger.info(f"  - Volume 24h: ${features.get('volume_24h', [0]).iloc[0]:.0f}")

            # Generate signal using the trader's logic
            market_price = features['market_probability'].iloc[0]
            rules_config = config['rules']

            # Check Rule 1: Arbitrage
            if rules_config['arbitrage']['enabled']:
                yes_price = market_price
                no_price = 1.0 - market_price
                total = yes_price + no_price

                logger.info(f"  - Arbitrage check: YES={yes_price:.4f} + NO={no_price:.4f} = {total:.4f}")

                if total < rules_config['arbitrage']['max_total_price']:
                    edge = rules_config['arbitrage']['max_total_price'] - total
                    logger.info(f"    ✅ ARBITRAGE SIGNAL! Edge={edge:.4f}")
                    if edge >= rules_config['arbitrage']['min_edge']:
                        logger.info(f"    ✅ Edge meets minimum ({rules_config['arbitrage']['min_edge']})")
                    else:
                        logger.info(f"    ❌ Edge too small (min: {rules_config['arbitrage']['min_edge']})")
                else:
                    logger.info(f"    ❌ No arbitrage (total >= {rules_config['arbitrage']['max_total_price']})")

            # Check Rule 3: Momentum
            if rules_config['momentum']['enabled']:
                price_change_1h = features.get('price_change_1h', [0]).iloc[0]
                volume_24h = features.get('volume_24h', [0]).iloc[0]

                logger.info(f"  - Momentum check: price_change_1h={price_change_1h:.4f}, volume_24h=${volume_24h:.0f}")

                if abs(price_change_1h) > rules_config['momentum']['min_price_change_1h']:
                    logger.info(f"    ✅ Price change meets threshold")
                    if volume_24h > rules_config['momentum']['min_volume_24h']:
                        logger.info(f"    ✅ MOMENTUM SIGNAL!")
                    else:
                        logger.info(f"    ❌ Volume too low (min: ${rules_config['momentum']['min_volume_24h']})")
                else:
                    logger.info(f"    ❌ Price change too small (min: {rules_config['momentum']['min_price_change_1h']})")

        except Exception as e:
            logger.error(f"Error processing market: {e}", exc_info=True)

    logger.info("\n" + "="*80)
    logger.info("DIAGNOSIS COMPLETE")
    logger.info("="*80)

if __name__ == '__main__':
    main()
