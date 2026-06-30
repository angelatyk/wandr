import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from wandr.config.settings import settings
from wandr.models.place import PlaceDetails
from wandr.tools.exceptions import MapsAPIError, PlaceNotFoundError

logger = logging.getLogger(__name__)

PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
PLACE_DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,regularOpeningHours,editorialSummary,"
    "rating,userRatingCount,types,businessStatus"
)

_MOCK_PLACE_KEYS = {"", "mock-places-key", "your-places-api-key"}


def _uses_mock_places() -> bool:
    return settings.google_places_api_key.strip() in _MOCK_PLACE_KEYS


def _format_opening_hours(hours: dict[str, Any] | None) -> str:
    if not hours:
        return "Unknown"
    descriptions = hours.get("weekdayDescriptions") or hours.get("weekday_descriptions")
    if descriptions:
        return "; ".join(descriptions)
    return "Unknown"


def _parse_place_response(place_id: str, payload: dict[str, Any]) -> PlaceDetails:
    business_status = payload.get("businessStatus") or "UNKNOWN"
    return PlaceDetails(
        place_id=payload.get("id") or place_id,
        name=(payload.get("displayName") or {}).get("text") or "Unknown",
        address=payload.get("formattedAddress") or "Unknown",
        opening_hours=_format_opening_hours(payload.get("regularOpeningHours")),
        editorial_summary=(payload.get("editorialSummary") or {}).get("text") or "",
        rating=payload.get("rating"),
        user_rating_count=payload.get("userRatingCount"),
        types=list(payload.get("types") or []),
        business_status=business_status,
        is_seasonal_or_closed=business_status in {"CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"},
        source="api",
    )


def _mock_place_details(place_id: str) -> PlaceDetails:
    """Deterministic mock data for local dev when no Places API key is configured."""
    catalog = {
        "sensoji_id": PlaceDetails(
            place_id="sensoji_id",
            name="Senso-ji",
            address="2 Chome-3-1 Asakusa, Taito City, Tokyo",
            opening_hours="Open 24 hours (main grounds); main hall roughly 6:00 AM – 5:00 PM",
            editorial_summary=(
                "Tokyo's oldest temple, famous for its Thunder Gate (Kaminarimon) "
                "and lively Nakamise shopping street."
            ),
            rating=4.5,
            user_rating_count=42000,
            types=["tourist_attraction", "place_of_worship", "point_of_interest"],
            business_status="OPERATIONAL",
            is_seasonal_or_closed=False,
            source="mock",
        ),
        "edo_museum_id": PlaceDetails(
            place_id="edo_museum_id",
            name="Edo-Tokyo Museum",
            address="1-4-1 Yokoami, Sumida City, Tokyo",
            opening_hours="Tue–Sun 9:30 AM – 5:30 PM; closed Mondays",
            editorial_summary=(
                "A museum chronicling Tokyo's transformation from the Edo period "
                "to the modern metropolis."
            ),
            rating=4.6,
            user_rating_count=18000,
            types=["museum", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            is_seasonal_or_closed=False,
            source="mock",
        ),
    }
    if place_id in catalog:
        return catalog[place_id]

    return PlaceDetails(
        place_id=place_id,
        name=place_id.replace("_", " ").title(),
        address="Unknown",
        opening_hours="Unknown",
        editorial_summary="No editorial summary available for this place.",
        rating=None,
        user_rating_count=None,
        types=["point_of_interest"],
        business_status="UNKNOWN",
        is_seasonal_or_closed=False,
        source="mock",
    )


async def _fetch_place_details(place_id: str) -> dict[str, Any]:
    encoded_id = urllib.parse.quote(place_id, safe="")
    url = PLACES_DETAILS_URL.format(place_id=encoded_id)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": PLACE_DETAILS_FIELD_MASK,
    }

    def _get() -> dict[str, Any]:
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise PlaceNotFoundError(f"No place found for place_id={place_id}") from exc
            body = exc.read().decode(errors="replace")
            raise MapsAPIError(f"Places API error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise MapsAPIError(f"Places API request failed: {exc}") from exc

    return await asyncio.to_thread(_get)


async def places_search(destination: str, persona_type: str, limit: int = 5) -> list:
    """Fetch candidate places for a destination and persona type."""
    return []


async def get_place_details(place_id: str) -> PlaceDetails:
    """Fetch opening hours, rating, editorial summary, and types for a place."""
    if not place_id or not place_id.strip():
        raise PlaceNotFoundError("place_id is required")

    if _uses_mock_places():
        logger.info("Using mock place details for %s (no Places API key configured)", place_id)
        return _mock_place_details(place_id)

    try:
        payload = await _fetch_place_details(place_id)
    except MapsAPIError as exc:
        # Dev fallback: mock catalog IDs still work if Places API (New) is not enabled yet
        if place_id in {"sensoji_id", "edo_museum_id"}:
            logger.warning(
                "Places API failed for %s (%s) — using mock data. "
                "Enable 'Places API (New)' in Google Cloud Console.",
                place_id,
                exc,
            )
            return _mock_place_details(place_id)
        raise

    if not payload:
        raise PlaceNotFoundError(f"No place found for place_id={place_id}")

    details = _parse_place_response(place_id, payload)
    logger.debug("Fetched place details for %s (%s)", details.name, details.place_id)
    return details


async def get_directions(
    origin_place_id: str,
    destination_place_id: str,
    mode: str = "walking",
) -> dict:
    """Fetch travel distance and time between places."""
    return {}
