"""Regression checks for trip duration parsing."""

import unittest

from ai.models.duration import parse_trip_duration


class ParseTripDurationTests(unittest.TestCase):
    def test_seven_hours_is_one_day_not_seven(self) -> None:
        parsed = parse_trip_duration("7 hours")
        self.assertEqual(parsed.day_count, 1)
        self.assertTrue(parsed.is_single_outing)
        self.assertEqual(parsed.total_hours, 7)

    def test_three_days(self) -> None:
        parsed = parse_trip_duration("3 days")
        self.assertEqual(parsed.day_count, 3)
        self.assertFalse(parsed.is_single_outing)

    def test_weekend(self) -> None:
        parsed = parse_trip_duration("weekend")
        self.assertEqual(parsed.day_count, 2)

    def test_bare_number_defaults_to_one_day(self) -> None:
        parsed = parse_trip_duration("7")
        self.assertEqual(parsed.day_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
