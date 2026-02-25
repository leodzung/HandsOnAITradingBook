# Polymarket Event Impact Trading System

A **self-validating, self-monitoring, and self-improving** algorithmic trading system for Polymarket prediction markets. Features machine learning-based event detection, real-time orderbook analysis, and autonomous constraint validation using harness engineering principles.

---

## ⚡ Quick Start (5 Minutes)

```bash
# Install dependencies
pip install -r requirements.txt

# Configure (if needed)
cp config/config.json.example config/config.json

# Validate system constraints
python scripts/validate_constraints.py

# Start a bot (paper trading by default)
python src/bots/trader.py
```

**Paper Trading Mode** (Default):
- Event trader: $1000 virtual balance
- Price-level trader: $500 virtual balance
- Short-expiry trader: $500 virtual balance

Set `"paper_trading": false` in config to trade with real funds.

---

## 📐 System Architecture

### Three Trading Strategies

| Bot | Strategy | Position DB |
|-----|----------|-------------|
| **Event Trader** | ML + news event impact prediction | `data/positions.db` |
| **Price-Level Trader** | Mean reversion at support/resistance | `data/positions_price_level.db` |
| **Short-Expiry Trader** | Time-decay arbitrage (<7 days) | `data/positions_short_expiry.db` |

### Centralized Services (Single Source of Truth)

All bots use these shared services to enforce consistency:

```
┌──────────────────────────────────────────────┐
│             Trading Bots (3)                 │
│  Event | Price-Level | Short-Expiry          │
└────────────────┬─────────────────────────────┘
                 │
        ┌────────┴────────┐
        │ Core Services   │
        ├─────────────────┤
        │ • PriceFetcher  │  ← Single source of truth for prices
        │ • TradeExecutor │  ← Centralized validation pipeline
        │ • PositionMgr   │  ← SQLite persistence
        │ • OrderbookMgr  │  ← WebSocket + fallback
        └─────────────────┘
```

#### **CRITICAL**: PriceFetcher Pattern

**Rule**: ALWAYS use PriceFetcher for ANY price data.

✅ **Correct**:
```python
from core.price_fetcher import PriceFetcher
entry_prices = price_fetcher.get_entry_prices(market_id)
```

❌ **Forbidden** (auto-detected by constraints):
```python
price = market['bestAsk']  # NEVER
price = market['outcomePrices']['YES']  # NEVER
```

**Why**: Handles YES/NO confusion, validates prices, manages WebSocket fallback.

---

## 🛡️ Constraint Validation System (Harness Engineering)

### Philosophy

> **"If you need documentation to explain how to use a system, the system isn't well-designed."**

Instead of 104 markdown files that get stale, we use:
- ✅ **CONSTRAINTS.yml** - Machine-readable, auto-validated rules
- ✅ **Self-documenting code** - Good names, clear structure
- ✅ **Git commits** - Historical record
- ❌ NOT markdown documentation

### Four Phases

| Phase | Feature | Benefit |
|-------|---------|---------|
| **1. Foundation** | Machine-readable constraints | Prevents regressions automatically |
| **2. CI/CD** | GitHub Actions validation | Runs on every commit |
| **3. Telemetry** | Runtime metric monitoring | Validates actual behavior |
| **4. Self-Improvement** | Pattern detection + auto-remediation | System learns from failures |

### Validate Constraints

```bash
# Validate all constraints
python scripts/validate_constraints.py

# Validate specific constraint
python scripts/validate_constraints.py --id ARCH-001

# CI mode (used in GitHub Actions)
python scripts/validate_constraints.py --ci
```

### Example Constraint

**ARCH-001: PriceFetcher is single source of truth**
```yaml
validation:
  - type: import_linter
    forbidden_patterns: ["market\\['bestBid'\\]"]
  - type: structural_test
    test_file: tests/structural/test_price_fetcher_constraint.py
telemetry:
  - metric: direct_market_access_violations
    threshold: 0
    alert: critical
```

If you try to access `market['bestBid']` directly:
- ❌ Import linter fails
- ❌ Structural tests fail
- ❌ CI blocks your commit
- ✅ System enforces correct pattern automatically

---

## 🔧 Core Services

### 1. PriceFetcher (`src/core/price_fetcher.py`)

**Single source of truth for ALL price data.**

