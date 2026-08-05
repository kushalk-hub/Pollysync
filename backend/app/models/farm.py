from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    district_slug: Mapped[str | None] = mapped_column(String(50), ForeignKey("districts.slug"), nullable=True)
    crop_type: Mapped[str] = mapped_column(String(80), index=True)
    variety: Mapped[str | None] = mapped_column(String(80), nullable=True, default=None)
    irrigation_method: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    pesticide_usage: Mapped[str | None] = mapped_column(String(30), nullable=True, default=None)
    water_availability: Mapped[str | None] = mapped_column(String(30), nullable=True, default=None)
    planting_date: Mapped[str | None] = mapped_column(String(16), nullable=True, default=None)
    harvest_date: Mapped[str | None] = mapped_column(String(16), nullable=True, default=None)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_acres: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class District(Base):
    __tablename__ = "districts"

    slug: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(50), default="Maharashtra")
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lng: Mapped[float] = mapped_column(Float)
    radius_km: Mapped[float] = mapped_column(Float, default=5.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
