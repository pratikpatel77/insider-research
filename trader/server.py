"""Local dashboard + JSON API on http://127.0.0.1:8760 . Only this computer can reach it."""
import json, math, threading, time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
from core import UserError
from dashboard_page import PAGE

PORT = 8760


class Api:
    def __init__(self, trader, scheduler):
        self.tr, self.sched = trader, scheduler
        self.pool, self.px, self.wanted, self.active, self.wake = ThreadPoolExecutor(6), {}, set(), None, threading.Event()
        self.funds = None
        threading.Thread(target=self._refresh_loop, daemon=True, name="prices").start()

    # ---------------------------------------------------------------- prices (refreshed in the background so the page never waits)
    def _refresh_loop(self):
        while True:
            try:
                b = self.active
                if b is not None and b.logged_in():
                    def get(s):
                        try:
                            return s, b.ltp(s)
                        except Exception:
                            return s, None
                    for s, px in self.pool.map(get, sorted(self.wanted)):
                        if px is not None or s not in self.px:
                            self.px[s] = px
            except Exception:
                pass
            try:
                self.funds = self.tr.available_funds()
            except Exception:
                self.funds = None
            self.wake.wait(15)
            self.wake.clear()

    # ---------------------------------------------------------------- state for the page
    def state(self):
        tr = self.tr
        err, sel = None, None
        try:
            sel = tr.selected_broker()
        except Exception as e:                       # e.g. credentials missing from .env
            err = str(e)
        active = sel if tr.mode == "live" else tr.get_broker()
        scan = tr.signals.load() or {}
        held = {p["sym"]: p for p in tr.positions("entering", "open")}
        used = {r["signal_key"] for r in tr.db.q("SELECT signal_key FROM positions WHERE status IN ('entering','open','closed') AND signal_key IS NOT NULL")}
        rejected = {r["signal_key"]: r["note"] for r in tr.db.q("SELECT signal_key, note FROM positions WHERE status='rejected' AND signal_key IS NOT NULL ORDER BY id")}
        cands = [c for c in scan.get("candidates", [])]
        want = {c["sym"] for c in cands if c["clean"]} | set(held)
        if want - self.wanted or active is not self.active:
            self.wanted, self.active = set(want), active
            self.wake.set()
        px = dict(self.px)
        band = tr.s["entry_band_pct"] / 100
        rows = []
        for c in cands:
            cap = c["avg_now"] * (1 + band) if c["avg_now"] else None
            ltp = px.get(c["sym"])
            if c["sym"] in held:
                status = "held"
            elif not c["clean"]:
                status = "not clean"
            elif c["key"] in used:
                status = "used"
            elif ltp is None:
                status = "no price"
            elif cap and ltp > cap:
                status = "above zone"
            elif c["key"] in rejected:
                status = "needs funds"
            else:
                status = "buyable"
            rows.append({k: c[k] for k in ("sym", "company", "value_cr", "avg_now", "notes", "last_disclosed", "sessions_left", "pending")}
                        | {"cap": cap, "ltp": ltp, "status": status, "reject_note": rejected.get(c["key"])})
        order = {"needs funds": 0, "buyable": 1, "above zone": 2, "no price": 3, "held": 4, "used": 5, "not clean": 6}
        rows.sort(key=lambda r: (order[r["status"]], -(r["value_cr"] or 0)))
        pos = []
        for p in tr.positions("entering", "open"):
            ltp = px.get(p["sym"])
            pos.append(p | {"ltp": ltp, "pnl_now": None if not (ltp and p["entry_price"]) else (ltp - p["entry_price"]) * p["qty"],
                            "pnl_pct": None if not (ltp and p["entry_price"]) else (ltp / p["entry_price"] - 1) * 100})
        closed = tr.db.q("SELECT * FROM positions WHERE status='closed' ORDER BY exit_time DESC LIMIT 100")
        allclosed = tr.db.one("SELECT COUNT(*) n, COALESCE(SUM(pnl),0) pnl, COALESCE(SUM(pnl>0),0) wins FROM positions WHERE status='closed'")
        scanning = tr.signals.running
        return {
            "now": tr.clock().strftime("%a %d %b %H:%M:%S"), "mode": tr.mode, "broker": tr.broker_name,
            "broker_ready": bool(sel and sel.logged_in()), "broker_error": err, "broker_auto_login": bool(sel and sel.auto_login), "live_unlocked": tr.env.get("TRADER_ALLOW_LIVE") == "1", "market_open": tr.market_open(),
            "settings": tr.s, "scan": {"at": scan.get("scanned_at"), "as_of": scan.get("as_of"), "running": scanning, "msg": tr.signals.progress_msg if scanning else "",
                                        "error": tr.signals.error},
            "candidates": rows, "positions": pos, "closed": closed, "slots_used": len(held), "funds": (tr.available_funds() if tr.get_broker().is_paper else self.funds),
            "totals": {"closed_n": allclosed["n"], "closed_pnl": allclosed["pnl"], "wins": allclosed["wins"],
                       "open_pnl": sum(p["pnl_now"] or 0 for p in pos)},
            "events": tr.db.q("SELECT ts, level, msg FROM events ORDER BY id DESC LIMIT 60"),
            "heartbeat": tr.db.get("heartbeat"),
        }

    # ---------------------------------------------------------------- actions
    def act(self, path, body):
        tr = self.tr
        if path == "/api/settings":
            tr.update_settings(body.get("changes", {}))
        elif path == "/api/buy":
            n = tr.start_buy(body.get("sym"), qty=body.get("qty") or None, amount=body.get("amount") or None, limit=body.get("limit") or None,
                             source="manual")
            return {"position": n}
        elif path == "/api/adopt":
            return {"position": tr.adopt(body.get("sym"), body.get("price"), body.get("qty"))}
        elif path == "/api/sell":
            tr.sell_now(int(body["id"]))
        elif path == "/api/scan":
            if tr.signals.running:
                raise UserError("A scan is already running")
            threading.Thread(target=self._scan, daemon=True).start()
        elif path == "/api/login":
            tr.login(totp=body.get("totp"), redirected_url=body.get("redirected_url"))
        elif path == "/api/mode":
            tr.set_mode(body.get("mode"), body.get("confirm", ""))
        elif path == "/api/broker":
            tr.set_broker(body.get("name"))
        else:
            raise UserError("Unknown action")
        return {}

    def _scan(self):
        try:
            self.tr.signals.scan()
            self.tr.db.event("info", "Scan finished")
        except Exception as e:
            self.tr.db.event("error", f"Scan failed: {e}")

    def fyers_url(self):
        b = self.tr.get_broker()
        return {"url": b.auth_url() if hasattr(b, "auth_url") else None}