```python
from core.price_fetcher import PriceFetcher

# Entry prices (ASK - what you pay to buy)
entry_prices = price_fetcher.get_entry_prices(market_id)

# Exit prices (BID - what you get when selling)
exit_prices = price_fetcher.get_exit_prices(market_id)
```

**Handles**:
- YES/NO price confusion detection
- Price validation (0.01 ≤ price ≤ 0.99)
- WebSocket orderbook (real-time) or REST fallback
- Polymarket API quirks (YES + NO ≠ 1.0)

### 2. OrderbookManager (`src/core/orderbook_manager.py`)

Dual-mode orderbook source with automatic fallback.

- **WebSocket Mode** (primary): Real-time updates, <1s latency
- **REST Mode** (fallback): Synthetic orderbook from `/price` endpoint
- **Auto-reconnection**: Exponential backoff (1s → 60s with jitter)

### 3. TradeExecutor (`src/core/trade_executor.py`)

Centralized validation: price → slippage → execution.

```python
executor.execute_trade(
    market_id=market_id,
    outcome='YES',
    size=100.0,
    expected_price=0.65,
    order_type='MARKET'
)
```

**Validates**:
1. Price reasonableness
2. Slippage vs max allowed
3. Balance sufficiency
4. Position limits

### 4. PositionManager (`src/core/position_manager_v2.py`)

SQLite-based persistence that survives restarts.

```python
from core.position_manager_v2 import PositionManager, DuplicatePositionError

pm = PositionManager(db_path='data/positions.db')
pm.save_position(market_id, outcome='YES', entry_price=0.65, size=100)
```

