-- Migration Script: Add Trend Tracking
-- Run this if you already have the old schema without trend tracking
-- For new setups, use setup_database_supabase.sql instead

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

-- Add source_trend column to creator_stats (if it doesn't exist)
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

-- Verify migration
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('daily_trends', 'creator_stats')
ORDER BY table_name, ordinal_position;
