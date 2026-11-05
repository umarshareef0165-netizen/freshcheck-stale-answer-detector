"""Built-in demo examples. All dates are sample data, not real-world facts
about any live product, price, or statistic. They exist so a judge can see
FRESH / CHECK / STALE / UNKNOWN in one click, without any API key.
"""
SAMPLES = [
    {
        "id": "stale",
        "label": "STALE example — old claim, newer source exists",
        "claim": "The tool costs $10 per month.",
        "claim_date": "2024-01-15",
        "sources": [
            {"title": "Pricing page (updated)", "url": "https://example.com/pricing",
             "date_text": "2026-10-01"},
        ],
    },
    {
        "id": "fresh",
        "label": "FRESH example — recent claim, source dated same day",
        "claim": "The tool costs $10 per month.",
        "claim_date": "2026-10-20",
        "sources": [
            {"title": "Pricing page", "url": "https://example.com/pricing",
             "date_text": "2026-10-20"},
        ],
    },
    {
        "id": "check",
        "label": "CHECK example — newer source, still inside window",
        "claim": "The tool costs $10 per month.",
        "claim_date": "2026-10-20",
        "sources": [
            {"title": "Pricing page (updated)", "url": "https://example.com/pricing",
             "date_text": "2026-11-01"},
        ],
    },
    {
        "id": "unknown",
        "label": "UNKNOWN example — no dates supplied",
        "claim": "The tool costs $10 per month.",
        "claim_date": "",
        "sources": [
            {"title": "Pricing page", "url": "https://example.com/pricing",
             "date_text": ""},
        ],
    },
]
