from fastapi import APIRouter
from app.core.config import settings
from app.core.cache import cache_health

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "pollisync-api"}


@router.get("/health/cache")
def health_cache() -> dict:
    return cache_health()


@router.get("/health/cors-debug")
def cors_debug() -> dict:
    return {
        "allowed_origins": settings.allowed_origins,
        "frontend_origin": settings.frontend_origin,
        "cors_origins": settings.cors_origins,
        "app_env": settings.app_env,
    }
