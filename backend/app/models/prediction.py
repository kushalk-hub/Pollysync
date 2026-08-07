import json
from datetime import datetime
import uuid

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def load_json(value, default):
    """Return a JSON column value as a Python object regardless of whether the
    backend stores it as JSONB (Postgres) or TEXT (SQLite)."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return default


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(String(36), ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    flowering_start: Mapped[str] = mapped_column(String(16))
    flowering_end: Mapped[str] = mapped_column(String(16))
    flowering_confidence: Mapped[float] = mapped_column(Float)
    psi_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(16))
    weather_summary: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), server_default="{}", default=dict
    )
    pollen_summary: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), server_default="{}", default=dict
    )
    ndvi_value: Mapped[float] = mapped_column(Float, default=0.0)
    bee_species: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), server_default="[]", default=list
    )
    recommendation: Mapped[str] = mapped_column(Text, default="")
    model_source: Mapped[str] = mapped_column(String(32), default="general")
    data_confidence: Mapped[str] = mapped_column(String(32), default="standard")
    prediction_inputs: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), server_default="{}", default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
