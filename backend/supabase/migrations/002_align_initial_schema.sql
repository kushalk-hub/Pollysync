-- PolliSync Supabase Schema
-- Phase 2: Align a database that already ran 001_initial_schema.sql
-- with the full schema the backend ORM expects.
-- All statements are idempotent (safe to run multiple times).

-- =====================================================
-- USERS: add columns used by the backend auth layer
-- =====================================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_subject TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS lockout_until TIMESTAMPTZ;

-- =====================================================
-- FARMS: add columns used by the backend farm model
-- =====================================================
ALTER TABLE farms ADD COLUMN IF NOT EXISTS pesticide_usage TEXT;
ALTER TABLE farms ADD COLUMN IF NOT EXISTS water_availability TEXT;

-- =====================================================
-- REVOKED TOKENS TABLE (JWT access-token blacklist)
-- =====================================================
CREATE TABLE IF NOT EXISTS revoked_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  jti TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_revoked_tokens_jti ON revoked_tokens(jti);

-- =====================================================
-- AGENT RATE LIMITS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS agent_rate_limits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  identifier TEXT NOT NULL,
  timestamp DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_rate_limits_identifier ON agent_rate_limits(identifier);
CREATE INDEX IF NOT EXISTS idx_agent_rate_limits_timestamp ON agent_rate_limits(timestamp);

-- =====================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================
ALTER TABLE revoked_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_rate_limits ENABLE ROW LEVEL SECURITY;

-- Revoked tokens: no user-facing policy (server-side blacklist managed with the service role)
-- Agent rate limits: no user-facing policy (server-side counters managed with the service role)
