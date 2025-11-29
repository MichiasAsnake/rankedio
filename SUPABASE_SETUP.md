# Supabase Setup Guide

Quick guide for setting up the TikTok Creator Discovery Engine with Supabase.

## Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click "New Project"
3. Fill in project details:
   - Name: `tiktok-ranking` (or your preferred name)
   - Database Password: Generate a strong password (save it!)
   - Region: Choose closest to your location
4. Click "Create new project" and wait for setup to complete

## Step 2: Get Your Database Credentials

1. In your Supabase project dashboard, click on **Settings** (gear icon)
2. Navigate to **Database** in the left sidebar
3. Scroll to **Connection string** section
4. You'll see several connection strings - you need these variables which are already in your `.env` file:
   - `POSTGRES_URL` - Pooled connection
   - `POSTGRES_URL_NON_POOLING` - Direct connection (used by ETL pipeline)
   - `POSTGRES_HOST`
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - `POSTGRES_DATABASE`

✅ **Good news**: These are already in your `.env` file!

## Step 3: Create Database Tables

1. In Supabase dashboard, go to **SQL Editor** (left sidebar)
2. Click "New query"
3. Copy the entire contents of `setup_database.sql` file
4. Paste into the SQL editor
5. Click **Run** or press `Cmd/Ctrl + Enter`

You should see a success message confirming the tables were created.

### Alternative: Copy-paste this SQL

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

## Step 4: Verify Tables Created

1. In Supabase dashboard, go to **Table Editor** (left sidebar)
2. You should see two tables:
   - `creators`
   - `creator_stats`

## Step 5: Add TikHub API Key

1. Open your `.env` file
2. Find the line `TIKHUB_API_KEY=`
3. Add your TikHub API key after the `=`
4. Save the file

Your `.env` should look like:
```bash
# ... existing Supabase variables ...

TIKHUB_API_KEY=your_actual_api_key_here
```

## Step 6: Test Connection

```bash
python test_connection.py
```

You should see:
```
✅ Found Supabase connection string
✅ Connected to PostgreSQL
✅ Required tables found: creators, creator_stats
✅ TIKHUB_API_KEY configured
✅ All tests passed! Ready to run ETL pipeline.
```

## Step 7: Run the Pipeline

```bash
python etl_pipeline.py
```

## Viewing Your Data

### Option 1: Supabase Table Editor
1. Go to **Table Editor** in Supabase dashboard
2. Click on `creators` or `creator_stats` to view data

### Option 2: SQL Editor
```sql
-- View all discovered creators
SELECT * FROM creators ORDER BY last_updated_at DESC;

-- View top growing creators today
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

## Troubleshooting

### Connection Issues

**Error: "Could not connect to database"**
- Verify your `.env` file has the correct Supabase credentials
- Check that your IP is allowed in Supabase (Dashboard > Settings > Database > Connection pooling)

**Error: "relation does not exist"**
- You haven't run the SQL to create tables yet
- Go back to Step 3

### API Issues

**Error: "TIKHUB_API_KEY not set"**
- Add your API key to `.env` file
- Make sure there are no quotes around the key value

**Error: "API request failed"**
- Verify your TikHub API key is valid
- Check you have API credits remaining
- Confirm the endpoint is accessible

## Next Steps

- Schedule the pipeline to run daily via cron
- Set up Supabase Row Level Security (RLS) if needed
- Create views for common queries
- Build a frontend dashboard using Supabase client libraries

## Need Help?

- Supabase Docs: https://supabase.com/docs
- TikHub API Docs: https://tikhub.io/docs
- Check `etl_pipeline.log` for detailed error messages
