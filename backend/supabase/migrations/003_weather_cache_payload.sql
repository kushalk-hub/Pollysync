-- PolliSync Supabase Schema
-- Phase 3: Store the full Open-Meteo response (current + daily forecast)
-- on weather_cache so cached replies can serve the 7-day forecast.
-- Idempotent (safe to run multiple times).

ALTER TABLE weather_cache ADD COLUMN IF NOT EXISTS payload JSONB;
