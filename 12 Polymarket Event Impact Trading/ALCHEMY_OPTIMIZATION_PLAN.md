# Alchemy Data Collector Performance Optimization Plan

## Context

The Alchemy data collector fetches OrderFilled events from Polymarket's CTF Exchange contract on Polygon using the Alchemy API. It has successfully collected **1,666,398 trades** (593 MB database) covering blocks 74.6M to 82.7M. However, performance analysis reveals several critical bottlenecks that slow down data collection and prevent downstream processing.

**Current Status:**
- ✅ Trade collection working (1.66M trades collected)
- ❌ Token mapping incomplete (0% coverage - blocking downstream use)
- ⚠️ Network reliability issues (connection resets, timeouts)
- ⚠️ Suboptimal database operations (individual INSERTs)
- ⚠️ Batch size logic bug (incremental updates try to fetch 7.8M blocks at once)

## Critical Files

| File | Purpose | Size |
|------|---------|------|
| `src/collectors/alchemy_collector.py` | Main collection engine | 29.7 KB |
| `src/utils/market_mapper.py` | Token ID → Condition ID mapping | TBD |
| `config/config.json` | Configuration (API keys, batch sizes) | TBD |
| `data/alchemy_trades.db` | Trade database | 593 MB |
| `logs/alchemy_collection.out` | Collection logs | 481 KB |

## Optimization Options (Prioritized by Impact/Effort Ratio)

### Priority 1: Quick Wins (High Impact, Low Effort)

#### 1.1 Fix Incremental Update Batch Logic (CRITICAL)
**Problem:** Incremental updates try to process 7.8M blocks in a single request, causing "Block range is too large" errors.

**Root Cause:** `incremental_update()` calls `_fetch_logs()` with full range instead of batching.

**Solution:**
- Modify `incremental_update()` to apply `batch_size_blocks` chunking
- Use same batching logic as `backfill_date_range()`

**Implementation:**
```python
def incremental_update(self):
    start_block = self._get_checkpoint() + 1
    current_block = self._get_current_block()

    # ADD BATCHING HERE
    for batch_start in range(start_block, current_block, self.batch_size_blocks):
        batch_end = min(batch_start + self.batch_size_blocks - 1, current_block)
        logs = self._fetch_logs(batch_start, batch_end)
        # ... process logs
```

**Expected Impact:** Eliminates "Block range is too large" errors, enables reliable incremental updates

---

#### 1.2 Complete Token Mapping Step (CRITICAL - UNBLOCKS DOWNSTREAM)
**Problem:** 1.66M trades collected but 0% have condition_id mapped. This blocks all downstream analysis and trading.

**Solution:**
```bash
cd /Users/leole/workspace/HandsOnAITradingBook/12\ Polymarket\ Event\ Impact\ Trading
python3 src/utils/market_mapper.py --update --update-trades
```

**Expected Impact:**
- Populates `token_condition_map` table from Gamma API
- Updates `on_chain_trades.condition_id` for all 1.66M trades
- Unblocks trading bot and analysis pipelines
- One-time operation: ~5-15 minutes

---

#### 1.3 Bulk Database Transactions
**Problem:** Individual INSERT statements for each trade + commit after each batch.

**Current Code:**
```python
for log_data in logs_data:
    cursor.execute("INSERT OR IGNORE INTO on_chain_trades ...")
conn.commit()  # After loop
```

**Solution:**
```python
# Batch insert
cursor.executemany(
    "INSERT OR IGNORE INTO on_chain_trades (...) VALUES (?, ?, ...)",
    [(log['tx_hash'], log['log_index'], ...) for log in logs_data]
)
conn.commit()
```

**Expected Impact:** 2-5x faster database writes for large batches

---

#### 1.4 Increase Batch Size (if using paid Alchemy tier)
**Problem:** Free tier limited to 9 blocks per request. Config has `batch_size_blocks: 10` but training pipeline uses 2000.

**Current Limits:**
- Free tier: 9 blocks max
- Growth tier: 2,000 blocks
- Scale tier: 10,000+ blocks

**Solution:**
- If using paid tier: Increase `batch_size_blocks` to 2000-5000
- Update `config/config.json`:
  ```json
  "data_collection": {
    "batch_size_blocks": 2000,
    "rate_limit_per_sec": 10
  }
  ```

