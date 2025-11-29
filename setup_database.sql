-- TikTok Creator Discovery Engine - Database Schema
-- Run this script to create the required tables

-- Drop tables if they exist (optional - uncomment for fresh start)
-- DROP TABLE IF EXISTS creator_stats CASCADE;
-- DROP TABLE IF EXISTS creators CASCADE;

-- Main Creator Profile Table
CREATE TABLE IF NOT EXISTS creators (
    user_id VARCHAR(50) PRIMARY KEY, -- distinct 'sec_uid' or 'uid'
    handle VARCHAR(100) NOT NULL,
    nickname VARCHAR(255),
    avatar_url TEXT,
    signature TEXT,
    last_updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on handle for faster lookups
CREATE INDEX IF NOT EXISTS idx_creators_handle ON creators(handle);

-- Daily Trends Tracking
CREATE TABLE IF NOT EXISTS daily_trends (
    id SERIAL PRIMARY KEY,
    trend_keyword VARCHAR(255) NOT NULL,
    discovered_at DATE DEFAULT CURRENT_DATE,
    rank INT,  -- Position in trending list
    UNIQUE(trend_keyword, discovered_at)
);

CREATE INDEX IF NOT EXISTS idx_daily_trends_date ON daily_trends(discovered_at);
CREATE INDEX IF NOT EXISTS idx_daily_trends_keyword ON daily_trends(trend_keyword);

-- Daily Snapshot for Growth Tracking
CREATE TABLE IF NOT EXISTS creator_stats (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES creators(user_id) ON DELETE CASCADE,
    recorded_date DATE DEFAULT CURRENT_DATE,

    -- Raw Stats
    follower_count BIGINT,
    heart_count BIGINT,    -- Total Likes
    video_count INT,

    -- Calculated Metrics
    daily_growth_followers INT,
    daily_growth_percent DECIMAL(5, 2),

    -- Source Trend (which trending keyword led to this discovery)
    source_trend VARCHAR(255),

    UNIQUE(user_id, recorded_date) -- Prevents duplicate entries per day
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_creator_stats_user_id ON creator_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_creator_stats_recorded_date ON creator_stats(recorded_date);
CREATE INDEX IF NOT EXISTS idx_creator_stats_growth ON creator_stats(daily_growth_percent DESC);
CREATE INDEX IF NOT EXISTS idx_creator_stats_source_trend ON creator_stats(source_trend);

-- Verify tables created successfully
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('creators', 'creator_stats')
ORDER BY table_name;

-- Note: To display table structures in psql client, use:
-- \d creators
-- \d creator_stats
-- (These commands only work in psql, not in Supabase SQL Editor)
