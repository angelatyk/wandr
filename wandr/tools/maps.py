# Stub maps tool functions

async def places_search(destination: str, persona_type: str, limit: int = 5) -> list:
    """Fetch candidate places for a destination and persona type."""
    # Stub implementation
    return []

async def get_place_details(place_id: str) -> dict:
    """Fetch enriched details for a place."""
    # Stub implementation
    return {}

async def get_directions(origin_place_id: str, destination_place_id: str, mode: str = "walking") -> dict:
    """Fetch travel distance and time between places."""
    # Stub implementation
    return {}
