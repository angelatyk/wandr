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
    "places.businessStatus,places.photos"
)
PLACE_DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,regularOpeningHours,editorialSummary,"
    "rating,userRatingCount,types,businessStatus,location"
)

_MOCK_PLACE_KEYS = {"", "mock-places-key", "your-places-api-key"}
_PHOTO_MAX_HEIGHT_PX = 640
_KNOWN_MOCK_PLACE_IDS = {
    "sensoji_id",
    "edo_museum_id",
    "imperial_palace_east_gardens_id",
    "yanaka_ginza_id",
    "tsukiji_outer_market_id",
    "teamlab_planets_id",
    "ueno_park_id",
    "shimokitazawa_id",
}
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
}


def _uses_mock_places() -> bool:
    return settings.google_places_api_key.strip() in _MOCK_PLACE_KEYS


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
        source=source,
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
            lat=35.7147,
            lng=139.7967,
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
            lat=35.6963,
            lng=139.7964,
            source="mock",
        ),
        "imperial_palace_east_gardens_id": PlaceDetails(
            place_id="imperial_palace_east_gardens_id",
            name="Imperial Palace East Gardens",
            address="1-1 Chiyoda, Chiyoda City, Tokyo",
            opening_hours="Varies seasonally; generally daytime entry with Monday/Friday closures",
            editorial_summary="Historic castle grounds with stone walls, gates, and layered Edo-period history.",
            rating=4.4,
            user_rating_count=9800,
            types=["park", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            is_seasonal_or_closed=False,
            lat=35.6852,
            lng=139.7533,
            source="mock",
        ),
        "yanaka_ginza_id": PlaceDetails(
            place_id="yanaka_ginza_id",
            name="Yanaka Ginza",
            address="3 Chome Sendagi, Bunkyo City, Tokyo",
            opening_hours="Most shops open late morning to early evening; varies by storefront",
            editorial_summary="A nostalgic old-town shopping street that still feels rooted in everyday neighborhood life.",
            rating=4.2,
            user_rating_count=7600,
            types=["shopping_mall", "point_of_interest"],
            business_status="OPERATIONAL",
            is_seasonal_or_closed=False,
            lat=35.7277,
            lng=139.7668,
            source="mock",
        ),
        "tsukiji_outer_market_id": PlaceDetails(
            place_id="tsukiji_outer_market_id",
            name="Tsukiji Outer Market",
            address="4 Chome-16-2 Tsukiji, Chuo City, Tokyo",
            opening_hours="Many stalls open early morning to early afternoon; closed varies by vendor",
            editorial_summary="A bustling market district known for seafood counters, knives, and quick breakfast stops.",
            rating=4.4,
            user_rating_count=29000,
            types=["market", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            is_seasonal_or_closed=False,
            lat=35.6655,
            lng=139.7708,
            source="mock",
        ),
        "teamlab_planets_id": PlaceDetails(
            place_id="teamlab_planets_id",
            name="teamLab Planets TOKYO DMM",
            address="6 Chome-1-16 Toyosu, Koto City, Tokyo",
            opening_hours="Daily hours vary; timed-entry tickets required",
            editorial_summary="An immersive digital-art museum with light, water, and mirrored spaces.",
            rating=4.4,
            user_rating_count=25000,
            types=["museum", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            is_seasonal_or_closed=False,
            lat=35.6491,
            lng=139.7898,
            source="mock",
        ),
        "ueno_park_id": PlaceDetails(
            place_id="ueno_park_id",
            name="Ueno Park",
            address="Uenokoen, Taito City, Tokyo",
            opening_hours="Open daily; museums within the park keep their own hours",
            editorial_summary="A major public park combining museums, shrines, and long walking paths.",
            rating=4.3,
            user_rating_count=31000,
            types=["park", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            is_seasonal_or_closed=False,
            lat=35.7148,
            lng=139.7745,
            source="mock",
        ),
        "shimokitazawa_id": PlaceDetails(
            place_id="shimokitazawa_id",
            name="Shimokitazawa",
            address="Kitazawa, Setagaya City, Tokyo",
            opening_hours="Neighborhood district; shop and cafe hours vary widely",
            editorial_summary="A laid-back district known for secondhand shops, cafes, and live music culture.",
            rating=4.3,
            user_rating_count=5400,
            types=["neighborhood", "point_of_interest"],
            business_status="OPERATIONAL",
            is_seasonal_or_closed=False,
            lat=35.6617,
            lng=139.6689,
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


def _mock_places_search(destination: str, persona_type: str, limit: int) -> list[PlaceSearchResult]:
    """Deterministic mock search results for local development."""
    catalog = {
        "sensoji_id": PlaceSearchResult(
            place_id="sensoji_id",
            name="Senso-ji",
            address="2 Chome-3-1 Asakusa, Taito City, Tokyo",
            opening_hours="Open 24 hours (main grounds); main hall roughly 6:00 AM - 5:00 PM",
            editorial_summary="Tokyo's oldest temple with a dramatic gate, lantern-lined approach, and strong Edo heritage.",
            rating=4.5,
            user_rating_count=42000,
            types=["tourist_attraction", "place_of_worship", "point_of_interest"],
            business_status="OPERATIONAL",
            photo_url="https://upload.wikimedia.org/wikipedia/commons/9/9e/Sens%C5%8D-ji_Kaminarimon_2020.jpg",
            source="mock",
        ),
        "edo_museum_id": PlaceSearchResult(
            place_id="edo_museum_id",
            name="Edo-Tokyo Museum",
            address="1-4-1 Yokoami, Sumida City, Tokyo",
            opening_hours="Tue-Sun 9:30 AM - 5:30 PM; closed Mondays",
            editorial_summary="A museum that traces Tokyo's transformation from the Edo shogunate to the modern capital.",
            rating=4.6,
            user_rating_count=18000,
            types=["museum", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            photo_url="https://upload.wikimedia.org/wikipedia/commons/4/47/Edo-Tokyo_Museum_2007-01.jpg",
            source="mock",
        ),
        "imperial_palace_east_gardens_id": PlaceSearchResult(
            place_id="imperial_palace_east_gardens_id",
            name="Imperial Palace East Gardens",
            address="1-1 Chiyoda, Chiyoda City, Tokyo",
            opening_hours="Varies seasonally; generally daytime entry with Monday/Friday closures",
            editorial_summary="Landscaped castle grounds with ramparts, gates, and remains of Edo Castle.",
            rating=4.4,
            user_rating_count=9800,
            types=["park", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            photo_url="https://upload.wikimedia.org/wikipedia/commons/2/20/East_Gardens_of_the_Imperial_Palace%2C_Tokyo.jpg",
            source="mock",
        ),
        "yanaka_ginza_id": PlaceSearchResult(
            place_id="yanaka_ginza_id",
            name="Yanaka Ginza",
            address="3 Chome Sendagi, Bunkyo City, Tokyo",
            opening_hours="Most shops open late morning to early evening; varies by storefront",
            editorial_summary="A nostalgic shopping street known for old Tokyo character, snack stalls, and neighborhood life.",
            rating=4.2,
            user_rating_count=7600,
            types=["shopping_mall", "point_of_interest"],
            business_status="OPERATIONAL",
            photo_url="https://upload.wikimedia.org/wikipedia/commons/3/3e/Yanaka_Ginza_2011.JPG",
            source="mock",
        ),
        "tsukiji_outer_market_id": PlaceSearchResult(
            place_id="tsukiji_outer_market_id",
            name="Tsukiji Outer Market",
            address="4 Chome-16-2 Tsukiji, Chuo City, Tokyo",
            opening_hours="Many stalls open early morning to early afternoon; closed varies by vendor",
            editorial_summary="A dense food market packed with seafood counters, knives, tea shops, and quick bites.",
            rating=4.4,
            user_rating_count=29000,
            types=["market", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            photo_url="https://upload.wikimedia.org/wikipedia/commons/d/d2/Tsukiji_fish_market.jpg",
            source="mock",
        ),
        "teamlab_planets_id": PlaceSearchResult(
            place_id="teamlab_planets_id",
            name="teamLab Planets TOKYO DMM",
            address="6 Chome-1-16 Toyosu, Koto City, Tokyo",
            opening_hours="Daily hours vary; timed-entry tickets required",
            editorial_summary="An immersive digital-art museum with reflective installations and barefoot sensory spaces.",
            rating=4.4,
            user_rating_count=25000,
            types=["museum", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            photo_url="https://upload.wikimedia.org/wikipedia/commons/e/e2/TeamLab_Borderless_Entrance.jpg",
            source="mock",
        ),
        "ueno_park_id": PlaceSearchResult(
            place_id="ueno_park_id",
            name="Ueno Park",
            address="Uenokoen, Taito City, Tokyo",
            opening_hours="Open daily; museums within the park keep their own hours",
            editorial_summary="A broad public park with museums, ponds, shrines, and one of Tokyo's classic stroll zones.",
            rating=4.3,
            user_rating_count=31000,
            types=["park", "tourist_attraction", "point_of_interest"],
            business_status="OPERATIONAL",
            photo_url="https://upload.wikimedia.org/wikipedia/commons/b/b4/Ueno_Park_2019.jpg",
            source="mock",
        ),
        "shimokitazawa_id": PlaceSearchResult(
            place_id="shimokitazawa_id",
            name="Shimokitazawa",
            address="Kitazawa, Setagaya City, Tokyo",
            opening_hours="Neighborhood district; shop and cafe hours vary widely",
            editorial_summary="An easygoing neighborhood known for indie shops, cafes, live houses, and secondhand style.",
            rating=4.3,
            user_rating_count=5400,
            types=["neighborhood", "point_of_interest"],
            business_status="OPERATIONAL",
            photo_url="https://upload.wikimedia.org/wikipedia/commons/8/89/Shimokitazawa_station_square_2020.jpg",
            source="mock",
        ),
    }

    persona_defaults = {
        "foodie": [
            "tsukiji_outer_market_id",
            "yanaka_ginza_id",
            "shimokitazawa_id",
            "ueno_park_id",
            "sensoji_id",
        ],
        "artist": [
            "teamlab_planets_id",
            "ueno_park_id",
            "shimokitazawa_id",
            "sensoji_id",
            "imperial_palace_east_gardens_id",
        ],
        "historian": [
            "sensoji_id",
            "edo_museum_id",
            "imperial_palace_east_gardens_id",
            "yanaka_ginza_id",
            "ueno_park_id",
        ],
        "adventurer": [
            "ueno_park_id",
            "imperial_palace_east_gardens_id",
            "teamlab_planets_id",
            "sensoji_id",
            "shimokitazawa_id",
        ],
        "local-life": [
            "yanaka_ginza_id",
            "shimokitazawa_id",
            "tsukiji_outer_market_id",
            "ueno_park_id",
            "sensoji_id",
        ],
    }

    ordered_ids = persona_defaults.get(persona_type, list(catalog))
    if destination.strip() and "tokyo" not in destination.lower():
        logger.info(
            "Using Tokyo-based mock search catalog for destination=%s because no live Places key is configured.",
            destination,
        )
    return [catalog[place_id] for place_id in ordered_ids[: max(limit, 0)] if place_id in catalog]


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
        return [normalized_query]

    try:
        payload = await _fetch_places_autocomplete(normalized_query)
    except MapsAPIError as exc:
        logger.warning("Places autocomplete failed for query=%r (%s)", normalized_query, exc)
        return [normalized_query]

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

    return suggestions or [normalized_query]


async def places_search(destination: str, persona_type: str, limit: int = 5) -> list[PlaceSearchResult]:
    """Fetch factual place candidates for itinerary planning."""
    if not destination or not destination.strip():
        raise PlaceNotFoundError("destination is required")

    if _uses_mock_places():
        logger.info(
            "Using mock place search for destination=%s persona=%s (no Places API key configured)",
            destination,
            persona_type,
        )
        return _mock_places_search(destination, persona_type, limit)

    unique_places: dict[str, PlaceSearchResult] = {}
    try:
        for query in _search_queries(destination, persona_type):
            remaining = max(limit - len(unique_places), 0)
            if remaining == 0:
                break

            payload = await _fetch_places_search(query, max(remaining, 1))
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
            "Places Search failed for destination=%s persona=%s (%s); using mock fallback.",
            destination,
            persona_type,
            exc,
        )
        return _mock_places_search(destination, persona_type, limit)

    if unique_places:
        results = list(unique_places.values())[:limit]
        logger.info(
            "Fetched %d place candidates for destination=%s persona=%s",
            len(results),
            destination,
            persona_type,
        )
        return results

    # Dev fallback mirrors get_place_details: keep the pipeline usable when
    # Places API (New) is not enabled but a mock-friendly destination is used.
    logger.warning(
        "Places Search returned no candidates for destination=%s persona=%s; using mock fallback.",
        destination,
        persona_type,
    )
    return _mock_places_search(destination, persona_type, limit)


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
        if place_id in _KNOWN_MOCK_PLACE_IDS:
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


_MOCK_TRAVEL_MIN: dict[tuple[str, str], int] = {
    ("sensoji_id", "edo_museum_id"): 15,
    ("edo_museum_id", "sensoji_id"): 15,
}
_DEFAULT_WALK_MIN = 12


def _uses_mock_directions() -> bool:
    return settings.google_maps_api_key.strip() == "mock-maps-key"


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
            "key": settings.google_maps_api_key,
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
    duration_min = _MOCK_TRAVEL_MIN.get((origin_place_id, destination_place_id), _DEFAULT_WALK_MIN)

    if _uses_mock_directions():
        return {
            "duration_min": duration_min,
            "distance_m": duration_min * 80,
            "mode": mode,
            "source": "mock",
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
            "Directions lookup failed for %s -> %s (%s); using fallback duration.",
            origin_place_id,
            destination_place_id,
            exc,
        )
        return {
            "duration_min": duration_min,
            "distance_m": duration_min * 80,
            "mode": mode,
            "source": "mock",
        }
