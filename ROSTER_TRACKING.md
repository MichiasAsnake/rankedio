# Roster Tracking & Stats Fix

## Overview

This document explains the two major improvements to the ETL pipeline:
1. **Fixed stats extraction** (empty columns bug fix)
2. **Roll Call tracking** (roster update feature)

---

## Issue 1: Empty Stats Columns (FIXED ✅)

### Problem
The `heart_count`, `video_count`, and `daily_growth` columns were showing NULL or empty values in the database.

### Root Cause
- Inconsistent JSON field names across different TikHub API responses
- No fallback handling for missing or malformed data
- Type conversion errors not caught

### Solution Implemented

**Location**: [etl_pipeline.py:689-719](etl_pipeline.py#L689-L719)

**Before**:
```python
current_follower_count = int(author.get('follower_count', 0))
current_heart_count = int(author.get('total_favorited', 0))
current_video_count = int(author.get('aweme_count', 0))
```

**After** (with multiple fallbacks):
```python
# Follower count with fallbacks
try:
    follower_count_raw = author.get('follower_count') or author.get('mplatform_followers_count') or 0
    current_follower_count = int(follower_count_raw) if follower_count_raw else 0
except (ValueError, TypeError):
    current_follower_count = 0

# Heart count with fallbacks
try:
    heart_count_raw = author.get('total_favorited') or author.get('favoriting_count') or 0
    current_heart_count = int(heart_count_raw) if heart_count_raw else 0
except (ValueError, TypeError):
    current_heart_count = 0

# Video count with fallbacks
try:
    video_count_raw = author.get('aweme_count') or author.get('video_count') or 0
    current_video_count = int(video_count_raw) if video_count_raw else 0
except (ValueError, TypeError):
    current_video_count = 0
```

### What Changed
1. **Multiple field name attempts**: Tries alternative field names from different API versions
2. **None/empty handling**: Uses `or` operator to provide fallbacks
3. **Exception handling**: Catches `ValueError` and `TypeError` to prevent crashes
4. **Default to 0**: Always returns 0 instead of None, preventing SQL NULL issues

### Field Name Mappings

| Stat | Primary Field | Fallback Fields |
|------|--------------|----------------|
| Followers | `follower_count` | `mplatform_followers_count` |
| Hearts | `total_favorited` | `favoriting_count` |
| Videos | `aweme_count` | `video_count` |

---

## Issue 2: The "Roster Problem" (FIXED ✅)

### Problem
If an existing creator wasn't found in today's trending search, their stats weren't updated. This meant:
- No daily growth tracking for inactive creators
- Missing historical data
- Incomplete velocity calculations

### Solution: "Roll Call" Loop

**Location**: [etl_pipeline.py:879-973](etl_pipeline.py#L879-L973)

### How It Works

```
Pipeline Flow:
1. Process trending keywords → Discover new Comets
2. Roll Call Loop → Update ALL roster creators
3. Generate statistics
```

### Roll Call Process

**Step 1: Fetch Roster**
```python
query = "SELECT user_id, handle FROM creators ORDER BY handle"
cursor.execute(query)
roster = cursor.fetchall()
```

**Step 2: Loop & Update**
For each creator in the database:
1. Skip if already updated from trending search (avoids duplicates)
2. Fetch fresh profile from TikHub API: `/api/v1/tiktok/app/v3/fetch_user_detail`
3. Extract current stats (follower_count, heart_count, video_count)
4. Calculate growth vs. yesterday
5. Upsert into `creator_stats` table
6. Sleep 1 second (rate limit protection)

**Step 3: Commit & Report**
```
🎯 Roll Call Complete:
   ✅ Updated: 45
   ❌ Failed: 2
   ⏭️  Skipped (already updated): 8
```

---

## New API Method: `fetch_user_profile()`

**Location**: [etl_pipeline.py:274-310](etl_pipeline.py#L274-L310)

```python
def fetch_user_profile(self, handle: str) -> Optional[Dict]:
    """
    Fetch user profile by handle/unique_id

    Args:
        handle: TikTok username (unique_id)

    Returns:
        User profile data or None if request fails
    """
    profile_url = 'https://api.tikhub.io/api/v1/tiktok/app/v3/fetch_user_detail'

    params = {
        'unique_id': handle
    }

    response = self.session.get(profile_url, params=params, timeout=30)
    data = response.json()

    if data.get('code') != 200:
        return None

    return data
```

### API Endpoint Details

**URL**: `https://api.tikhub.io/api/v1/tiktok/app/v3/fetch_user_detail`

**Parameters**:
- `unique_id`: TikTok handle (e.g., "streetinterviewer123")

**Response Structure**:
```json
{
  "code": 200,
  "data": {
    "user": {
      "follower_count": 45123,
      "total_favorited": 1234567,
      "aweme_count": 234,
      "unique_id": "username",
      "sec_uid": "MS4w...",
      "nickname": "Display Name"
    }
  }
}
```

**Fallback Response Paths**:
The code tries multiple possible structures:
1. `data.user` (most common)
2. `data.userInfo` (alternative)
3. `data` itself (fallback)

---

## Code Integration

### Main Pipeline Flow

**Location**: [etl_pipeline.py:1025-1133](etl_pipeline.py#L1025-L1133)

```python
def run(self):
    # Step 1: Fetch trending keywords
    trending_keywords = self.api.get_trending_keywords(limit=10)

    # Step 2: Store trends in database
    for keyword in trending_keywords:
        self.db_manager.insert_daily_trend(cursor, keyword, rank)

    # Step 3: Process each trending keyword
    for keyword in trending_keywords:
        count = self.process_trend(keyword, cursor)
        total_discovered += count

    # Step 4: Roll Call - Update all existing creators (NEW!)
    roll_call_count = self.roll_call_update(cursor)
    conn.commit()

    # Step 5: Generate statistics
    logger.info(f"🎯 Pipeline completed. Total Comets discovered: {total_discovered}")
```

---

## Performance Considerations

### Rate Limiting

**Protection**: `time.sleep(1)` between each API call

**Why**: Prevents hitting TikHub API rate limits

**Impact**:
- 10 creators = ~10 seconds
- 100 creators = ~100 seconds (~2 minutes)
- 1000 creators = ~1000 seconds (~17 minutes)

### Skipping Already Updated

The roll call **skips creators already updated** from trending searches:

```python
if user_id in self.discovered_creators:
    logger.debug(f"Skipping @{handle} (already updated from trending)")
    continue
```

This saves:
- API calls
- Processing time
- Database operations

### Database Efficiency

**Upsert Strategy**: Uses `ON CONFLICT` to prevent duplicates:
```sql
INSERT INTO creator_stats (user_id, recorded_date, ...)
VALUES (...)
ON CONFLICT (user_id, recorded_date)
DO UPDATE SET ...
```

---

## Example Output

```
============================================================
Starting TikTok Comet Discovery ETL Pipeline
Dynamic Trend Chaining Mode
============================================================

🔍 Fetching today's top trends...
✅ Found 10 trending keywords
   Top trends: Girl Dinner, Street Interview, ...

📊 Processing 10 trends

Processing trend: Street Interview
✅ Comet saved: @streetguy123 (47,521 followers, growth: +2,341 / 5.18%)
✅ Discovered 15 Comets for trend: Street Interview

[... more trends ...]

============================================================
🎯 Starting Roll Call - Updating All Roster Creators
============================================================
📋 Found 55 creators in roster

[1/55] Fetching profile for @creator1...
  ✅ Updated: 48,234 followers (+1,123 / 2.38%)

[2/55] Fetching profile for @creator2...
  ✅ Updated: 51,987 followers (+234 / 0.45%)

[3/55] Skipping @creator3 (already updated from trending)

[... continue for all creators ...]

============================================================
🎯 Roll Call Complete:
   ✅ Updated: 45
   ❌ Failed: 2
   ⏭️  Skipped (already updated): 8
============================================================

============================================================
🎯 Pipeline completed. Total Comets discovered: 127
============================================================

📊 Context-First Filter Statistics:
   Total videos processed: 1000
   ❌ Rejected by Layer 1 (Platform Check): 250
   ❌ Rejected by Layer 2 (Pronoun Check): 150
   ❌ Rejected by Layer 3 (Face Presence): 300
   ✅ Passed all filters: 300
   💾 Saved to database: 127
============================================================
```

---

## Error Handling

### Graceful Degradation

If a creator's profile fails to fetch:
1. **Log warning**: `Failed to fetch profile for @username`
2. **Increment failed counter**
3. **Continue to next creator** (don't crash entire pipeline)
4. **Sleep 1 second** (still respect rate limits)

### Transaction Safety

Each creator update uses **transaction isolation**:
```python
try:
    # Update creator stats
    self.db_manager.insert_creator_stats(cursor, stats_data)
    updated_count += 1
except Exception as e:
    logger.error(f"Error updating @{handle}: {e}")
    failed_count += 1
    # Pipeline continues!
```

### Rollback Protection

If roll call fails entirely:
```python
try:
    roll_call_count = self.roll_call_update(cursor)
    conn.commit()
except Exception as e:
    logger.error(f"❌ Error during roll call update: {e}")
    conn.rollback()
    # Pipeline continues to statistics!
```

---

## Database Impact

### Before Roll Call
```sql
-- Query creators with stats
SELECT c.handle, cs.recorded_date, cs.follower_count
FROM creators c
LEFT JOIN creator_stats cs ON c.user_id = cs.user_id
WHERE cs.recorded_date = CURRENT_DATE;

-- Result: Only creators found in trending searches (20-50 per day)
```

### After Roll Call
```sql
-- Query creators with stats
SELECT c.handle, cs.recorded_date, cs.follower_count
FROM creators c
LEFT JOIN creator_stats cs ON c.user_id = cs.user_id
WHERE cs.recorded_date = CURRENT_DATE;

-- Result: ALL creators in database (100% coverage)
```

---

## Monitoring & Troubleshooting

### Check Roll Call Success Rate

```sql
-- See which creators were updated today
SELECT
    c.handle,
    cs.follower_count,
    cs.daily_growth_followers,
    cs.daily_growth_percent,
    cs.source_trend
FROM creators c
JOIN creator_stats cs ON c.user_id = cs.user_id
WHERE cs.recorded_date = CURRENT_DATE
ORDER BY cs.daily_growth_percent DESC;
```

### Identify Failed Updates

If a creator's stats show NULL today but had data yesterday:
1. **Check API credits**: TikHub might be rate limiting
2. **Verify handle**: Username might have changed
3. **Check logs**: Look for error messages for that creator

### Roll Call Taking Too Long?

If you have 1000+ creators and roll call takes too long:

**Option 1: Reduce sleep time** (risky - may hit rate limits)
```python
time.sleep(0.5)  # 500ms instead of 1s
```

**Option 2: Skip inactive creators**
```python
# Only update creators with recent activity
query = """
    SELECT user_id, handle
    FROM creators
    WHERE last_updated_at > NOW() - INTERVAL '7 days'
"""
```

**Option 3: Run roll call separately**
Create a separate script `roll_call_only.py` that runs independently.

---

## Testing

### Test Stats Extraction

```python
# Test with sample API response
author = {
    'follower_count': None,  # Missing
    'mplatform_followers_count': 50000,  # Fallback
    'total_favorited': '1234567',  # String (needs conversion)
    'aweme_count': 0  # Zero is valid
}

stats = engine.extract_stats_data('user123', author, cursor)

# Should return:
# {
#     'follower_count': 50000,  # Used fallback
#     'heart_count': 1234567,   # Converted string to int
#     'video_count': 0,         # Zero is valid (not NULL)
# }
```

### Test Roll Call

```python
# Create test database with sample creators
INSERT INTO creators (user_id, handle, nickname) VALUES
    ('user1', 'testuser1', 'Test User 1'),
    ('user2', 'testuser2', 'Test User 2');

# Run pipeline
python3 etl_pipeline.py

# Check results
SELECT * FROM creator_stats WHERE recorded_date = CURRENT_DATE;
```

---

## Migration Guide

### Existing Installations

If you're upgrading from a previous version:

1. **Update code**:
   ```bash
   git pull  # or copy new etl_pipeline.py
   ```

2. **No schema changes required** ✅
   - Roll call uses existing tables
   - Stats extraction is backward compatible

3. **Test with small roster**:
   ```bash
   # First run will update all creators
   python3 etl_pipeline.py
   ```

4. **Monitor logs**:
   - Check for failed profile fetches
   - Verify stats are no longer NULL

---

## FAQ

### Q: Will roll call update creators twice if they're in trending?

**A**: No. The roll call skips creators already updated during the trending search phase using the `discovered_creators` set.

### Q: What if a creator's handle changes?

**A**: The API call will fail, and that creator will be counted in "Failed" stats. You'll need to manually update the handle in the database.

### Q: Does roll call slow down the pipeline significantly?

**A**: Yes, if you have many creators. For 100 creators, add ~2 minutes. For 1000 creators, add ~17 minutes. This is intentional to respect rate limits.

### Q: Can I disable roll call?

**A**: Yes, comment out the roll call section in the `run()` method:
```python
# Step 4: Roll Call - Update all existing creators
# try:
#     roll_call_count = self.roll_call_update(cursor)
#     conn.commit()
# except Exception as e:
#     logger.error(f"❌ Error during roll call update: {e}")
#     conn.rollback()
```

### Q: Why are some stats still 0?

**A**: The creator might genuinely have 0 hearts/videos, or the API didn't return those fields. Check the logs for that specific creator.

---

## Next Steps

1. **Run the updated pipeline** and verify stats are populating
2. **Monitor roll call performance** with your roster size
3. **Check database** for NULL values (should be eliminated)
4. **Adjust rate limits** if needed (sleep duration)

For general pipeline usage, see [README.md](README.md) or [QUICKSTART.md](QUICKSTART.md).
