# Final ETL Pipeline Implementation

## Overview

Complete two-phase ETL pipeline for discovering and tracking TikTok "Comet" creators (10k-100k followers with high engagement).

---

## Architecture: Two-Phase System

### Phase 1: Discovery (New Creator Search)
- Fetches dynamic trending keywords from TikHub
- Searches videos for each trending keyword
- Applies Context-First filters (Platform/Pronoun/Face)
- Discovers and saves new Comet creators

### Phase 2: Roll Call (Roster Updates)
- Queries all existing creators from database
- Fetches fresh stats for each creator via `handler_user_profile`
- Calculates daily growth (today vs yesterday)
- Updates `creator_stats` for all roster members

---

## Data Mapping (EXACT API Paths)

### Roll Call Endpoint
**URL**: `https://api.tikhub.io/api/v1/tiktok/app/v3/handler_user_profile`

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
      "uid": "1234567890"
    }
  }
}
```

**Extraction Paths**:
| Field | Path | Purpose |
|-------|------|---------|
| Followers | `response['data']['user']['follower_count']` | Current follower count |
| Hearts | `response['data']['user']['total_favorited']` | Total likes received |
| Video Count | `response['data']['user']['aweme_count']` | Number of videos posted |
| Handle | `response['data']['user']['unique_id']` | TikTok username |
| UID | `response['data']['user']['uid']` | TikTok user ID |

**Code Implementation** ([etl_pipeline.py:928-948](etl_pipeline.py#L928-L948)):
```python
# Extract user data from response using EXACT paths
data = response.get('data', {})
user_info = data.get('user', {})

# These fields will be used by extract_stats_data():
# - follower_count
# - total_favorited
# - aweme_count
```

---

## Context-First Filtering System

### Layer 1: Platform Check (Metadata)
**Purpose**: Reject multi-platform creators (Twitch streamers, YouTubers)

**Blacklist Keywords**:
```python
PLATFORM_KEYWORDS = [
    'twitch', 'youtube', 'kick', 'discord', 'streaming', 'streamer',
    'ttv', 'yt', 'patreon', 'onlyfans', 'twitter', 'instagram',
    'fanpage', 'fan page', 'archive', 'clips', 'highlights', 'moments',
    'daily', 'compilation', 'best of'
]
```

**Logic**: Scans bio, nickname, and handle for keywords

### Layer 2: Pronoun Check (Caption)
**Purpose**: Reject repost accounts that narrate others' content

**Repost Patterns**:
```python
REPOST_PRONOUNS = ['bro', 'he', 'she', 'they']
```

**Logic**: Rejects if caption starts with these pronouns (e.g., "Bro really said...")

### Layer 3: Face Presence (Computer Vision)
**Purpose**: Confirm human on camera (not scenery/gameplay/text)

**Threshold**: Face must be > 2% of frame

**Technology**: OpenCV Haar Cascade face detection

---

## Phase 1: Discovery Flow

```
1. Fetch trending keywords
   ↓
2. For each keyword:
   ├─ Fetch videos (fetch_video_search_result)
   ├─ Extract author + statistics
   ├─ Apply Layer 1: Platform check
   ├─ Apply Layer 2: Pronoun check
   ├─ Apply Layer 3: Face detection
   ├─ Check Comet criteria (10k-100k followers, 50k+ views)
   └─ Save to database
   ↓
3. Track discovered_creators set (avoid duplicates)
```

**Location**: [etl_pipeline.py:1056-1105](etl_pipeline.py#L1056-L1105)

---

## Phase 2: Roll Call Flow

```
1. Query database: SELECT user_id, handle FROM creators
   ↓
2. For each creator:
   ├─ Skip if already updated in Phase 1
   ├─ API call: handler_user_profile?unique_id={handle}
   ├─ Extract: follower_count, total_favorited, aweme_count
   ├─ Query yesterday's stats
   ├─ Calculate growth: today - yesterday
   ├─ Upsert to creator_stats
   └─ time.sleep(1) for rate limiting
   ↓
