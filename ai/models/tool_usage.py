from pydantic import BaseModel, Field

from ai.models.audio import AudioScript
from ai.models.place import PlaceSearchResult
from ai.models.route import RouteModel


class ApiMockCounter(BaseModel):
    api: int = 0
    mock: int = 0


class PlacesSearchCounter(ApiMockCounter):
    confirmed: int = 0


class TTSCounter(BaseModel):
    inline: int = 0
    signed_url: int = 0
    text_only: int = 0


class ToolUsageModel(BaseModel):
    places_search: PlacesSearchCounter = Field(default_factory=PlacesSearchCounter)
    place_details: ApiMockCounter = Field(default_factory=ApiMockCounter)
    directions: ApiMockCounter = Field(default_factory=ApiMockCounter)
    tts: TTSCounter = Field(default_factory=TTSCounter)


def load_tool_usage(raw_usage: object | None) -> ToolUsageModel:
    if raw_usage in (None, ""):
        return ToolUsageModel()
    return ToolUsageModel.model_validate(raw_usage)


def merge_tool_usage(base: ToolUsageModel, delta: ToolUsageModel) -> ToolUsageModel:
    return ToolUsageModel(
        places_search=PlacesSearchCounter(
            api=base.places_search.api + delta.places_search.api,
            mock=base.places_search.mock + delta.places_search.mock,
            confirmed=base.places_search.confirmed + delta.places_search.confirmed,
        ),
        place_details=ApiMockCounter(
            api=base.place_details.api + delta.place_details.api,
            mock=base.place_details.mock + delta.place_details.mock,
        ),
        directions=ApiMockCounter(
            api=base.directions.api + delta.directions.api,
            mock=base.directions.mock + delta.directions.mock,
        ),
        tts=TTSCounter(
            inline=base.tts.inline + delta.tts.inline,
            signed_url=base.tts.signed_url + delta.tts.signed_url,
            text_only=base.tts.text_only + delta.tts.text_only,
        ),
    )


def usage_from_places_search(candidates: list[PlaceSearchResult]) -> ToolUsageModel:
    usage = ToolUsageModel()
    if any(candidate.source == "api" for candidate in candidates):
        usage.places_search.api = 1
    elif any(candidate.source == "mock" for candidate in candidates):
        usage.places_search.mock = 1
    return usage


def usage_from_audio_scripts(scripts: list[AudioScript]) -> ToolUsageModel:
    usage = ToolUsageModel()
    for script in scripts:
        if script.research_source == "api":
            usage.place_details.api += 1
        elif script.research_source == "mock":
            usage.place_details.mock += 1

        if script.tts_attempted:
            if script.audio_source == "inline":
                usage.tts.inline += 1
            elif script.audio_source == "signed_url":
                usage.tts.signed_url += 1
            elif script.audio_source == "text_only":
                usage.tts.text_only += 1
    return usage


def usage_from_route(route: RouteModel) -> ToolUsageModel:
    usage = ToolUsageModel()
    for stop in route.stops:
        if stop.place_source == "api":
            usage.place_details.api += 1
        elif stop.place_source == "mock":
            usage.place_details.mock += 1

        if stop.travel_source == "api":
            usage.directions.api += 1
        elif stop.travel_source == "mock":
            usage.directions.mock += 1
    return usage
