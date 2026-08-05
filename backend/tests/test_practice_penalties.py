from app.models.farm import Farm
from app.services.prediction_service import (
    _apply_psi_penalties,
    _compute_practice_penalties,
)


def _farm(pesticide_usage=None, water_availability=None):
    return Farm(
        id="test",
        user_id="user",
        name="Test Farm",
        crop_type="Mustard",
        pesticide_usage=pesticide_usage,
        water_availability=water_availability,
    )


def test_no_penalties_when_unrecorded():
    penalties = _compute_practice_penalties(_farm(), rainfall_7d=20)
    assert penalties == {"pesticide_usage": 0, "water_availability": 0}


def test_pesticide_penalties_scale_with_timing():
    assert _compute_practice_penalties(_farm("none"), 20)["pesticide_usage"] == 0
    assert _compute_practice_penalties(_farm("pre_flowering"), 20)["pesticide_usage"] == -5
    assert _compute_practice_penalties(_farm("during_flowering"), 20)["pesticide_usage"] == -15


def test_water_penalties():
    assert _compute_practice_penalties(_farm(water_availability="irrigated"), 5)["water_availability"] == 0
    assert _compute_practice_penalties(_farm(water_availability="water_stressed"), 5)["water_availability"] == -12
    assert _compute_practice_penalties(_farm(water_availability="rainfed"), 5)["water_availability"] == -6
    assert _compute_practice_penalties(_farm(water_availability="rainfed"), 30)["water_availability"] == 0


def test_apply_psi_penalties_floors_at_zero():
    psi, risk = _apply_psi_penalties(10, {"pesticide_usage": -15, "water_availability": -12})
    assert psi == 0
    assert risk == "High"


def test_apply_psi_penalties_reclassifies_risk():
    psi, risk = _apply_psi_penalties(75, {"pesticide_usage": -15, "water_availability": 0})
    assert psi == 60
    assert risk == "Medium"