3. Report: Updated X, Failed Y, Skipped Z
```

**Location**: [etl_pipeline.py:879-971](etl_pipeline.py#L879-L971)

**Key Features**:
- ✅ Skips creators already updated from Phase 1
- ✅ Rate limiting (1 second between requests)
- ✅ Graceful error handling (continues on failure)
- ✅ Transaction isolation per creator

---

## Stats Extraction with Fallbacks

**Location**: [etl_pipeline.py:689-719](etl_pipeline.py#L689-L719)

```python
# Followers with multiple fallbacks
try:
    follower_count_raw = author.get('follower_count') or author.get('mplatform_followers_count') or 0
    current_follower_count = int(follower_count_raw) if follower_count_raw else 0
except (ValueError, TypeError):
    current_follower_count = 0

# Hearts with fallbacks
try:
    heart_count_raw = author.get('total_favorited') or author.get('favoriting_count') or 0
    current_heart_count = int(heart_count_raw) if heart_count_raw else 0
except (ValueError, TypeError):
    current_heart_count = 0

# Videos with fallbacks
try:
    video_count_raw = author.get('aweme_count') or author.get('video_count') or 0
    current_video_count = int(video_count_raw) if video_count_raw else 0
except (ValueError, TypeError):
    current_video_count = 0
```

**Why This Works**:
- ✅ Tries primary field names (TikHub standard)
- ✅ Falls back to alternative field names (API variations)
- ✅ Handles None, empty strings, and missing keys
- ✅ Catches type conversion errors
- ✅ Defaults to 0 (never NULL in database)

---

## Velocity Calculation

**Formula**:
```python
growth = today_followers - yesterday_followers
growth_percent = (growth / yesterday_followers) * 100
```

**Implementation** ([etl_pipeline.py:720-737](etl_pipeline.py#L720-L737)):
```python
today = date.today()
yesterday = today - timedelta(days=1)

# Query previous day's stats
previous_stats = self.db_manager.get_previous_stats(cursor, user_id, yesterday)

if previous_stats:
    previous_followers = previous_stats[0]
    daily_growth = current_follower_count - previous_followers

    if previous_followers > 0:
        growth_percent = Decimal((daily_growth / previous_followers) * 100).quantize(Decimal('0.01'))
    else:
        growth_percent = Decimal('0.00')
else:
    # First time seeing this creator
    daily_growth = 0
    growth_percent = Decimal('0.00')
```

---

## Example Output

```bash
python3 etl_pipeline.py
```

```
============================================================
TikTok Comet Discovery ETL Pipeline
Two-Phase System: Discovery + Roll Call
============================================================

============================================================
PHASE 1: DISCOVERY (Trending Keywords Only)
============================================================

🔍 Fetching dynamic trending keywords...
✅ Found 10 trending keywords
   Top trends: taylor hill, Bird Game 3, tini mac and cheese, ...

Processing trend: taylor hill
✅ Comet saved: @creator1 (18,047 followers, growth: +0 / 0.00%)
✅ Discovered 4 Comets for trend: taylor hill

[... more trends ...]

============================================================
PHASE 2: ROLL CALL (Update Existing Roster)
============================================================
🎯 Starting Roll Call - Updating All Roster Creators
============================================================
📋 Found 55 creators in roster

[1/55] Fetching profile for @oldcreator1...
  ✅ Updated: 48,234 followers (+1,123 / 2.38%)

[2/55] Fetching profile for @oldcreator2...
  ✅ Updated: 51,987 followers (+234 / 0.45%)

[3/55] Skipping @creator1 (already updated from trending)

============================================================
🎯 Roll Call Complete:
   ✅ Updated: 45
   ❌ Failed: 2
   ⏭️  Skipped (already updated): 8
============================================================

============================================================
🎯 PIPELINE COMPLETED
============================================================
   Phase 1 - New Comets discovered: 4
   Phase 2 - Roster creators updated: 45
   Total database updates: 49
============================================================

