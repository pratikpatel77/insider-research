"""Definedge Securities (Integrate API). Endpoints and fields follow the official docs and the pyintegrate client:
https://www.definedgesecurities.com/api-documentation/  and  https://github.com/Definedge-Securities/pyintegrate

Since 31 Mar 2026 SEBI rules make `algo_id` mandatory on placeorder: put yours in DEFINEDGE_ALGO_ID.
Run `python selftest.py --broker definedge` once to check the field mapping on your account before going live."""
import csv, io, os, time, zipfile

import requests

import config
from .base import Broker, BrokerError, LIMIT, MARKET, SL_LIMIT, OPEN, COMPLETE, REJECTED, CANCELLED, num

AUTH = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc"
BASE = "https://integrate.definedgesecurities.com/dart/v1"
MASTER = "https://app.definedgesecurities.com/public/allmaster.zip"
MASTER_COLS = ["segment", "token", "symbol", "trading_symbol", "instrument_type", "expiry", "tick_size", "lot_size",
               "option_type", "strike", "isin", "price_mult"]
PRICE_TYPE = {LIMIT: "LIMIT", MARKET: "MARKET", SL_LIMIT: "SL-LIMIT"}
STATUS = {"COMPLETE": COMPLETE, "REJECTED": REJECTED, "CANCELED": CANCELLED, "CANCELLED": CANCELLED}


class Definedge(Broker):
    name = "definedge"

    def __init__(self, env):
        self.token, self.secret = env.get("DEFINEDGE_API_TOKEN", ""), env.get("DEFINEDGE_API_SECRET", "")
        self.totp = env.get("DEFINEDGE_TOTP_SECRET", "").strip()
        self.algo_id = env.get("DEFINEDGE_ALGO_ID", "").strip()
        if not (self.token and self.secret and self.totp):
            raise BrokerError("Definedge: set DEFINEDGE_API_TOKEN, DEFINEDGE_API_SECRET and DEFINEDGE_TOTP_SECRET in trader/.env")
        self.key, self.sym_map, self.s = None, None, requests.Session()

    # ---- session
    def login(self, **kw):
        import pyotp
        r1 = self.s.get(f"{AUTH}/login/{self.token}", headers={"api_secret": self.secret}, timeout=15)
        r1.raise_for_status()
        r2 = self.s.post(f"{AUTH}/token", json={"otp_token": r1.json()["otp_token"], "otp": pyotp.TOTP(self.totp).now()}, timeout=15)
        r2.raise_for_status()
        self.key = r2.json().get("api_session_key")
        if not self.key:
            raise BrokerError(f"Definedge login failed: {r2.text[:200]}")

    def logged_in(self):
        return bool(self.key)

    def _call(self, method, path, **kw):
        if not self.key:
            raise BrokerError("Definedge: not logged in")
        r = self.s.request(method, f"{BASE}/{path}", headers={"Authorization": self.key}, timeout=20, **kw)
        try:
            data = r.json()
        except ValueError:
            raise BrokerError(f"Definedge {path}: HTTP {r.status_code} {r.text[:200]}")
        if r.status_code == 401 or (isinstance(data, dict) and str(data.get("status", "")).upper() == "ERROR"):
            raise BrokerError(f"Definedge {path}: {str(data)[:300]}")
        return data

    # ---- symbols
    def _master(self):
        if self.sym_map is None:
            cache = config.DATA / "definedge_master.csv"
            if not cache.exists() or time.time() - cache.stat().st_mtime > 86400:
                b = requests.get(MASTER, timeout=60).content
                z = zipfile.ZipFile(io.BytesIO(b))
                cache.write_bytes(z.read(z.namelist()[0]))
            m = {}
            with open(cache, encoding="utf-8", errors="ignore", newline="") as f:
                for row in csv.reader(f):
                    if len(row) >= 5 and row[0] == "NSE" and row[3].endswith("-EQ"):
                        m[row[3][:-3]] = (row[1], row[3])            # symbol -> (token, trading_symbol)
            if not m:
                raise BrokerError("Definedge symbol master had no NSE equity rows")
            self.sym_map = m
        return self.sym_map

    def _sym(self, sym):
        try:
            return self._master()[sym]
        except KeyError:
            raise BrokerError(f"{sym} not found in the Definedge NSE equity master")

    # ---- market data and orders
    def ltp(self, sym):
        token, _ = self._sym(sym)
        px = num(self._call("GET", f"quotes/NSE/{token}").get("ltp"))
        if px <= 0:
            raise BrokerError(f"Definedge returned no price for {sym}")
        return px

    def place(self, sym, side, qty, kind, price=0.0, trigger=0.0, tag=""):
        if not self.algo_id:
            raise BrokerError("Definedge: DEFINEDGE_ALGO_ID is not set in trader/.env (mandatory for API orders)")
        _, ts = self._sym(sym)
        body = {"exchange": "NSE", "order_type": side, "price": f"{price:.2f}" if kind != MARKET else "0",
                "price_type": PRICE_TYPE[kind], "product_type": "CNC", "quantity": str(int(qty)), "tradingsymbol": ts,
                "algo_id": self.algo_id, "validity": "DAY", "remarks": (tag or "insider-trader")[:20]}
        if kind == SL_LIMIT:
            body["trigger_price"] = f"{trigger:.2f}"
        d = self._call("POST", "placeorder", json=body)
        if str(d.get("status", "")).upper() != "SUCCESS" or not d.get("order_id"):
            raise BrokerError(f"Definedge rejected the order: {str(d)[:300]}")
        return str(d["order_id"])

    def order(self, oid):
        d = self._call("GET", "orders")
        rows = d.get("orders", d.get("data", [])) if isinstance(d, dict) else d
        for o in rows:
            if str(o.get("order_id")) == str(oid):
                st = STATUS.get(str(o.get("order_status", "")).upper(), OPEN)
                filled = int(num(o.get("filled_qty")))
                avg = next((num(o[k]) for k in ("average_price", "avg_price", "averageprice", "fill_price", "avgprc") if o.get(k)), 0.0)
                if filled and not avg and st == COMPLETE:
                    avg = num(o.get("price"))
                return dict(status=st, filled=filled, qty=filled + int(num(o.get("pending_qty"))), avg=avg,
                            msg=str(o.get("rejection_reason") or o.get("remarks") or ""))
        raise BrokerError(f"Definedge: order {oid} not in the order book")

    def cancel(self, oid):
        d = self._call("GET", f"cancel/{oid}")
        return str(d.get("status", "")).upper() == "SUCCESS"

    def funds(self):
        d = self._call("GET", "limits")
        d = d if isinstance(d, dict) else {}
        for k in ("cash", "available_cash", "cash_available", "net_available_margin", "available_margin", "cash_balance", "net", "opening_balance"):
            if d.get(k) not in (None, ""):
                return num(d[k])
        return None

    def raw_dump(self, sym="TCS"):
        return {"quote": self._call("GET", f"quotes/NSE/{self._sym(sym)[0]}"), "orders": self._call("GET", "orders"),
                "holdings": self._call("GET", "holdings"), "limits": self._call("GET", "limits")}
