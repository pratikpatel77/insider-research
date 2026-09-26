"""Paper broker: fills orders against real NSE last prices (or an injected price function in tests).
No account, no login, no money. Orders and fills are kept in data/paper_orders.json so a restart doesn't lose them."""
import json, os, threading, time

import config
from .base import Broker, BrokerError, LIMIT, MARKET, SL_LIMIT, OPEN, COMPLETE, CANCELLED, REJECTED


QUOTE_URL = "https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolData&marketType=N&series=EQ&symbol={}"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}.NS?interval=1d&range=1d"


class NSEData:
    """Last price and tick size for an NSE stock from NSE's public quote page (Yahoo as a price fallback).
    Used by the paper broker for prices and by every mode for tick sizes (a price that is not a multiple of the tick is rejected)."""

    def __init__(self):
        self._nse, self._lock, self._cache = None, threading.Lock(), {}

    def _nse_quote(self, sym):
        import nse_live
        for attempt in (0, 1):
            with self._lock:
                if self._nse is None or attempt:
                    self._nse = nse_live.NSE()                    # (re)creates the session and its cookies
                r = self._nse.s.get(QUOTE_URL.format(sym), timeout=15)
            if r.status_code == 200:
                e = r.json()["equityResponse"][0]
                px = float(e["tradeInfo"]["lastPrice"] or 0)
                tick = float(e["priceInfo"].get("tickSize") or 0.05)
                if px > 0:
                    return px, tick
        raise BrokerError(f"NSE quote unavailable for {sym}")

    def _yahoo(self, sym):
        import requests
        r = requests.get(YAHOO_URL.format(sym), headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        px = float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
        if px <= 0:
            raise BrokerError(f"No price for {sym}")
        return px

    def quote(self, sym):
        hit = self._cache.get(sym)
        if hit and time.time() - hit[0] < 5:
            return hit[1], hit[2]
        try:
            px, tick = self._nse_quote(sym)
        except Exception:
            try:
                px, tick = self._yahoo(sym), (self._cache.get(sym) or (0, 0, 0.05))[2]
            except Exception as e:
                raise BrokerError(f"No price for {sym}: {e}")
        self._cache[sym] = (time.time(), px, tick)
        return px, tick

    def ltp(self, sym):
        return self.quote(sym)[0]

    def tick(self, sym):
        return self.quote(sym)[1]


NSEDATA = NSEData()


class PaperBroker(Broker):
    name, is_paper = "paper", True

    def __init__(self, price_fn=None, path=None):
        self.price_fn = price_fn or NSEDATA.ltp
        self.path = path if path is not None else config.DATA / "paper_orders.json"
        self.orders, self.seq, self.lock = {}, 0, threading.RLock()
        if self.path and os.path.exists(self.path):
            try:
                d = json.load(open(self.path, encoding="utf-8"))
                self.orders, self.seq = d["orders"], d["seq"]
            except (OSError, ValueError, KeyError):
                pass

    def login(self, **kw):
        return None

    def ltp(self, sym):
        return float(self.price_fn(sym))

    def _save(self):
        if self.path:
            tmp = str(self.path) + ".tmp"
            json.dump({"orders": self.orders, "seq": self.seq}, open(tmp, "w", encoding="utf-8"))
            os.replace(tmp, self.path)

    def place(self, sym, side, qty, kind, price=0.0, trigger=0.0, tag=""):
        with self.lock:
            if qty < 1:
                raise BrokerError("quantity must be at least 1")
            self.seq += 1
            oid = f"P{self.seq:06d}"
            self.orders[oid] = dict(sym=sym, side=side, qty=int(qty), kind=kind, price=float(price), trigger=float(trigger),
                                    status=OPEN, filled=0, avg=0.0, msg="")
            self._match(oid)
            self._save()
            return oid

    def _match(self, oid):
        o = self.orders[oid]
        if o["status"] != OPEN:
            return
        px = self.ltp(o["sym"])
        fill = None
        if o["kind"] == MARKET:
            fill = px
        elif o["kind"] == LIMIT:
            if (o["side"] == "BUY" and px <= o["price"]) or (o["side"] == "SELL" and px >= o["price"]):
                fill = px
        elif o["kind"] == SL_LIMIT and o["side"] == "SELL" and px <= o["trigger"]:
            if px >= o["price"]:                              # triggered, and the limit is still reachable
                fill = px
            # else: the price gapped through the limit; the order stays open, exactly like a real stop-limit
        if fill is not None:
            o.update(status=COMPLETE, filled=o["qty"], avg=fill)

    def order(self, oid):
        with self.lock:
            if oid not in self.orders:
                raise BrokerError(f"unknown paper order {oid}")
            self._match(oid)
            self._save()
            o = self.orders[oid]
            return dict(status=o["status"], filled=o["filled"], qty=o["qty"], avg=o["avg"], msg=o["msg"])

    def cancel(self, oid):
        with self.lock:
            o = self.orders.get(oid)
            if o and o["status"] == OPEN:
                o["status"] = CANCELLED
                self._save()
                return True
            return False
