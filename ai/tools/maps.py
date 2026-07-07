"""Google Maps / Places API client.

All HTTP calls run via asyncio.to_thread so the event loop is never blocked.
Mock detection is centralized here — callers don't need to know which env var
pattern signals a non-configured key.
"""

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ai.config.settings import settings
from ai.models.place import PlaceDetails, PlaceSearchResult
from ai.tools.exceptions import MapsAPIError, PlaceNotFoundError

logger = logging.getLogger(__name__)

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
PLACE_PHOTO_URL = "https://places.googleapis.com/v1/{photo_name}/media"
MAPS_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
PLACE_SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.regularOpeningHours,"
    "places.editorialSummary,places.rating,places.userRatingCount,places.types,"
    "places.businessStatus,places.photos,places.location"
)
PLACE_DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,regularOpeningHours,editorialSummary,"
    "rating,userRatingCount,types,businessStatus,location"
)

_MOCK_PLACE_KEYS = {
    "",
    "mock-google-cloud-key",
    "your-google-cloud-api-key",
    "mock-places-key",
    "your-places-api-key",
}
_MOCK_ROUTE_KEYS = {
    "",
    "mock-google-cloud-key",
    "your-google-cloud-api-key",
    "mock-maps-key",
    "your-maps-api-key",
}
_PHOTO_MAX_HEIGHT_PX = 640

_PERSONA_SEARCH_QUERIES: dict[str, tuple[str, ...]] = {
    "foodie": (
        "best food markets and street food in {destination}",
        "iconic restaurants and local food halls in {destination}",
    ),
    "artist": (
        "best art museums galleries and architecture in {destination}",
        "creative neighborhoods and design landmarks in {destination}",
    ),
    "historian": (
        "top historical landmarks and museums in {destination}",
        "heritage temples monuments and old town sites in {destination}",
    ),
    "adventurer": (
        "best viewpoints parks and outdoor experiences in {destination}",
        "walking trails nature spots and active attractions in {destination}",
    ),
    "local-life": (
        "local neighborhoods cafes and markets in {destination}",
        "everyday local hangouts and community districts in {destination}",
    ),
    "tourist": (
        "top attractions and must-see landmarks in {destination}",
        "most popular tourist sites in {destination}",
    ),
}


def _uses_mock_places() -> bool:
    return (settings.google_places_api_key or "").strip() in _MOCK_PLACE_KEYS


def _uses_mock_routes() -> bool:
    return (settings.google_routes_api_key or "").strip() in _MOCK_ROUTE_KEYS


def _format_opening_hours(hours: dict[str, Any] | None) -> str:
    if not hours:
        return "Unknown"
    descriptions = hours.get("weekdayDescriptions") or hours.get("weekday_descriptions")
    if descriptions:
        return "; ".join(descriptions)
    return "Unknown"


def _location_from_payload(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    location = payload.get("location") or {}
    return location.get("latitude"), location.get("longitude")


def _parse_place_response(place_id: str, payload: dict[str, Any]) -> PlaceDetails:
    business_status = payload.get("businessStatus") or "UNKNOWN"
    lat, lng = _location_from_payload(payload)
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
        lat=lat,
        lng=lng,
        source="api",
    )


