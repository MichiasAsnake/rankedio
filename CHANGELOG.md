# Changelog

## v2.0.0 - Dynamic Trend Chaining (2025-11-27)

### 🎯 Major Features

#### Dynamic Trend Discovery
- **Automatic Trend Fetching**: Pipeline now automatically fetches top 10 trending keywords from TikHub API
- **Trend Attribution**: Tracks which trending keyword led to discovering each creator
- **Intelligent Fallback**: Falls back to hardcoded hashtags if trending API fails

### 📊 Database Changes

#### New Tables
- **`daily_trends`**: Stores trending keywords with ranking
  - `id` (SERIAL PRIMARY KEY)
  - `trend_keyword` (VARCHAR 255)
  - `discovered_at` (DATE)
  - `rank` (INT)
  - Unique constraint on `(trend_keyword, discovered_at)`

#### Updated Tables
- **`creator_stats`**: Added `source_trend` column
  - `source_trend` (VARCHAR 255) - Links discovery to trending keyword
  - New index on `source_trend` for faster queries

### 🔧 Code Changes

#### New Methods
- `TikHubAPI.get_trending_keywords()` - Fetches trending keywords from TikHub
- `DatabaseManager.insert_daily_trend()` - Stores trending keywords

#### Updated Methods
- `extract_stats_data()` - Now includes `source_trend` parameter
- `process_video_item()` - Accepts and passes `source_trend`
- `process_hashtag()` → `process_trend()` - Renamed for clarity
- `run()` - Complete rewrite to implement dynamic trend chaining

#### New Workflow
```
Old: Hardcoded Hashtags → Search → Filter → Save

New: Fetch Trends → Store Trends → Search Each Trend → Filter → Save with Attribution
```

### 📝 Documentation

#### New Files
- `MIGRATION_GUIDE.md` - Step-by-step migration instructions
- `migration_add_trends.sql` - SQL migration script for existing databases
- `CHANGELOG.md` - This file

#### Updated Files
- `setup_database_supabase.sql` - Added daily_trends table and source_trend column
- `setup_database.sql` - Added daily_trends table and source_trend column
- `etl_pipeline.py` - Complete rewrite of trend processing logic
- `README.md` - Updated with dynamic trend chaining documentation

### 🚀 Usage Changes

#### Before
```python
# Hardcoded hashtags in Config
HASHTAGS = ['#streetinterviews', '#cozygaming', '#gymtok']
engine.run(HASHTAGS)
```

#### After
```python
# Automatically fetches trending keywords
# Config.HASHTAGS now used only as fallback
engine.run(fallback_hashtags=Config.HASHTAGS)
```

### 🔍 New Analytics Queries

```sql
-- See which trends found the most Comets
SELECT
    source_trend,
    COUNT(*) as creator_count,
    AVG(daily_growth_percent) as avg_growth
FROM creator_stats
WHERE recorded_date = CURRENT_DATE
GROUP BY source_trend
ORDER BY creator_count DESC;

-- View today's trending keywords
SELECT trend_keyword, rank
FROM daily_trends
WHERE discovered_at = CURRENT_DATE
ORDER BY rank;
```

### ⚠️ Breaking Changes

None - fully backward compatible with proper migration.

### 🐛 Bug Fixes

- Improved defensive JSON parsing in API responses
- Better error handling for trending API failures
- Enhanced logging for trend processing

### 📦 Dependencies

No new dependencies - still using:
- `requests==2.31.0`
- `psycopg2-binary==2.9.9`
- `python-dotenv==1.0.0`

---

## v1.0.0 - Initial Release

### Features
- Supabase integration
- TikHub API integration
- Comet creator discovery (10k-100k followers, 50k+ views)
- Daily growth tracking and velocity calculation
- Robust error handling and logging
- Hardcoded hashtag processing
