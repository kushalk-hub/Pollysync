import warnings

from unittest.mock import AsyncMock, patch

import pandas as pd

import pytest


@pytest.mark.asyncio
async def test_prediction_models_predict_without_feature_name_warning():
    from app.services.prediction_service import _get_models, _build_model_frame

    models = _get_models(use_mh=True)
    f_model = models["flowering_model"]
    f_scaler = models["flowering_scaler"]

    features = {
        "temp_7d_mean": 27.5,
        "humidity": 62.0,
        "rainfall_7d": 4.2,
        "wind_speed": 9.5,
        "ndvi": 0.55,
        "day_of_year": 60,
        "month": 3,
        "crop_mustard": 1,
        "crop_sunflower": 0,
        "crop_cotton": 0,
        "bee_richness": 3,
        "pollen_tree": 40,
        "pollen_grass": 30,
        "pollen_weed": 20,
    }

    frame = _build_model_frame(features, f_model, f_scaler)
    scaled = pd.DataFrame(f_scaler.transform(frame), columns=frame.columns)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        start_doy = int(round(f_model.predict(scaled)[0]))

    bad = [str(w.message) for w in caught if "feature names" in str(w.message).lower()]
    assert not bad, f"predict emitted feature-name warning: {bad}"
    assert 1 <= start_doy <= 365


@pytest.mark.asyncio
async def test_live_features_retries_ndvi_before_falling_back():
    from app.services.prediction_service import _get_live_or_fallback_features

    class FakeFarm:
        location_lat = 19.99
        location_lng = 73.8
        crop_type = "sunflower"

    env_features = {
        "temp_7d_mean": 24.6,
        "humidity": 94.2,
        "rainfall_7d": 48.3,
        "wind_speed": 14.1,
        "bee_richness": 5,
        "pollen_tree": 2,
        "pollen_grass": 3,
        "pollen_weed": 2,
        "ndvi": None,
    }
    weather = {
        "temperature": 24.6,
        "humidity": 94.2,
        "rainfall": 48.3,
        "wind_speed": 14.1,
    }

    with (
        patch(
            "app.services.prediction_service.get_environment_features",
            AsyncMock(return_value=env_features),
        ) as mock_env,
        patch(
            "app.services.prediction_service.get_ndvi_with_cache",
            AsyncMock(return_value=0.2388),
        ) as mock_ndvi,
    ):
        result = await _get_live_or_fallback_features(
            FakeFarm(), weather, __import__("datetime").datetime.now()
        )

    mock_ndvi.assert_awaited_once()
    assert result["ndvi"] == 0.2388


@pytest.mark.asyncio
async def test_live_features_falls_back_when_ndvi_unavailable():
    from app.services.prediction_service import _get_live_or_fallback_features

    class FakeFarm:
        location_lat = 19.99
        location_lng = 73.8
        crop_type = "sunflower"

    env_features = {
        "temp_7d_mean": 24.6,
        "humidity": 94.2,
        "rainfall_7d": 48.3,
        "wind_speed": 14.1,
        "bee_richness": 5,
        "pollen_tree": 2,
        "pollen_grass": 3,
        "pollen_weed": 2,
        "ndvi": None,
    }
    weather = {
        "temperature": 24.6,
        "humidity": 94.2,
        "rainfall": 48.3,
        "wind_speed": 14.1,
    }

    with (
        patch(
            "app.services.prediction_service.get_environment_features",
            AsyncMock(return_value=env_features),
        ),
        patch(
            "app.services.prediction_service.get_ndvi_with_cache",
            AsyncMock(return_value=None),
        ),
    ):
        result = await _get_live_or_fallback_features(
            FakeFarm(), weather, __import__("datetime").datetime.now()
        )

    assert result["ndvi"] == 0.65
