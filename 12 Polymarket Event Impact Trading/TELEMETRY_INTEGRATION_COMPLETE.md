# Telemetry Integration - Phase 3 Complete

> **Status:** ✅ Complete (2026-02-24)
>
> Runtime metric monitoring integrated with constraint validation system.
> System now validates both static code patterns AND live runtime behavior.

## Overview

Phase 3 adds **runtime telemetry monitoring** to the constraint validation system,
enabling continuous validation of system health metrics against defined thresholds.
This transforms the system from validating "what the code looks like" to also
validating "how the system is actually behaving."

##

 What Was Implemented

### 1. Telemetry System (`src/monitoring/telemetry.py`) ✅

**Core Features:**
- ✅ SQLite-based metric storage with timestamps
- ✅ Two data types: Metrics (numeric values) and Events (discrete occurrences)
- ✅ Query interface for constraint validation
- ✅ Historical metric tracking
- ✅ Automatic system metric collection
- ✅ Threshold checking with multiple operators

**Database Schema:**

```sql
-- Metrics: time-series numeric data
CREATE TABLE metrics (
    timestamp TEXT,
    metric_name TEXT,
    metric_value REAL,
    metadata TEXT,
    source TEXT
);

-- Events: discrete occurrences
CREATE TABLE events (
    timestamp TEXT,
    event_type TEXT,
    event_data TEXT,
    severity TEXT,
    source TEXT
);
```

**Metrics Collected:**

| Metric | Source | Description |
|--------|--------|-------------|
| `positions_without_sl_tp_{bot}` | PositionManager | Positions missing stop-loss/take-profit |
| `open_positions_{bot}` | PositionManager | Current open position count |
| `bots_silent` | BotHealthMonitor | Count of silent/crashed bots |
| `circuit_breaker_trips` | Trading bots | Circuit breaker activations |
| `websocket_fallback_rate` | OrderbookManager | WebSocket fallback percentage |
| `slippage_rejection_rate` | TradeExecutor | Trades rejected for slippage |

**API:**

```python
from monitoring.telemetry import TradeTelemetry

telemetry = TradeTelemetry()

# Record metric
telemetry.record_metric('positions_without_sl_tp', 0)

# Record event
telemetry.record_event('circuit_breaker_trip',
                       event_data={'reason': '3 losses'},
                       severity='warning')

# Query latest metrics
metrics = telemetry.get_latest_metrics()

# Check threshold
ok = telemetry.check_metric_threshold('websocket_fallback_rate', 0.20, 'lte')

# Get historical data
history = telemetry.get_metric_history('slippage_rejection_rate', hours=24)
```

### 2. Telemetry Helpers (`src/monitoring/telemetry_helpers.py`) ✅

**Convenience functions for trading bots:**

```python
from monitoring.telemetry_helpers import (
    record_position_opened,
    record_circuit_breaker_trip,
    record_slippage_rejection,
    record_websocket_fallback,
    update_open_positions_count
)

# In trading bot code:
record_position_opened(
    market_id='0x123',
    outcome='YES',
    size=100.0,
    entry_price=0.65,
    has_sl_tp=True,
    source='event_trader'
)

record_circuit_breaker_trip(
    consecutive_losses=3,
    cooldown_hours=4.0,
    source='price_level_trader'
)
```

**Available Helpers:**
- `record_trade_attempt()` - Trade decisions (executed/rejected/skipped)
- `record_position_opened()` - New positions
- `record_circuit_breaker_trip()` - Circuit breaker activations
- `record_sl_tp_exit()` - Stop-loss/take-profit exits
- `record_slippage_rejection()` - Slippage-based rejections
- `record_websocket_fallback()` - WebSocket fallbacks
- `record_feature_drift_alert()` - ML feature drift
- `update_open_positions_count()` - Position count updates
- `update_balance()` - Balance tracking

### 3. Constraint Validation Integration ✅

**Updated `scripts/validate_constraints.py`:**

The `_check_telemetry()` method now:
- ✅ Collects current system metrics
- ✅ Queries telemetry database
- ✅ Checks metrics against thresholds
- ✅ Reports violations/warnings
- ✅ Handles missing metrics gracefully

