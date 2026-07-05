import re
from typing import Literal

from pydantic import BaseModel


class ParsedDuration(BaseModel):
    """Structured trip length derived from free-text persona.duration."""

    raw: str
    unit: Literal["hours", "days", "weeks", "months", "unknown"]
    amount: float
    day_count: int
    total_hours: float | None = None
    is_single_outing: bool = False

    @property
    def summary(self) -> str:
        if self.is_single_outing and self.total_hours is not None:
            hours = int(self.total_hours) if self.total_hours.is_integer() else self.total_hours
            return f"a single {hours}-hour outing (1 calendar day)"
        if self.unit == "days":
            n = int(self.amount) if self.amount.is_integer() else self.amount
            return f"{n} calendar day(s)"
        if self.unit == "weeks":
            return f"{self.amount} week(s) (~{self.day_count} days)"
        return self.raw or "1 calendar day"


def parse_trip_duration(duration: str | None) -> ParsedDuration:
    """
    Convert persona duration text into calendar day count for itinerary structure.

    Hour-scale outings (e.g. "7 hours") always map to day_count=1 — never 7 days.
    """
    raw = (duration or "").strip()
    if not raw:
        return ParsedDuration(raw="", unit="unknown", amount=1, day_count=1)

    text = raw.lower()

    if "weekend" in text:
        return ParsedDuration(
            raw=raw,
            unit="days",
            amount=2,
            day_count=2,
            total_hours=48,
            is_single_outing=False,
        )

    unit_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|days?|d\b|weeks?|w\b|months?|month)",
        text,
    )
    if unit_match:
        amount = float(unit_match.group(1))
        token = unit_match.group(2)

        if token.startswith("h"):
            return ParsedDuration(
                raw=raw,
                unit="hours",
                amount=amount,
                day_count=1,
                total_hours=amount,
                is_single_outing=True,
            )
        if token.startswith("d"):
            days = max(1, int(round(amount)))
            return ParsedDuration(
                raw=raw,
                unit="days",
                amount=amount,
                day_count=days,
                total_hours=amount * 24,
                is_single_outing=days <= 1,
            )
        if token.startswith("w"):
            days = max(1, int(round(amount * 7)))
            return ParsedDuration(
                raw=raw,
                unit="weeks",
                amount=amount,
                day_count=days,
                total_hours=days * 24,
                is_single_outing=False,
            )
        if token.startswith("month"):
            days = max(1, int(round(amount * 30)))
            return ParsedDuration(
                raw=raw,
                unit="months",
                amount=amount,
                day_count=days,
                total_hours=days * 24,
                is_single_outing=False,
            )

    if "hour" in text or re.search(r"\bhrs?\b", text):
        number = re.search(r"(\d+(?:\.\d+)?)", text)
        hours = float(number.group(1)) if number else 1.0
        return ParsedDuration(
            raw=raw,
            unit="hours",
            amount=hours,
            day_count=1,
            total_hours=hours,
            is_single_outing=True,
        )

    if "day" in text:
        number = re.search(r"(\d+(?:\.\d+)?)", text)
        days = max(1, int(round(float(number.group(1))))) if number else 1
        return ParsedDuration(
            raw=raw,
            unit="days",
            amount=float(days),
            day_count=days,
            total_hours=days * 24,
            is_single_outing=days <= 1,
        )

    if "week" in text:
        number = re.search(r"(\d+(?:\.\d+)?)", text)
        weeks = float(number.group(1)) if number else 1.0
        days = max(1, int(round(weeks * 7)))
        return ParsedDuration(
            raw=raw,
            unit="weeks",
            amount=weeks,
            day_count=days,
            total_hours=days * 24,
            is_single_outing=False,
        )

    # Bare number without unit — default to 1 day (do NOT treat "7" as 7 days).
    return ParsedDuration(raw=raw, unit="unknown", amount=1, day_count=1)


def max_stops_for_duration(parsed: ParsedDuration) -> int:
    """Upper bound on final stops that fit the requested time window."""
    if parsed.is_single_outing and parsed.total_hours:
        # Generous bound to allow user to pack their itinerary if they want
        return max(3, min(8, int(parsed.total_hours // 1.2)))
    if parsed.day_count == 1:
        return 6
    return max(4, min(10, parsed.day_count * 5))


def max_options_per_day(parsed: ParsedDuration, day_count: int) -> int:
    """How many place options to surface per day in options mode."""
    if parsed.is_single_outing and parsed.total_hours:
        return max(5, min(12, int(parsed.total_hours * 1.5)))
    return max(5, min(10, 4 + day_count))
