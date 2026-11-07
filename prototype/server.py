"""FreshCheck demo server — Python standard library only, no pip packages.

Run:  python3 server.py            (serves http://127.0.0.1:8000)
      python3 server.py 8080       (custom port)
      PORT=10000 python3 server.py (Render-style: binds 0.0.0.0:$PORT)

When the PORT environment variable is set (Render, Heroku, ...), the
server binds 0.0.0.0 on that port; otherwise it binds 127.0.0.1 locally.

Two ways to check a claim:
- "Check freshness" — deterministic date analysis, no network, no key.
- "Re-verify with live web (Tavily)" — fetches live sources via the
  Tavily Search API and re-runs the same deterministic analysis on
  them. Needs TAVILY_API_KEY in the environment; without it the button
  reports honestly that re-verification is not configured. The verdict
  is always computed by analyzer.py — Tavily only supplies evidence.

No data is stored; everything is analysed in memory per request.
"""
import html
import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import tavily
from analyzer import analyze
from samples import SAMPLES

COLORS = {"FRESH": "#1a7f37", "CHECK": "#9a6700", "STALE": "#cf222e", "UNKNOWN": "#57606a"}

TAVILY_ERROR_TEXT = {
    "no_api_key": "Live re-verification is not configured: no Tavily API key "
                  "(set the TAVILY_API_KEY environment variable).",
    "empty_claim": "Nothing to re-verify: the claim is empty.",
    "network": "Live re-verification failed: could not reach Tavily "
               "(network error). The offline verdict above still stands.",
    "bad_response": "Live re-verification failed: Tavily returned an "
                    "unexpected response. The offline verdict above still stands.",
}


def tavily_error_text(error):
    if error in TAVILY_ERROR_TEXT:
        return TAVILY_ERROR_TEXT[error]
    if error.startswith("http_"):
        return (f"Live re-verification failed: Tavily returned HTTP "
                f"{error[5:]}. The offline verdict above still stands.")
    return f"Live re-verification failed ({error})."


def result_block(result, reverify_form=False):
    color = COLORS[result["verdict"]]
    rows = "".join(
        f"<tr><td>{html.escape(s['title'])}</td>"
        f"<td>{html.escape(s['url'])}</td>"
        f"<td>{html.escape(s['date'] or 'no date')}</td></tr>"
        for s in result["sources"])
    button = ""
    if reverify_form:
        src = (result.get("sources") or [{}])[0]
        button = """
        <form method="post" action="/reverify">
          <input type="hidden" name="claim" value="{claim}">
          <input type="hidden" name="claim_date" value="{claim_date}">
          <input type="hidden" name="s1_title" value="{s1_title}">
          <input type="hidden" name="s1_url" value="{s1_url}">
          <input type="hidden" name="s1_date" value="{s1_date}">
          <p><button type="submit">Re-verify with live web (Tavily)</button></p>
        </form>""".format(
            claim=html.escape(result.get("_claim", ""), quote=True),
            claim_date=html.escape(result.get("_claim_date", ""), quote=True),
            s1_title=html.escape(src.get("title", ""), quote=True),
            s1_url=html.escape(src.get("url", ""), quote=True),
            s1_date=html.escape(src.get("date", "") or "", quote=True))
    return f"""
        <h2>Result</h2>
        <p><span style="background:{color};color:#fff;padding:4px 10px;border-radius:6px;">
        {result['verdict']}</span> &nbsp; confidence {result['confidence']}%</p>
        <p>{html.escape(result['explanation'])}</p>
        <p>Claim date: {result['claim_date'] or 'none'} &nbsp;|&nbsp;
           Newest source: {result['newest_source_date'] or 'none'} &nbsp;|&nbsp;
           Claim age: {result['claim_age_days']} days &nbsp;|&nbsp;
           Newer source exists: {result['newer_source_exists']}</p>
        <table border="1" cellpadding="6"><tr><th>Source</th><th>URL</th><th>Date</th></tr>{rows}</table>
        <p><em>This verdict is about evidence freshness only. It does not
        prove the claim true or false.</em></p>{button}"""