**Expected Impact:** 200-500x fewer API calls, 10-50x faster collection

---

### Priority 2: Moderate Impact (Worth Doing)

#### 2.1 Batch Block Timestamp Fetching
**Problem:** Sequential `eth_getBlockByNumber` calls for each unique block in logs.

**Current:**
```python
for block_num in unique_blocks:
    timestamp = self._get_block_timestamp(block_num)  # Individual RPC call
```

**Solution - Parallel Requests:**
```python
import concurrent.futures

def _fetch_block_timestamps_batch(self, block_numbers):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(self._get_block_timestamp, bn): bn
                   for bn in block_numbers}
        return {bn: future.result() for bn, future in futures.items()}
```

**Expected Impact:** 3-5x faster timestamp fetching for blocks with many trades

---

#### 2.2 Implement Connection Pooling & Better Retry Logic
**Problem:** Frequent connection resets, SSL errors, timeouts causing 2-37 minute delays.

**Current Issues:**
- `ConnectionResetError(54, 'Connection reset by peer')`
- `SSLEOFError`
- `Read timed out` (30-60 seconds)

**Solution:**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def _create_session(self):
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=20,
        pool_block=False
    )
    session.mount("https://", adapter)
    return session
```

**Expected Impact:** Reduces network errors by 50-80%, eliminates multi-minute delays

---

#### 2.3 Use Multiple Public RPC Endpoints (Load Balancing)
**Problem:** Only 2 endpoints, fallback logic only switches after errors.

**Current:**
```python
self.endpoints = [
    f"https://polygon-mainnet.g.alchemy.com/v2/{api_key}",
    "https://polygon-rpc.com"
]
```

**Solution - Add More Endpoints:**
```python
self.endpoints = [
    f"https://polygon-mainnet.g.alchemy.com/v2/{api_key}",
    "https://polygon-rpc.com",
    "https://rpc-mainnet.matic.network",
    "https://polygon-bor.publicnode.com",
    "https://polygon.llamarpc.com"
]

def _get_next_endpoint(self):
    # Round-robin instead of sequential
    endpoint = self.endpoints[self.current_endpoint_idx]
    self.current_endpoint_idx = (self.current_endpoint_idx + 1) % len(self.endpoints)
    return endpoint
```

**Expected Impact:** Distributes load, reduces individual endpoint rate limit hits

---

#### 2.4 Optimize Database Indexes
**Problem:** Large database (593 MB) may have index overhead during writes.

**Current Indexes:**
```sql
CREATE INDEX idx_block_number ON on_chain_trades(block_number);
CREATE INDEX idx_block_timestamp ON on_chain_trades(block_timestamp);
CREATE INDEX idx_condition_id ON on_chain_trades(condition_id);
```

**Solution:**
- Disable indexes during bulk collection
- Rebuild indexes after backfill complete
- Use covering indexes for common queries

```python
# Before bulk insert
cursor.execute("DROP INDEX IF EXISTS idx_block_number")
cursor.execute("DROP INDEX IF EXISTS idx_block_timestamp")

# ... bulk insert ...

# After complete
cursor.execute("CREATE INDEX idx_block_number ON on_chain_trades(block_number)")
cursor.execute("CREATE INDEX idx_block_timestamp ON on_chain_trades(block_timestamp)")
```

**Expected Impact:** 10-30% faster writes during bulk collection

---

### Priority 3: Advanced (High Effort, Variable Impact)

#### 3.1 Async I/O with asyncio + aiohttp
**Problem:** Synchronous requests block during I/O waits.

**Solution:** Rewrite collector to use async/await:
```python
import asyncio
import aiohttp

class AsyncAlchemyCollector:
    async def _fetch_logs_async(self, start_block, end_block):
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=payload) as resp:
                return await resp.json()

    async def collect_batch(self, start, end):
        logs = await self._fetch_logs_async(start, end)
        # Process concurrently
        tasks = [self._process_log(log) for log in logs]
        await asyncio.gather(*tasks)
