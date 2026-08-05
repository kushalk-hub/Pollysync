from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FarmCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    crop_type: str = Field(min_length=2, max_length=80)
    district_slug: str | None = Field(default=None, max_length=50)
    variety: str | None = Field(default=None, max_length=80)
    irrigation_method: str | None = Field(default=None, max_length=50)
    pesticide_usage: str | None = Field(default=None, max_length=30)
    water_availability: str | None = Field(default=None, max_length=30)
    planting_date: str | None = Field(default=None, max_length=16)
    harvest_date: str | None = Field(default=None, max_length=16)
    location_name: str | None = Field(default=None, max_length=255)
    location_lat: float | None = Field(default=None, ge=-90, le=90)
    location_lng: float | None = Field(default=None, ge=-180, le=180)
    area_acres: float | None = Field(default=None, gt=0)
    soil_type: str | None = Field(default=None, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def normalize_frontend_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "crop_type" not in normalized and "crop" in normalized:
            normalized["crop_type"] = normalized["crop"]
        if "location_name" not in normalized and "location" in normalized:
            normalized["location_name"] = normalized["location"]
        return normalized


class FarmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    crop_type: str | None = Field(default=None, min_length=2, max_length=80)
    district_slug: str | None = Field(default=None, max_length=50)
    variety: str | None = Field(default=None, max_length=80)
    irrigation_method: str | None = Field(default=None, max_length=50)
    pesticide_usage: str | None = Field(default=None, max_length=30)
    water_availability: str | None = Field(default=None, max_length=30)
    planting_date: str | None = Field(default=None, max_length=16)
    harvest_date: str | None = Field(default=None, max_length=16)
    location_name: str | None = Field(default=None, max_length=255)
    location_lat: float | None = Field(default=None, ge=-90, le=90)
    location_lng: float | None = Field(default=None, ge=-180, le=180)
    area_acres: float | None = Field(default=None, gt=0)
    soil_type: str | None = Field(default=None, max_length=50)
    is_default: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_frontend_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "crop_type" not in normalized and "crop" in normalized:
            normalized["crop_type"] = normalized["crop"]
        if "location_name" not in normalized and "location" in normalized:
            normalized["location_name"] = normalized["location"]
        return normalized


class FarmRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    crop_type: str
    crop: str
    district_slug: str | None = None
    variety: str | None = None
    irrigation_method: str | None = None
    pesticide_usage: str | None = None
    water_availability: str | None = None
    planting_date: str | None = None
    harvest_date: str | None = None
    location_name: str | None = None
    location: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    area_acres: float | None = None
    soil_type: str | None = None
    is_default: bool = False
    latest_psi: int | None = None
    created_at: datetime


class DistrictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    state: str
    centroid_lat: float
    centroid_lng: float
    radius_km: float
