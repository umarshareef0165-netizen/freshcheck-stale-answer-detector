# FreshCheck — Stale-Answer Detector

> Paste an AI answer (or any claim) plus its sources with dates.
> FreshCheck returns one verdict — **FRESH / CHECK / STALE / UNKNOWN** —
> with confidence, a written explanation, and an evidence table, so you
> do not reuse an outdated answer.

**Built for:** Geek Room Global AI Hackathon (HackCulture), solo entry by
Umar Shareef. Category: Tavily — Stale-Answer Detection.
**Status:** working prototype. Not yet submitted to HackCulture at the
time this README was written; the live submission state is on the
HackCulture dashboard, not in this file.

## What it judges — and what it does not

FreshCheck judges **evidence freshness only**. It does **not** verify
that a claim is true or false, does not call the live web, does not call
any LLM, and stores nothing. Everything is analysed in memory and
forgotten on refresh.

## How a verdict is decided

- **FRESH** — no source newer than the claim, and the claim is inside
  the 180-day window.
- **CHECK** — a newer source exists but the claim is inside the window,
  OR the claim is recent but only an older source was supplied.
- **STALE** — the claim is older than 180 days with a newer source, or
  the claim is old and unsupported by any supplied source.
- **UNKNOWN** — no usable dates on the claim or any source.

Partial dates (month/year, or year only) cap confidence at 70% and say so
on screen. If no claim date is typed, the first date found inside the
claim text is used.

## Run it

```bash
python3 prototype/server.py   # http://127.0.0.1:8000
```

No pip packages, no API key, no database. Python 3.10+ is enough.

## Test it

```bash
python3 -m unittest discover -s tests -v   # 16/16 at delivery
```

## Try it in under a minute

Open the app and click the four built-in samples — STALE, FRESH, CHECK,
UNKNOWN. They use sample data only (no real-world price or statistic is
claimed) and need no typing, no key, and no network call.

## Project layout

```
prototype/analyzer.py   deterministic date parsing + verdict logic
prototype/server.py     stdlib-only demo web server (http.server)
prototype/samples.py    four built-in examples (sample data only)
tests/test_analyzer.py  16 unit tests
```

## Licence

MIT — see `LICENSE`.

## Honest limitations

- No live-web fetching, no Tavily API call, no LLM call (yet).
- The demo form takes one source per check; the analyzer already
  accepts a list of sources.
- No accounts, no database, no persistence by design.