**Key Pattern**: `DuplicatePositionError` maintains architectural boundary (bots don't import `sqlite3`).

---

## 📊 Telemetry & Self-Improvement

### Phase 3: Telemetry Integration

**System collects 10+ runtime metrics:**
- `positions_without_sl_tp_{bot}` - Missing stop-loss/take-profit
- `open_positions_{bot}` - Current position count
- `bots_silent` - Silent/crashed bots
- `circuit_breaker_trips` - Circuit breaker activations
- `websocket_fallback_rate` - WebSocket fallback %
- `slippage_rejection_rate` - Rejected trades

**Integration**:
```python
from monitoring.telemetry_helpers import record_position_opened

record_position_opened(
    market_id=market_id,
    outcome='YES',
    size=100.0,
    entry_price=0.65,
    has_sl_tp=True,
    source='event_trader'
)
```

### Phase 4: Self-Improvement

**Pattern Detection** (5 algorithms):
- Recurring events (e.g., circuit breaker trips 5+ times)
- Event clusters (e.g., 3 WebSocket failures within 30 min)
- Event sequences (e.g., drift → prediction errors)
- Metric violations (e.g., slippage >30% for 10 samples)
- Correlated failures (e.g., bot silence + WebSocket fallback)

**Analyze Patterns**:
```bash
# Analyze last week
python3 scripts/analyze_patterns.py

# Generate constraint suggestions
python3 scripts/analyze_patterns.py --suggest --output suggestions.yml
```

**Auto-Remediation**:
- ✅ Safe actions (auto-run): Cleanup temp files, compact database
- ⏸️ Manual approval: Restart bots, reset WebSocket

**Automated via Cron**:
- Telemetry collection: Every 5 minutes
- Pattern analysis: Daily at 8 AM
- Auto-remediation: Every 4 hours
- Constraint validation: Hourly

---

## 🚀 Development Workflow

### 1. Make Changes
Edit code, add features, fix bugs.

### 2. Validate Locally
```bash
python scripts/validate_constraints.py
pytest tests/structural/
```

### 3. Commit & Push
```bash
git commit -m "Description"
git push origin master
# GitHub Actions runs constraint validation automatically
```

### 4. Review
- Green ✅: All constraints pass → safe to merge
- Red ❌: Violations → fix before merging

---

## ⚙️ Configuration

### Bot Configs

**Event Trader**: `config/config.json`
```json
{
  "paper_trading": true,
  "initial_balance": 1000,
  "max_positions": 5,
  "stop_loss_pct": 0.15,
  "take_profit_pct": 0.25,
  "orderbook_source": "websocket"
}
```

**API Credentials**: Create `config/secrets.json` (gitignored)
```json
{
  "polymarket": {
    "api_key": "your_key",
    "secret": "your_secret"
  }
}
```

---

## 🔍 Critical Polymarket API Quirks

### 1. ALWAYS Use `/price` Endpoint
- ❌ `/book` endpoint is BROKEN (stale data)
- ✅ `/price` endpoint is CORRECT (matches web UI)

### 2. YES + NO ≠ 1.0
Market maker spread: `YES + NO ≈ 1.03-1.10` (NOT 1.0!)

### 3. WebSocket Orderbook
- ✅ All bots use real-time WebSocket
- ✅ Auto-fallback to REST if unavailable
- ✅ Exponential backoff reconnection

---

## 🗂️ Databases

| Database | Purpose |
|----------|---------|
| `positions.db` | Event trader positions |
| `positions_price_level.db` | Price-level trader positions |
| `positions_short_expiry.db` | Short-expiry trader positions |
| `telemetry.db` | Runtime metrics and events |
| `price_tracking.db` | Price history |

---

## 🧪 Testing

```bash
# Structural tests (architectural boundaries)
pytest tests/structural/ -v

# Integration tests (end-to-end)
pytest tests/integration/ -v

# All tests with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

---

## 📦 Project Structure

```
12 Polymarket Event Impact Trading/
├── src/
│   ├── bots/                       # Trading bots
│   ├── core/                       # Core services (PriceFetcher, etc.)
│   ├── features/                   # Feature extraction
│   └── monitoring/                 # Telemetry & self-improvement
├── scripts/
│   ├── validate_constraints.py     # Constraint validation
│   ├── collect_telemetry.py        # Telemetry collection
│   └── analyze_patterns.py         # Pattern analysis
├── tests/
│   ├── structural/                 # Architectural tests
│   └── integration/                # End-to-end tests
├── config/                         # Configuration files
├── data/                           # Databases
├── logs/                           # Log files
├── CONSTRAINTS.yml                 # Machine-readable constraints
└── README.md                       # This file
```

---

## 🆘 Troubleshooting

### Bot Not Finding Markets
- Check expiry filters in config
- Verify API connection
- Review market filters

### Prices Always 0.5
- ✅ Use PriceFetcher (never direct market access)
- Check `/price` endpoint (not `/book`)

### Position Manager Duplicate Key Error
Expected! Position already exists. Catch `DuplicatePositionError`.

### WebSocket Disconnecting
Expected! Auto-reconnection handles this. Monitor `websocket_fallback_rate`.

### Constraint Validation Failing
1. Read error message
2. Run locally: `python scripts/validate_constraints.py --id <ID>`
3. Fix violation
4. Re-validate

---

## 🎯 Production Deployment

### Pre-Production Checklist
1. ✅ Paper trading validation (2+ weeks)
2. ✅ All constraints passing
3. ✅ Telemetry collecting
4. ⏳ Risk parameters tuned
5. ⏳ Monitoring configured

### Go Live
1. Set `paper_trading = false`
2. Start with small balance ($100)
3. Monitor closely for 24 hours
4. Gradually increase positions

---

## 📚 Key Concepts

### Harness Engineering
Systems validate themselves through executable constraints rather than documentation.

**Before** (traditional):
```markdown
⚠️ IMPORTANT: Always use PriceFetcher!
```
Developers forget, docs get ignored.

**After** (harness engineering):
```yaml
forbidden_patterns: ["market\\['bestBid'\\]"]
```
Automated validation catches violations before merge.

### Single Source of Truth
**Problem**: Multiple places to access data = inconsistencies

**Solution**: Centralized services (PriceFetcher, TradeExecutor, etc.)

### Constraint Validation
**Not**: Markdown docs that get stale
**Instead**: Machine-readable YAML that auto-validates

---

## 📖 Resources

- **Polymarket Docs**: https://docs.polymarket.com/
- **CLOB API**: https://docs.polymarket.com/#clob-api
- **GitHub Actions**: Check constraint validation status
- **Constraints**: See `CONSTRAINTS.yml` for all enforced rules

---

## 🤝 Contributing

1. Read `CONSTRAINTS.yml` to understand enforced rules
2. Make changes
3. Run `python scripts/validate_constraints.py`
4. All constraints must pass before merge
5. Commit and push

---

## 📄 License

See main repository LICENSE

---

**System Status**: ✅ Self-validating | ✅ Self-monitoring | ✅ Self-improving

**Last Updated**: 2026-02-25
