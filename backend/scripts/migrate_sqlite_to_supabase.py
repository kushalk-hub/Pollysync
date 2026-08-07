"""
PolliSync Data Migration Script
Migrates data from SQLite to Supabase PostgreSQL

Usage:
    python migrate_sqlite_to_supabase.py

Requirements:
    - sqlite3 (built-in)
    - supabase (pip install supabase)
    - psycopg2-binary (pip install psycopg2-binary)
"""

import os
import sys
import json
import uuid
import sqlite3
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client, Client


# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pollisync.db")


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_sqlite_connection() -> sqlite3.Connection:
    if not os.path.exists(SQLITE_DB_PATH):
        raise FileNotFoundError(f"SQLite database not found at {SQLITE_DB_PATH}")
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def generate_uuid() -> str:
    return str(uuid.uuid4())


def parse_json(value, default):
    """Parse a JSON column value that may be a str (SQLite) into a Python object
    so it can be stored in a Supabase JSONB column."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return default


def migrate_users(sqlite_conn: sqlite3.Connection, supabase: Client) -> dict:
    """Migrate users and return mapping of old_id -> new_uuid"""
    print("Migrating users...")
    cursor = sqlite_conn.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    
    id_mapping = {}
    
    for row in rows:
        old_id = row["id"]
        new_uuid = generate_uuid()
        
        supabase.table("users").insert({
            "id": new_uuid,
            "email": row["email"],
            "hashed_password": row["hashed_password"],
            "full_name": row["full_name"],
            "phone": row["phone"],
            "role": row["role"],
            "organization": row["organization"],
            "language": row["language"] or "en",
            "oauth_provider": row["oauth_provider"],
            "oauth_subject": row["oauth_subject"],
            "is_active": bool(row["is_active"]),
            "has_onboarded": bool(row["has_onboarded"]),
            "failed_login_attempts": row["failed_login_attempts"] or 0,
            "lockout_until": row["lockout_until"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }).execute()
        
        id_mapping[old_id] = new_uuid
        print(f"  Migrated user: {row['email']} ({old_id} -> {new_uuid})")
    
    print(f"Migrated {len(rows)} users")
    return id_mapping


def migrate_districts(supabase: Client):
    """Districts are already seeded by the database initialization"""
    print("Checking districts...")
    result = supabase.table("districts").select("*").execute()
    if result.data:
        print(f"Found {len(result.data)} districts (already seeded)")
    else:
        print("No districts found. Please run the backend to seed districts.")


def migrate_farms(sqlite_conn: sqlite3.Connection, supabase: Client, user_id_mapping: dict) -> dict:
    """Migrate farms and return mapping of old_id -> new_uuid"""
    print("Migrating farms...")
    cursor = sqlite_conn.execute("SELECT * FROM farms")
    rows = cursor.fetchall()
    
    id_mapping = {}
    
    # Get districts for location mapping
    districts_result = supabase.table("districts").select("*").execute()
    districts = {d["name"].lower(): d["slug"] for d in districts_result.data}
    
    for row in rows:
        old_id = row["id"]
        new_uuid = generate_uuid()
        
        # Map old user_id to new UUID
        new_user_id = user_id_mapping.get(row["user_id"])
        if not new_user_id:
            print(f"  WARNING: User {row['user_id']} not found for farm {row['name']}, skipping")
            continue
        
        # Try to determine district from location_name
        district_slug = None
        if row["location_name"]:
            location_lower = row["location_name"].lower()
            for name, slug in districts.items():
                if name in location_lower or location_lower in name:
                    district_slug = slug
                    break
        
        supabase.table("farms").insert({
            "id": new_uuid,
            "user_id": new_user_id,
            "name": row["name"],
            "district_slug": district_slug,
            "crop_type": row["crop_type"],
            "variety": row["variety"],
            "irrigation_method": row["irrigation_method"],
            "pesticide_usage": row["pesticide_usage"],
            "water_availability": row["water_availability"],
            "planting_date": row["planting_date"],
            "harvest_date": row["harvest_date"],
            "location_name": row["location_name"],
            "location_lat": row["location_lat"],
            "location_lng": row["location_lng"],
            "area_acres": row["area_acres"],
            "soil_type": row["soil_type"],
            "is_default": False,
            "created_at": row["created_at"],
        }).execute()
        
        id_mapping[old_id] = new_uuid
        print(f"  Migrated farm: {row['name']} ({old_id} -> {new_uuid})")
    
    print(f"Migrated {len(rows)} farms")
    return id_mapping


def migrate_predictions(sqlite_conn: sqlite3.Connection, supabase: Client, farm_id_mapping: dict):
    """Migrate predictions"""
    print("Migrating predictions...")
    cursor = sqlite_conn.execute("SELECT * FROM predictions")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        new_uuid = generate_uuid()
        
        # Map old farm_id to new UUID
        new_farm_id = farm_id_mapping.get(row["farm_id"])
        if not new_farm_id:
            print(f"  WARNING: Farm {row['farm_id']} not found for prediction {row['id']}, skipping")
            continue
        
        try:
            prediction_inputs = row["prediction_inputs"]
        except IndexError:
            prediction_inputs = "{}"
        
        supabase.table("predictions").insert({
            "id": new_uuid,
            "farm_id": new_farm_id,
            "flowering_start": row["flowering_start"],
            "flowering_end": row["flowering_end"],
            "flowering_confidence": row["flowering_confidence"],
            "psi_score": row["psi_score"],
            "risk_level": row["risk_level"],
            "weather_summary": parse_json(row["weather_summary"], {}),
            "pollen_summary": parse_json(row["pollen_summary"], {}),
            "ndvi_value": row["ndvi_value"],
            "bee_species": parse_json(row["bee_species"], []),
            "recommendation": row["recommendation"],
            "model_source": row["model_source"],
            "data_confidence": row["data_confidence"],
            "prediction_inputs": parse_json(prediction_inputs, {}),
            "created_at": row["created_at"],
        }).execute()
        
        count += 1
        print(f"  Migrated prediction: {row['id']} -> {new_uuid}")
    
    print(f"Migrated {count} predictions")


def migrate_weather_cache(sqlite_conn: sqlite3.Connection, supabase: Client, farm_id_mapping: dict):
    """Migrate weather cache"""
    print("Migrating weather cache...")
    cursor = sqlite_conn.execute("SELECT * FROM weather_cache")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        new_uuid = generate_uuid()
        
        new_farm_id = farm_id_mapping.get(row["farm_id"])
        if not new_farm_id:
            continue
        
        supabase.table("weather_cache").insert({
            "id": new_uuid,
            "farm_id": new_farm_id,
            "temperature": row["temperature"],
            "humidity": row["humidity"],
            "rainfall": row["rainfall"],
            "wind_speed": row["wind_speed"],
            "timestamp": row["timestamp"],
        }).execute()
        
        count += 1
    
    print(f"Migrated {count} weather cache entries")


def migrate_bee_occurrences(sqlite_conn: sqlite3.Connection, supabase: Client, farm_id_mapping: dict):
    """Migrate bee occurrences"""
    print("Migrating bee occurrences...")
    cursor = sqlite_conn.execute("SELECT * FROM bee_occurrences")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        new_uuid = generate_uuid()
        
        new_farm_id = farm_id_mapping.get(row["farm_id"])
        if not new_farm_id:
            continue
        
        supabase.table("bee_occurrences").insert({
            "id": new_uuid,
            "farm_id": new_farm_id,
            "species_name": row["species_name"],
            "lat": row["lat"],
            "lng": row["lng"],
            "observation_date": row["observation_date"],
        }).execute()
        
        count += 1
    
    print(f"Migrated {count} bee occurrences")


def migrate_notifications(sqlite_conn: sqlite3.Connection, supabase: Client, user_id_mapping: dict, farm_id_mapping: dict):
    """Migrate notifications"""
    print("Migrating notifications...")
    cursor = sqlite_conn.execute("SELECT * FROM notifications")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        new_uuid = generate_uuid()
        
        new_user_id = user_id_mapping.get(row["user_id"])
        new_farm_id = farm_id_mapping.get(row["farm_id"]) if row["farm_id"] else None
        
        if not new_user_id:
            continue
        
        supabase.table("notifications").insert({
            "id": new_uuid,
            "type": row["type"],
            "title": row["title"],
            "message": row["message"],
            "read": bool(row["read"]),
            "farm_id": new_farm_id,
            "user_id": new_user_id,
            "created_at": row["created_at"],
        }).execute()
        
        count += 1
    
    print(f"Migrated {count} notifications")


def migrate_refresh_tokens(sqlite_conn: sqlite3.Connection, supabase: Client, user_id_mapping: dict):
    """Migrate refresh tokens"""
    print("Migrating refresh tokens...")
    cursor = sqlite_conn.execute("SELECT * FROM refresh_tokens")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        new_uuid = generate_uuid()
        
        new_user_id = user_id_mapping.get(row["user_id"])
        if not new_user_id:
            continue
        
        supabase.table("refresh_tokens").insert({
            "id": new_uuid,
            "user_id": new_user_id,
            "token_hash": row["token_hash"],
            "expires_at": row["expires_at"],
            "revoked_at": row["revoked_at"],
            "created_at": row["created_at"],
        }).execute()
        
        count += 1
    
    print(f"Migrated {count} refresh tokens")


def migrate_team_members(sqlite_conn: sqlite3.Connection, supabase: Client, user_id_mapping: dict, farm_id_mapping: dict):
    """Migrate team members"""
    print("Migrating team members...")
    cursor = sqlite_conn.execute("SELECT * FROM team_members")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        new_uuid = generate_uuid()
        
        new_farm_id = farm_id_mapping.get(row["farm_id"])
        new_invited_by = user_id_mapping.get(row["invited_by"]) if row["invited_by"] else None
        
        if not new_farm_id:
            print(f"  WARNING: Farm {row['farm_id']} not found for team member {row['id']}, skipping")
            continue
        
        supabase.table("team_members").insert({
            "id": new_uuid,
            "farm_id": new_farm_id,
            "email": row["email"],
            "name": row["name"],
            "role": row["role"],
            "status": row["status"],
            "invited_by": new_invited_by,
            "created_at": row["created_at"],
        }).execute()
        
        count += 1
        print(f"  Migrated team member: {row['id']} -> {new_uuid}")
    
    print(f"Migrated {count} team members")


def migrate_notification_preferences(sqlite_conn: sqlite3.Connection, supabase: Client, user_id_mapping: dict):
    """Migrate notification preferences"""
    print("Migrating notification preferences...")
    cursor = sqlite_conn.execute("SELECT * FROM notification_preferences")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        new_uuid = generate_uuid()
        
        new_user_id = user_id_mapping.get(row["user_id"])
        if not new_user_id:
            print(f"  WARNING: User {row['user_id']} not found for notification preferences, skipping")
            continue
        
        supabase.table("notification_preferences").insert({
            "id": new_uuid,
            "user_id": new_user_id,
            "push_critical": bool(row["push_critical"]),
            "push_daily": bool(row["push_daily"]),
            "push_system": bool(row["push_system"]),
            "email_weekly": bool(row["email_weekly"]),
            "email_billing": bool(row["email_billing"]),
            "whatsapp_urgent": bool(row["whatsapp_urgent"]),
            "sms_alerts": bool(row["sms_alerts"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }).execute()
        
        count += 1
    
    print(f"Migrated {count} notification preferences")


def migrate_revoked_tokens(sqlite_conn: sqlite3.Connection, supabase: Client):
    """Migrate revoked tokens"""
    print("Migrating revoked tokens...")
    cursor = sqlite_conn.execute("SELECT * FROM revoked_tokens")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        supabase.table("revoked_tokens").insert({
            "jti": row["jti"],
            "expires_at": row["expires_at"],
        }).execute()
        
        count += 1
    
    print(f"Migrated {count} revoked tokens")


def migrate_agent_rate_limits(sqlite_conn: sqlite3.Connection, supabase: Client):
    """Migrate agent rate limits"""
    print("Migrating agent rate limits...")
    cursor = sqlite_conn.execute("SELECT * FROM agent_rate_limits")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        supabase.table("agent_rate_limits").insert({
            "identifier": row["identifier"],
            "timestamp": row["timestamp"],
        }).execute()
        
        count += 1
    
    print(f"Migrated {count} agent rate limits")


def main():
    print("=" * 60)
    print("PolliSync Data Migration: SQLite -> Supabase PostgreSQL")
    print("=" * 60)
    
    try:
        supabase = get_supabase_client()
        sqlite_conn = get_sqlite_connection()
        
        print(f"\nSQLite database: {SQLITE_DB_PATH}")
        print(f"Supabase URL: {SUPABASE_URL}")
        
        # Check if SQLite has data
        cursor = sqlite_conn.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        if user_count == 0:
            print("\nNo users found in SQLite database. Nothing to migrate.")
            return
        
        print(f"\nFound {user_count} users in SQLite database")
        
        # Confirm migration
        response = input("\nProceed with migration? (yes/no): ")
        if response.lower() != "yes":
            print("Migration cancelled.")
            return
        
        print("\nStarting migration...\n")
        
        # Migrate in order
        user_id_mapping = migrate_users(sqlite_conn, supabase)
        migrate_districts(supabase)
        farm_id_mapping = migrate_farms(sqlite_conn, supabase, user_id_mapping)
        migrate_predictions(sqlite_conn, supabase, farm_id_mapping)
        migrate_weather_cache(sqlite_conn, supabase, farm_id_mapping)
        migrate_bee_occurrences(sqlite_conn, supabase, farm_id_mapping)
        migrate_notifications(sqlite_conn, supabase, user_id_mapping, farm_id_mapping)
        migrate_refresh_tokens(sqlite_conn, supabase, user_id_mapping)
        migrate_team_members(sqlite_conn, supabase, user_id_mapping, farm_id_mapping)
        migrate_notification_preferences(sqlite_conn, supabase, user_id_mapping)
        migrate_revoked_tokens(sqlite_conn, supabase)
        migrate_agent_rate_limits(sqlite_conn, supabase)
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
        # Print summary
        print("\nMigration Summary:")
        print(f"  Users: {len(user_id_mapping)}")
        print(f"  Farms: {len(farm_id_mapping)}")
        
        sqlite_conn.close()
        
    except Exception as e:
        print(f"\nError during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