**Example Constraint with Telemetry:**

```yaml
constraints:
  risk_management:
    - id: RISK-001
      title: "Stop-loss and take-profit always active"
      validation:
        - type: integration_test
          command: pytest tests/integration/test_position_monitoring.py
      telemetry:
        - metric: positions_without_sl_tp
          threshold: 0
          alert: critical
          description: "Count of open positions missing SL/TP"
```

**Telemetry Validation Output:**

```
📊 Telemetry Checks:
   ✅ positions_without_sl_tp: 0 ≤ 0
   ✅ circuit_breaker_trips: No events
   ❌ websocket_fallback_rate: 0.25 > 0.20
```

### 4. Telemetry Collection Script ✅

**File:** `scripts/collect_telemetry.py`

**Features:**
- ✅ One-shot or daemon mode
- ✅ Configurable collection interval
- ✅ Optional constraint validation after collection
- ✅ Comprehensive logging

**Usage:**

```bash
# One-shot collection
python scripts/collect_telemetry.py

# Continuous collection (every 5 minutes)
python scripts/collect_telemetry.py --daemon --interval 300

# Collect + validate constraints
python scripts/collect_telemetry.py --validate

# Daemon with validation
python scripts/collect_telemetry.py --daemon --validate --interval 300
```

**Cron Integration:**

```bash
# Add to crontab for periodic collection
# Every 5 minutes
*/5 * * * * cd /path/to/project && python scripts/collect_telemetry.py

# Every hour with validation
0 * * * * cd /path/to/project && python scripts/collect_telemetry.py --validate
```

## Architecture

### Telemetry Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                       Trading Bots                              │
│  - Event Trader                                                 │
│  - Price Level Trader                                           │
│  - Short Expiry Trader                                          │
└──────┬──────────────────────────────────────────────────────────┘
       │
       │ telemetry_helpers.record_*()
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TradeTelemetry                                │
│  - record_metric()                                              │
│  - record_event()                                               │
│  - collect_system_metrics()                                     │
└──────┬──────────────────────────────────────────────────────────┘
       │
       │ Stores in SQLite
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   data/telemetry.db                             │
│  - metrics table (time-series data)                             │
│  - events table (discrete occurrences)                          │
└──────┬──────────────────────────────────────────────────────────┘
       │
       │ Queried by
       ▼
┌─────────────────────────────────────────────────────────────────┐
│            validate_constraints.py                              │
│  - Reads CONSTRAINTS.yml telemetry definitions                  │
│  - Queries telemetry database                                   │
│  - Checks thresholds                                            │
│  - Reports violations                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Metric Collection Flow

```
┌──────────────────────┐
│ collect_telemetry.py │
│ (Manual/Cron/Daemon) │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│ TradeTelemetry.collect_system_metrics()      │
└──────────┬───────────────────────────────────┘
           │
           ├─► _collect_position_metrics()
           │   └─► PositionManager.get_open_positions()
           │       └─► Count positions without SL/TP
           │
           ├─► _collect_bot_health_metrics()
           │   └─► BotHealthMonitor.check_bot_liveness()
           │       └─► Count silent bots
           │
           └─► _collect_trading_metrics()
               └─► Query bot state (future)
```

## Integration with Existing Constraints

All 13 constraints can now have telemetry checks:

### Architecture Constraints

**ARCH-004: WebSocket orderbook with fallback**
```yaml
telemetry:
  - metric: websocket_fallback_rate
    threshold: 0.20
    alert: warning
    description: "Alert if >20% of requests use fallback"
```

### Risk Management Constraints

**RISK-001: Stop-loss/take-profit always active**
```yaml
telemetry:
  - metric: positions_without_sl_tp
    threshold: 0
    alert: critical
    description: "Count of open positions missing SL/TP"
```

**RISK-002: Circuit breaker after 3 losses**
```yaml
telemetry:
  - metric: circuit_breaker_trips
    alert_on_change: true
    alert: warning
    description: "Alert when circuit breaker activates"
```