```

**Pros:**
- 5-10x throughput with concurrent requests
- Better resource utilization

**Cons:**
- Major rewrite (~50% of code)
- Complexity increase
- Debugging harder

**Expected Impact:** 5-10x faster collection (after significant development time)

---

#### 3.2 Parallel Multi-Worker Collection
**Problem:** Single-threaded collection, only processes one batch at a time.

**Solution:** Divide block range across multiple workers:
```python
# Worker 1: Blocks 74M - 76M
# Worker 2: Blocks 76M - 78M
# Worker 3: Blocks 78M - 80M
# Worker 4: Blocks 80M - 82M

# Each worker:
# - Has own checkpoint
# - Writes to same database (with locking)
# - Uses different API keys or endpoints
```

**Pros:**
- 3-4x collection speed with 4 workers
- Can use multiple Alchemy API keys

**Cons:**
- Database contention (needs WAL mode + careful locking)
- Checkpoint management complex
- Requires orchestration

**Expected Impact:** 3-5x faster with 4 workers

---

#### 3.3 Upgrade to Alchemy Growth/Scale Tier
**Problem:** Free tier limited to 9 blocks/request and lower rate limits.

**Alchemy Pricing Tiers:**
| Tier | Blocks/Request | Rate Limit | Cost |
|------|----------------|------------|------|
| Free | 9 | Low | $0 |
| Growth | 2,000 | Medium | $49/month |
| Scale | 10,000+ | High | $399/month |

**Solution:** Upgrade to Growth tier ($49/month)

**Expected Impact:**
- 200x larger batches (9 → 2000 blocks)
- 10-50x faster collection
- Higher rate limits
- Pays for itself if time is valuable

---

### Priority 4: Nice to Have

#### 4.1 Caching Block Timestamps
**Problem:** Re-fetching same block timestamps across runs.

**Solution:**
```python
# Add block_timestamps table
CREATE TABLE block_timestamps (
    block_number INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL
);

# Check cache before RPC call
def _get_block_timestamp(self, block_number):
    cached = self._get_cached_timestamp(block_number)
    if cached:
        return cached
    timestamp = self._fetch_timestamp_rpc(block_number)
    self._cache_timestamp(block_number, timestamp)
    return timestamp
```

**Expected Impact:** 50-90% reduction in timestamp RPC calls for overlapping ranges

---

#### 4.2 Prometheus Metrics & Monitoring
**Problem:** Hard to track collection performance and bottlenecks in real-time.

**Solution:**
```python
from prometheus_client import Counter, Histogram, Gauge

trades_collected = Counter('alchemy_trades_collected', 'Total trades')
rpc_duration = Histogram('alchemy_rpc_duration_seconds', 'RPC latency')
current_block = Gauge('alchemy_current_block', 'Last processed block')
```

**Expected Impact:** Better visibility, faster debugging, trend analysis

---

#### 4.3 Compressed Database Storage
**Problem:** 593 MB database, will grow to 5-10 GB over time.

**Solution:**
```python
# Use ZSTD compression for blobs
import zstandard as zstd

