from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.farm import Farm
from app.models.prediction import Prediction, load_json
from app.models.user import User
from app.schemas.prediction import DashboardSummary, PredictionCreate, PredictionRead
from app.services.prediction_service import run_prediction

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("", response_model=PredictionRead, status_code=201)
async def create_prediction(
    payload: PredictionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Prediction:
    farm = _owned_farm_or_404(payload.farm_id, current_user.id, db)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    prediction = await run_prediction(farm, db, region=payload.region)
    return _prediction_to_read(prediction, farm)


@router.get("", response_model=list[PredictionRead])
def list_predictions(
    farm_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Prediction]:
    farm = _owned_farm_or_404(farm_id, current_user.id, db)
    rows = (
        db.scalars(
            select(Prediction)
            .where(Prediction.farm_id == farm_id)
            .order_by(Prediction.created_at.desc())
        )
        .all()
    )
    return [_prediction_to_read(p, farm) for p in rows]


@router.get("/latest", response_model=PredictionRead | None)
def latest_prediction(
    farm_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Prediction | None:
    farm = _owned_farm_or_404(farm_id, current_user.id, db)
    prediction = (
        db.scalars(
            select(Prediction)
            .where(Prediction.farm_id == farm_id)
            .order_by(Prediction.created_at.desc())
            .limit(1)
        )
        .first()
    )
    if not prediction:
        return None
    return _prediction_to_read(prediction, farm)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    farm_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardSummary:
    farm = _owned_farm_or_404(farm_id, current_user.id, db)
    prediction = (
        db.scalars(
            select(Prediction)
            .where(Prediction.farm_id == farm.id)
            .order_by(Prediction.created_at.desc())
            .limit(1)
        )
        .first()
    )
    from app.services.bee_service import get_bee_species_for_farm
    bee_species = get_bee_species_for_farm(farm_id, db)
    return DashboardSummary(
        farm={"id": farm.id, "name": farm.name, "crop_type": farm.crop_type,
              "location_lat": farm.location_lat, "location_lng": farm.location_lng},
        current_weather=_get_weather_summary(farm_id, db),
        latest_prediction=_prediction_to_read(prediction, farm) if prediction else None,
        bee_species=bee_species,
    )


def _owned_farm_or_404(farm_id: str, user_id: str, db: Session) -> Farm:
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.user_id == user_id))
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


def _normalise_setting(value):
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, float):
        return round(value, 6)
    return value


def _is_prediction_stale(prediction: Prediction, farm: Farm) -> bool:
    snapshot = load_json(prediction.prediction_inputs, {}).get("farm_settings")
    if not snapshot:
        return False
    for field in ("crop_type", "planting_date", "harvest_date", "location_name", "location_lat", "location_lng",
                  "pesticide_usage", "water_availability"):
        if _normalise_setting(snapshot.get(field)) != _normalise_setting(getattr(farm, field)):
            return True
    return False


def _prediction_to_read(p: Prediction, farm: Farm | None = None) -> PredictionRead:
    return PredictionRead(
        id=p.id,
        farm_id=p.farm_id,
        flowering_start=p.flowering_start,
        flowering_end=p.flowering_end,
        flowering_confidence=p.flowering_confidence,
        psi_score=p.psi_score,
        risk_level=p.risk_level,
        weather_summary=load_json(p.weather_summary, {}),
        pollen_summary=load_json(p.pollen_summary, {}),
        ndvi_value=p.ndvi_value,
        bee_species=load_json(p.bee_species, []),
        recommendation=p.recommendation,
        created_at=p.created_at,
        model_source=p.model_source,
        data_confidence=p.data_confidence,
        prediction_inputs=load_json(p.prediction_inputs, {}),
        is_stale=_is_prediction_stale(p, farm) if farm else False,
    )


def _get_weather_summary(farm_id: str, db: Session) -> dict | None:
    from app.models.weather_cache import WeatherCache
    wc = (
        db.query(WeatherCache)
        .filter(WeatherCache.farm_id == farm_id)
        .order_by(WeatherCache.timestamp.desc())
        .first()
    )
    if not wc:
        return None
    return {
        "temperature": wc.temperature,
        "humidity": wc.humidity,
        "rainfall": wc.rainfall,
        "wind_speed": wc.wind_speed,
    }
