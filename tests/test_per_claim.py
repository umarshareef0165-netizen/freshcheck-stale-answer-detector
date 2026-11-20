"""Tests for per-claim freshness scores (Problem Statement 06).

Each claim in a multi-claim answer gets its own 0-100 freshness score
plus verdict, rendered as a table by the server.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prototype"))
from analyzer import analyze_claims, freshness_score, split_claims


class TestSplitClaims(unittest.TestCase):
    def test_lines_and_sentences(self):
        claims = split_claims(
            "As of 2024-01-15, the tool costs $10 per month.\n"
            "As of 2026-10-20, the tool costs $12 per month.")
        self.assertEqual(len(claims), 2)
        self.assertTrue(claims[0].startswith("As of 2024-01-15"))
        self.assertTrue(claims[1].startswith("As of 2026-10-20"))

    def test_blank_lines_dropped(self):
        self.assertEqual(split_claims("One claim.\n\n\nSecond claim."),
                         ["One claim.", "Second claim."])
        self.assertEqual(split_claims(""), [])
        self.assertEqual(split_claims("   \n  "), [])


class TestPerClaimScores(unittest.TestCase):
    TODAY = date(2026, 11, 4)
    SRC = [{"title": "Pricing", "url": "https://example.com",
            "date_text": "2026-10-01"}]

    def test_old_and_new_claims_score_differently(self):
        text = ("As of 2024-01-15, the tool costs $10 per month. "
                "As of 2026-10-20, the tool costs $12 per month.")
        claims = analyze_claims(text, "", self.SRC, today=self.TODAY)
        self.assertEqual(len(claims), 2)
        # Old claim, newer source exists -> STALE, low freshness score.
        self.assertEqual(claims[0]["verdict"], "STALE")
        self.assertLessEqual(claims[0]["score"], 20)
        # Recent claim -> CHECK, mid score (newest source predates it).
        self.assertEqual(claims[1]["verdict"], "CHECK")
        self.assertEqual(claims[1]["score"], 50)
        self.assertGreater(claims[1]["score"], claims[0]["score"])

    def test_single_claim_returns_one_scored_entry(self):
        claims = analyze_claims("The tool costs $10.", "2024-01-15",
                                self.SRC, today=self.TODAY)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["verdict"], "STALE")
        self.assertTrue(0 <= claims[0]["score"] <= 100)

    def test_fresh_claim_scores_high(self):
        src = [{"title": "Pricing", "url": "https://example.com",
                "date_text": "2026-10-20"}]
        claims = analyze_claims("As of 2026-10-20, the tool costs $10.",
                                "", src, today=self.TODAY)
        self.assertEqual(claims[0]["verdict"], "FRESH")
        self.assertGreaterEqual(claims[0]["score"], 80)

    def test_score_mapping(self):
        self.assertEqual(freshness_score({"verdict": "FRESH", "confidence": 85}), 85)
        self.assertEqual(freshness_score({"verdict": "CHECK", "confidence": 65}), 50)
        self.assertEqual(freshness_score({"verdict": "STALE", "confidence": 90}), 10)
        self.assertEqual(freshness_score({"verdict": "UNKNOWN", "confidence": 10}), 20)


if __name__ == "__main__":
    unittest.main()
