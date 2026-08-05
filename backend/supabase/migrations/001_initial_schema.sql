-- PolliSync Supabase Schema
-- Phase 1: Initial Schema Creation

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 1. DISTRICTS TABLE
-- =====================================================
CREATE TABLE districts (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  state TEXT DEFAULT 'Maharashtra',
  centroid_lat FLOAT NOT NULL,
  centroid_lng FLOAT NOT NULL,
  radius_km FLOAT DEFAULT 5.0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Seed Maharashtra districts (trained cities)
INSERT INTO districts (slug, name, state, centroid_lat, centroid_lng, radius_km) VALUES
  ('amaravati', 'Amaravati', 'Maharashtra', 16.2348, 79.7433, 5.0),
  ('aurangabad', 'Aurangabad', 'Maharashtra', 19.8762, 75.3433, 5.0),
  ('jalgaon', 'Jalgaon', 'Maharashtra', 21.0078, 75.9928, 5.0),
  ('kolhapur', 'Kolhapur', 'Maharashtra', 16.7050, 74.2433, 5.0),
  ('latur', 'Latur', 'Maharashtra', 18.4088, 76.5602, 5.0),
  ('nagpur', 'Nagpur', 'Maharashtra', 21.1458, 79.0882, 5.0),
  ('nashik', 'Nashik', 'Maharashtra', 19.9975, 73.7898, 5.0),
  ('pune', 'Pune', 'Maharashtra', 18.5204, 73.8567, 5.0),
  ('satara', 'Satara', 'Maharashtra', 17.6868, 73.9997, 5.0),
  ('solapur', 'Solapur', 'Maharashtra', 17.6599, 75.9064, 5.0),
  ('mumbai', 'Mumbai', 'Maharashtra', 19.0760, 72.8777, 5.0),
  ('ahmednagar', 'Ahmednagar', 'Maharashtra', 19.0952, 74.7496, 5.0),
  ('amravati', 'Amravati', 'Maharashtra', 20.9374, 77.7796, 5.0),
  ('chandrapur', 'Chandrapur', 'Maharashtra', 19.9615, 79.3032, 5.0),
  ('dhule', 'Dhule', 'Maharashtra', 20.9040, 74.7748, 5.0),
  ('gadchiroli', 'Gadchiroli', 'Maharashtra', 20.1809, 80.0883, 5.0),
  ('gondia', 'Gondia', 'Maharashtra', 21.4602, 80.1883, 5.0),
  ('hingoli', 'Hingoli', 'Maharashtra', 19.7150, 77.1310, 5.0),
  ('joshipura', 'Joshipura', 'Maharashtra', 16.9243, 74.8433, 5.0),
  ('parbhani', 'Parbhani', 'Maharashtra', 19.2686, 76.7708, 5.0),
  ('wardha', 'Wardha', 'Maharashtra', 20.7453, 78.6023, 5.0),
  ('washim', 'Washim', 'Maharashtra', 20.1117, 77.1330, 5.0),
  ('yeotmal', 'Yavatmal', 'Maharashtra', 20.3897, 78.1308, 5.0);

-- =====================================================
-- 2. USERS TABLE (synced with Firebase Auth)
-- =====================================================
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firebase_uid TEXT UNIQUE,
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  phone TEXT,
  role TEXT,
  organization TEXT,
  language TEXT DEFAULT 'en',
  is_active BOOLEAN DEFAULT true,
  has_onboarded BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- =====================================================
-- 3. FARMS TABLE (UUID primary key)
-- =====================================================
CREATE TABLE farms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  district_slug TEXT REFERENCES districts(slug),
  crop_type TEXT NOT NULL,
  variety TEXT,
  irrigation_method TEXT,
  pesticide_usage TEXT,
  water_availability TEXT,
  planting_date TEXT,
  harvest_date TEXT,
  location_name TEXT,
  location_lat FLOAT,
  location_lng FLOAT,
  area_acres FLOAT,
  soil_type TEXT,
  is_default BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_farms_user_id ON farms(user_id);
CREATE INDEX idx_farms_district_slug ON farms(district_slug);

-- =====================================================
-- 4. PREDICTIONS TABLE (UUID foreign key)
-- =====================================================
CREATE TABLE predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
  flowering_start TEXT NOT NULL,
  flowering_end TEXT NOT NULL,
  flowering_confidence FLOAT NOT NULL,
  psi_score INTEGER NOT NULL,
  risk_level TEXT NOT NULL,
  weather_summary JSONB DEFAULT '{}',
  pollen_summary JSONB DEFAULT '{}',
  ndvi_value FLOAT DEFAULT 0.0,
  bee_species JSONB DEFAULT '[]',
  recommendation TEXT DEFAULT '',
  model_source TEXT DEFAULT 'general',
  data_confidence TEXT DEFAULT 'standard',
  prediction_inputs JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_predictions_farm_id ON predictions(farm_id);

-- =====================================================
-- 5. WEATHER CACHE TABLE
-- =====================================================
CREATE TABLE weather_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
  temperature FLOAT,
  humidity FLOAT,
  rainfall FLOAT,
  wind_speed FLOAT,
  timestamp TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_weather_cache_farm_id ON weather_cache(farm_id);

-- =====================================================
-- 6. BEE OCCURRENCES TABLE
-- =====================================================
CREATE TABLE bee_occurrences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
  species_name TEXT,
  lat FLOAT,
  lng FLOAT,
  observation_date TEXT
);

