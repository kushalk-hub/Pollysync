import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.prediction import Prediction
from app.services.bee_service import get_mock_bees
from app.services.environment_service import get_environment_features, get_ndvi_with_cache
from app.services.feature_engineering import build_features
from app.services.weather_service import (
    cache_weather,
    fetch_weather,
    get_cached_weather,
    get_fallback_weather,
)

MODELS_DIR = Path(
    os.getenv("MODELS_DIR") or
    (Path(__file__).resolve().parent.parent.parent.parent / "ml" / "models")
)

_model_cache = {}

# Maharashtra bounding box (approximate)
MAHARASHTRA_BBOX = {"lat_min": 15.5, "lat_max": 22.0, "lon_min": 72.5, "lon_max": 80.5}


def _get_models(use_mh: bool):
    """Lazy-load model group (general or MH) and cache it per worker.
    
    Only loads the model group actually needed — avoids loading all 12
    model/scaler files at startup across every uvicorn worker.
    """
    suffix = "_mh" if use_mh else ""
    cache_key = f"models{suffix}"
    if cache_key not in _model_cache:
        models = {}
        for name in ("flowering", "psi", "risk"):
            model_path = (MODELS_DIR / f"{name}_model{suffix}.pkl").resolve()
            scaler_path = (MODELS_DIR / f"{name}_scaler{suffix}.pkl").resolve()
            
            # Validate path traversal protection
            models_dir_resolved = MODELS_DIR.resolve()
            if not str(model_path).startswith(str(models_dir_resolved)) or not str(scaler_path).startswith(str(models_dir_resolved)):
                raise ValueError("Unauthorized path traversal detected in model loading.")

            if model_path.exists():
                try:
                    models[f"{name}_model"] = joblib.load(str(model_path))
                except Exception:
                    models[f"{name}_model"] = None
            if scaler_path.exists():
                try:
                    models[f"{name}_scaler"] = joblib.load(str(scaler_path))
                except Exception:
                    models[f"{name}_scaler"] = None
        _model_cache[cache_key] = models
    return _model_cache[cache_key]


def _is_in_maharashtra(lat: float, lon: float) -> bool:
    return (
        MAHARASHTRA_BBOX["lat_min"] <= lat <= MAHARASHTRA_BBOX["lat_max"]
        and MAHARASHTRA_BBOX["lon_min"] <= lon <= MAHARASHTRA_BBOX["lon_max"]
    )


def _compute_practice_penalties(farm: Farm, rainfall_7d: float) -> dict:
    """Deterministic PSI adjustments for farm-management practices.

    Pesticide use directly threatens pollinators, and water availability
    governs crop health during flowering. Both are farm-level inputs the
    trained models were never given, so they are applied as transparent
    rule-based penalties on top of the ML PSI score.
    """
    pesticide = (farm.pesticide_usage or "").strip().lower()
    if pesticide == "during_flowering":
        pesticide_penalty = -15
    elif pesticide == "pre_flowering":
        pesticide_penalty = -5
    else:
        pesticide_penalty = 0

    water = (farm.water_availability or "").strip().lower()
    if water == "water_stressed":
        water_penalty = -12
    elif water == "rainfed" and (rainfall_7d or 0) < 15:
        water_penalty = -6
    else:
        water_penalty = 0

    return {
        "pesticide_usage": pesticide_penalty,
        "water_availability": water_penalty,
    }


def _apply_psi_penalties(psi: int, penalties: dict) -> tuple[int, str]:
    adjusted = max(0, min(100, psi + sum(penalties.values())))
    if adjusted >= 70:
        risk = "Low"
    elif adjusted >= 40:
        risk = "Medium"
    else:
        risk = "High"
    return adjusted, risk