def clean(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


def make_handler(api):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _host_ok(self):
            return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, "{}")
            try:
                if self.path == "/":
                    return self._send(200, PAGE, "text/html")
                if self.path == "/api/state":
                    return self._send(200, json.dumps(clean(api.state()), default=str))
                if self.path == "/api/fyers_url":
                    return self._send(200, json.dumps(api.fyers_url()))
                self._send(404, "{}")
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))

        def do_POST(self):
            # A web page on another site must not be able to place orders: require our custom header (which browsers
            # never send cross-site without a permission check this server does not grant) and a local Host.
            if not self._host_ok() or self.headers.get("X-Trader") != "1":
                return self._send(403, json.dumps({"error": "forbidden"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                self._send(200, json.dumps(clean(api.act(self.path, body)), default=str))
            except UserError as e:
                self._send(400, json.dumps({"error": str(e)}))
            except Exception as e:
                api.tr.db.event("error", f"{self.path}: {e}")
                self._send(500, json.dumps({"error": str(e) or e.__class__.__name__}))
    return H


class Server(ThreadingHTTPServer):
    allow_reuse_address = False       # on Windows the default would let a second copy silently share the port


def serve(trader, scheduler, port=PORT):
    return Server(("127.0.0.1", port), make_handler(Api(trader, scheduler)))
