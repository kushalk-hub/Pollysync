-- PolliSync Supabase Schema
-- Phase 4: Store the fetch coordinates on weather_cache so cached weather
-- captured for a farm's previous location is never served after the farm moves.
-- Idempotent (safe to run multiple times).

ALTER TABLE weather_cache ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE weather_cache ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_weather_cache_coords
  ON weather_cache (farm_id, latitude, longitude);
