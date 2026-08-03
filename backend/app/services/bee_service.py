import httpx
from sqlalchemy.orm import Session

from app.models.bee_occurrence import BeeOccurrence
from app.core.cache import cache_get, cache_set
from app.core.circuit_breaker import circuit_breaker

GBIF_URL = (
    "https://api.gbif.org/v1/occurrence/search"
    "?taxonKey=4334"
    "&decimalLatitude={lat}"
    "&decimalLongitude={lng}"
    "&distance={radius_deg}"
    "&limit=100"
    "&basisOfRecord=HUMAN_OBSERVATION"
)

MOCK_BEES = {
    "Mustard": ["Apis cerana", "Apis dorsata", "Apis florea"],
    "Sunflower": ["Apis mellifera", "Bombus taschenbergi"],
    "Wheat": ["Apis cerana", "Apis florea"],
    "Rice": ["Apis cerana", "Apis dorsata"],
    "Cotton": ["Apis mellifera", "Apis dorsata", "Apis florea"],
}


async def fetch_bees(lat: float, lng: float, radius_km: int = 10) -> list[dict]:
    radius_deg = radius_km / 111
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GBIF_URL.format(lat=lat, lng=lng, radius_deg=radius_deg),
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = data.get("results", [])
        return [
            {
                "species": r.get("species", "Unknown"),
                "lat": r.get("decimalLatitude"),
                "lng": r.get("decimalLongitude"),
                "date": r.get("eventDate", ""),
            }
            for r in results
            if r.get("decimalLatitude") and r.get("decimalLongitude")
        ]


@circuit_breaker("gbif", max_failures=3, window_seconds=300)
async def fetch_bees_protected(lat: float, lng: float, radius_km: int = 10) -> list[dict]:
    """Fetch bees with circuit breaker protection."""
    return await fetch_bees(lat, lng, radius_km)


def get_mock_bees(crop_type: str) -> list[str]:
    return MOCK_BEES.get(crop_type, ["Apis cerana"])


def store_bees(farm_id: str, occurrences: list[dict], db: Session) -> None:
    for occ in occurrences:
        existing = (
            db.query(BeeOccurrence)
            .filter(
                BeeOccurrence.farm_id == farm_id,
                BeeOccurrence.species_name == occ["species"],
                BeeOccurrence.lat == occ["lat"],
                BeeOccurrence.lng == occ["lng"],
            )
            .first()
        )
        if not existing:
            db.add(
                BeeOccurrence(
                    farm_id=farm_id,
                    species_name=occ["species"],
                    lat=occ["lat"],
                    lng=occ["lng"],
                    observation_date=occ.get("date", ""),
                )
            )
    db.commit()


def get_bee_species_for_farm(farm_id: str, db: Session) -> list[str]:
    rows = (
        db.query(BeeOccurrence.species_name)
        .filter(BeeOccurrence.farm_id == farm_id)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


async def get_bee_data_with_cache(farm_id: str, lat: float, lng: float, db: Session) -> dict:
    """Get bee data with L1/L2 cache layer."""
    cache_key = f"{lat},{lng}"
    
    # L1/L2 cache check
    cached = cache_get(cache_key, group="bees")
    if cached:
        return cached
    
    # DB cache check
    db_species = get_bee_species_for_farm(farm_id, db)
    if db_species:
        result = {
            "species": db_species,
            "richness": len(db_species),
            "source": "db_cache",
        }
        cache_set(cache_key, result, ttl=900, group="bees")
        return result
    
    # Live fetch
    try:
        occurrences = await fetch_bees(lat, lng)
        species = list({occ["species"] for occ in occurrences})
        result = {
            "species": species,
            "richness": len(species),
            "occurrences": occurrences[:10],  # Limit for cache size
            "source": "live",
        }
        cache_set(cache_key, result, ttl=900, group="bees")
        return result
    except Exception:
        # Fallback to mock data
        return {
            "species": ["Apis cerana"],
            "richness": 1,
            "source": "fallback",
        }
