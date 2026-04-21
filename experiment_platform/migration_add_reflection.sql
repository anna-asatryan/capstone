-- ============================================================================
-- Migration: add reflection columns to existing participants table.
-- Run this ONCE in the Supabase SQL Editor if you already ran setup_supabase.sql
-- previously and want to add the post-trial metacognitive reflection columns
-- without dropping existing tables.
--
-- If you are setting up Supabase from scratch, ignore this file — run
-- setup_supabase.sql instead, which already includes these columns.
-- ============================================================================

ALTER TABLE participants
    ADD COLUMN IF NOT EXISTS self_reported_reliance TEXT,
    ADD COLUMN IF NOT EXISTS ai_surprise_strategy TEXT;

-- Verification
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'participants'
  AND column_name IN ('self_reported_reliance', 'ai_surprise_strategy');
