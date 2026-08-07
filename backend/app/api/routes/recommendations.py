import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.core.config import settings
from app.database import get_db
from app.models.farm import Farm
from app.models.prediction import Prediction, load_json
from app.models.user import User

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class GenerateRequest(BaseModel):
    farm_id: str
    prediction_id: str


def _weather(prediction: Prediction) -> dict:
    return load_json(prediction.weather_summary, {})


def _build_prompt(farm: Farm, prediction: Prediction) -> str:
    weather = _weather(prediction)
    bee_species = load_json(prediction.bee_species, [])

    return f"""You are an expert agronomist advising an Indian farmer. Use only the supplied facts; never invent pests, rainfall, or crop stages.

Farm details:
- Crop: {farm.crop_type}
- Location: {farm.location_name or 'Recorded farm location'} ({farm.location_lat}, {farm.location_lng})
- Planting date: {farm.planting_date or 'Not recorded'}
- Expected harvest: {farm.harvest_date or 'Not recorded'}
- Variety: {farm.variety or 'Not recorded'}
- Soil: {farm.soil_type or 'Not recorded'}
- Pesticide use: {farm.pesticide_usage or 'Not recorded'} (none / pre_flowering / during_flowering)
- Water availability: {farm.water_availability or 'Not recorded'} (rainfed / irrigated / water_stressed)

Current conditions:
- Temperature: {weather.get('temperature', 'N/A')} C
- Humidity: {weather.get('humidity', 'N/A')}%
- Rainfall: {weather.get('rainfall', 'N/A')} mm
- Wind: {weather.get('wind_speed', 'N/A')} km/h

Prediction:
- Flowering window: {prediction.flowering_start} to {prediction.flowering_end}
- Pollination suitability index: {prediction.psi_score}/100
- Risk level: {prediction.risk_level}
- NDVI crop health index: {prediction.ndvi_value:.2f}
- Nearby bee species: {', '.join(bee_species) if bee_species else 'N/A'}

Write a concise 90-140 word Markdown advisory in this exact structure:
## <crop> advisory
<two-sentence assessment using PSI, weather, flowering window, and NDVI.>
**Recommended now**
- <specific action 1>
- <specific action 2>
- <specific action 3, only if useful>
**Watch out**
<one clear risk warning; say "No urgent warning" for low risk.>
**Confidence:** <one short sentence>

Be practical, concise, and mention the crop by name."""


def _extract_gemini_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts") or []
    return "\n".join(part.get("text", "") for part in parts).strip()


def _is_valid_recommendation(recommendation: str, farm: Farm) -> bool:
    compact = " ".join(recommendation.split())
    crop = (farm.crop_type or "").strip().lower()
    action_terms = ("recommend", "avoid", "monitor", "check", "maintain", "schedule", "scout")
    return (
        len(compact) >= 120
        and bool(crop)
        and crop in compact.lower()
        and "recommended now" in compact.lower()
        and any(term in compact.lower() for term in action_terms)
    )


async def _generate_gemini_recommendation(farm: Farm, prediction: Prediction) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.llm_model or settings.gemini_model}:generateContent"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            url,
            headers={"x-goog-api-key": settings.llm_api_key or settings.gemini_api_key},
            json={
                "contents": [{"role": "user", "parts": [{"text": _build_prompt(farm, prediction)}]}],
                "generationConfig": {"temperature": 0.35, "maxOutputTokens": 360},
            },
        )
        response.raise_for_status()
    recommendation = _extract_gemini_text(response.json())
    if not _is_valid_recommendation(recommendation, farm):
        raise ValueError("AI returned an incomplete recommendation")
    return recommendation


def _generate_local_recommendation(farm: Farm, prediction: Prediction) -> str:
    weather = _weather(prediction)
    temperature = weather.get("temperature", "N/A")
    humidity = weather.get("humidity", "N/A")
    wind = weather.get("wind_speed", "N/A")
    crop = farm.crop_type or "Your crop"
    ndvi_note = "healthy canopy cover" if prediction.ndvi_value >= 0.6 else "crop health that needs closer scouting"

    if prediction.risk_level == "High":
        actions = [
            "Avoid pesticide spraying during pollinator activity and postpone non-essential disturbance.",
            "Inspect flowers and soil moisture early today, then correct water stress before midday.",
            "Check the next forecast before scheduling exposed field work.",
        ]
        warning = "High pollination risk: protect flowering activity until weather conditions improve."
    elif prediction.risk_level == "Medium":
        actions = [
            "Scout flowering plants early and record moisture or pest stress.",
            "Keep irrigation steady through the flowering window without overwatering.",
            "Plan sprays outside active pollinator hours and reassess the weather first.",
        ]
        warning = "Moderate risk: watch humidity and wind before a field intervention."
    else:
        actions = [
            "Keep flowering rows and field edges accessible for pollinators.",
            "Maintain the current irrigation schedule and scout during the cooler part of the day.",
            "Schedule any spray outside active pollinator hours.",
        ]
        warning = "No urgent warning; continue monitoring weather ahead of the flowering window."

    action_lines = "\n".join(f"- {action}" for action in actions)

    practice_notes = []
    pesticide = (farm.pesticide_usage or "").strip().lower()
    water = (farm.water_availability or "").strip().lower()
    if pesticide == "during_flowering":
        practice_notes.append("Pause all pesticide sprays immediately during the flowering window to protect pollinators.")
    elif pesticide == "pre_flowering":
        practice_notes.append("Keep pesticide applications outside the flowering window only.")
    if water == "water_stressed":
        practice_notes.append("Address water stress before midday: irrigation is critical for flower retention.")
    elif water == "rainfed":
        practice_notes.append("Rainfed field: monitor the 7-day rainfall trend and soil moisture closely.")
    practice_lines = "\n".join(f"- {note}" for note in practice_notes)

    watch_extra = ""
    if pesticide == "during_flowering":
        watch_extra += " Ongoing pesticide use during flowering is actively suppressing pollinator activity."
    if water == "water_stressed":
        watch_extra += " Water stress is reducing flower retention and pollen viability."

    return (
        f"## {crop} advisory\n\n"
        f"Your PSI is {prediction.psi_score}/100 ({prediction.risk_level.lower()} risk). "
        f"Temperature is {temperature}°C, humidity is {humidity}%, wind is {wind} km/h, and NDVI indicates {ndvi_note}. "
        f"The predicted flowering window is {prediction.flowering_start} to {prediction.flowering_end}.\n\n"
        f"**Recommended now**\n{action_lines}\n"
        f"{practice_lines + chr(10) if practice_lines else ''}"
        f"**Watch out**\n{warning}{watch_extra}\n\n"
        "**Confidence:** Based on the latest weather, farm settings, and prediction model."
    )


@router.post("/generate", response_model=dict)
async def generate_recommendation(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    farm = db.scalar(select(Farm).where(Farm.id == payload.farm_id, Farm.user_id == current_user.id))
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    prediction = db.scalar(
        select(Prediction).where(Prediction.id == payload.prediction_id, Prediction.farm_id == farm.id)
    )
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    active_llm_key = settings.llm_api_key or settings.gemini_api_key
    if active_llm_key and active_llm_key != "change-me-in-production":
        try:
            recommendation = await _generate_gemini_recommendation(farm, prediction)
        except (httpx.HTTPError, ValueError):
            recommendation = _generate_local_recommendation(farm, prediction)
    else:
        recommendation = _generate_local_recommendation(farm, prediction)

    prediction.recommendation = recommendation
    db.commit()
    return {"recommendation": recommendation}
