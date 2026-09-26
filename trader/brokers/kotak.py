"""Kotak Neo (neo-api-client). Order codes: exchange nse_cm, product CNC, order type L / MKT / SL, side B / S.
Run `python selftest.py --broker kotak` once to check the field mapping on your account before going live."""
from .base import Broker, BrokerError, LIMIT, MARKET, SL_LIMIT, OPEN, COMPLETE, REJECTED, CANCELLED, num

KIND = {LIMIT: "L", MARKET: "MKT", SL_LIMIT: "SL"}


class Kotak(Broker):
    name = "kotak"

    def __init__(self, env):
        self.key, self.mobile, self.ucc = env.get("KOTAK_NEO_CONSUMER_KEY", ""), env.get("KOTAK_NEO_MOBILE_NUMBER", ""), env.get("KOTAK_NEO_UCC", "")
        self.mpin, self.totp = env.get("KOTAK_NEO_MPIN", ""), env.get("KOTAK_NEO_TOTP_SECRET", "").strip()
        self.env_name = env.get("KOTAK_NEO_ENV", "prod")
        missing = [n for n, v in [("KOTAK_NEO_CONSUMER_KEY", self.key), ("KOTAK_NEO_MOBILE_NUMBER", self.mobile), ("KOTAK_NEO_UCC", self.ucc),
                                  ("KOTAK_NEO_MPIN", self.mpin)] if not v]
        if missing:
            raise BrokerError("Kotak: set " + ", ".join(missing) + " in trader/.env")
        self.auto_login = bool(self.totp)          # without the TOTP seed, the dashboard asks for the 6-digit code each day
        self.client, self.tokens = None, {}

    def login(self, totp=None, **kw):
        try:
            from neo_api_client import NeoAPI
        except ImportError:
            raise BrokerError("Kotak: run  pip install neo-api-client")
        if self.totp:
            import pyotp
            code = pyotp.TOTP(self.totp).now()
        else:
            code = str(totp or "").strip()
            if not (code.isdigit() and len(code) == 6):
                raise BrokerError("Kotak: enter the 6-digit code from your authenticator app")
        c = NeoAPI(consumer_key=self.key, environment=self.env_name)
        r1 = c.totp_login(mobile_number=self.mobile, ucc=self.ucc, totp=code)
        if "error" in r1:
            raise BrokerError(f"Kotak TOTP login failed: {r1}")
        r2 = c.totp_validate(mpin=self.mpin)
        if "error" in r2:
            raise BrokerError(f"Kotak MPIN validation failed: {r2}")
        self.client = c

    def logged_in(self):
        return self.client is not None

    def _c(self):
        if not self.client:
            raise BrokerError("Kotak: not logged in")
        return self.client

    def _token(self, sym):
        if sym not in self.tokens:
            res = self._c().search_scrip(exchange_segment="nse_cm", symbol=sym)
            rows = res if isinstance(res, list) else (res or {}).get("data", [])
            best = next((r for r in rows if str(r.get("pTrdSymbol", "")).upper() == f"{sym}-EQ".upper()), None) \
                or next((r for r in rows if str(r.get("pGroup", "")).upper() == "EQ" and str(r.get("pSymbolName", "")).upper() == sym.upper()), None)
            if not best:
                raise BrokerError(f"Kotak: {sym} not found on NSE cash")
            self.tokens[sym] = (str(best["pSymbol"]), str(best.get("pTrdSymbol") or f"{sym}-EQ"))
        return self.tokens[sym]

    def ltp(self, sym):
        tok, _ = self._token(sym)
        res = self._c().quotes(instrument_tokens=[{"instrument_token": tok, "exchange_segment": "nse_cm"}], quote_type="all")
        rows = res if isinstance(res, list) else (res or {}).get("message", (res or {}).get("data", []))
        px = num((rows[0] if rows else {}).get("ltp") or (rows[0] if rows else {}).get("last_traded_price"))
        if px <= 0:
            raise BrokerError(f"Kotak returned no price for {sym}: {str(res)[:200]}")
        return px

    def place(self, sym, side, qty, kind, price=0.0, trigger=0.0, tag=""):
        _, ts = self._token(sym)
        r = self._c().place_order(exchange_segment="nse_cm", product="CNC", price=f"{price:.2f}" if kind != MARKET else "0",
                                  order_type=KIND[kind], quantity=str(int(qty)), validity="DAY", trading_symbol=ts,
                                  transaction_type="B" if side == "BUY" else "S", amo="NO",
                                  trigger_price=f"{trigger:.2f}" if kind == SL_LIMIT else "0", tag=(tag or "insider")[:20])
        oid = (r or {}).get("nOrdNo")
        if not oid:
            raise BrokerError(f"Kotak rejected the order: {str(r)[:300]}")
        return str(oid)

    def order(self, oid):
        res = self._c().order_report()
        for o in (res or {}).get("data", []) or []:
            if str(o.get("nOrdNo")) == str(oid):
                s = str(o.get("ordSt", "")).lower()
                st = COMPLETE if s in ("complete", "traded") else REJECTED if s == "rejected" else CANCELLED if s in ("cancelled", "canceled") else OPEN
                filled = int(num(o.get("fldQty")))
                return dict(status=st, filled=filled, qty=filled + int(num(o.get("unFldSz"))), avg=num(o.get("avgPrc")),
                            msg=str(o.get("rejRsn") or ""))
        raise BrokerError(f"Kotak: order {oid} not in the order book")

    def cancel(self, oid):
        r = self._c().cancel_order(order_id=str(oid))
        return "error" not in (r or {}) and "Error" not in (r or {})

    def funds(self):
        d = self._c().limits()
        d = d if isinstance(d, dict) else {}
        for k in ("Net", "CashAvailable", "AvailableCash", "net", "NetAvailableMargin", "AvailableMargin"):
            if d.get(k) not in (None, ""):
                return num(d[k])
        return None

    def raw_dump(self, sym="TCS"):
        c = self._c()
        return {"scrip": self._token(sym), "quote": c.quotes(instrument_tokens=[{"instrument_token": self._token(sym)[0], "exchange_segment": "nse_cm"}],
                                                              quote_type="all"), "order_report": c.order_report(), "limits": c.limits()}
