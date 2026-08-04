import logging
import re
import time
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from google.genai import Client
from google.genai.errors import ClientError as GenAIClientError
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.core.config import settings
from app.database import get_db
from app.models.user import User
from app.models.agent_rate_limit import AgentRateLimit

from .embedder import SupabaseVectorStore, embed_text
from .prompts import get_system_prompt, get_user_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

_client: Client | None = None

_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = 20


async def assemble_farm_context(farm_id: str, db: Session) -> str:
    """Assemble live farm data for agent context."""
    from app.models.farm import Farm
    from app.models.prediction import Prediction
    from app.services.weather_service import get_weather_with_cache
    from app.services.bee_service import get_bee_data_with_cache
    
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        return ""
    
    # Get latest prediction
    prediction = (
        db.query(Prediction)
        .filter(Prediction.farm_id == farm_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    
    # Get live weather
    try:
        weather = await get_weather_with_cache(str(farm.id), farm.location_lat, farm.location_lng, db)
        weather_info = f"Temperature: {weather.get('current', {}).get('temperature_2m', 'N/A')}°C, Humidity: {weather.get('current', {}).get('relative_humidity_2m', 'N/A')}%"
    except Exception:
        weather_info = "Weather data unavailable"
    
    # Get bee data
    try:
        bee_data = await get_bee_data_with_cache(str(farm.id), farm.location_lat, farm.location_lng, db)
        bee_info = f"Bee species richness: {bee_data.get('richness', 'N/A')}"
    except Exception:
        bee_info = "Bee data unavailable"
    
    # Get prediction info
    if prediction:
        pred_info = f"Risk level: {prediction.risk_level}, PSI: {prediction.psi_score}"
    else:
        pred_info = "No prediction available"
    
    context = f"""
Live farm conditions:
Crop: {farm.crop_type}
District: {farm.location_name or 'Unknown'}

Weather: {weather_info}
Bee Data: {bee_info}
Prediction: {pred_info}
"""
    return context


def _check_rate_limit(identifier: str, db: Session) -> None:
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW
    db.execute(
        delete(AgentRateLimit).where(
            AgentRateLimit.identifier == identifier,
            AgentRateLimit.timestamp <= window_start
        )
    )
    count = db.scalar(
        select(func.count(AgentRateLimit.id)).where(
            AgentRateLimit.identifier == identifier,
            AgentRateLimit.timestamp > window_start
        )
    )
    if count >= _RATE_LIMIT_MAX:
        db.commit()
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down.",
        )
    db.add(AgentRateLimit(identifier=identifier, timestamp=now))
    db.commit()


def _sanitize_input(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"<[^>]*>", "", stripped)
    stripped = stripped.replace("<user_question>", "").replace("</user_question>", "")
    
    injection_keywords = [
        "ignore previous instructions", 
        "ignore all instructions",
        "system override", 
        "bypass rules",
        "developer mode",
        "jailbreak"
    ]
    for kw in injection_keywords:
        stripped = re.sub(re.escape(kw), "[removed directive]", stripped, flags=re.IGNORECASE)
        
    return stripped[:4000]


def _get_client() -> Client:
    global _client
    if _client is None:
        key = settings.llm_api_key or settings.gemini_api_key
        if not key:
            raise HTTPException(status_code=503, detail="LLM API key not configured")
        _client = Client(api_key=key)
    return _client


def _llm_model() -> str:
    return settings.llm_model or settings.gemini_model or "gemini-2.5-flash"


async def _query_gemini(messages: list[dict[str, Any]]) -> str:
    client = _get_client()
    model = _llm_model()

    system_content = ""
    conversation = []
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        else:
            role = "model" if msg["role"] == "assistant" else "user"
            conversation.append({"role": role, "parts": [{"text": msg["content"]}]})

    if not conversation:
        return ""

    try:
        if system_content:
            response = await client.aio.models.generate_content(
                model=model,
                contents=conversation,
                config={"system_instruction": system_content},
            )
        else:
            response = await client.aio.models.generate_content(
                model=model,
                contents=conversation,
            )
    except GenAIClientError as exc:
        if exc.code == 429:
            raise HTTPException(
                status_code=429,
                detail="AI rate limit exceeded. Try again later.",
            )
        if exc.code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail="AI authentication failed. Check API key configuration.",
            )
        raise HTTPException(status_code=502, detail="AI request failed. Please try again later.")
    except Exception as exc:
        logger.exception("Unexpected AI request error")
        raise HTTPException(status_code=502, detail="AI request failed. Please try again later.")

    return (response.text or "").strip()


@router.post("/chat")
async def chat(
    payload: dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _check_rate_limit(current_user.id, db)

    farm_data: dict[str, Any] | None = payload.get("farm_data")
    farm_id: str | None = payload.get("farm_id")
    messages: list[dict[str, str]] = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Input sanitization
    for msg in messages:
        msg["content"] = _sanitize_input(msg.get("content", ""))

    system_prompt = get_system_prompt()

    # Add live farm context if farm_id is provided
    if farm_id:
        try:
            live_context = await assemble_farm_context(farm_id, db)
            if live_context:
                system_prompt += f"\n\n{live_context}"
        except Exception:
            logger.warning("Failed to assemble farm context", exc_info=True)

    if farm_data:
        try:
            store = SupabaseVectorStore()
            query_text = (
                f"{farm_data.get('crop_name', '')} "
                f"{farm_data.get('location', '')} "
                f"{farm_data.get('risk_level', '')}"
            )
            query_vec = await embed_text(query_text)
            results = await store.search(query_vec, top_k=3)
            if results:
                context = "\n\n".join(r["content"] for r in results)
                system_prompt += f"\n\nRelevant knowledge:\n{context}"
        except Exception:
            logger.warning("RAG knowledge search failed, continuing without context", exc_info=True)

        user_message = get_user_message(**farm_data)
        last_user_msg = messages[-1]["content"] if messages else ""
        messages = [
            {"role": "system", "content": system_prompt},
            *messages[:-1],
            {"role": "user", "content": f"{user_message}\n\nUser question:\n<user_question>\n{last_user_msg}\n</user_question>"},
        ]
    else:
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] = f"<user_question>\n{messages[-1]['content']}\n</user_question>"
        messages = [{"role": "system", "content": system_prompt}, *messages]

    reply = await _query_gemini(messages)
    return {"reply": reply}


@router.post("/search")
async def search_knowledge(
    payload: dict[str, str],
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _check_rate_limit(current_user.id, db)

    query = payload.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    query = _sanitize_input(query)
    try:
        store = SupabaseVectorStore()
        vec = await embed_text(query)
        results = await store.search(vec, top_k=5)
        return {"results": results}
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Knowledge search is temporarily unavailable.")


@router.get("/context")
async def get_agent_context(
    farm_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Debug endpoint to see assembled agent context."""
    _check_rate_limit(current_user.id, db)
    context = await assemble_farm_context(farm_id, db)
    return {"context": context}
