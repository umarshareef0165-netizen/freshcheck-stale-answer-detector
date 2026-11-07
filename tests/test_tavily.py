"""Tests for the Tavily live re-verification (no real network calls).

The live HTTP transport is injected via ``http_post`` so every test runs
offline against fixtures. One test spins up the real server on an
ephemeral port and checks the /reverify route without a key.
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prototype"))
from analyzer import analyze
import tavily


FIXTURE_OK = {
    "results": [
        {"title": "Pricing update", "url": "https://example.com/pricing",
         "content": "The price changed.", "published_date": "2026-10-01"},
        {"title": "Old blog post", "url": "https://example.com/blog",
         "content": "Posted on 2024-01-15 about the old price.",
         "published_date": None},
        {"title": "No date anywhere", "url": "https://example.com/x",
         "content": "Nothing dated here.", "published_date": None},
    ],
    "response_time": 0.4,
}


def fake_http_ok(payload, api_key):
    assert payload["query"] == "The tool costs $10 per month."
    assert api_key == "tvly-test"
    assert payload["max_results"] == 5
    return FIXTURE_OK


class TestReverify(unittest.TestCase):
    def test_ok_normalises_sources(self):
        out = tavily.reverify("The tool costs $10 per month.",
                               api_key="tvly-test", http_post=fake_http_ok)
        self.assertTrue(out["ok"])
        self.assertEqual(out["raw_count"], 3)
        self.assertEqual(out["dated"], 2)  # published_date + content date
        self.assertEqual(out["sources"][0]["date_text"], "2026-10-01")
        self.assertEqual(out["sources"][0]["date_source"], "published_date")
        self.assertEqual(out["sources"][1]["date_text"], "2024-01-15")
        self.assertEqual(out["sources"][1]["date_source"], "content")
        self.assertEqual(out["sources"][2]["date_text"], "")
        self.assertEqual(out["sources"][2]["date_source"], "none")

    def test_no_key(self):
        out = tavily.reverify("anything", api_key=None, http_post=fake_http_ok)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "no_api_key")

    def test_empty_claim(self):
        out = tavily.reverify("   ", api_key="tvly-test", http_post=fake_http_ok)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "empty_claim")

    def test_http_error(self):
        def boom(payload, api_key):
            raise urllib.error.HTTPError("https://api.tavily.com/search",
                                         401, "Unauthorized", {}, None)
        out = tavily.reverify("x", api_key="bad", http_post=boom)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "http_401")

    def test_network_error(self):
        def boom(payload, api_key):
            raise urllib.error.URLError("boom")
        out = tavily.reverify("x", api_key="tvly-test", http_post=boom)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "network")

    def test_bad_response(self):
        out = tavily.reverify("x", api_key="tvly-test",
                               http_post=lambda p, k: {"nonsense": True})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "bad_response")

    def test_live_sources_drive_verdict(self):
        """Live sources newer than an old claim must flip the verdict."""
        out = tavily.reverify("The tool costs $10 per month.",
                               api_key="tvly-test", http_post=fake_http_ok)
        result = analyze("The tool costs $10 per month.", "2024-01-15",
                         out["sources"], today=date(2026, 11, 5))
        self.assertEqual(result["verdict"], "STALE")
        self.assertEqual(result["newest_source_date"], "2026-10-01")


class TestServerReverify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server as srv
        cls._server = HTTPServer(("127.0.0.1", 0), srv.Handler)
        cls.port = cls._server.server_address[1]
        cls._thread = threading.Thread(target=cls._server.serve_forever,
                                       daemon=True)
        cls._thread.start()
        # No key in the environment for these tests.
        os.environ.pop("TAVILY_API_KEY", None)

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()

    def _post(self, path, body):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body.encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode()

    def _get(self, path):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}{path}", timeout=10) as resp:
            return resp.read().decode()

    def test_health_reports_tavily_off(self):
        data = json.loads(self._get("/health"))
        self.assertTrue(data["ok"])
        self.assertFalse(data["tavily"])

    def test_reverify_without_key_is_honest(self):
        html = self._post("/reverify", "claim=The+tool+costs+%2410&claim_date=2024-01-15")
        self.assertIn("Live re-verification (Tavily)", html)
        self.assertIn("not configured", html)
        self.assertIn("TAVILY_API_KEY", html)

    def test_main_page_shows_tavily_status(self):
        html = self._get("/")
        self.assertIn("Live re-verify via Tavily", html)
        self.assertIn("not configured", html)


if __name__ == "__main__":
    unittest.main()
