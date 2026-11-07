"""FreshCheck — live re-verification via the Tavily Search API.

Python standard library only (urllib). No key is ever hard-coded here:
the key comes from the TAVILY_API_KEY environment variable, read by the
server at request time.

What it does: given the claim text, it asks Tavily for live web results
and normalises them into the same source dicts the deterministic
``analyzer`` already understands ({title, url, date_text}). The verdict
itself is still computed by ``analyzer.analyze`` — Tavily only supplies
fresher evidence; it never decides the verdict.

Honesty rules:
- No key configured  -> {"ok": False, "error": "no_api_key"}.
- Any network/HTTP/JSON failure -> {"ok": False, "error": ...}.
  Failures are reported to the user, never hidden and never faked.
- A result without a published date falls back to the first date found
  in its content snippet (marked "content"); if none is found the
  source is kept with an empty date and the analyzer treats it as
  undated. No date is ever invented.
- Tavily's own ``published_date`` may be null for ordinary pages; that
  is normal and is not an error.
"""
import json
import urllib.error
import urllib.request

from analyzer import find_dates

TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT_SECONDS = 20


def _default_http(payload, api_key):
    """POST the search payload to Tavily; returns the decoded JSON dict."""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        TAVILY_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode())


def _normalise_result(result):
    """One Tavily result -> analyzer source dict (plus date provenance)."""
    title = (result or {}).get("title", "") or ""
    url = (result or {}).get("url", "") or ""
    published = (result or {}).get("published_date") or ""
    date_text = published.strip() if isinstance(published, str) else ""
    date_source = "published_date" if date_text else "none"
    if not date_text:
        # Fall back to the first date mentioned in the content snippet.
        content = (result or {}).get("content", "") or ""
        found = find_dates(content[:500])
        if found:
            date_text = found[0][0].isoformat()
            date_source = "content"
    return {
        "title": title,
        "url": url,
        "date_text": date_text,
        "date_source": date_source,
    }


def reverify(claim_text, api_key=None, max_results=5, http_post=None):
    """Fetch live web sources for ``claim_text`` via Tavily.

    Returns {"ok": True, "sources": [...], "dated": int, "raw_count": int}
    or {"ok": False, "error": "<no_api_key|network|http_<code>|bad_response>"}.
    ``http_post`` is an injectable transport for tests; it must accept
    (payload, api_key) and return the decoded response dict.
    """
    if not claim_text or not str(claim_text).strip():
        return {"ok": False, "error": "empty_claim"}
    if not api_key:
        return {"ok": False, "error": "no_api_key"}
    payload = {
        "query": str(claim_text).strip(),
        "search_depth": "basic",
        "max_results": max(1, min(int(max_results), 10)),
        "include_answer": False,
        "include_raw_content": False,
    }
    call = http_post or _default_http
    try:
        data = call(payload, api_key)
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"http_{exc.code}"}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"ok": False, "error": "network"}
    except Exception:
        return {"ok": False, "error": "network"}
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return {"ok": False, "error": "bad_response"}
    sources = [_normalise_result(r) for r in data["results"]]
    dated = sum(1 for s in sources if s["date_text"])
    return {"ok": True, "sources": sources, "dated": dated,
            "raw_count": len(sources)}
