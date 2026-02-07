-- Create subscribers table for email alerts
CREATE TABLE IF NOT EXISTS subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    subscribed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    preferences JSONB DEFAULT '{"weekly_digest": true, "new_comets": true}'::jsonb,
    is_active BOOLEAN DEFAULT true,
    unsubscribed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for email lookups
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(is_active) WHERE is_active = true;

-- Add RLS policies
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;

-- Allow inserts from authenticated and anon users (for signup)
CREATE POLICY "Allow public insert" ON subscribers
    FOR INSERT
    TO anon, authenticated
    WITH CHECK (true);

-- Only service role can read/update subscribers
CREATE POLICY "Service role can manage subscribers" ON subscribers
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
