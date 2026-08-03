import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path, override=True)


@dataclass(frozen=True)
class Settings:
    app_name: str = "PolliSync API"
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./pollisync.db")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "")
    cors_origins: str = os.getenv("CORS_ORIGINS", "")
    secret_key: str = os.getenv("SECRET_KEY", "")
    algorithm: str = "HS256"
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
    refresh_token_days: int = int(os.getenv("REFRESH_TOKEN_DAYS", "14"))
    oauth_google_client_id: str = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "")
    oauth_google_client_secret: str = os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "")
    oauth_google_redirect_uri: str = os.getenv("OAUTH_GOOGLE_REDIRECT_URI", "")
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
    firebase_service_account_json: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    firebase_service_account_path: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")
    firebase_private_key: str = os.getenv("FIREBASE_PRIVATE_KEY", "")
    firebase_client_email: str = os.getenv("FIREBASE_CLIENT_EMAIL", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    pollen_api_key: str = os.getenv("POLLEN_API_KEY", "")
    ee_service_account: str = os.getenv("EE_SERVICE_ACCOUNT", "")
    ee_private_key_file: str = os.getenv("EE_PRIVATE_KEY_FILE", "")

    @property
    def allowed_origins(self) -> list[str]:
        origins = []
        if self.cors_origins:
            origins = [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]
        if self.frontend_origin:
            cleaned_frontend = self.frontend_origin.strip().rstrip("/")
            if cleaned_frontend not in origins:
                origins.append(cleaned_frontend)
        return origins

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}
    
    @property
    def is_supabase_configured(self) -> bool:
        """Check if Supabase is properly configured."""
        return bool(self.supabase_url and self.supabase_anon_key)

    def validate_security(self) -> None:
        if not self.secret_key:
            raise RuntimeError("SECRET_KEY must be set in .env to a strong random value.")
        if self.is_production:
            if (
                self.secret_key == "change-me-in-production"
                or "dev-key" in self.secret_key
                or "do-not-use" in self.secret_key
                or len(self.secret_key) < 32
            ):
                raise RuntimeError("SECRET_KEY must be a strong random value of at least 32 characters in production.")


settings = Settings()
