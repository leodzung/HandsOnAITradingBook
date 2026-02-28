#!/usr/bin/env python3
"""
Alchemy On-Chain Data Collector
Fetches OrderFilled events from Polymarket's CTF Exchange contract on Polygon.

Based on IMDEA paper methodology for collecting on-chain trade data.

MODES:
  Continuous (production):  python3 alchemy_collector.py --continuous
  Historical backfill:      python3 alchemy_collector.py --backfill-days 30
  Single update:            python3 alchemy_collector.py --incremental

TWO-STEP PROCESS (token mapping):

Step 1 - Collect on-chain trades:
    python3 alchemy_collector.py --continuous  # or --incremental

Step 2 - Map token IDs to condition IDs:
    python3 market_mapper.py --update --update-trades

The first step collects raw trades (with token IDs).
The second step maps those token IDs to market condition IDs.

For production deployment, use continuous mode with nohup:
  nohup python3 alchemy_collector.py --continuous >> alchemy.out 2>&1 &

For programmatic usage, see training_pipeline.py which orchestrates both steps.
"""

import json
import sqlite3
import logging
import time
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AlchemyDataCollector:
    """
    Collect on-chain trade data from Polymarket's CTF Exchange.

    Uses Alchemy API to fetch OrderFilled events and decode trade data
    including price, size, and token_id for market mapping.
    """

    # Polymarket CTF Exchange contract on Polygon
    CTF_EXCHANGE_ADDRESS = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

    # OrderFilled event signature: keccak256("OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)")
    ORDER_FILLED_TOPIC = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"

    # Polygon average block time ~2 seconds
    BLOCKS_PER_HOUR = 1800
    BLOCKS_PER_DAY = 43200

    # Batch size per endpoint (Alchemy free tier = 10 blocks max)
    ENDPOINT_BATCH_SIZES = {
        "alchemy.com": 9,
        "drpc.org": 500,
        "1rpc.io": 200,
    }

    def __init__(self, api_key: str, db_path: str = 'data/alchemy_trades.db',
                 rate_limit_per_sec: float = 5.0, batch_size_blocks: int = 500):
        """
        Initialize the Alchemy collector.

        Args:
            api_key: Alchemy API key
            db_path: Path to SQLite database (default: separate DB to avoid conflicts)
            rate_limit_per_sec: Maximum requests per second
            batch_size_blocks: Number of blocks per eth_getLogs request
        """
        self.api_key = api_key
        self.db_path = db_path
        self.rate_limit_per_sec = rate_limit_per_sec
        self.batch_size_blocks = batch_size_blocks
        self.min_request_interval = 1.0 / rate_limit_per_sec
        self.last_request_time = 0
        self.is_running = False  # For continuous mode
        self._timestamp_cache = {}  # block_number -> datetime

        # dRPC primary (supports 2000+ block batches, no old-block crashes)
        # Alchemy free tier: 10-block max, crashes on old blocks
        self.endpoints = [
            "https://polygon.drpc.org",  # dRPC - primary
            f"https://polygon-mainnet.g.alchemy.com/v2/{api_key}",
            "https://1rpc.io/matic",  # 1RPC
        ]
        self.current_endpoint_idx = 0

        self.endpoint = self.endpoints[self.current_endpoint_idx]
        logger.info(f"Using RPC endpoint: {self.endpoint}")

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Enable WAL mode for better crash resilience
        cursor.execute("PRAGMA journal_mode=WAL")
        # Set busy timeout to wait up to 30 seconds for locks
        cursor.execute("PRAGMA busy_timeout=30000")

        # On-chain trades table
        # NOTE: condition_id starts as NULL. After collection, run:
        #   python3 market_mapper.py --update --update-trades
        # to populate condition_ids from token_condition_map.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS on_chain_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT NOT NULL,
                log_index INTEGER NOT NULL,
                block_number INTEGER NOT NULL,
                block_timestamp TEXT NOT NULL,
                maker_asset_id TEXT,      -- Token ID from on-chain event
                maker_amount_filled REAL,
                taker_amount_filled REAL,
                price REAL,
                condition_id TEXT,        -- Market ID, populated by market_mapper
                UNIQUE(tx_hash, log_index)
            )
        ''')

        # Token-to-condition mapping table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_condition_map (
                token_id TEXT PRIMARY KEY,
                condition_id TEXT NOT NULL,
                outcome_index INTEGER
            )
        ''')

        # Checkpoints for incremental updates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_checkpoints (
                source TEXT PRIMARY KEY,
                last_block INTEGER,
                last_timestamp TEXT,
                updated_at TEXT
            )
        ''')

        # Create indexes for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trades_block
            ON on_chain_trades(block_number)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp
            ON on_chain_trades(block_timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trades_condition
            ON on_chain_trades(condition_id)
        ''')

        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    def _get_batch_size(self) -> int:
        """Get appropriate batch size for the current endpoint."""
        for domain, size in self.ENDPOINT_BATCH_SIZES.items():
            if domain in self.endpoint:
                return size
        return self.batch_size_blocks

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _make_rpc_call(self, method: str, params: List, max_retries: int = 5) -> Optional[Dict]:
        """Make a JSON-RPC call to Alchemy with retry logic."""
        self._rate_limit()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=60
                )

                # Retry on 503/429 with exponential backoff, try next endpoint
                if response.status_code in (503, 429):
                    # Try next endpoint
                    self.current_endpoint_idx = (self.current_endpoint_idx + 1) % len(self.endpoints)
                    self.endpoint = self.endpoints[self.current_endpoint_idx]
                    wait_time = (2 ** attempt) * 2  # 2, 4, 8, 16, 32 seconds
                    logger.warning(f"{response.status_code} error, switching to {self.endpoint}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    error = result['error']
                    error_code = error.get('code')
                    error_msg = str(error.get('message', '')).lower()
                    # Retryable errors: rate limits, server crashes, internal errors
                    if error_code in (-32090, -32000, -32603) or 'rate' in error_msg or 'crash' in error_msg:
                        self.current_endpoint_idx = (self.current_endpoint_idx + 1) % len(self.endpoints)
                        self.endpoint = self.endpoints[self.current_endpoint_idx]
                        wait_time = (2 ** attempt) * 5  # 5, 10, 20, 40, 80 seconds
                        logger.warning(f"RPC error {error_code}: {error.get('message')}, switching to {self.endpoint}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    logger.error(f"RPC error (non-retryable): {error}")
                    return None

                return result.get("result")

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"Request error: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request error after {max_retries} attempts: {e}")
                    return None

        return None

    def get_current_block(self) -> Optional[int]:
        """Get the current block number."""
        result = self._make_rpc_call("eth_blockNumber", [])
        if result:
            return int(result, 16)
        return None

    def get_block_timestamp(self, block_number: int) -> Optional[datetime]:
        """Get timestamp for a block (with in-memory cache)."""
        if block_number in self._timestamp_cache:
            return self._timestamp_cache[block_number]
        result = self._make_rpc_call(
            "eth_getBlockByNumber",
            [hex(block_number), False]
        )
        if result and "timestamp" in result:
            ts = int(result["timestamp"], 16)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            self._timestamp_cache[block_number] = dt
            return dt
        return None

    def get_batch_timestamps(self, block_numbers: set) -> Dict[int, str]:
        """
        Get timestamps for a batch of blocks efficiently.

        Fetches timestamps for the min and max blocks, then interpolates
        the rest using Polygon's ~2 second block time. This reduces RPC
        calls from N to 2 per batch.
        """
        if not block_numbers:
            return {}

        sorted_blocks = sorted(block_numbers)
        min_block, max_block = sorted_blocks[0], sorted_blocks[-1]

        # Fetch actual timestamps for boundary blocks
        min_ts = self.get_block_timestamp(min_block)
        max_ts = self.get_block_timestamp(max_block)

        if not min_ts:
            return {}
        if not max_ts:
            max_ts = min_ts

        # Interpolate timestamps for intermediate blocks
        block_range = max_block - min_block
        if block_range > 0:
            time_range = (max_ts - min_ts).total_seconds()
            secs_per_block = time_range / block_range
        else:
            secs_per_block = 2.0  # Polygon average

        timestamps = {}
        for block_num in sorted_blocks:
            offset_secs = (block_num - min_block) * secs_per_block
            block_time = min_ts + timedelta(seconds=offset_secs)
            timestamps[block_num] = block_time.isoformat()

        return timestamps

    def estimate_block_at_time(self, target_time: datetime, current_block: int = None) -> int:
        """
        Estimate the block number at a given time.

        Uses binary search with actual block timestamps for accuracy.
        """
        if current_block is None:
            current_block = self.get_current_block()

        current_time = self.get_block_timestamp(current_block)
        if not current_time:
            return current_block

        # Estimate based on 2-second block time
        time_diff = (current_time - target_time).total_seconds()
        estimated_block = current_block - int(time_diff / 2)

        # Ensure non-negative
        return max(1, estimated_block)

    def fetch_order_filled_logs(self, from_block: int, to_block: int) -> List[Dict]:
        """
        Fetch OrderFilled event logs for a block range.

        Args:
            from_block: Start block (inclusive)
            to_block: End block (inclusive)

        Returns:
            List of decoded log entries
        """
        params = [{
            "address": self.CTF_EXCHANGE_ADDRESS,
            "topics": [self.ORDER_FILLED_TOPIC],
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block)
        }]

        result = self._make_rpc_call("eth_getLogs", params)

        if result is None:
            return []

        return result

    def decode_order_filled(self, log: Dict) -> Optional[Dict]:
        """
        Decode an OrderFilled event log.

        Event signature:
        OrderFilled(bytes32 indexed orderHash, address indexed maker, address indexed taker,
                    uint256 makerAssetId, uint256 takerAssetId, uint256 makerAmountFilled,
                    uint256 takerAmountFilled, uint256 fee)

        Topics: [0]=event_sig, [1]=orderHash, [2]=maker, [3]=taker
        Data: makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee

        Returns:
            Decoded trade data or None if decoding fails
        """
        try:
            topics = log.get("topics", [])
            data = log.get("data", "0x")

            # Need at least 4 topics and 5 data fields (320 hex chars)
            if len(topics) < 4 or len(data) < 2 + 64 * 5:
                return None

            # Remove '0x' prefix from data
            data = data[2:]

            # Extract from topics (indexed params)
            order_hash = topics[1]
            maker = "0x" + topics[2][26:]  # Last 20 bytes
            taker = "0x" + topics[3][26:]

            # Extract from data (non-indexed params)
            maker_asset_id = int(data[0:64], 16)
            taker_asset_id = int(data[64:128], 16)
            maker_amount = int(data[128:192], 16)
            taker_amount = int(data[192:256], 16)
            # fee = int(data[256:320], 16)  # Not needed

            # Convert amounts (both have 6 decimals on Polymarket)
            maker_amount_decimal = maker_amount / 1e6
            taker_amount_decimal = taker_amount / 1e6

            # Determine token ID and calculate price
            # If makerAssetId = 0, maker is paying USDC for tokens (takerAssetId is the token)
            # If takerAssetId = 0, taker is paying USDC for tokens (makerAssetId is the token)
            if maker_asset_id == 0:
                # Maker pays USDC (makerAmount), receives tokens (takerAmount)
                token_id = str(taker_asset_id)
                usdc_amount = maker_amount_decimal
                token_amount = taker_amount_decimal
            else:
                # Maker provides tokens (makerAmount), receives USDC (takerAmount)
                token_id = str(maker_asset_id)
                token_amount = maker_amount_decimal
                usdc_amount = taker_amount_decimal

            # Price = USDC per token
            price = usdc_amount / token_amount if token_amount > 0 else 0

            return {
                "tx_hash": log.get("transactionHash"),
                "log_index": int(log.get("logIndex", "0x0"), 16),
                "block_number": int(log.get("blockNumber", "0x0"), 16),
                "maker": maker,
                "taker": taker,
                "maker_asset_id": token_id,  # Store the actual token ID
                "maker_amount_filled": token_amount,
                "taker_amount_filled": usdc_amount,
                "price": price
            }

        except Exception as e:
            logger.debug(f"Error decoding log: {e}")
            return None

    def store_trades(self, trades: List[Dict], block_timestamps: Dict[int, str]):
        """Store decoded trades in the database."""
        if not trades:
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stored = 0
        for trade in trades:
            try:
                block_num = trade["block_number"]
                timestamp = block_timestamps.get(block_num, "")

                cursor.execute('''
                    INSERT OR IGNORE INTO on_chain_trades
                    (tx_hash, log_index, block_number, block_timestamp,
                     maker_asset_id, maker_amount_filled, taker_amount_filled, price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade["tx_hash"],
                    trade["log_index"],
                    block_num,
                    timestamp,
                    trade["maker_asset_id"],
                    trade["maker_amount_filled"],
                    trade["taker_amount_filled"],
                    trade["price"]
                ))
                stored += 1
            except Exception as e:
                logger.debug(f"Error storing trade: {e}")

        conn.commit()
        conn.close()
        return stored

    def get_checkpoint(self, source: str = "alchemy") -> Optional[int]:
        """Get the last processed block from checkpoint."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT last_block FROM collection_checkpoints WHERE source = ?",
            (source,)
        )
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def save_checkpoint(self, source: str, block_number: int):
        """Save checkpoint for resumable collection."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO collection_checkpoints
            (source, last_block, last_timestamp, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (
            source,
            block_number,
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat()
        ))

        conn.commit()
        conn.close()

    def backfill_historical_trades(self, start_date: datetime = None,
                                   end_date: datetime = None,
                                   resume: bool = True) -> int:
        """
        Backfill historical trades from on-chain data.

        Args:
            start_date: Start date for backfill (default: 6 months ago)
            end_date: End date for backfill (default: now)
            resume: Whether to resume from last checkpoint

        Returns:
            Total number of trades collected
        """
        current_block = self.get_current_block()
        if not current_block:
            logger.error("Could not get current block")
            return 0

        # Default to 6 months ago
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=180)

        # Estimate block range
        end_block = current_block
        start_block = self.estimate_block_at_time(start_date, current_block)

        # Resume from checkpoint if available
        if resume:
            checkpoint = self.get_checkpoint("alchemy")
            if checkpoint and checkpoint > start_block:
                start_block = checkpoint + 1
                logger.info(f"Resuming from checkpoint block {start_block}")

        logger.info(f"Backfilling trades from block {start_block} to {end_block}")
        logger.info(f"  Approximately {(end_block - start_block) / self.BLOCKS_PER_DAY:.1f} days of data")

        total_trades = 0
        total_logs = 0
        current = start_block

        while current < end_block:
            batch_size = self._get_batch_size()
            batch_end = min(current + batch_size - 1, end_block)

            # Fetch logs for this batch
            logs = self.fetch_order_filled_logs(current, batch_end)
            total_logs += len(logs)

            if logs:
                # Decode trades
                trades = []
                block_numbers = set()

                for log in logs:
                    decoded = self.decode_order_filled(log)
                    if decoded:
                        trades.append(decoded)
                        block_numbers.add(decoded["block_number"])

                # Fetch block timestamps (interpolated - 2 RPC calls instead of N)
                block_timestamps = self.get_batch_timestamps(block_numbers)

                # Store trades
                stored = self.store_trades(trades, block_timestamps)
                total_trades += stored

                logger.info(f"  Blocks {current}-{batch_end}: {len(logs)} logs, {stored} trades stored")
            else:
                logger.debug(f"  Blocks {current}-{batch_end}: no logs")

            # Save checkpoint
            self.save_checkpoint("alchemy", batch_end)

            current = batch_end + 1

        # Clear cache after backfill
        self._timestamp_cache.clear()
        logger.info(f"Backfill complete: {total_logs} total logs, {total_trades} trades stored")

        # Remind users about mapping
        logger.info("")
        logger.info("=" * 70)
        logger.info("NEXT STEP: Map token IDs to condition IDs")
        logger.info("Run: python3 market_mapper.py --update --update-trades")
        logger.info("This connects on-chain trades to Polymarket markets")
        logger.info("=" * 70)

        return total_trades

    def incremental_update(self) -> int:
        """
        Update with new trades since last checkpoint.

        Returns:
            Number of new trades collected
        """
        current_block = self.get_current_block()
        if not current_block:
            logger.error("Could not get current block")
            return 0

        # Get last checkpoint
        last_block = self.get_checkpoint("alchemy")
        if not last_block:
            # Start from 1 hour ago if no checkpoint
            last_block = current_block - self.BLOCKS_PER_HOUR

        if last_block >= current_block:
            logger.info("Already up to date")
            return 0

        logger.info(f"Incremental update from block {last_block + 1} to {current_block}")

        total_trades = 0
        current = last_block + 1

        while current < current_block:
            batch_size = self._get_batch_size()
            batch_end = min(current + batch_size - 1, current_block)

            logs = self.fetch_order_filled_logs(current, batch_end)

            if logs:
                trades = []
                block_numbers = set()

                for log in logs:
                    decoded = self.decode_order_filled(log)
                    if decoded:
                        trades.append(decoded)
                        block_numbers.add(decoded["block_number"])

                # Fetch block timestamps (interpolated - 2 RPC calls instead of N)
                block_timestamps = self.get_batch_timestamps(block_numbers)

                stored = self.store_trades(trades, block_timestamps)
                total_trades += stored

            self.save_checkpoint("alchemy", batch_end)
            current = batch_end + 1

        logger.info(f"Incremental update complete: {total_trades} new trades")

        # Remind users about mapping if trades were collected
        if total_trades > 0:
            logger.info("")
            logger.info("=" * 70)
            logger.info("NEXT STEP: Map token IDs to condition IDs")
            logger.info("Run: python3 market_mapper.py --update --update-trades")
            logger.info("=" * 70)

        return total_trades

    def get_trades_for_market(self, condition_id: str,
                              start_time: datetime = None,
                              end_time: datetime = None) -> List[Dict]:
        """
        Get all trades for a specific market.

        Requires token-to-condition mapping to be populated first.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT t.* FROM on_chain_trades t
            WHERE t.condition_id = ?
        '''
        params = [condition_id]

        if start_time:
            query += " AND t.block_timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND t.block_timestamp <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY t.block_timestamp"

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        return [dict(zip(columns, row)) for row in rows]

    def get_vwap(self, condition_id: str, start_time: datetime,
                 end_time: datetime) -> Optional[float]:
        """
        Calculate volume-weighted average price for a market in a time window.
        """
        trades = self.get_trades_for_market(condition_id, start_time, end_time)

        if not trades:
            return None

        total_value = sum(t["price"] * t["maker_amount_filled"] for t in trades)
        total_volume = sum(t["maker_amount_filled"] for t in trades)

        if total_volume == 0:
            return None

        return total_value / total_volume

    def get_statistics(self) -> Dict:
        """Get collection statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Total trades
        cursor.execute("SELECT COUNT(*) FROM on_chain_trades")
        stats["total_trades"] = cursor.fetchone()[0]

        # Date range
        cursor.execute("""
            SELECT MIN(block_timestamp), MAX(block_timestamp)
            FROM on_chain_trades
            WHERE block_timestamp != ''
        """)
        result = cursor.fetchone()
        stats["earliest_trade"] = result[0] if result[0] else None
        stats["latest_trade"] = result[1] if result[1] else None

        # Unique markets (with mapping)
        cursor.execute("""
            SELECT COUNT(DISTINCT condition_id) FROM on_chain_trades
            WHERE condition_id IS NOT NULL
        """)
        stats["unique_markets"] = cursor.fetchone()[0]

        # Trades per day (recent)
        cursor.execute("""
            SELECT DATE(block_timestamp) as date, COUNT(*) as count
            FROM on_chain_trades
            WHERE block_timestamp >= DATE('now', '-7 days')
            GROUP BY DATE(block_timestamp)
            ORDER BY date DESC
            LIMIT 7
        """)
        stats["recent_daily_counts"] = dict(cursor.fetchall())

        # Checkpoint status
        cursor.execute("SELECT source, last_block FROM collection_checkpoints")
        stats["checkpoints"] = dict(cursor.fetchall())

        conn.close()
        return stats

    def run_continuous(self, interval_seconds: int = 120):
        """
        Run collector continuously with periodic updates.

        Similar to trader.py pattern - runs indefinitely until stopped.

        Args:
            interval_seconds: Seconds between collection cycles (default: 120)
        """
        logger.info(f"Starting continuous Alchemy collection (every {interval_seconds} sec)")
        logger.info("Press Ctrl+C to stop gracefully")

        self.is_running = True
        collection_count = 0

        while self.is_running:
            try:
                collection_count += 1
                logger.info(f"--- Collection cycle #{collection_count} ---")

                # Run incremental update
                trades = self.incremental_update()

                if trades == 0:
                    logger.info("No new trades (already up to date)")

                # Wait for next cycle
                logger.info(f"Next collection in {interval_seconds} seconds...")
                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.stop()
            except Exception as e:
                logger.error(f"Error in collection cycle: {e}", exc_info=True)
                logger.info("Retrying in 1 minute...")
                time.sleep(60)

    def stop(self):
        """Stop the continuous collector."""
        logger.info("Stopping Alchemy collector...")
        self.is_running = False
        logger.info("Alchemy collector stopped")


def main():
    """Main collection routine."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Alchemy On-Chain Data Collector",
        epilog="Examples:\n"
               "  Backfill historical:  python3 alchemy_collector.py --backfill-days 30\n"
               "  Single update:        python3 alchemy_collector.py --incremental\n"
               "  Continuous mode:      python3 alchemy_collector.py --continuous\n"
               "  With nohup:           nohup python3 alchemy_collector.py --continuous >> alchemy.out 2>&1 &",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api-key", help="Alchemy API key")
    parser.add_argument("--incremental", action="store_true",
                        help="Run incremental update only (one-time)")
    parser.add_argument("--backfill-days", type=int, default=180, metavar="DAYS",
                        help="Days to backfill (one-time, default: 180)")
    parser.add_argument("--continuous", action="store_true",
                        help="Run continuously, collecting updates every 120 seconds (recommended for production)")
    parser.add_argument("--interval", type=int, default=120, metavar="SECONDS",
                        help="Seconds between updates in continuous mode (default: 120)")
    parser.add_argument("--stats", action="store_true",
                        help="Show collection statistics")
    args = parser.parse_args()

    # Load config
    config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
    api_key = args.api_key

    if not api_key and config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            api_key = config.get("alchemy_api_key")

    if not api_key:
        logger.error("Alchemy API key required. Set via --api-key or config.json")
        return

    collector = AlchemyDataCollector(api_key)

    if args.stats:
        stats = collector.get_statistics()
        print("\n=== Alchemy Collection Statistics ===")
        print(f"Total trades: {stats['total_trades']:,}")
        print(f"Date range: {stats['earliest_trade']} to {stats['latest_trade']}")
        print(f"Unique markets: {stats['unique_markets']}")
        print(f"\nRecent daily counts:")
        for date, count in stats.get("recent_daily_counts", {}).items():
            print(f"  {date}: {count:,}")
        print(f"\nCheckpoints: {stats['checkpoints']}")
        return

    if args.continuous:
        # Continuous mode - runs forever until stopped
        collector.run_continuous(interval_seconds=args.interval)
        return

    if args.incremental:
        # One-time incremental update
        collector.incremental_update()
    else:
        # One-time historical backfill
        start_date = datetime.now(timezone.utc) - timedelta(days=args.backfill_days)
        collector.backfill_historical_trades(start_date=start_date)


if __name__ == "__main__":
    main()