def _build_search_result(
    payload: dict[str, Any],
    *,
    photo_url: str = "",
    source: str = "api",
) -> PlaceSearchResult:
    lat, lng = _location_from_payload(payload)
    return PlaceSearchResult(
        place_id=payload.get("id") or "",
        name=(payload.get("displayName") or {}).get("text") or "Unknown",
        address=payload.get("formattedAddress") or "Unknown",
        opening_hours=_format_opening_hours(payload.get("regularOpeningHours")),
        editorial_summary=(payload.get("editorialSummary") or {}).get("text") or "",
        rating=payload.get("rating"),
        user_rating_count=payload.get("userRatingCount"),
        types=list(payload.get("types") or []),
        business_status=payload.get("businessStatus") or "UNKNOWN",
        photo_url=photo_url,
        lat=lat,
        lng=lng,
        source=source,
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


async def _fetch_place_photo_url(photo_name: str) -> str:
    if not photo_name:
        return ""

    encoded_name = urllib.parse.quote(photo_name, safe="/")
    query = urllib.parse.urlencode(
        {
            "maxHeightPx": _PHOTO_MAX_HEIGHT_PX,
            "skipHttpRedirect": "true",
        }
    )
    url = f"{PLACE_PHOTO_URL.format(photo_name=encoded_name)}?{query}"
    headers = {"X-Goog-Api-Key": settings.google_places_api_key}

    def _get() -> str:
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode())
                return payload.get("photoUri") or ""
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise MapsAPIError(f"Places Photo API error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise MapsAPIError(f"Places Photo request failed: {exc}") from exc

    try:
        return await asyncio.to_thread(_get)
    except MapsAPIError as exc:
        logger.warning("Unable to fetch photo for %s: %s", photo_name, exc)
        return ""


async def _fetch_places_search(query: str, page_size: int) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": PLACE_SEARCH_FIELD_MASK,
    }
    body = json.dumps(
        {
            "textQuery": query,
            "pageSize": page_size,
            "languageCode": "en",
            "rankPreference": "RELEVANCE",
        }
    ).encode()

    def _post() -> dict[str, Any]:
        request = urllib.request.Request(PLACES_SEARCH_URL, headers=headers, data=body, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")
            raise MapsAPIError(f"Places Search API error {exc.code}: {body_text}") from exc
        except urllib.error.URLError as exc:
            raise MapsAPIError(f"Places Search request failed: {exc}") from exc

    return await asyncio.to_thread(_post)


async def _fetch_places_autocomplete(query: str) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_places_api_key,
    }
    body = json.dumps(
        {
            "input": query,
            "languageCode": "en",
        }
    ).encode()

    def _post() -> dict[str, Any]:
        request = urllib.request.Request(PLACES_AUTOCOMPLETE_URL, headers=headers, data=body, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")
            raise MapsAPIError(f"Places Autocomplete API error {exc.code}: {body_text}") from exc
        except urllib.error.URLError as exc:
            raise MapsAPIError(f"Places Autocomplete request failed: {exc}") from exc

    return await asyncio.to_thread(_post)


def _search_queries(destination: str, persona_type: str) -> tuple[str, ...]:
    persona_queries = _PERSONA_SEARCH_QUERIES.get(persona_type, ())
    base = tuple(query.format(destination=destination) for query in persona_queries)
    fallback = (f"top attractions and neighborhoods in {destination}",)
    return base + fallback


async def autocomplete_places(query: str, limit: int = 5) -> list[str]:
    """Return location suggestions for frontend text inputs."""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    if _uses_mock_places():
        logger.warning("Skipping autocomplete because GOOGLE_CLOUD_API_KEY is not configured.")
        return []

    try:
        payload = await _fetch_places_autocomplete(normalized_query)
    except MapsAPIError as exc:
        logger.warning("Places autocomplete failed for query=%r (%s)", normalized_query, exc)
        return []

    suggestions: list[str] = []
    seen: set[str] = set()
    for suggestion_payload in payload.get("suggestions", []):
        prediction = suggestion_payload.get("placePrediction") or {}
        text_obj = prediction.get("text") or {}
        label = text_obj.get("text") or ""

        if not label or label in seen:
            continue
        seen.add(label)
        suggestions.append(label)
        if len(suggestions) >= limit:
            break

    return suggestions


async def places_search(
    destination: str,
    persona_type: str,
    limit: int = 5,
    explicit_query: str | None = None,
) -> list[PlaceSearchResult]:
    """Fetch factual place candidates for itinerary planning."""
    if _uses_mock_places():
        logger.warning("Skipping place search because GOOGLE_PLACES_API_KEY is not configured.")
        return []

    if not destination or not destination.strip():
        raise PlaceNotFoundError("destination is required")

    unique_places: dict[str, PlaceSearchResult] = {}
    try:
        queries = [explicit_query] if explicit_query else _search_queries(destination, persona_type)
        for query in queries:
            remaining = max(limit - len(unique_places), 0)
            if remaining == 0:
                break

            # Google Places API restricts pageSize to a maximum of 20.
            # Our queries tuple contains multiple fallbacks, so the loop will 
            # naturally roll over to the next query to accumulate up to the limit.
            page_size = min(remaining, 20)
            payload = await _fetch_places_search(query, max(page_size, 1))
            for place_payload in payload.get("places", []):
                place_id = place_payload.get("id")
                if not place_id or place_id in unique_places:
                    continue

                photo_name = ((place_payload.get("photos") or [{}])[0]).get("name", "")
                photo_url = await _fetch_place_photo_url(photo_name)
                unique_places[place_id] = _build_search_result(place_payload, photo_url=photo_url, source="api")

                if len(unique_places) >= limit:
                    break
    except MapsAPIError as exc:
        logger.warning(
            "Places Search failed for destination=%s persona=%s (%s).",
            destination,
            persona_type,
            exc,
        )
        return []

    if unique_places:
        results = list(unique_places.values())[:limit]
        logger.info(
            "Fetched %d place candidates for destination=%s persona=%s",
            len(results),
            destination,
            persona_type,
        )
        return results

    logger.warning(
        "Places Search returned no candidates for destination=%s persona=%s.",
        destination,
        persona_type,
    )
    return []


async def get_place_details(place_id: str) -> PlaceDetails:
    """Fetch opening hours, rating, editorial summary, and types for a place."""
    if _uses_mock_places():
        raise MapsAPIError("GOOGLE_PLACES_API_KEY is not configured")

    if not place_id or not place_id.strip():
        raise PlaceNotFoundError("place_id is required")

    payload = await _fetch_place_details(place_id)

    if not payload:
        raise PlaceNotFoundError(f"No place found for place_id={place_id}")

    details = _parse_place_response(place_id, payload)
    logger.debug("Fetched place details for %s (%s)", details.name, details.place_id)
    return details


_DEFAULT_WALK_MIN = 12


async def _fetch_directions(
    origin_place_id: str,
    destination_place_id: str,
    mode: str,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "origin": f"place_id:{origin_place_id}",
            "destination": f"place_id:{destination_place_id}",
            "mode": mode,
            "key": settings.google_routes_api_key,
        }
    )
    url = f"{MAPS_DIRECTIONS_URL}?{query}"

    def _get() -> dict[str, Any]:
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")
            raise MapsAPIError(f"Directions API error {exc.code}: {body_text}") from exc
        except urllib.error.URLError as exc:
            raise MapsAPIError(f"Directions request failed: {exc}") from exc

    return await asyncio.to_thread(_get)


