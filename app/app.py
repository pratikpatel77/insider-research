"""Insider Buy Screener: a local web app. Double-click "Start Insider Screener.bat" to run.

Fetches NSE insider filings and prices live and applies the tested rules. The raw NSE data
(filings, daily prices) is never written to disk. The one thing that is saved is the finished
watchlist, in ".scan_cache.json" next to this file, so reopening the app later today shows it
instantly instead of re-scanning. That file is overwritten by the next scan and ignored once
it's from an earlier day.
"""
import datetime as dt
import io, json, math, os, socket, threading, traceback, warnings, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pandas as pd

import engine, nse_live
from ui import PAGE

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
STATE = {"running": False, "msg": "Ready", "pct": 0, "error": None, "result": None}
PRICES, FILINGS = nse_live.PriceCache(), nse_live.FilingCache()
LOCK = threading.Lock()
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".scan_cache.json")


def progress(msg, pct):
    STATE["msg"], STATE["pct"] = msg, max(STATE["pct"], int(pct))


def scan():
    try:
        STATE.update(running=True, error=None, pct=0, msg="Starting")
        STATE["result"] = engine.run_scan(progress, PRICES, FILINGS)
        save_cache(STATE["result"])
    except Exception as e:  # shown to the user in the page
        traceback.print_exc()
        STATE["error"] = str(e) or e.__class__.__name__
    finally:
        STATE["running"] = False