# Or switch to DuckDB for columnar compression
# Or use PostgreSQL with toast compression
```

**Expected Impact:** 50-80% smaller database, faster queries

---

## Implementation Sequence

### Phase 1: Critical Fixes (Do Immediately)
1. **Fix incremental update batching** (1 hour)
   - Modify `incremental_update()` to chunk by `batch_size_blocks`
   - Test with `--incremental` flag

2. **Run token mapping** (5-15 minutes)
   ```bash
   python3 src/utils/market_mapper.py --update --update-trades
   ```

3. **Implement bulk database transactions** (2 hours)
   - Replace individual INSERTs with `executemany()`
   - Add transaction blocks around batches

### Phase 2: Quick Wins (1-2 days)
4. **Increase batch size** (if paid tier) (30 minutes)
5. **Batch block timestamp fetching** (3 hours)
6. **Improve retry logic & connection pooling** (4 hours)
7. **Add multiple RPC endpoints** (1 hour)

### Phase 3: Performance Boost (3-5 days)
8. **Optimize database indexes** (2 hours)
9. **Cache block timestamps** (3 hours)
10. **Consider Alchemy tier upgrade** (decision point)

### Phase 4: Advanced (Optional, 1-2 weeks)
11. **Async I/O rewrite** (if bottlenecks remain)
12. **Parallel multi-worker collection** (if time-critical)
13. **Prometheus monitoring** (if running long-term)

---

## Verification Steps

After implementing optimizations:

1. **Test incremental update:**
   ```bash
   python3 src/collectors/alchemy_collector.py --incremental
   ```
   - Verify no "Block range too large" errors
   - Check batch sizes in logs (should be ≤ batch_size_blocks)

2. **Verify token mapping:**
   ```sql
   SELECT COUNT(*) FROM token_condition_map;
   -- Should be > 0

   SELECT COUNT(*) FROM on_chain_trades WHERE condition_id IS NOT NULL;
   -- Should be > 0 (ideally 100% coverage)
   ```

3. **Benchmark collection speed:**
   - Before: Note trades/hour from logs
   - After: Compare trades/hour improvement
   - Target: 5-10x improvement with Priority 1+2 fixes

4. **Monitor error rates:**
   ```bash
   grep -i error logs/alchemy_collection.out | wc -l
   ```
   - Should decrease significantly after connection pooling

5. **Test continuous mode:**
   ```bash
   nohup python3 src/collectors/alchemy_collector.py --continuous >> logs/alchemy.out 2>&1 &
   ```
   - Run for 1 hour, check stability

---

## Expected Performance Improvements

| Optimization | Time Saved | Complexity |
|-------------|------------|------------|
| Fix batch logic | ∞ (unblocks collection) | Low |
| Run token mapping | N/A (unblocks downstream) | None |
| Bulk transactions | 2-5x faster writes | Low |
| Increase batch size | 10-50x fewer API calls | Low |
| Batch timestamps | 3-5x faster timestamps | Medium |
| Connection pooling | 50-80% fewer errors | Medium |
| Multiple endpoints | 30-50% better reliability | Low |
| Async I/O | 5-10x throughput | High |
| Parallel workers | 3-5x speed | High |
| Alchemy upgrade | 10-50x collection speed | None ($) |

**Combined Phase 1+2 Expected Impact:** 10-30x overall speedup

---

## Configuration Changes

`config/config.json` (recommended settings after fixes):

```json
{
  "alchemy_api_key": "kRJDa-58lYVF4H7p07GI5",
  "data_collection": {
    "backfill_months": 6,
    "batch_size_blocks": 2000,  // If paid tier, else 9
    "rate_limit_per_sec": 10,   // If paid tier, else 5
    "max_retries": 5,
    "retry_backoff_base": 2,
    "connection_timeout_sec": 60,
    "enable_timestamp_cache": true,
    "bulk_insert_batch_size": 1000
  }
}
```

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Batch logic fix | Low | Test with small ranges first |
| Token mapping | Low | Read-only + UPDATE query, can rollback |
| Bulk transactions | Low | Database has UNIQUE constraints |
| Async rewrite | High | Keep original code, gradual migration |
| Parallel workers | Medium | WAL mode + careful locking, test locally |
| Alchemy upgrade | Low | Can downgrade, month-to-month |

---

## Estimated Timeline

- **Phase 1 (Critical):** 3-4 hours
- **Phase 2 (Quick Wins):** 1-2 days
- **Phase 3 (Performance):** 3-5 days
- **Phase 4 (Advanced):** 1-2 weeks (optional)

**Recommended:** Start with Phase 1 immediately to unblock collection and downstream processes.

---

## Summary of Key Issues Found

### Critical Issues:
1. **Batch size bug** - Incremental updates ignore batch_size_blocks, try to fetch 7.8M blocks at once
2. **Token mapping incomplete** - 0% of 1.66M trades have condition_id mapped, blocking all downstream use
3. **Network instability** - Connection resets, SSL errors, timeouts causing 2-37 minute delays

### Performance Issues:
4. **Suboptimal database writes** - Individual INSERTs instead of bulk transactions
5. **Sequential timestamp fetching** - One RPC call per block instead of parallel/batch
6. **Limited batch size** - Free tier: 9 blocks max (paid tier: 2000 blocks)

### Quick Wins Available:
- Fix batch logic → Unblocks collection
- Run token mapping → Unblocks trading
- Bulk transactions → 2-5x faster writes
- Connection pooling → 50-80% fewer errors
- **Combined impact: 10-30x speedup**
