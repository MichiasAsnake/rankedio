# Migration Guide: Dynamic Trend Chaining

## What Changed?

The ETL pipeline now features **Dynamic Trend Chaining** - it automatically fetches today's trending keywords from TikTok instead of using a hardcoded list.

## New Features

### 1. Automatic Trend Discovery
- Fetches top 10 trending keywords from TikHub API every run
- Falls back to hardcoded hashtags if the API fails
- Stores trending keywords in a new `daily_trends` table

### 2. Trend Attribution
- Tracks which trending keyword led to discovering each creator
- New `source_trend` column in `creator_stats` table
- Enables analysis of which trends produce the best Comets

### 3. New Database Tables

**`daily_trends` table:**
- Stores trending keywords discovered each day
- Tracks ranking position
- Prevents duplicate entries per day

**Updated `creator_stats` table:**
- New `source_trend` column
- Links each creator discovery to the trending keyword

## Migration Steps

### For Existing Users (Already Have Tables)

Run this SQL in your Supabase SQL Editor:

```sql
-- Create daily_trends table
CREATE TABLE IF NOT EXISTS daily_trends (
    id SERIAL PRIMARY KEY,
    trend_keyword VARCHAR(255) NOT NULL,
    discovered_at DATE DEFAULT CURRENT_DATE,
    rank INT,
    UNIQUE(trend_keyword, discovered_at)
);

CREATE INDEX IF NOT EXISTS idx_daily_trends_date ON daily_trends(discovered_at);
CREATE INDEX IF NOT EXISTS idx_daily_trends_keyword ON daily_trends(trend_keyword);

-- Add source_trend column to creator_stats
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'creator_stats' AND column_name = 'source_trend'
    ) THEN
        ALTER TABLE creator_stats ADD COLUMN source_trend VARCHAR(255);
        CREATE INDEX idx_creator_stats_source_trend ON creator_stats(source_trend);
    END IF;
END $$;
```

Or simply run the migration file:
```bash
# Copy the contents of migration_add_trends.sql into Supabase SQL Editor
```

### For New Users

Use the updated schema file:
- [setup_database_supabase.sql](setup_database_supabase.sql) (for Supabase)
- [setup_database.sql](setup_database.sql) (for local PostgreSQL)

## How It Works

### Old Workflow
```
Hardcoded Hashtags → Search Videos → Filter Comets → Save to DB
```

### New Workflow
```
1. Fetch Trending Keywords from TikHub API
2. Store Trends in daily_trends table
3. Loop through each trending keyword
4. Search Videos for that keyword
5. Filter Comets
6. Save to DB with source_trend attribution
```

## Code Changes

### Main Changes in `etl_pipeline.py`

1. **New Method: `TikHubAPI.get_trending_keywords()`**
   - Calls: `https://api.tikhub.io/api/v1/tiktok/web/fetch_trending_searchwords`
   - Returns top 10 trending keywords
   - Defensive parsing for different response structures

2. **New Method: `DatabaseManager.insert_daily_trend()`**
   - Stores trending keywords with ranking
   - Prevents duplicates per day

3. **Updated Method: `extract_stats_data()`**
   - Now accepts `source_trend` parameter
   - Includes trend attribution in returned data

4. **Updated Method: `process_video_item()`**
   - Accepts and passes `source_trend` parameter

5. **Renamed Method: `process_hashtag()` → `process_trend()`**
   - More generic name
   - Passes source_trend to video processing

6. **Updated Method: `run()`**
   - Fetches trending keywords first
   - Stores trends in database
   - Uses trends instead of hardcoded hashtags
   - Falls back to hardcoded hashtags if API fails

## Usage

### Run with Dynamic Trends (Default)
```bash
python etl_pipeline.py
```

This will:
1. Fetch today's top 10 trending keywords
2. Search for Comets using those trends
3. Store which trend led to each discovery

### Customize Fallback Hashtags

Edit [etl_pipeline.py](etl_pipeline.py):
```python
HASHTAGS = [
    '#streetinterviews',
    '#cozygaming',
    '#gymtok',
    '#yourhashtag'  # Used only if trending API fails
]
```

## New Queries

### View Today's Trending Keywords
```sql
SELECT trend_keyword, rank
FROM daily_trends
WHERE discovered_at = CURRENT_DATE
ORDER BY rank;
```

### See Which Trends Found the Most Comets
```sql
SELECT
    source_trend,
    COUNT(*) as creator_count,
    AVG(daily_growth_percent) as avg_growth
FROM creator_stats
WHERE recorded_date = CURRENT_DATE
    AND source_trend IS NOT NULL
GROUP BY source_trend
ORDER BY creator_count DESC;
```

### Find Creators Discovered from a Specific Trend
```sql
SELECT
    c.handle,
    c.nickname,
    cs.follower_count,
    cs.daily_growth_percent,
    cs.source_trend
FROM creator_stats cs
JOIN creators c ON c.user_id = cs.user_id
WHERE cs.source_trend = 'Girl Dinner'  -- Replace with your trend
    AND cs.recorded_date = CURRENT_DATE
ORDER BY cs.daily_growth_percent DESC;
```

## Benefits

1. **Always Fresh** - Automatically finds what's trending right now
2. **Better Discovery** - Catches viral trends early
3. **Trend Analytics** - Know which trends produce the best Comets
4. **Automated** - No manual hashtag updates needed
5. **Resilient** - Falls back to hardcoded hashtags if API fails

## Troubleshooting

**"No trending keywords found"**
- Check your TikHub API key is valid
- Verify API endpoint is accessible
- Pipeline will fallback to hardcoded hashtags automatically

**"Column 'source_trend' does not exist"**
- You need to run the migration SQL
- See "Migration Steps" above

**"Relation 'daily_trends' does not exist"**
- Run the migration SQL or updated schema
- See "Migration Steps" above

## Backward Compatibility

The updated code is **backward compatible**:
- If trending API fails, falls back to Config.HASHTAGS
- Existing databases will work after running migration
- Old behavior available by passing hashtags directly

## Questions?

Check the updated [README.md](README.md) or [QUICKSTART.md](QUICKSTART.md) for more details.