**RISK-003: Slippage estimation before execution**
```yaml
telemetry:
  - metric: slippage_rejection_rate
    threshold: 0.30
    alert: warning
    description: "Alert if >30% trades rejected for slippage"
```

### Model Quality Constraints

**ML-002: Feature drift detection**
```yaml
telemetry:
  - metric: kendall_tau_rank_stability
    threshold: 0.70
    alert: warning
  - metric: top_k_overlap
    threshold: 0.60
    alert: critical
```

### Operations Constraints

**OPS-001: Bot health monitoring**
```yaml
telemetry:
  - metric: bots_silent
    threshold: 0
    alert: critical
    description: "Count of bots without activity >30 minutes"
```

## Benefits Achieved

### 1. **Runtime Validation** ✅
- System behavior validated, not just code structure
- Catches issues that static analysis misses
- Continuous monitoring vs point-in-time checks

### 2. **Early Warning System** ⚡
- Alerts before problems become critical
- Example: WebSocket fallback rate climbing → investigate before outage
- Example: Positions without SL/TP → fix before losses

### 3. **Historical Analysis** 📊
- Metrics stored with timestamps
- Trend analysis possible
- Post-mortem investigation enabled

### 4. **Integrated Validation** 🔗
- Telemetry checks part of CI/CD pipeline
- Same validation locally and in production
- No separate monitoring system needed

### 5. **Low Overhead** 💨
- Async metric recording (non-blocking)
- SQLite for efficiency
- Minimal impact on trading performance

## Usage Examples

### For Bot Developers

**Adding Telemetry to Existing Bot:**

```python
# At top of file
from monitoring.telemetry_helpers import (
    record_position_opened,
    record_circuit_breaker_trip,
    update_open_positions_count
)

class MyTradingBot:
    def __init__(self):
        self.bot_name = 'my_trader'

    def execute_trade(self, market_id, outcome, size, entry_price):
        # ... execute trade ...

        # Record telemetry
        record_position_opened(
            market_id=market_id,
            outcome=outcome,
            size=size,
            entry_price=entry_price,
            has_sl_tp=True,  # Always set SL/TP!
            source=self.bot_name
        )

        # Update position count
        positions = self.position_manager.get_open_positions()
        update_open_positions_count(self.bot_name, len(positions))

    def check_circuit_breaker(self):
        if self.consecutive_losses >= 3:
            self.circuit_breaker_active = True

            # Record telemetry
            record_circuit_breaker_trip(
                consecutive_losses=self.consecutive_losses,
                cooldown_hours=4.0,
                source=self.bot_name
            )
```

### For Operations

**Manual Metric Collection:**

```bash
# Collect metrics now
python scripts/collect_telemetry.py

# View metrics
python -c "from monitoring.telemetry import TradeTelemetry; \
           t = TradeTelemetry(); \
           print(t.get_latest_metrics())"
```

**Continuous Monitoring:**

```bash
# Run as daemon (every 5 minutes)
nohup python scripts/collect_telemetry.py --daemon --interval 300 >> logs/telemetry.log 2>&1 &

# Or use systemd service (recommended)
sudo systemctl start polymarket-telemetry
```

**Validation with Telemetry:**

```bash
# Collect metrics + validate constraints
python scripts/collect_telemetry.py --validate

# Or run validation separately (uses existing telemetry data)
python scripts/validate_constraints.py
```

## Cron Integration

Add to crontab for automated collection:

```bash
# Edit crontab
crontab -e

# Add lines:
# Collect metrics every 5 minutes
*/5 * * * * cd /path/to/project && python scripts/collect_telemetry.py

# Validate constraints every hour
0 * * * * cd /path/to/project && python scripts/collect_telemetry.py --validate

# Daily telemetry summary
0 8 * * * cd /path/to/project && python scripts/analyze_telemetry.py --daily
```

## Monitoring Dashboard (Future)

Phase 3 lays the groundwork for a monitoring dashboard:

**Planned Features:**
- Real-time metric visualization
- Historical trend charts
- Alert history
- Constraint violation timeline
- Bot health overview

