import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prototype"))
from analyzer import analyze, find_dates, parse_date


class TestDates(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(parse_date("2024-01-15"), (date(2024, 1, 15), False))

    def test_slash(self):
        self.assertEqual(parse_date("2024/01/15"), (date(2024, 1, 15), False))

    def test_month_name(self):
        self.assertEqual(parse_date("12 Jan 2024"), (date(2024, 1, 12), False))
        self.assertEqual(parse_date("Jan 12, 2024"), (date(2024, 1, 12), False))

    def test_partial_month_year(self):
        self.assertEqual(parse_date("January 2024"), (date(2024, 1, 1), True))

    def test_partial_year_only(self):
        self.assertEqual(parse_date("2024"), (date(2024, 1, 1), True))

    def test_invalid(self):
        self.assertEqual(parse_date("no date here"), (None, False))
        self.assertEqual(parse_date(""), (None, False))

    def test_find_dates_in_text(self):
        found = find_dates("Updated 1 October 2026, first published 2024-01-15")
        self.assertEqual(len(found), 2)


class TestVerdicts(unittest.TestCase):
    TODAY = date(2026, 11, 4)
    SRC = [{"title": "Pricing", "url": "https://example.com", "date_text": "2026-10-01"}]

    def test_stale_old_claim_newer_source(self):
        r = analyze("Costs $10.", "2024-01-15", self.SRC, today=self.TODAY)
        self.assertEqual(r["verdict"], "STALE")

    def test_fresh_recent_claim(self):
        src = [{"title": "Pricing", "url": "https://example.com", "date_text": "2026-10-20"}]
        r = analyze("Costs $10.", "2026-10-20", src, today=self.TODAY)
        self.assertEqual(r["verdict"], "FRESH")

    def test_check_recent_claim_older_source(self):
        # Recent claim, only an older source: not proven stale, but CHECK.
        r = analyze("Costs $10.", "2026-10-20", self.SRC, today=self.TODAY)
        self.assertEqual(r["verdict"], "CHECK")

    def test_check_newer_source_inside_window(self):
        src = [{"title": "Pricing", "url": "https://example.com", "date_text": "2026-11-01"}]
        r = analyze("Costs $10.", "2026-10-20", src, today=self.TODAY)
        self.assertEqual(r["verdict"], "CHECK")

    def test_stale_source_predates_claim(self):
        src = [{"title": "Old page", "url": "https://example.com", "date_text": "2023-01-01"}]
        r = analyze("Costs $10.", "2024-01-15", src, today=self.TODAY)
        self.assertEqual(r["verdict"], "STALE")

    def test_unknown_no_dates(self):
        r = analyze("Costs $10.", "", [{"title": "Page", "url": "", "date_text": ""}],
                    today=self.TODAY)
        self.assertEqual(r["verdict"], "UNKNOWN")

    def test_partial_caps_confidence(self):
        r = analyze("Costs $10.", "January 2024",
                    [{"title": "P", "url": "", "date_text": "2026-10-01"}],
                    today=self.TODAY)
        self.assertEqual(r["verdict"], "STALE")
        self.assertLessEqual(r["confidence"], 70)

    def test_claim_date_found_in_claim_text(self):
        r = analyze("As of 2024-01-15, costs $10.", "", self.SRC, today=self.TODAY)
        self.assertEqual(r["claim_date"], "2024-01-15")
        self.assertEqual(r["verdict"], "STALE")

    def test_window_boundary(self):
        # Exactly 180 days old, newer source exists -> CHECK (not > window).
        r = analyze("Costs $10.", "2026-05-08", self.SRC, today=self.TODAY)
        self.assertEqual(r["verdict"], "CHECK")


if __name__ == "__main__":
    unittest.main()