def to_json(o):
    if o is pd.NaT:
        return None
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime("%d %b %Y, %H:%M") if (o.hour or o.minute) else o.strftime("%d %b %Y")
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (set,)):
        return sorted(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def clean_nans(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: clean_nans(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean_nans(v) for v in x]
    return x


def save_cache(r):
    """Write only the finished watchlist to disk (never the raw NSE downloads), so a later reopen
    today can skip the wait. Failing to write is never fatal - the app just re-scans next time."""
    try:
        payload = {"signals": r["signals"], "near": r["near"], "meta": r["meta"],
                   "tx": r["tx"].to_dict("records"), "other": r["other"].to_dict("records")}
        payload = clean_nans(json.loads(json.dumps(payload, default=to_json)))
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, CACHE_FILE)
    except OSError:
        pass


def load_cache():
    """Return today's cached scan, or None if there isn't one - a cache from an earlier day is
    never used automatically, so the watchlist can't go stale without you noticing."""
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        d = json.load(open(CACHE_FILE, encoding="utf-8"))
        if not str(d.get("meta", {}).get("run_at", "")).startswith(dt.date.today().strftime("%d %b %Y")):
            return None
        return {"signals": d["signals"], "near": d["near"], "meta": d["meta"],
                "tx": pd.DataFrame(d["tx"]), "other": pd.DataFrame(d["other"])}
    except (OSError, ValueError, KeyError):
        return None


def _parse_disp(v):
    """Undo to_json's "DD Mon YYYY[, HH:MM]" display formatting. A freshly-scanned result still
    holds real Timestamp/date objects and passes straight through; only a cache-loaded result
    needs this. Bulk pd.to_datetime() guesses one format for the whole column and breaks on
    mixed values (e.g. "15 Jun 2026" vs "5 Jun 2026"), so each value is parsed on its own."""
    if not isinstance(v, str):
        return v
    for fmt in ("%d %b %Y, %H:%M", "%d %b %Y"):
        try:
            return pd.to_datetime(v, format=fmt)
        except ValueError:
            continue
    return pd.NaT


def excel_bytes(res):
    sig = pd.DataFrame([{
        "Symbol": r["sym"], "Company": r["company"], "Insider group": ", ".join(r["groups"]),
        "Who bought (category): holding before -> after": " | ".join(f"{p['name']} ({p['cat']}): {p['before']:.2f}% -> {p['after']:.2f}%" for p in r["people"]),
        "First trade": r["first_trade"], "Last trade": r["last_trade"], "First disclosed": r["first_disclosed"], "Last disclosed": r["last_disclosed"],
        "Filings": r["filings"], "Shares bought": r["shares"], "Value (Rs cr)": round(r["value_cr"], 2), "Avg buy price": round(r["avg_price"], 2),
        "Own holding increase %": round(r["own_incr"], 1), "% of company bought": r["pct_company"], "Mcap (Rs cr)": r["mcap_cr"],
        "Last close": r["close"], "Close vs insider price %": r["vs_insider"], "From 52w high %": r["from_high"],
        "Median daily value (Rs cr)": r["liq_cr"], "Sessions left": r["sessions_left"], "Exit warning": r["exit_detail"],
        "Notes": "; ".join(r["notes"])} for r in res["signals"]])
    for c in ["First trade", "Last trade"]:
        if c in sig: sig[c] = pd.to_datetime(sig[c].map(_parse_disp)).dt.date
    for c in ["First disclosed", "Last disclosed"]:
        if c in sig: sig[c] = pd.to_datetime(sig[c].map(_parse_disp)).dt.strftime("%Y-%m-%d %H:%M")
    near = pd.DataFrame(res["near"])
    if len(near): near["disclosed"] = pd.to_datetime(near.disclosed.map(_parse_disp)).dt.strftime("%Y-%m-%d")
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        sig.to_excel(w, "Watchlist", index=False)
        res["tx"].to_excel(w, "Signal transactions", index=False)
        res["other"].to_excel(w, "Other insider filings", index=False)
        near.to_excel(w, "Big buys not qualifying", index=False)
        pd.DataFrame({"Rule": [
            "Buy + Market Purchase of equity (NSE PIT Reg 7(2) filing)",
            "Buyer is an individual promoter / promoter group / relative / director / KMP (not a company, LLP, trust or fund)",
            "Shares bought >= 5% of the buyer(s)' prior holding",
            "Market cap <= Rs 10,000 cr",
            "EQ series, median daily value >= Rs 1 cr (60 sessions), traded >= 95% of days, <= 2 circuit hits in 20 sessions, price >= Rs 10",
            "No promoter-side market sale in prior 180 days (director/KMP signals: no insider sale in prior 90 days)",
            "Watch for 120 sessions from disclosure; a new qualifying buy restarts it; an insider sale afterwards = exit warning"]}).to_excel(w, "Rules", index=False)
    return bio.getvalue()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/status":
            s = {k: STATE[k] for k in ("running", "msg", "pct", "error")}
            s["has_result"] = STATE["result"] is not None
            return self._send(200, json.dumps(s))
        if self.path == "/api/result":
            r = STATE["result"]
            if r is None:
                return self._send(404, json.dumps({"error": "No scan yet"}))
            payload = clean_nans(json.loads(json.dumps({"signals": r["signals"], "near": r["near"], "meta": r["meta"]}, default=to_json)))
            return self._send(200, json.dumps(payload))
        if self.path == "/api/excel":
            r = STATE["result"]
            if r is None:
                return self._send(404, json.dumps({"error": "Run a scan first"}))
            name = f"Insider_Watchlist_{pd.Timestamp.now():%Y-%m-%d}.xlsx"
            return self._send(200, excel_bytes(r), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              {"Content-Disposition": f'attachment; filename="{name}"'})
        self._send(404, json.dumps({"error": "Not found"}))

    def do_POST(self):
        if self.path == "/api/scan":
            with LOCK:
                if not STATE["running"]:
                    STATE["running"] = True
                    threading.Thread(target=scan, daemon=True).start()
            return self._send(202, json.dumps({"started": True}))
        self._send(404, json.dumps({"error": "Not found"}))


def free_port(start=8741):
    for p in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 0


if __name__ == "__main__":
    cached = load_cache()
    if cached:
        STATE["result"] = cached
        print("  Loaded today's earlier scan from cache - open the app to see it right away.", flush=True)
    port = free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}/"
    print("\n  Insider Buy Screener is running at", url, flush=True)
    print("  Keep this window open while you use it. Close it to stop the app.\n", flush=True)
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
