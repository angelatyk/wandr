class PlaceNotFoundError(Exception):
    """Raised when Google Places returns no result for a place_id."""


class MapsAPIError(Exception):
    """Raised when the Google Places API request fails."""


class TTSError(Exception):
    """Raised when Cloud TTS or audio upload fails."""
