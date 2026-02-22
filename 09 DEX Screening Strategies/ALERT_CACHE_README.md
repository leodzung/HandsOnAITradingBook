# Alert Cache System

## Overview

The alert cache prevents sending duplicate "best available" emails for the same token within a 1-hour window. This solves the problem of receiving the same low-quality token alert every 10 minutes when cron runs.

## How It Works

### 1. **Cache File**: `alert_cache.json`

Stores recently alerted tokens with timestamps:

```json
{
  "0x5aE6ABD70147d2214CaC2E2DEE7af15235bF4444": {
    "symbol": "BRAIN/WBNB",
    "timestamp": "2025-11-09T15:53:47.147081",
    "score": 59.1,
    "is_best_available": true
  }
}
```

### 2. **Caching Rules**

**High-Quality Alerts (Score >= 70)**:
- ✅ **Always sent** (never cached/blocked)
- These are genuine opportunities worth alerting on
- Cached for tracking, but won't block future alerts

**"Best Available" Alerts (Score < 70)**:
- ⏳ **Cached for 1 hour**
- If same token found again within 1 hour: **SKIP EMAIL**
- After 1 hour: Can alert again if still best available

### 3. **Cache Cleanup**

- Automatic cleanup runs on every scan
- Entries older than 2 hours are removed
- Keeps cache file small and performant

## Usage Example

### First Run (15:53:47):
```
📊 No opportunities above threshold (70)
Highest scorer: BRAIN/WBNB with 59.1/100
Sending 'best available' email...
✅ Market update email sent!
```

**Cache Created:**
```json
{
  "0x5aE6ABD7...": {
    "symbol": "BRAIN/WBNB",
    "timestamp": "2025-11-09T15:53:47",
    "score": 59.1,
    "is_best_available": true
  }
}
```

### Second Run (15:54:12) - 25 seconds later:
```
📊 No opportunities above threshold (70)
Highest scorer: BRAIN/WBNB with 59.1/100
⏭️  Skipping 'best available' email - BRAIN/WBNB was alerted 0 minutes ago
   (Previous alert: 15:53:47, Score: 59.1/100)
   Will retry next scan cycle (10 minutes)
```

**Result: No duplicate email sent!**

### Tenth Run (16:53:48) - 1 hour later:
```
📊 No opportunities above threshold (70)
Highest scorer: BRAIN/WBNB with 59.1/100
Sending 'best available' email...
✅ Market update email sent!
```

**Result: Email sent again (cache expired)**

## Configuration

### Change Cache Duration

Edit `run_with_email_alerts_v2.py`:

```python
# Default: 1 hour
if was_recently_alerted(token_address, alert_cache, hours=1):

# Change to 2 hours:
if was_recently_alerted(token_address, alert_cache, hours=2):

# Change to 30 minutes:
if was_recently_alerted(token_address, alert_cache, hours=0.5):
```

### Disable Caching

To disable caching entirely (not recommended):

```python
# Comment out the cache check:
# if was_recently_alerted(token_address, alert_cache, hours=1):
#     print(f"⏭️  Skipping...")
#     ...
# else:

# Always send:
print("Sending 'best available' email...")
# ... rest of email sending code
```

## Cache File Management

### View Current Cache

```bash
cat alert_cache.json
```

### Clear Cache Manually

```bash
rm alert_cache.json
```

Next run will create a fresh cache.

### Check Cache Age

```bash
cat alert_cache.json | python3 -m json.tool
```

Look at `timestamp` field to see when each token was alerted.

## Benefits

### Without Caching (Old Behavior):
```
15:00 → Email: "BRAIN/WBNB (59.1/100)"
15:10 → Email: "BRAIN/WBNB (59.1/100)"  ← Duplicate!
15:20 → Email: "BRAIN/WBNB (59.1/100)"  ← Duplicate!
15:30 → Email: "BRAIN/WBNB (59.1/100)"  ← Duplicate!
15:40 → Email: "BRAIN/WBNB (59.1/100)"  ← Duplicate!
15:50 → Email: "BRAIN/WBNB (59.1/100)"  ← Duplicate!
```

**Result: 6 emails in 1 hour for the same token**

### With Caching (New Behavior):
```
15:00 → Email: "BRAIN/WBNB (59.1/100)"  ✅ Sent
15:10 → Skipped (cached)
15:20 → Skipped (cached)
15:30 → Skipped (cached)
15:40 → Skipped (cached)
15:50 → Skipped (cached)
16:00 → Email: "BRAIN/WBNB (59.1/100)"  ✅ Sent (cache expired)
```

**Result: 1 email per hour maximum**

## Important Notes

### High-Quality Alerts Are Never Blocked

If a token suddenly improves and crosses the 70/100 threshold:

```
15:00 → "Best Available": BRAIN (59/100) - Cached
15:10 → HIGH-QUALITY: BRAIN (72/100) - ✅ SENT (bypasses cache)
```

High-quality alerts always go through, even if recently cached.

### Different Tokens Don't Block Each Other

```
15:00 → "Best Available": BRAIN (59/100) - Cached
15:10 → "Best Available": SNAIL (58/100) - ✅ SENT (different token)
```

Only the same token address is deduplicated.

## Troubleshooting

### Problem: Still Getting Duplicate Emails

**Check cache file exists:**
```bash
ls -la alert_cache.json
```

**Check cache contents:**
```bash
cat alert_cache.json
```

**Check file permissions:**
```bash
chmod 644 alert_cache.json
```

### Problem: Not Getting Any "Best Available" Emails

**Clear the cache:**
```bash
rm alert_cache.json
```

**Check if token is actually changing:**
- Different tokens each scan → Should get emails
- Same token every scan → Working as intended (1 email/hour)

### Problem: Cache Growing Too Large

**Manual cleanup:**
```bash
rm alert_cache.json
```

**Automatic cleanup runs every scan** - entries > 2 hours old are removed.

## Technical Details

### Cache Functions

**`load_alert_cache()`**
- Loads cache from file
- Auto-cleans entries > 2 hours old
- Returns empty dict if file missing

**`save_alert_cache(cache)`**
- Saves cache to JSON file
- Called after successful email send

**`was_recently_alerted(address, cache, hours=1)`**
- Checks if token was alerted within time window
- Returns True if cached, False if can send

**`add_to_alert_cache(address, symbol, score, is_best_available, cache)`**
- Adds token to cache after email sent
- Includes timestamp, symbol, score

### Cache Lifecycle

```
1. Scan runs → Load cache from disk
2. Find opportunities → Check if cached
3. If cached → Skip email
4. If not cached → Send email → Save to cache
5. Next scan → Repeat
```

## Performance

- **File Size**: ~50-100 bytes per cached token
- **Lookup Time**: < 1ms (in-memory dict lookup)
- **Cleanup Time**: < 10ms (runs on every load)
- **Max Cached Tokens**: Limited by 2-hour expiry (~12 tokens max at 10min intervals)

Very lightweight and performant!
