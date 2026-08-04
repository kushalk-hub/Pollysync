import warnings

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