CREATE INDEX idx_bee_occurrences_farm_id ON bee_occurrences(farm_id);

-- =====================================================
-- 7. NOTIFICATIONS TABLE
-- =====================================================
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT,
  title TEXT,
  message TEXT,
  read BOOLEAN DEFAULT false,
  farm_id UUID REFERENCES farms(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);

-- =====================================================
-- 8. TEAM MEMBERS TABLE
-- =====================================================
CREATE TABLE team_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
  email TEXT,
  name TEXT,
  role TEXT DEFAULT 'viewer',
  status TEXT DEFAULT 'pending',
  invited_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_team_members_farm_id ON team_members(farm_id);

-- =====================================================
-- 9. NOTIFICATION PREFERENCES TABLE
-- =====================================================
CREATE TABLE notification_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  push_critical BOOLEAN DEFAULT true,
  push_daily BOOLEAN DEFAULT true,
  push_system BOOLEAN DEFAULT true,
  email_weekly BOOLEAN DEFAULT false,
  email_billing BOOLEAN DEFAULT false,
  whatsapp_urgent BOOLEAN DEFAULT false,
  sms_alerts BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- =====================================================
-- 10. REFRESH TOKENS TABLE
-- =====================================================
CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- =====================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE farms ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE weather_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE bee_occurrences ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;

-- Users can read/update their own data
CREATE POLICY users_self_policy ON users
  FOR ALL USING (id = auth.uid());

-- Farms: users can only access their own farms
CREATE POLICY farms_user_policy ON farms
  FOR ALL USING (user_id = auth.uid());

-- Predictions: users can only access predictions for their farms
CREATE POLICY predictions_user_policy ON predictions
  FOR ALL USING (
    farm_id IN (SELECT id FROM farms WHERE user_id = auth.uid())
  );

-- Weather cache: users can only access their farm's weather
CREATE POLICY weather_cache_user_policy ON weather_cache
  FOR ALL USING (
    farm_id IN (SELECT id FROM farms WHERE user_id = auth.uid())
  );

-- Bee occurrences: users can only access their farm's bee data
CREATE POLICY bee_occurrences_user_policy ON bee_occurrences
  FOR ALL USING (
    farm_id IN (SELECT id FROM farms WHERE user_id = auth.uid())
  );

-- Notifications: users can only access their own notifications
CREATE POLICY notifications_user_policy ON notifications
  FOR ALL USING (user_id = auth.uid());

-- Team members: users can access teams for their farms
CREATE POLICY team_members_user_policy ON team_members
  FOR ALL USING (
    farm_id IN (SELECT id FROM farms WHERE user_id = auth.uid())
  );

-- Notification preferences: users can only access their own
CREATE POLICY notification_preferences_user_policy ON notification_preferences
  FOR ALL USING (user_id = auth.uid());

-- Refresh tokens: users can only access their own tokens
CREATE POLICY refresh_tokens_user_policy ON refresh_tokens
  FOR ALL USING (user_id = auth.uid());

-- Districts: public read access (no RLS needed for districts)
-- Districts are reference data, everyone can read them