def _predict_flowering_baseline(features: dict) -> tuple[int, float]:
    base = {
        "mustard": 15, "sunflower": 60, "cotton": 120,
    }
    crop = "mustard"
    for key in base:
        if features.get(f"crop_{key}", 0):
            crop = key
            break
    start = base[crop] + int(features.get("temp_7d_mean", 25) - 25) * 2
    start = max(1, min(365, start))
    confidence = 0.70
    return start, confidence


def _predict_psi_baseline(features: dict) -> tuple[int, str]:
    score = 0
    temp = features.get("temp_7d_mean", 25)
    humidity = features.get("humidity", 60)
    ndvi = features.get("ndvi", 0.5)
    bee_count = features.get("bee_richness", 0)

    if 20 <= temp <= 32:
        score += 25
    elif 15 <= temp <= 35:
        score += 15
    if 50 <= humidity <= 80:
        score += 20
    elif 30 <= humidity <= 90:
        score += 10
    if ndvi > 0.6:
        score += 20
    elif ndvi > 0.4:
        score += 10
    if bee_count >= 3:
        score += 15
    elif bee_count >= 1:
        score += 8

    score = max(0, min(100, score))

    if score >= 70:
        risk = "Low"
    elif score >= 40:
        risk = "Medium"
    else:
        risk = "High"

    return score, risk


def _flowering_window_from_farm_settings(farm: Farm) -> tuple[datetime, datetime, float] | None:
    if not farm.planting_date:
        return None

    try:
        planting = datetime.fromisoformat(farm.planting_date)
    except ValueError:
        return None

    crop_offsets = {
        "mustard": (35, 45),
        "sunflower": (50, 60),
        "cotton": (55, 70),
        "wheat": (70, 85),
        "rice": (60, 75),
    }
    crop_key = (farm.crop_type or "").lower()
    start_offset, end_offset = crop_offsets.get(crop_key, (45, 55))
    start_date = planting + timedelta(days=start_offset)
    end_date = planting + timedelta(days=end_offset)

    if farm.harvest_date:
        try:
            harvest = datetime.fromisoformat(farm.harvest_date)
            end_date = min(end_date, harvest)
            if end_date <= start_date:
                end_date = start_date + timedelta(days=7)
        except ValueError:
            pass

    return start_date, end_date, 0.82


def _prepare_features_for_model(features: dict, model) -> dict:
    """Augment feature dict with zone features expected by MH model."""
    if hasattr(model, "feature_names_in_"):
        try:
            expected = list(model.feature_names_in_)
        except Exception:
            expected = []
    else:
        expected = []

    if not expected:
        return features

    # Add any zone/elevation features if missing
    augmented = dict(features)
    zone_defaults = {
        "zone_western_ghats": 0, "zone_scarce_rainfall": 0,
        "zone_marathwada": 0, "zone_vidarbha": 0,
        "zone_konkan": 0, "zone_khandesh": 0,
        "elevation_m": 500,
    }
    for col, val in zone_defaults.items():
        if col in expected and col not in augmented:
            augmented[col] = val

    # Add engineered features if expected
    eng_defaults = {
        "temp_humidity": 0, "temp_ndvi": 0, "humidity_rainfall": 0,
        "temp_sq": 0, "ndvi_sq": 0, "bee_total": 0, "temp_wind": 0,
    }
    if "temp_humidity" in expected:
        augmented["temp_humidity"] = (
            augmented.get("temp_7d_mean", 25) * augmented.get("humidity", 60) / 100
        )
        augmented["temp_sq"] = augmented.get("temp_7d_mean", 25) ** 2
        augmented["ndvi_sq"] = augmented.get("ndvi", 0.5) ** 2
        augmented["bee_total"] = (
            augmented.get("bee_richness", 0) * augmented.get("bee_count", 15)
        )
        augmented["temp_wind"] = (
            augmented.get("temp_7d_mean", 25) * augmented.get("wind_speed", 10)
        )
        if "temp_ndvi" in expected:
            augmented["temp_ndvi"] = (
                augmented.get("temp_7d_mean", 25) * augmented.get("ndvi", 0.5)
            )
        if "humidity_rainfall" in expected:
            augmented["humidity_rainfall"] = (
                augmented.get("humidity", 60) * augmented.get("rainfall_7d", 5) / 100
            )

    return augmented


