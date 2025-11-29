# Quick Start Guide (5 Minutes)

Get your TikTok Creator Discovery Engine running in 5 minutes.

## ⚡ Prerequisites

You need:
- ✅ Supabase account (you have this - credentials in `.env.example`)
- ⏳ TikHub API key ([Get free trial here](https://tikhub.io))

## 🚀 Setup Steps

### 1. Install Python Dependencies (1 min)

```bash
pip install -r requirements.txt
```

### 2. Setup Environment File (30 sec)

```bash
# Copy your env file (if not already named .env)
cp .env.example .env

# Edit and add your TikHub API key
# Change this line:
TIKHUB_API_KEY=
# To this:
TIKHUB_API_KEY=your_actual_key_here
```

### 3. Create Database Tables in Supabase (2 min)

1. Open your Supabase dashboard: https://supabase.com/dashboard
2. Go to **SQL Editor** (left sidebar)
3. Click **New Query**
4. Copy-paste this SQL:

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

CREATE INDEX idx_creators_handle ON creators(handle);

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

CREATE INDEX idx_creator_stats_user_id ON creator_stats(user_id);
CREATE INDEX idx_creator_stats_recorded_date ON creator_stats(recorded_date);
CREATE INDEX idx_creator_stats_growth ON creator_stats(daily_growth_percent DESC);
```

5. Click **Run** (or press `Cmd/Ctrl + Enter`)
6. You should see "Success. No rows returned"

### 4. Test Everything Works (30 sec)

```bash
python test_connection.py
```

Expected output:
```
✅ Found Supabase connection string
✅ Connected to PostgreSQL
✅ Required tables found: creators, creator_stats
✅ TIKHUB_API_KEY configured
✅ All tests passed! Ready to run ETL pipeline.
```

### 5. Run the Pipeline! (1 min)

```bash
python etl_pipeline.py
```

You'll see output like:
```
2025-11-27 10:30:15 - INFO - Processing hashtag: #streetinterviews
2025-11-27 10:30:16 - INFO - Discovered Comet: @example_user (45,230 followers, +1,250 growth)
2025-11-27 10:30:20 - INFO - Pipeline completed. Total Comets discovered: 8
```

## 📊 View Your Data

### In Supabase Dashboard:
1. Go to **Table Editor**
2. Click on `creators` or `creator_stats` tables
3. See your discovered Comet creators!

### Or use SQL Editor:
```sql
-- Top 10 fastest growing creators today
SELECT
    c.handle,
    c.nickname,
    cs.follower_count,
    cs.daily_growth_followers,
    cs.daily_growth_percent
FROM creator_stats cs
JOIN creators c ON c.user_id = cs.user_id
WHERE cs.recorded_date = CURRENT_DATE
ORDER BY cs.daily_growth_percent DESC
LIMIT 10;
```

## 🎯 Customize It

Edit hashtags in `etl_pipeline.py` (around line 60):

```python
HASHTAGS = [
    '#streetinterviews',
    '#cozygaming',
    '#yourhashtag',  # Add your niches here!
]
```

Adjust "Comet" criteria (around line 54):

```python
MIN_FOLLOWERS = 10_000      # Lower bound
MAX_FOLLOWERS = 100_000     # Upper bound
MIN_VIDEO_VIEWS = 50_000    # Minimum video views
```

## 🔄 Run Daily (Optional)

Add to crontab to run every day at 2 AM:

```bash
crontab -e
```

Add this line:
```
0 2 * * * cd /path/to/rankedio && /usr/bin/python3 etl_pipeline.py
```

## ❓ Troubleshooting

**"Could not connect to database"**
- Check your `.env` file has Supabase credentials
- Make sure you copied from `.env.example` to `.env`

**"relation does not exist"**
- You forgot to run the SQL in Step 3
- Go back and create the tables in Supabase SQL Editor

**"TIKHUB_API_KEY not set"**
- Add your API key to `.env` file
- No quotes needed: `TIKHUB_API_KEY=abc123xyz`

## 📚 More Help

- Detailed setup: See [SUPABASE_SETUP.md](SUPABASE_SETUP.md)
- Full documentation: See [README.md](README.md)
- Logs: Check `etl_pipeline.log` for errors

---

That's it! You're now discovering Comet creators 🌟