📊 Context-First Filter Statistics:
   Total videos processed: 200
   ❌ Rejected by Layer 1 (Platform Check): 50
   ❌ Rejected by Layer 2 (Pronoun Check): 30
   ❌ Rejected by Layer 3 (Face Presence): 80
   ✅ Passed all filters: 40
   ⚠️  Rejected by Comet criteria: 36
   💾 Saved to database: 4

   Layer 1 (Platform) rejection rate: 25.0%
   Layer 2 (Pronoun) rejection rate: 15.0%
   Layer 3 (Face) rejection rate: 40.0%
   Filter pass rate: 20.0%
============================================================
```

---

## Database Schema

### Creators Table
```sql
CREATE TABLE creators (
    user_id VARCHAR(255) PRIMARY KEY,
    handle VARCHAR(100) NOT NULL,
    nickname VARCHAR(255),
    avatar_url TEXT,
    signature TEXT,
    last_updated_at TIMESTAMP DEFAULT NOW()
);
```

### Creator Stats Table
```sql
CREATE TABLE creator_stats (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES creators(user_id),
    recorded_date DATE DEFAULT CURRENT_DATE,
    follower_count BIGINT,
    heart_count BIGINT,
    video_count INT,
    daily_growth_followers INT,
    daily_growth_percent DECIMAL(5, 2),
    source_trend VARCHAR(255),
    UNIQUE(user_id, recorded_date)
);
```

### Daily Trends Table
```sql
CREATE TABLE daily_trends (
    id SERIAL PRIMARY KEY,
    trend_keyword VARCHAR(255) NOT NULL,
    discovered_at DATE DEFAULT CURRENT_DATE,
    rank INT,
    UNIQUE(trend_keyword, discovered_at)
);
```

---

## Configuration (.env)

```bash
# Database Connection (Supabase)
POSTGRES_URL_NON_POOLING="postgres://user:pass@host:5432/postgres?sslmode=require"

# TikHub API
TIKHUB_API_KEY=your_api_key_here
```

---

## Dependencies (requirements.txt)

```txt
# HTTP Requests
requests==2.31.0

# PostgreSQL Database Adapter
psycopg2-binary==2.9.9

# Environment Variable Management
python-dotenv==1.0.0

# Computer Vision - Face Detection Filter
opencv-python-headless==4.8.1.78
numpy==1.24.3
```

---

## Installation & Setup

### 1. Install Dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Supabase and TikHub credentials
```

### 3. Setup Database
```bash
# Run in Supabase SQL Editor
psql -f setup_database_supabase.sql

# OR manually run schema creation
```

### 4. Run Pipeline
```bash
python3 etl_pipeline.py
```

---

## Performance Characteristics

### Phase 1 (Discovery)
- **Speed**: ~2-5s per trending keyword (depends on video count)
- **API Calls**: ~10-50 per keyword (video search + pagination)
- **Face Detection**: ~1-2s per video cover image
- **Expected Duration**: 2-5 minutes for 10 trends

### Phase 2 (Roll Call)
- **Speed**: ~1s per creator (API + sleep)
- **API Calls**: 1 per creator (handler_user_profile)
- **Expected Duration**: 1s × creator_count
  - 50 creators = ~50 seconds
  - 100 creators = ~100 seconds
  - 500 creators = ~8 minutes

### Total Pipeline Time
- **Small roster (10-50 creators)**: 3-7 minutes
- **Medium roster (100-200 creators)**: 5-12 minutes
- **Large roster (500+ creators)**: 15-25 minutes

---

## Error Handling

### Graceful Degradation

**Phase 1 Failures**:
- Trending API fails → Pipeline exits (no fallback)
- Video search fails → Skip keyword, continue to next
- Filter fails → Reject creator, continue processing
- Database error → Rollback trend, continue to next

**Phase 2 Failures**:
- Profile fetch fails → Count as failed, continue to next creator
- Database error → Rollback creator, continue to next
- Entire Phase 2 fails → Still shows Phase 1 results

### Transaction Safety

```python
# Per-creator savepoint
cursor.execute("SAVEPOINT before_insert")
try:
    # Upsert creator and stats
    cursor.execute("RELEASE SAVEPOINT before_insert")
except psycopg2.Error:
    cursor.execute("ROLLBACK TO SAVEPOINT before_insert")
```

