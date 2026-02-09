# Integrating Price Tracker into Trader

## Step 1: Add Import to trader.py

Add this import at the top of `trader.py`:

```python
from price_tracker import PriceTracker
```

## Step 2: Initialize Tracker in __init__

In the `PolymarketTrader.__init__()` method, add:

```python
def __init__(self, config: Dict):
    # ... existing code ...

    # Add price tracker
    self.price_tracker = PriceTracker()
    logger.info("Price tracker initialized")
```

## Step 3: Track Events in process_signal

In the `process_signal()` method, add tracking after feature extraction:

```python
def process_signal(self, event, market: Dict):
    # ... existing code up to line 302 ...

    features_df = pd.DataFrame([features])

    # ===== ADD THIS: Track the event-market pair =====
    try:
        self.price_tracker.track_event(
            event=event,
            market=market,
            entry_price=current_price,
            features=features  # Use the raw features dict
        )
    except Exception as e:
        logger.error(f"Error tracking event: {e}")
    # ===== END ADDITION =====

    # Generate signal (existing code continues)
    signal = self.signal_generator.generate_signal(features_df, current_price)
    # ... rest of existing code ...
```

## Why Track All Events?

We track **every event-market match**, not just trades, because:
- Gives us more training data
- Captures false negatives (events we should have traded)
- Learns from both actions and inactions
- Builds comprehensive dataset

## Complete Integration Code

Here's the exact code to add to `trader.py`:

### At the top (line ~15):
```python
from price_tracker import PriceTracker
```

### In __init__ method (around line 180):
```python
# Initialize price tracker
self.price_tracker = PriceTracker()
logger.info("✓ Price tracker initialized")
```

### In process_signal method (after line 304):
```python
# Track this event-market pair for later labeling
try:
    self.price_tracker.track_event(
        event=event,
        market=market,
        entry_price=current_price,
        features=features
    )
    logger.info(f"  → Tracking price movement for: {market.get('question')[:40]}...")
except Exception as e:
    logger.error(f"Error tracking event: {e}")
```

That's it! The tracker is now integrated.
