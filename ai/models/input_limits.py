"""Shared input length caps — generous for real trips, tight enough to block abuse.

These are character limits (not tokens). Rough guide: 1 token ≈ 4 characters.
"""

# ~800 words — detailed vibe, dietary needs, must-sees, refinement notes.
FREE_TEXT_MAX = 4000

# Google Places labels + long international addresses.
LOCATION_TEXT_MAX = 400

# Duration strings, persona labels, transit preference.
SHORT_TEXT_MAX = 100

# Google place_id strings.
PLACE_ID_MAX = 300

# Upper bound on toggled stops at finalize (multi-week trips).
MAX_CONFIRMED_PLACES = 100