---

## Monitoring Queries

### Check Today's Discoveries
```sql
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

### Top Growing Creators (7 Days)
```sql
SELECT
    c.handle,
    SUM(cs.daily_growth_followers) as total_growth,
    AVG(cs.daily_growth_percent) as avg_daily_percent
FROM creators c
JOIN creator_stats cs ON c.user_id = cs.user_id
WHERE cs.recorded_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY c.user_id, c.handle
ORDER BY total_growth DESC
LIMIT 20;
```

### Filter Effectiveness
```sql
-- See which trends produce the most Comets
SELECT
    source_trend,
    COUNT(*) as creators_found,
    AVG(follower_count) as avg_followers
FROM creator_stats
WHERE recorded_date = CURRENT_DATE
    AND source_trend IS NOT NULL
GROUP BY source_trend
ORDER BY creators_found DESC;
```

---

## Troubleshooting

### Issue: "No trending keywords found"
**Cause**: TikHub API failure or invalid API key

**Solution**:
1. Check API key in .env
2. Verify TikHub account has credits
3. Test API manually: `curl -H "Authorization: Bearer YOUR_KEY" https://api.tikhub.io/api/v1/tiktok/web/fetch_trending_searchwords`

---

### Issue: "Roll Call updating 0 creators"
**Cause**: All creators were already updated in Phase 1

**Solution**: This is normal! It means all creators in roster were found in trending searches.

**Verification**:
```sql
SELECT COUNT(*) FROM creators;  -- Total roster
SELECT COUNT(*) FROM creator_stats WHERE recorded_date = CURRENT_DATE;  -- Updated today
```

---

### Issue: Stats columns still showing 0
**Cause**: API response structure changed or fields missing

**Solution**:
1. Check logs for specific creator
2. Manually test API: `curl "https://api.tikhub.io/api/v1/tiktok/app/v3/handler_user_profile?unique_id=username"`
3. Verify response structure matches expected paths
4. Add additional fallback fields if needed

---

### Issue: Database errors "value too long"
**Cause**: VARCHAR(50) too small for user_id

**Solution**:
```sql
ALTER TABLE creators ALTER COLUMN user_id TYPE VARCHAR(255);
ALTER TABLE creator_stats ALTER COLUMN user_id TYPE VARCHAR(255);
```

---

## API Rate Limits

### TikHub Limits
- **Video Search**: ~60 requests/minute
- **Trending Keywords**: ~60 requests/minute
- **User Profile**: ~60 requests/minute

### Pipeline Rate Limiting
- **Phase 1**: No explicit rate limiting (TikHub handles it)
- **Phase 2**: 1 second sleep between requests (60 requests/minute)

**Recommendation**: If you have 500+ creators, consider running roll call separately or increasing sleep time.

---

## Production Deployment

### Cron Schedule
```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/rankedio && python3 etl_pipeline.py >> logs/etl_$(date +\%Y\%m\%d).log 2>&1
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python3", "etl_pipeline.py"]
```

### Environment Variables (Production)
```bash
POSTGRES_URL_NON_POOLING=postgres://...  # From Supabase
TIKHUB_API_KEY=...  # From TikHub dashboard
```

---

## Summary

**Phase 1**: Discovers new Comets from trending keywords
**Phase 2**: Updates all roster creators' daily stats

**Total Updates Per Run**: Phase 1 discoveries + Phase 2 roster updates

**Key Features**:
- ✅ Dynamic trending keyword discovery
- ✅ Context-First filtering (platform/pronoun/face)
- ✅ Robust stats extraction with fallbacks
- ✅ Daily growth velocity tracking
- ✅ Complete roster coverage (no missed updates)
- ✅ Transaction safety and error handling
- ✅ Rate limiting protection

**Next Steps**:
1. Run the pipeline: `python3 etl_pipeline.py`
2. Monitor logs for errors
3. Verify database updates
4. Adjust filters if needed (see [CONTEXT_FIRST_FILTER.md](CONTEXT_FIRST_FILTER.md))