def _expected_feature_names(model, scaler) -> list[str]:
    for artifact in (model, scaler):
        if hasattr(artifact, "feature_names_in_"):
            try:
                names = list(artifact.feature_names_in_)
                if names:
                    return names
            except Exception:
                continue
    return []


def _build_model_frame(features: dict, model, scaler) -> pd.DataFrame:
    expected_cols = _expected_feature_names(model, scaler)
    augmented = _prepare_features_for_model(features, model or scaler)

    if not expected_cols:
        expected_cols = sorted(augmented.keys())

    row = {column: augmented.get(column, 0) for column in expected_cols}
    return pd.DataFrame([row], columns=expected_cols)


async def _get_live_or_fallback_features(farm: Farm, weather: dict, now: datetime) -> dict:
    try:
        env_features = await get_environment_features(
            lat=farm.location_lat,
            lon=farm.location_lng,
            crop_type=farm.crop_type,
            as_of=now.date(),
        )
    except Exception:
        env_features = {}

    live_ndvi = env_features.get("ndvi")

    # If the environment snapshot had no NDVI (Earth Engine hiccup), retry a
    # fresh live query before falling back to the hardcoded default.
    if live_ndvi is None:
        try:
            retry = await get_ndvi_with_cache(
                lat=farm.location_lat,
                lon=farm.location_lng,
                as_of=now.date(),
            )
            if retry is not None:
                live_ndvi = retry
        except Exception:
            pass

    pollen_tree = env_features.get("pollen_tree")
    pollen_grass = env_features.get("pollen_grass")
    pollen_weed = env_features.get("pollen_weed")
    bee_richness = env_features.get("bee_richness")

    bee_species = get_mock_bees(farm.crop_type)
    features = build_features(
        crop_type=farm.crop_type,
        temperature=env_features.get("temp_7d_mean", weather["temperature"]),
        humidity=env_features.get("humidity", weather["humidity"]),
        rainfall=env_features.get("rainfall_7d", weather["rainfall"]),
        wind_speed=env_features.get("wind_speed", weather["wind_speed"]),
        ndvi=live_ndvi if live_ndvi is not None else 0.65,
        bee_count=bee_richness if bee_richness is not None else len(bee_species),
        month=now.month,
        day_of_year=now.timetuple().tm_yday,
    )

    if pollen_tree is not None:
        features["pollen_tree"] = pollen_tree
    if pollen_grass is not None:
        features["pollen_grass"] = pollen_grass
    if pollen_weed is not None:
        features["pollen_weed"] = pollen_weed
    if bee_richness is not None:
        features["bee_richness"] = bee_richness

    return features


