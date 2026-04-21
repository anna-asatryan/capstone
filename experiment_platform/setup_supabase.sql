-- ============================================================================
-- Experiment Platform: Supabase Schema
-- Run this ONCE in the Supabase SQL Editor after creating a new project.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- participants: one row per person who starts the experiment
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_number SERIAL,                     -- auto-incrementing, drives round-robin group assignment
    participant_group TEXT NOT NULL,               -- 'group_1' | 'group_2' | 'group_3'
    age_range TEXT,                                -- '18-24' | '25-34' | '35-44' | '45-54' | '55+'
    education TEXT,                                -- 'High school' | "Bachelor's (in progress)" | "Bachelor's (completed)" | "Master's or higher"
    consent_timestamp TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,                      -- set when experiment finishes
    completed BOOLEAN DEFAULT FALSE,
    trust_rating INTEGER,                          -- 1-5, collected post-experiment
    self_reported_reliance TEXT,                   -- 'Never'|'Rarely'|'Sometimes'|'Often'|'Always'
    ai_surprise_strategy TEXT,                     -- self-reported strategy when AI surprises
    total_cost FLOAT,                              -- participant's total loss across 18 experimental trials
    optimal_cost FLOAT,                            -- what an optimal cost-minimizing strategy would have lost
    session_id TEXT,                               -- used for retake prevention + session resumption
    current_trial_index INTEGER DEFAULT 0,         -- for resumption after disconnect
    current_phase TEXT DEFAULT 'consent'           -- tracks where participant is in the flow
);

-- ----------------------------------------------------------------------------
-- trials: one row per trial per participant (2 practice + 18 experimental = 20 rows per completion)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
    trial_index INTEGER NOT NULL,                  -- -2,-1 practice; 1-18 experimental
    case_id INTEGER NOT NULL,                      -- links back to the case data in config.py
    case_position INTEGER NOT NULL,                -- static fixture position (-2..-1 or 1..18)
    block TEXT NOT NULL,                           -- 'practice' | 'block_1' | 'block_2' | 'block_3'
    protocol TEXT NOT NULL,                        -- 'no_ai' | 'ai_first' | 'human_first'
    difficulty_tier TEXT NOT NULL,                 -- 'easy' | 'medium' | 'hard'
    difficulty_score FLOAT,
    y_true INTEGER NOT NULL,                       -- 1=default, 0=repaid
    pred_prob FLOAT NOT NULL,                      -- model-predicted probability of default
    model_correct INTEGER NOT NULL,                -- 1 if model is correct at 0.5 threshold
    model_optimal INTEGER NOT NULL,                -- 1 if model decision = cost-optimal decision

    -- Step 1 responses (human_first protocol only; NULL otherwise)
    decision_init INTEGER,                         -- 1=approve, 0=reject
    prob_estimate_init FLOAT,                      -- [0,1]
    time_to_init_ms INTEGER,

    -- Final responses (always populated)
    decision_final INTEGER NOT NULL,               -- 1=approve, 0=reject
    prob_estimate_final FLOAT NOT NULL,            -- [0,1]
    confidence INTEGER,                            -- 0-100, optional
    time_to_final_ms INTEGER,
    total_trial_ms INTEGER NOT NULL,

    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE (participant_id, trial_index)           -- prevents duplicate submissions on retry
);

-- ----------------------------------------------------------------------------
-- quiz_responses: logs every answer to the comprehension quiz (both attempts if needed)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
    attempt INTEGER NOT NULL DEFAULT 1,            -- 1 or 2
    question_id INTEGER NOT NULL,                  -- 1..3
    selected_answer TEXT NOT NULL,                 -- 'A' | 'B' | 'C' | 'D'
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- Indexes
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_participants_session_id ON participants (session_id);
CREATE INDEX IF NOT EXISTS idx_participants_completed ON participants (completed);
CREATE INDEX IF NOT EXISTS idx_trials_participant_id ON trials (participant_id);
CREATE INDEX IF NOT EXISTS idx_quiz_responses_participant_id ON quiz_responses (participant_id);

-- ----------------------------------------------------------------------------
-- Row Level Security
-- The anon key is used by the Streamlit app. We allow insert/select/update
-- only. Delete is NOT granted to anon: data should be removed via the
-- service role key from the Supabase dashboard.
-- ----------------------------------------------------------------------------
ALTER TABLE participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE trials ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_responses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_insert_participants" ON participants;
DROP POLICY IF EXISTS "anon_select_participants" ON participants;
DROP POLICY IF EXISTS "anon_update_participants" ON participants;
DROP POLICY IF EXISTS "anon_insert_trials" ON trials;
DROP POLICY IF EXISTS "anon_select_trials" ON trials;
DROP POLICY IF EXISTS "anon_update_trials" ON trials;
DROP POLICY IF EXISTS "anon_insert_quiz_responses" ON quiz_responses;
DROP POLICY IF EXISTS "anon_select_quiz_responses" ON quiz_responses;

CREATE POLICY "anon_insert_participants" ON participants FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "anon_select_participants" ON participants FOR SELECT TO anon USING (true);
CREATE POLICY "anon_update_participants" ON participants FOR UPDATE TO anon USING (true) WITH CHECK (true);

CREATE POLICY "anon_insert_trials"       ON trials       FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "anon_select_trials"       ON trials       FOR SELECT TO anon USING (true);
CREATE POLICY "anon_update_trials"       ON trials       FOR UPDATE TO anon USING (true) WITH CHECK (true);

CREATE POLICY "anon_insert_quiz_responses" ON quiz_responses FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "anon_select_quiz_responses" ON quiz_responses FOR SELECT TO anon USING (true);