async def get_directions(
    origin_place_id: str,
    destination_place_id: str,
    mode: str = "walking",
) -> dict:
    """Fetch travel distance and time between places."""


    if _uses_mock_routes():
        logger.warning("Skipping directions lookup because GOOGLE_ROUTES_API_KEY is not configured.")
        return {
            "duration_min": 0,
            "distance_m": 0,
            "mode": mode,
            "source": "none",
        }

    try:
        payload = await _fetch_directions(origin_place_id, destination_place_id, mode)
        route = (payload.get("routes") or [{}])[0]
        leg = (route.get("legs") or [{}])[0]
        duration = leg.get("duration") or {}
        distance = leg.get("distance") or {}
        duration_sec = duration.get("value")
        distance_m = distance.get("value")

        if duration_sec is None or distance_m is None:
            raise MapsAPIError(f"Directions response missing leg data: {payload}")

        return {
            "duration_min": max(1, round(duration_sec / 60)),
            "distance_m": distance_m,
            "mode": mode,
            "source": "api",
        }
    except MapsAPIError as exc:
        logger.warning(
            "Directions lookup failed for %s -> %s (%s); returning no synthetic duration.",
            origin_place_id,
            destination_place_id,
            exc,
        )
        return {
            "duration_min": 0,
            "distance_m": 0,
            "mode": mode,
            "source": "none",
        }
