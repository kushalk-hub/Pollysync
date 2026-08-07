from pydantic import BaseModel


class WeatherCurrent(BaseModel):
    temperature: float
    humidity: float
    rainfall: float
    wind_speed: float
    timestamp: str | None = None
    source: str | None = None


class ForecastDay(BaseModel):
    date: str
    temp_max: float
    temp_min: float
    rainfall: float


class WeatherForecast(BaseModel):
    forecast: list[ForecastDay]
    source: str | None = None
