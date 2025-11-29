# TikTok Creator Discovery Engine

A robust ETL pipeline for discovering "Comet" creators on TikTok—creators with low follower counts but high engagement velocity.

## Overview

This pipeline:
- Searches TikTok videos by hashtag using the TikHub API
- Identifies "Comet" creators (10k-100k followers, 50k+ video views)
- Tracks daily growth metrics and velocity
- Stores data in PostgreSQL for analysis

## Prerequisites

- Python 3.8+
- Supabase account ([Sign up here](https://supabase.com)) OR PostgreSQL 12+
- TikHub API Key ([Get one here](https://tikhub.io))

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Database

#### Option A: Using Supabase (Recommended)

1. Create a new Supabase project at [supabase.com](https://supabase.com)
2. Go to the SQL Editor in your Supabase dashboard
3. Copy and paste the contents of `setup_database.sql` or run the following:

```sql
-- Main Creator Profile
CREATE TABLE creators (
    user_id VARCHAR(50) PRIMARY KEY,
    handle VARCHAR(100) NOT NULL,
    nickname VARCHAR(255),
    avatar_url TEXT,
    signature TEXT,
    last_updated_at TIMESTAMP DEFAULT NOW()
);

-- Daily Snapshot for Growth Tracking
CREATE TABLE creator_stats (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES creators(user_id) ON DELETE CASCADE,
    recorded_date DATE DEFAULT CURRENT_DATE,

    follower_count BIGINT,
    heart_count BIGINT,
    video_count INT,

    daily_growth_followers INT,
    daily_growth_percent DECIMAL(5, 2),

    UNIQUE(user_id, recorded_date)
);
```

4. Run the query to create the tables

#### Option B: Using Local PostgreSQL

```bash
psql -d your_database -f setup_database.sql
```

### 3. Configure Environment Variables

Your `.env` file should already have your Supabase credentials. Just add your TikHub API key:

**For Supabase** (your current setup):
```bash
# Your existing Supabase variables are already set
# Just add:
TIKHUB_API_KEY=your_tikhub_api_key_here
```

**For Local PostgreSQL** (alternative):
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tiktok_ranking
DB_USER=postgres
DB_PASSWORD=your_password

TIKHUB_API_KEY=your_api_key
```

The script automatically detects which connection method to use (Supabase connection string or individual parameters).

## Usage

### Run the Pipeline

```bash
python etl_pipeline.py
```

### Customize Hashtags

Edit the `HASHTAGS` list in [etl_pipeline.py](etl_pipeline.py):

```python
HASHTAGS = [
    '#streetinterviews',
    '#cozygaming',
    '#gymtok',
    '#yourhashtag'
]
```

### Adjust Comet Criteria

Modify the constants in the `Config` class:

```python
MIN_FOLLOWERS = 10_000      # Minimum followers
MAX_FOLLOWERS = 100_000     # Maximum followers
MIN_VIDEO_VIEWS = 50_000    # Minimum video views
```

## Architecture

### Key Components

1. **TikHubAPI**: Handles all API interactions with error handling
2. **DatabaseManager**: Manages PostgreSQL operations (upserts, queries)
3. **CometDiscoveryEngine**: Main ETL orchestration and filtering logic

### Data Flow

```
Hashtags → TikHub API → Filter Comets → Upsert Creators → Calculate Growth → Store Stats
```

### Growth Calculation

For each creator discovered today:
1. Query yesterday's stats from `creator_stats`
2. Calculate: `growth = today_followers - yesterday_followers`
3. Calculate: `growth_percent = (growth / yesterday_followers) * 100`
4. If no previous record exists, growth defaults to 0

## Logging

Logs are written to:
- Console (stdout)
- `etl_pipeline.log` file

## Error Handling

The pipeline includes:
- API timeout handling (30s)
- Defensive JSON parsing
- Database transaction rollbacks on error
- Per-hashtag error isolation (one failure won't stop the pipeline)

## Scheduling

Run daily via cron:

```bash
0 2 * * * /usr/bin/python3 /path/to/etl_pipeline.py
```

## Monitoring

Check logs for:
- `Discovered Comet:` - New creators found
- `Total Comets discovered:` - Summary count
- Error messages for debugging

## Performance

- Processes ~100 videos per hashtag (5 pages × 20 results)
- Uses efficient bulk upserts
- Tracks unique creators per run to avoid duplicates

## License

Proprietary - Internal Use Only