**Implementation:** Streamlit or Grafana dashboard reading from `telemetry.db`

## Troubleshooting

### Telemetry Not Collecting

**Problem:** No metrics in database

**Solutions:**
1. Check telemetry.db exists: `ls -lh data/telemetry.db`
2. Run collection manually: `python scripts/collect_telemetry.py`
3. Check bot integration: Ensure bots import telemetry_helpers
4. Check logs for errors

### Metrics Always Zero

**Problem:** Metrics show 0 even though system is active

**Solutions:**
1. Verify bots are calling telemetry_helpers functions
2. Check that bots are actually running: `ps aux | grep trader`
3. Run `collect_system_metrics()` to refresh from source
4. Check database timestamps are recent

### Validation Shows "Telemetry Not Available"

**Problem:** Constraint validation can't load telemetry

**Solutions:**
1. Verify src/monitoring/telemetry.py exists
2. Check Python path includes src/ directory
3. Install any missing dependencies
4. Run manually: `python -c "from monitoring.telemetry import TradeTelemetry"`

## Files Created/Modified

**New Files:**
- `src/monitoring/telemetry.py` - Core telemetry system (500+ lines)
- `src/monitoring/telemetry_helpers.py` - Convenience functions for bots (300+ lines)
- `scripts/collect_telemetry.py` - Collection script (150+ lines)
- `TELEMETRY_INTEGRATION_COMPLETE.md` - This file

**Modified Files:**
- `scripts/validate_constraints.py` - Added real telemetry checking (replaced stub)

## Testing

### Manual Testing

```bash
# Test telemetry recording
python -c "
from monitoring.telemetry import TradeTelemetry
t = TradeTelemetry()
t.record_metric('test_metric', 42)
metrics = t.get_latest_metrics()
print('test_metric' in metrics)  # Should print: True
"

# Test collection
python scripts/collect_telemetry.py

# Test validation with telemetry
python scripts/validate_constraints.py --category risk_management
```

### Integration Testing

```python
# tests/integration/test_telemetry.py
def test_telemetry_integration():
    from monitoring.telemetry import TradeTelemetry
    from monitoring.telemetry_helpers import record_position_opened

    t = TradeTelemetry(db_path='data/test_telemetry.db')

    # Record a position
    record_position_opened(
        market_id='test',
        outcome='YES',
        size=100,
        entry_price=0.65,
        has_sl_tp=True,
        source='test_bot'
    )

    # Verify recorded
    events = t.get_recent_events(hours=1, event_type='position_opened')
    assert len(events) > 0
    assert events[0]['event_data']['market_id'] == 'test'
```

## Next Steps

### Phase 4: Feedback Loops & Self-Improvement

With telemetry in place, the system can now:

1. **Auto-detect patterns** - Analyze failure telemetry
2. **Suggest constraints** - Propose new constraints from patterns
3. **Auto-remediation** - Fix common issues automatically
4. **Performance tracking** - Measure constraint effectiveness

### Future Enhancements

- **Grafana Integration** - Visualize metrics
- **Prometheus Export** - Export metrics in Prometheus format
- **Alerting System** - Telegram/Email alerts on violations
- **ML-Based Anomaly Detection** - Detect unusual patterns
- **Auto-scaling** - Adjust resources based on metrics

## Conclusion

Phase 3 transforms the constraint validation system from **static code analysis**
to **runtime behavior monitoring**. The system now validates:

- ✅ **What the code looks like** (Phase 1: Constraints)
- ✅ **How the code runs in CI** (Phase 2: CI/CD)
- ✅ **How the system actually behaves** (Phase 3: Telemetry)

This creates a **comprehensive safety net** that catches issues at multiple levels:
- Import linters catch forbidden patterns
- Structural tests verify architecture
- Telemetry validates runtime behavior
- All automated in CI/CD pipeline

The Polymarket trading system is now **self-validating**, **self-monitoring**, and
ready for the next evolution: **self-improving** (Phase 4).

---

**Last updated:** 2026-02-24
**Status:** ✅ Phase 3 Complete
**Next:** Phase 4 - Feedback Loops & Self-Improvement