def page(result=None, form=None, reverify=None, tavily_on=False):
    form = form or {}
    sample_buttons = "".join(
        f'<button type="submit" name="sample" value="{s["id"]}">{html.escape(s["label"])}</button> '
        for s in SAMPLES)
    result_html = ""
    if result:
        result_html = result_block(result, reverify_form=True)
    reverify_html = ""
    if reverify is not None:
        if reverify.get("ok"):
            live = reverify["result"]
            reverify_html = (
                "<h2>Live re-verification (Tavily)</h2>"
                f"<p>Checked the live web just now: {reverify['raw_count']} "
                f"source(s) returned, {reverify['dated']} with a usable date. "
                "The verdict below is computed from those live sources by the "
                "same deterministic rules as the offline check.</p>"
                + result_block(live, reverify_form=False))
        else:
            reverify_html = (
                "<h2>Live re-verification (Tavily)</h2>"
                f"<p>{html.escape(tavily_error_text(reverify['error']))}</p>")
    tavily_note = ("Live re-verify via Tavily: <b>enabled</b>."
                   if tavily_on else
                   "Live re-verify via Tavily: <b>not configured</b> "
                   "(no TAVILY_API_KEY in the environment).")
    return f"""<!doctype html><html><head><meta charset="utf-8">
    <title>FreshCheck — Stale-Answer Detector</title></head><body>
    <h1>FreshCheck — Stale-Answer Detector</h1>
    <p>Paste an answer and its sources with dates. FreshCheck flags whether
    the evidence looks current, or whether the answer should be re-checked
    before you reuse it. No AI model, no data stored.</p>
    <p>{tavily_note}</p>
    <form method="post" action="/check">
      <p>Answer / claim:<br><textarea name="claim" rows="3" cols="70">{html.escape(form.get('claim', ''))}</textarea></p>
      <p>Claim date (e.g. 2024-01-15):<br><input name="claim_date" size="30" value="{html.escape(form.get('claim_date', ''))}"></p>
      <p>Source 1 title:<br><input name="s1_title" size="70" value="{html.escape(form.get('s1_title', ''))}"></p>
      <p>Source 1 URL:<br><input name="s1_url" size="70" value="{html.escape(form.get('s1_url', ''))}"></p>
      <p>Source 1 date:<br><input name="s1_date" size="30" value="{html.escape(form.get('s1_date', ''))}"></p>
      <p><button type="submit">Check freshness</button></p>
    </form>
    <h2>Try a sample (no typing needed)</h2>
    <form method="post" action="/sample">{sample_buttons}</form>
    {result_html}
    {reverify_html}
    <hr><p>Geek Room Global AI Hackathon prototype — solo, Umar Shareef.
    Deterministic date analysis only; see README for honest limitations.</p>
    </body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send(json.dumps({
                "ok": True,
                "today": date.today().isoformat(),
                "tavily": bool(os.environ.get("TAVILY_API_KEY")),
            }), "application/json")
        else:
            self._send(page(tavily_on=bool(os.environ.get("TAVILY_API_KEY"))))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(length).decode())
        get = lambda k: fields.get(k, [""])[0]
        key_on = bool(os.environ.get("TAVILY_API_KEY"))
        if self.path == "/sample":
            sample = next((s for s in SAMPLES if s["id"] == get("sample")), SAMPLES[0])
            result = analyze(sample["claim"], sample["claim_date"], sample["sources"])
            result["_claim"] = sample["claim"]
            result["_claim_date"] = sample["claim_date"]
            self._send(page(result, {"claim": sample["claim"],
                                     "claim_date": sample["claim_date"]},
                            tavily_on=key_on))
            return
        if self.path == "/reverify":
            claim, claim_date = get("claim"), get("claim_date")
            outcome = tavily.reverify(claim, api_key=os.environ.get("TAVILY_API_KEY"))
            if outcome.get("ok"):
                live = analyze(claim, claim_date, outcome["sources"])
                reverify = {"ok": True, "result": live,
                           "raw_count": outcome["raw_count"],
                           "dated": outcome["dated"]}
            else:
                reverify = {"ok": False, "error": outcome["error"]}
            # Keep the offline verdict visible alongside the live one.
            offline_sources = [{"title": get("s1_title"), "url": get("s1_url"),
                                "date_text": get("s1_date")}]
            offline = analyze(claim, claim_date, offline_sources)
            offline["_claim"] = claim
            offline["_claim_date"] = claim_date
            self._send(page(offline, {"claim": claim, "claim_date": claim_date,
                                      "s1_title": get("s1_title"),
                                      "s1_url": get("s1_url"),
                                      "s1_date": get("s1_date")},
                            reverify=reverify, tavily_on=key_on))
            return
        sources = [{"title": get("s1_title"), "url": get("s1_url"),
                    "date_text": get("s1_date")}]
        result = analyze(get("claim"), get("claim_date"), sources)
        result["_claim"] = get("claim")
        result["_claim_date"] = get("claim_date")
        self._send(page(result, {"claim": get("claim"), "claim_date": get("claim_date"),
                                 "s1_title": get("s1_title"), "s1_url": get("s1_url"),
                                 "s1_date": get("s1_date")}, tavily_on=key_on))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    # Render/Heroku-style hosts set PORT; bind 0.0.0.0 there so the
    # platform can reach the service. Locally, stay on 127.0.0.1.
    if "PORT" in os.environ:
        port = int(os.environ["PORT"])
        host = "0.0.0.0"
    else:
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
        host = "127.0.0.1"
    print(f"FreshCheck on http://{host}:{port}  (Ctrl+C to stop)")
    HTTPServer((host, port), Handler).serve_forever()
