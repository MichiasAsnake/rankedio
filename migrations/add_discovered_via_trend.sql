-- Migration: Add discovered_via_trend column to creators table
-- This tracks which trending keyword led to the discovery of each creator

ALTER TABLE creators
ADD COLUMN IF NOT EXISTS discovered_via_trend VARCHAR(255);

-- Create index for filtering by trend
CREATE INDEX IF NOT EXISTS idx_creators_discovered_via_trend
ON creators(discovered_via_trend);

COMMENT ON COLUMN creators.discovered_via_trend IS 'The trending keyword that led to this creator being discovered (e.g., #WinterFashion)';
