"""FreshCheck — stale-answer detection, deterministic, no LLM, no paid API.

Honest scope: this prototype does NOT verify facts against the live web.
It detects *staleness risk*: a dated claim checked against dated sources.
- A claim is a short statement plus the date it was supposedly true.
- A source is a title/URL plus the date it was published or last updated.
- The verdict compares the newest source date with the claim date and
  with a caller-supplied "today" so tests are reproducible.

Verdicts:
  FRESH  — newest source is on/after the claim date, and the claim is
           not older than the freshness window (default 180 days).
  CHECK  — a newer source exists but the claim is inside the window, or
           dates are partial (year-only) so confidence is capped.
  STALE  — the claim is older than the window AND a newer source exists,
           or the newest source predates the claim (claim cites nothing
           that could support it).
  UNKNOWN — no usable dates on the claim or on any source.

Dates accepted: YYYY-MM-DD, YYYY/MM/DD, "12 Jan 2024", "Jan 12, 2024",
"January 2024" (treated as the 1st of the month, flagged partial),
"2024" (treated as Jan 1, flagged partial).
"""
import re
from datetime import date

MONTHS = {m.lower(): i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
MONTHS.update({m[:3]: i for m, i in MONTHS.items()})

ISO_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
DMY_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
MDY_RE = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})")
# Month-year only: a bare "word + year" (e.g. "published 2024") must NOT
# count as a month. The alternation below is month names only.
_MONTH = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|"
          "Oct|Nov|Dec")
MY_RE = re.compile(r"(" + _MONTH + r")\s+(\d{4})", re.IGNORECASE)
YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def parse_date(text):
    """Return (date | None, partial: bool). Partial = month/year or year only."""
    if not text:
        return None, False
    text = text.strip()
    m = ISO_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), False
        except ValueError:
            return None, False
    m = DMY_RE.search(text)
    if m and m.group(2).lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))), False
        except ValueError:
            return None, False
    m = MDY_RE.search(text)
    if m and m.group(1).lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))), False
        except ValueError:
            return None, False
    m = MY_RE.search(text)
    if m and m.group(1).lower() in MONTHS:
        try:
            return date(int(m.group(2)), MONTHS[m.group(1).lower()], 1), True
        except ValueError:
            return None, False
    m = YEAR_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), 1, 1), True
        except ValueError:
            return None, False
    return None, False


def find_dates(text):
    """All dates found in free text, in order, as (date, partial).

    Overlapping matches are de-duplicated: e.g. "1 October 2026" must not
    also count as "October 2026". A non-partial match wins over a partial
    match covering the same span.
    """
    if not text:
        return []
    spans = []  # (start, end, date, partial)
    for pattern in (ISO_RE, DMY_RE, MDY_RE, MY_RE):
        for m in pattern.finditer(text):
            d, partial = parse_date(m.group(0))
            if d:
                spans.append((m.start(), m.end(), d, partial))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept = []
    for start, end, d, partial in spans:
        if any(start >= ks and end <= ke for ks, ke, _, _ in kept):
            continue
        kept.append((start, end, d, partial))
    out = [(d, partial) for _, _, d, partial in sorted(kept)]
    # Year-only only if nothing more precise was found.
    if not out:
        for m in YEAR_RE.finditer(text):
            d, partial = parse_date(m.group(0))
            if d:
                out.append((d, partial))
    return out


def analyze(claim_text, claim_date_text, sources, today=None, window_days=180):
    """sources: list of dicts {title, url, date_text}.

    Returns a dict with verdict, confidence (0-100), ages, evidence list,
    and a human-readable explanation. Never claims a fact is true/false;
    it only reports whether the supporting evidence looks current.
    """
    today = today or date.today()
    claim_date, claim_partial = parse_date(claim_date_text or "")
    if claim_date is None:
        found = find_dates(claim_text or "")
        if found:
            claim_date, claim_partial = found[0]
    parsed_sources = []
    for s in sources or []:
        d, partial = parse_date((s or {}).get("date_text", ""))
        if d is None:
            d, partial = parse_date((s or {}).get("title", ""))
        parsed_sources.append({
            "title": (s or {}).get("title", ""),
            "url": (s or {}).get("url", ""),
            "date": d.isoformat() if d else None,
            "partial": partial,
            "has_date": d is not None,
        })
    dated = [p for p in parsed_sources if p["has_date"]]
    if claim_date is None or not dated:
        return {
            "verdict": "UNKNOWN",
            "confidence": 30 if dated or claim_date else 10,
            "claim_date": claim_date.isoformat() if claim_date else None,
            "newest_source_date": max((p["date"] for p in dated), default=None),
            "claim_age_days": (today - claim_date).days if claim_date else None,
            "newer_source_exists": False,
            "sources": parsed_sources,
            "explanation": ("No usable dates on the claim or on the sources, so "
                            "staleness cannot be judged. Add a claim date and a "
                            "source publication/update date."),
        }
    newest = max(p["date"] for p in dated)
    newest_d = date.fromisoformat(newest)
    age = (today - claim_date).days
    newer_exists = newest_d > claim_date
    any_partial = claim_partial or any(p["partial"] for p in dated)
    if newest_d < claim_date:
        # A source older than the claim does not prove the claim wrong;
        # it only means the claim is not directly supported by what was
        # supplied. Old + unsupported = STALE; recent + unsupported = CHECK.
        if age > window_days:
            verdict, confidence = "STALE", 85
            why = ("The newest source predates the claim and the claim is "
                   "outside the freshness window, so nothing supplied can "
                   "support it as dated.")
        else:
            verdict, confidence = "CHECK", 60
            why = ("The newest source predates the claim, so the claim is "
                   "not directly supported by the supplied sources, but it "
                   "is still inside the freshness window — verify it against "
                   "a newer source before quoting it.")
    elif age > window_days and newer_exists:
        verdict, confidence = "STALE", 90
        why = (f"The claim is {age} days old (window: {window_days} days) "
               f"and a newer source exists ({newest}), so the answer "
               f"should be re-checked before reuse.")
    elif newer_exists:
        verdict, confidence = "CHECK", 65
        why = ("A newer source exists, but the claim is still inside the "
               "freshness window — verify the newer source before quoting it.")
    else:
        verdict, confidence = "FRESH", 85
        why = ("No source is newer than the claim and the claim is inside "
               "the freshness window — the evidence looks current.")
    if any_partial:
        confidence = min(confidence, 70)
        why += " Confidence is capped because at least one date is partial (month/year or year only)."
    return {
        "verdict": verdict,
        "confidence": confidence,
        "claim_date": claim_date.isoformat(),
        "newest_source_date": newest,
        "claim_age_days": age,
        "newer_source_exists": newer_exists,
        "sources": parsed_sources,
        "explanation": why,
    }
