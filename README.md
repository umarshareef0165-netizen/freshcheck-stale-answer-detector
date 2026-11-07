# FreshCheck — Stale-Answer Detector

> Paste an AI answer (or any claim) plus its sources with dates.
> FreshCheck returns one verdict — **FRESH / CHECK / STALE / UNKNOWN** —
> with confidence, a written explanation, and an evidence table, so you
> do not reuse an outdated answer.

**Built for:** Geek Room Global AI Hackathon (HackCulture), solo entry by
Umar Shareef. Category: Tavily — Stale-Answer Detection.
**Status:** working prototype with live Tavily re-verification.
Public repo: https://github.com/umarshareef0165-netizen/freshcheck-stale-answer-detector
Not yet submitted to HackCulture at the time this README was written; the
live submission state is on the HackCulture dashboard, not in this file.

## What it judges — and what it does not

FreshCheck judges **evidence freshness only**. It does **not** verify
that a claim is true or false, does not call any LLM, and stores
nothing. Everything is analysed in memory and forgotten on refresh.
The offline check calls no network at all. The optional
**"Re-verify with live web (Tavily)"** button fetches live sources via
the Tavily Search API and re-runs the same deterministic rules on them;
Tavily supplies evidence, it never decides the verdict. Without a
`TAVILY_API_KEY` the button says so honestly instead of faking a check.

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

No pip packages, no database. Python 3.10+ is enough. The offline check
needs no key at all; live re-verification needs `TAVILY_API_KEY`:

```bash
TAVILY_API_KEY=tvly-... python3 prototype/server.py
```

(The key is never committed to the repo.)

## Test it

```bash
python3 -m unittest discover -s tests -v   # 26/26 (16 analyzer + 10 Tavily)
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
prototype/tavily.py     live re-verification via Tavily Search API (urllib)
tests/test_analyzer.py  16 unit tests
tests/test_tavily.py    10 tests (fixtures + mocked HTTP + live server, no key)
```

## Licence

MIT — see `LICENSE`.

## Honest limitations

- No LLM call. Live re-verification needs a Tavily API key; without one
  the app says so and the offline check still works.
- The demo form takes one source per check; the analyzer already
  accepts a list of sources.
- No accounts, no database, no persistence by design.
