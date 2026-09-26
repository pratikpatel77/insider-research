"""Fyers (fyers-apiv3). Symbols look like NSE:TCS-EQ; order types 1 limit, 2 market, 4 stop-limit; side 1 buy / -1 sell.
Fyers needs a browser login each morning: the dashboard shows a link, you log in, and paste the address you land on.
Run `python selftest.py --broker fyers` once to check the field mapping on your account before going live."""
import json, os
from urllib.parse import parse_qs, urlparse

import config
from .base import Broker, BrokerError, LIMIT, MARKET, SL_LIMIT, OPEN, COMPLETE, REJECTED, CANCELLED, num

TYPE = {LIMIT: 1, MARKET: 2, SL_LIMIT: 4}
STATUS = {1: CANCELLED, 2: COMPLETE, 5: REJECTED}          # 4 = transit, 6 = pending -> OPEN


class Fyers(Broker):
    name = "fyers"
    auto_login = False

    def __init__(self, env):
        self.app_id, self.secret, self.redirect = env.get("FYERS_APP_ID", ""), env.get("FYERS_SECRET_KEY", ""), env.get("FYERS_REDIRECT_URI", "")
        if not (self.app_id and self.secret and self.redirect):
            raise BrokerError("Fyers: set FYERS_APP_ID, FYERS_SECRET_KEY and FYERS_REDIRECT_URI in trader/.env")
        self.client, self._tok = None, config.DATA / "fyers_token.json"
        token = env.get("FYERS_ACCESS_TOKEN", "")
        if self._tok.exists():
            try:
                d = json.load(open(self._tok))
                if d.get("date") == config.now().strftime("%Y-%m-%d"):      # tokens expire daily
                    token = d["token"]
            except (OSError, ValueError, KeyError):
                pass
        if token:
            try:
                self._connect(token)
            except BrokerError:
                self.client = None

    def _model(self):
        try:
            from fyers_apiv3 import fyersModel
        except ImportError:
            raise BrokerError("Fyers: run  pip install fyers-apiv3")
        return fyersModel

    def _connect(self, token):
        fm = self._model()
        (config.DATA / "logs").mkdir(parents=True, exist_ok=True)
        c = fm.FyersModel(client_id=self.app_id, token=token, is_async=False, log_path=str(config.DATA / "logs"))
        r = c.funds()
        if r.get("s") != "ok":
            raise BrokerError(f"Fyers token not accepted: {r}")
        self.client = c

    def auth_url(self):
        fm = self._model()
        s = fm.SessionModel(client_id=self.app_id, redirect_uri=self.redirect, response_type="code", grant_type="authorization_code")
        return s.generate_authcode()

    def login(self, auth_code=None, redirected_url=None, **kw):
        code = auth_code
        if redirected_url:
            code = (parse_qs(urlparse(redirected_url).query).get("auth_code") or [None])[0]
        if not code:
            raise BrokerError("Fyers: log in with the link, then paste the full address of the page you land on")
        fm = self._model()
        s = fm.SessionModel(client_id=self.app_id, secret_key=self.secret, redirect_uri=self.redirect, response_type="code",
                            grant_type="authorization_code")
        s.set_token(code)
        r = s.generate_token()
        if "access_token" not in r:
            raise BrokerError(f"Fyers login failed: {r}")
        json.dump({"date": config.now().strftime("%Y-%m-%d"), "token": r["access_token"]}, open(self._tok, "w"))
        self._connect(r["access_token"])

    def logged_in(self):
        return self.client is not None

    def _c(self):
        if not self.client:
            raise BrokerError("Fyers: not logged in today")
        return self.client

    def ltp(self, sym):
        r = self._c().quotes({"symbols": f"NSE:{sym}-EQ"})
        try:
            px = num(r["d"][0]["v"]["lp"])
        except (KeyError, IndexError, TypeError):
            px = 0
        if px <= 0:
            raise BrokerError(f"Fyers returned no price for {sym}: {str(r)[:200]}")
        return px

    def place(self, sym, side, qty, kind, price=0.0, trigger=0.0, tag=""):
        data = {"symbol": f"NSE:{sym}-EQ", "qty": int(qty), "type": TYPE[kind], "side": 1 if side == "BUY" else -1, "productType": "CNC",
                "limitPrice": round(price, 2) if kind != MARKET else 0, "stopPrice": round(trigger, 2) if kind == SL_LIMIT else 0,
                "validity": "DAY", "disclosedQty": 0, "offlineOrder": False, "orderTag": "".join(c for c in (tag or "insider") if c.isalnum())[:20]}
        r = self._c().place_order(data)
        if r.get("s") != "ok" or not r.get("id"):
            raise BrokerError(f"Fyers rejected the order: {str(r)[:300]}")
        return str(r["id"])

    def order(self, oid):
        r = self._c().orderbook({"id": oid})
        for o in r.get("orderBook", []) or []:
            if str(o.get("id")) == str(oid):
                return dict(status=STATUS.get(o.get("status"), OPEN), filled=int(num(o.get("filledQty"))), qty=int(num(o.get("qty"))),
                            avg=num(o.get("tradedPrice")), msg=str(o.get("message") or ""))
        raise BrokerError(f"Fyers: order {oid} not in the order book")

    def cancel(self, oid):
        return self._c().cancel_order({"id": oid}).get("s") == "ok"

    def funds(self):
        r = self._c().funds()
        for row in r.get("fund_limit", []) or []:
            if str(row.get("title", "")).strip().lower() == "available balance":
                return num(row.get("equityAmount"))
        return None

    def raw_dump(self, sym="TCS"):
        c = self._c()
        return {"quote": c.quotes({"symbols": f"NSE:{sym}-EQ"}), "orderbook": c.orderbook(), "funds": c.funds()}
