"""FreshCheck demo server — Python standard library only, no pip packages.

Run:  python3 server.py            (serves http://127.0.0.1:8000)
      python3 server.py 8080       (custom port)
No API key, no network call, no database. Data is entered in the form
and analysed in memory; nothing is stored.
"""
import html
import json
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from analyzer import analyze
from samples import SAMPLES

COLORS = {"FRESH": "#1a7f37", "CHECK": "#9a6700", "STALE": "#cf222e", "UNKNOWN": "#57606a"}


def page(result=None, form=None):
    form = form or {}
    sample_buttons = "".join(
        f'<button type="submit" name="sample" value="{s["id"]}">{html.escape(s["label"])}</button> '
        for s in SAMPLES)
    result_html = ""
    if result:
        color = COLORS[result["verdict"]]
        rows = "".join(
            f"<tr><td>{html.escape(s['title'])}</td>"
            f"<td>{html.escape(s['url'])}</td>"
            f"<td>{html.escape(s['date'] or 'no date')}</td></tr>"
            for s in result["sources"])
        result_html = f"""
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
        prove the claim true or false.</em></p>"""
    return f"""<!doctype html><html><head><meta charset="utf-8">
    <title>FreshCheck — Stale-Answer Detector</title></head><body>
    <h1>FreshCheck — Stale-Answer Detector</h1>
    <p>Paste an answer and its sources with dates. FreshCheck flags whether
    the evidence looks current, or whether the answer should be re-checked
    before you reuse it. No AI model, no API key, no data stored.</p>
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
            self._send(json.dumps({"ok": True, "today": date.today().isoformat()}),
                       "application/json")
        else:
            self._send(page())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(length).decode())
        get = lambda k: fields.get(k, [""])[0]
        if self.path == "/sample":
            sample = next((s for s in SAMPLES if s["id"] == get("sample")), SAMPLES[0])
            result = analyze(sample["claim"], sample["claim_date"], sample["sources"])
            self._send(page(result, {"claim": sample["claim"],
                                     "claim_date": sample["claim_date"]}))
            return
        sources = [{"title": get("s1_title"), "url": get("s1_url"),
                    "date_text": get("s1_date")}]
        result = analyze(get("claim"), get("claim_date"), sources)
        self._send(page(result, {"claim": get("claim"), "claim_date": get("claim_date"),
                                 "s1_title": get("s1_title"), "s1_url": get("s1_url"),
                                 "s1_date": get("s1_date")}))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"FreshCheck on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
