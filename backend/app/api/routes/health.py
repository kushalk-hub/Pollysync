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


@router.get("/health/models")
def health_models() -> dict:
    """Report where the ML model artifacts live and whether they loaded.

    Lets you confirm the deployed backend resolves the .pkl directory and
    successfully loads both model groups (general + Maharashtra).
    """
    from app.services.prediction_service import MODELS_DIR, _get_models

    artifacts = []
    for name in ("flowering", "psi", "risk"):
        for suffix in ("", "_mh"):
            pkl = MODELS_DIR / f"{name}_model{suffix}.pkl"
            artifacts.append({"file": pkl.name, "exists": pkl.exists()})

    return {
        "models_dir": str(MODELS_DIR),
        "models_dir_exists": MODELS_DIR.exists(),
        "general_loaded": all(_get_models(False).values()),
        "maharashtra_loaded": all(_get_models(True).values()),
        "artifacts": artifacts,
    }