async def run_prediction(farm: Farm, db: Session, region: str = "auto") -> Prediction:
    cached = get_cached_weather(farm.id, db)
    if cached:
        weather = {"temperature": cached.temperature, "humidity": cached.humidity,
                   "rainfall": cached.rainfall, "wind_speed": cached.wind_speed}
    else:
        try:
            raw = await fetch_weather(farm.location_lat, farm.location_lng)
        except Exception:
            raw = get_fallback_weather(farm.location_lat, farm.location_lng)
        cached = cache_weather(farm.id, raw, db)
        weather = {"temperature": cached.temperature, "humidity": cached.humidity,
                   "rainfall": cached.rainfall, "wind_speed": cached.wind_speed}

    now = datetime.now(timezone.utc)
    bee_species = get_mock_bees(farm.crop_type)
    features = await _get_live_or_fallback_features(farm, weather, now)

    # Determine if we should use MH model
    use_mh = False
    if region == "maharashtra":
        use_mh = True
    elif region == "auto":
        use_mh = _is_in_maharashtra(farm.location_lat, farm.location_lng)

    # Lazy-load only the model group needed (general or MH)
    models = _get_models(use_mh)
    f_model = models.get("flowering_model")
    f_scaler = models.get("flowering_scaler")
    p_model = models.get("psi_model")
    p_scaler = models.get("psi_scaler")
    r_model = models.get("risk_model")
    r_scaler = models.get("risk_scaler")
    model_source = "maharashtra_v2" if use_mh else "general_v1"
    data_confidence = "high (1545 real MH rows)" if use_mh else "standard"

    models_loaded = all([f_model, f_scaler, p_model, p_scaler, r_model, r_scaler])

    if models_loaded:
        try:
            flowering_df = _build_model_frame(features, f_model, f_scaler)
            X_scaled = pd.DataFrame(f_scaler.transform(flowering_df), columns=flowering_df.columns)
            start_doy = int(round(f_model.predict(X_scaled)[0]))
            start_doy = max(1, min(365, start_doy))
            confidence = 0.92 if use_mh else 0.87

            psi_df = _build_model_frame(features, p_model, p_scaler)
            psi = int(round(p_model.predict(pd.DataFrame(p_scaler.transform(psi_df), columns=psi_df.columns))[0]))
            psi = max(0, min(100, psi))

            risk_df = _build_model_frame(features, r_model, r_scaler)
            risk_raw = r_model.predict(pd.DataFrame(r_scaler.transform(risk_df), columns=risk_df.columns))[0]
            if hasattr(r_model, "_label_encoder"):
                risk = r_model._label_encoder.inverse_transform([risk_raw])[0]
            else:
                risk = risk_raw
        except Exception:
            start_doy, confidence = _predict_flowering_baseline(features)
            psi, risk = _predict_psi_baseline(features)
            model_source = "baseline"
            data_confidence = "low"
    else:
        start_doy, confidence = _predict_flowering_baseline(features)
        psi, risk = _predict_psi_baseline(features)
        model_source = "baseline"
        data_confidence = "low"

    from datetime import datetime as dt
    settings_window = _flowering_window_from_farm_settings(farm)
    if settings_window:
        start_date, end_date, settings_confidence = settings_window
        confidence = max(confidence, settings_confidence)
    else:
        start_date = dt.fromordinal(dt(now.year, 1, 1).toordinal() + start_doy - 1)
        end_date = dt.fromordinal(start_date.toordinal() + 7)

    # Farm-management practice penalties (rule-based, applied on top of ML PSI)
    penalties = _compute_practice_penalties(farm, features.get("rainfall_7d", 0))
    if any(penalties.values()):
        psi, risk = _apply_psi_penalties(psi, penalties)

    prediction = Prediction(
        farm_id=farm.id,
        flowering_start=start_date.strftime("%Y-%m-%d"),
        flowering_end=end_date.strftime("%Y-%m-%d"),
        flowering_confidence=confidence,
        psi_score=psi,
        risk_level=risk,
        weather_summary=weather,
        pollen_summary={"tree": features["pollen_tree"],
                        "grass": features["pollen_grass"],
                        "weed": features["pollen_weed"]},
        ndvi_value=features["ndvi"],
        bee_species=bee_species,
        model_source=model_source,
        data_confidence=data_confidence,
        prediction_inputs={
            "farm_settings": {
                "crop_type": farm.crop_type,
                "planting_date": farm.planting_date,
                "harvest_date": farm.harvest_date,
                "location_name": farm.location_name,
                "location_lat": farm.location_lat,
                "location_lng": farm.location_lng,
                "pesticide_usage": farm.pesticide_usage,
                "water_availability": farm.water_availability,
            },
            "practice_penalties": {
                "pesticide_usage": {
                    "level": farm.pesticide_usage or "unknown",
                    "psi_adjustment": penalties["pesticide_usage"],
                },
                "water_availability": {
                    "level": farm.water_availability or "unknown",
                    "psi_adjustment": penalties["water_availability"],
                },
            },
        },
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction

