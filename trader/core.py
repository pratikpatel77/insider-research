"""The trading logic: buy (manual or automatic), protect every position with a broker stop-loss order, follow the
trailing rule, and record exits. Everything after a buy is automatic.

Daily rhythm (see scheduler.py):  ~08:40 scan  ->  09:16 stop orders re-placed  ->  09:20 automatic buys  ->
                                  every 30 s: check fills and stop orders  ->  evening: official closes raise the trailing stops.
"""
import datetime as dt, threading, time, urllib.parse, urllib.request

import config, risk
from brokers import (BrokerError, COMPLETE, LIMIT, MARKET, OPEN, REJECTED, CANCELLED, SL_LIMIT, LIVE_BROKERS, make)
from brokers.paper import NSEDATA
from signals import SignalSource

MARKET_OPEN, MARKET_CLOSE = dt.time(9, 15), dt.time(15, 30)
STOPS_FROM = dt.time(9, 16)          # stop orders are (re)placed from here: DAY orders from yesterday have expired


class UserError(Exception):
    """A refusal the user should see (bad quantity, price outside the entry band, kill switch...)."""


class Trader:
    def __init__(self, db, signals=None, broker=None, clock=config.now, sleep=time.sleep, env=None, tick_fn=None):
        self.db, self.signals, self.clock, self.sleep = db, signals or SignalSource(db), clock, sleep
        self.env = env if env is not None else config.load_env()
        self.s = config.load_settings()
        self._injected, self._tick_fn, self._ticks = broker, tick_fn or NSEDATA.tick, {}
        self._brokers, self.lock = {}, threading.RLock()
        self.threads = []

    # ---------------------------------------------------------------- settings, mode, broker
    def update_settings(self, changes):
        new = dict(self.s)
        for k, v in changes.items():
            if k not in config.DEFAULTS:
                raise UserError(f"Unknown setting {k}")
            try:
                new[k] = config.coerce(k, v)
            except (ValueError, TypeError) as e:
                raise UserError(f"Invalid value for {k}: {e}")
        self.s = new
        config.save_settings(new)
        self.db.event("info", "Settings updated: " + ", ".join(sorted(changes)))

    @property
    def mode(self):
        return self.db.get("mode", "paper")

    @property
    def broker_name(self):
        return self.db.get("broker", "paper")

    def set_broker(self, name):
        if name != "paper" and name not in LIVE_BROKERS:
            raise UserError(f"Unknown broker {name}")
        if self.open_count() and name != self.broker_name:
            raise UserError("Close or wait out the open positions before switching broker")
        self.db.set("broker", name)
        self._brokers.pop(name, None)

    def set_mode(self, mode, confirm=""):
        if mode == "paper":
            self.db.set("mode", "paper")
            self.db.event("warn", "Switched to PAPER trading")
            return
        if mode != "live":
            raise UserError("Mode must be paper or live")
        if self.env.get("TRADER_ALLOW_LIVE") != "1":
            raise UserError("Live trading is locked. Add TRADER_ALLOW_LIVE=1 to trader/.env and restart to unlock it.")
        if self.broker_name not in LIVE_BROKERS:
            raise UserError("Choose a broker (definedge, kotak or fyers) before going live")
        if confirm != "GO LIVE":
            raise UserError('Type GO LIVE to confirm')
        if self.open_count() and self.mode == "paper":
            raise UserError("Close the paper positions before going live")
        self.get_broker(live=True).ltp("TCS")            # fails early if the broker is not reachable / logged in
        self.db.set("mode", "live")
        self.db.event("warn", f"LIVE trading enabled on {self.broker_name}")

    def get_broker(self, live=None):
        if self._injected is not None:
            return self._injected
        live = (self.mode == "live") if live is None else live
        key = self.broker_name if live else "paper"
        if key not in self._brokers:
            self._brokers[key] = make(key, self.env)
        return self._brokers[key]

    def selected_broker(self):
        """The broker chosen in the dashboard (live adapter), even while still in paper mode, so you can log in before going live."""
        if self._injected is not None:
            return self._injected
        return self.get_broker(live=self.broker_name != "paper")

    def login(self, **kw):
        b = self.selected_broker()
        try:
            b.login(**kw)
        except BrokerError:
            raise
        except Exception as e:
            raise BrokerError(f"{b.name} login failed: {e}")
        self.db.event("info", f"{b.name} logged in")

    def ensure_login(self):
        b = self.get_broker()
        if not b.logged_in():
            if not b.auto_login:
                raise UserError(f"{b.name} needs a manual login today: open the dashboard and use the Login box")
            self.login()

    # ---------------------------------------------------------------- helpers
    def tick(self, sym):
        """Price tick of the stock (0.05 for most, 0.10 for some). Orders at other prices are rejected by the exchange."""
        if sym not in self._ticks:
            try:
                self._ticks[sym] = round(float(self._tick_fn(sym)), 2) or 0.05
            except Exception:
                return 0.05                                   # not cached: try again next time
        return self._ticks[sym]

    def rt(self, x, sym, mode="nearest"):
        return risk.round_tick(x, mode, self.tick(sym))

    def today(self):
        return self.clock().strftime("%Y-%m-%d")

    def market_open(self, t=None):
        t = t or self.clock()
        return t.weekday() < 5 and MARKET_OPEN <= t.time() <= MARKET_CLOSE

    def positions(self, *status):
        q = "SELECT * FROM positions" + (f" WHERE status IN ({','.join('?' * len(status))})" if status else "") + " ORDER BY id"
        return self.db.q(q, status)

    def open_count(self):
        return len(self.positions("entering", "open"))

    def notify(self, msg):
        tok, chat = self.env.get("TELEGRAM_BOT_TOKEN"), self.env.get("TELEGRAM_CHAT_ID")
        if tok and chat:
            def send():
                try:
                    data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
                    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=15).read()
                except Exception:
                    pass
            threading.Thread(target=send, daemon=True).start()

    def _log_order(self, pid, sym, side, kind, purpose, qty, price, trigger, oid, note=""):
        return self.db.insert("orders", ts=self.clock().strftime("%Y-%m-%d %H:%M:%S"), day=self.today(), mode=self.mode, position_id=pid,
                              sym=sym, side=side, kind=kind, purpose=purpose, qty=qty, price=price, trigger=trigger, broker_oid=oid,
                              status="OPEN", filled=0, avg=0, note=note)

    def _orders_today(self):
        return self.db.one("SELECT COUNT(*) n FROM orders WHERE day=?", (self.today(),))["n"]

    def _candidate(self, sym):
        scan = self.signals.load() or {}
        return next((c for c in scan.get("candidates", []) if c["sym"] == sym), None)

    # ---------------------------------------------------------------- margin
    def available_funds(self):
        """Cash available for new buys, or None if unknown. Paper mode uses the pretend balance in settings."""
        b = self.get_broker()
        if b.is_paper:
            spent = sum((p["entry_price"] or 0) * (p["qty"] or 0) for p in self.positions("open"))
            pending = self.db.one("SELECT COALESCE(SUM(o.qty*o.price),0) v FROM orders o JOIN positions p ON p.id=o.position_id "
                                  "WHERE o.purpose='entry' AND p.status='entering'")["v"]
            gains = self.db.one("SELECT COALESCE(SUM(pnl),0) v FROM positions WHERE status='closed' AND mode='paper'")["v"]
            return self.s["paper_capital"] + gains - spent - pending
        try:
            return b.funds()
        except Exception:
            return None

    def _reject(self, pid, sym, reason):
        """A trade the system could not take for lack of margin. It stays visible so it can be bought by hand once funds are added."""
        self.db.update("positions", pid, status="rejected", note=reason[:300])
        self.db.event("warn", f"REJECTED {sym}: {reason}")
        self.notify(f"Trade rejected: {sym}. {reason}")

    # ---------------------------------------------------------------- buying
    def start_buy(self, sym, qty=None, amount=None, limit=None, source="manual"):
        """Validate, check margin, place the entry order and hand over to a background thread that waits for the fill.
        Only Clean signals whose price is still inside the entry band can be bought, by hand or automatically.
        Returns the position id. Raises UserError with a plain-English reason if the buy is refused."""
        sym = str(sym).strip().upper()
        if not sym:
            raise UserError("Enter a symbol")
        b = self.get_broker()
        with self.lock:
            if self.s["kill_switch"]:
                raise UserError("Kill switch is on: new buys are blocked")
            if not b.is_paper and not self.market_open():
                raise UserError("The market is closed (09:15 to 15:30 on weekdays)")
            if any(p["sym"] == sym for p in self.positions("entering", "open")):
                raise UserError(f"{sym} is already held: one position per stock")
            cap_n = self.s["max_positions"]
            if cap_n and self.open_count() >= cap_n:
                raise UserError(f"The limit of {cap_n} open positions is reached")
            if self._orders_today() >= self.s["max_orders_per_day"]:
                raise UserError("Daily order limit reached")
            cand = self._candidate(sym)
            if not cand:
                raise UserError(f"{sym} is not on today's signal list. Only signals can be bought.")
            if not cand["clean"]:
                raise UserError(f"{sym} is not a Clean signal ({'; '.join(cand['notes'])}). Only Clean signals are traded.")
            done = self.db.one("SELECT id FROM positions WHERE signal_key=? AND status IN ('entering','open','closed')", (cand["key"],))
            if done:
                raise UserError(f"{sym}: this insider signal was already traded. A fresh insider buy is needed to re-enter.")
            if not cand.get("avg_now"):
                raise UserError(f"{sym}: the insiders' average price is unknown, so the entry range cannot be checked")
            self.ensure_login()
            ltp = b.ltp(sym)
            cap = cand["avg_now"] * (1 + self.s["entry_band_pct"] / 100)
            if ltp > cap:
                raise UserError(f"{sym} is at Rs {ltp:.2f}, above the entry limit of Rs {cap:.2f} "
                                f"({self.s['entry_band_pct']:.0f}% over the insiders' average). Not allowed.")
            cap_px = self.rt(cap, sym, "down")
            if limit:
                lim = self.rt(float(limit), sym)
                if lim > cap_px:
                    raise UserError(f"Limit price Rs {lim:.2f} is above the entry limit of Rs {cap_px:.2f}")
            else:
                lim = min(self.rt(ltp * (1 + self.s["limit_buffer_pct"] / 100), sym, "up"), cap_px)
            if lim <= 0:
                raise UserError("Invalid limit price")
            q = int(qty) if qty else int((float(amount) if amount else self.s["position_amount"]) // lim)
            if q < 1:
                raise UserError(f"Amount is too small to buy one share at Rs {lim:.2f}")
            if q * lim > self.s["max_order_value"]:
                raise UserError(f"Order value Rs {q * lim:,.0f} is above the safety cap of Rs {self.s['max_order_value']:,.0f} "
                                "(change 'max_order_value' in settings if this is intended)")
            pid = self.db.insert("positions", sym=sym, company=cand.get("company", ""), mode=self.mode, broker=b.name, status="entering",
                                 source=source, signal_key=cand["key"], insider_avg=cand["avg_now"], qty=q,
                                 entry_time=self.clock().strftime("%Y-%m-%d %H:%M:%S"))
            need, have = q * lim * 1.003, self.available_funds()          # +0.3% for charges
            if have is not None and have < need:
                reason = (f"Not enough margin: needs about Rs {need:,.0f}, Rs {max(have, 0):,.0f} available. "
                          "Add funds, then buy it from the app while it is still in range.")
                self._reject(pid, sym, reason)
                raise UserError(reason)
            try:
                oid = b.place(sym, "BUY", q, LIMIT, price=lim, tag="insider")
            except BrokerError as e:
                if any(w in str(e).lower() for w in ("margin", "fund", "insufficient", "balance")):
                    reason = f"Broker rejected the order for margin: {e}"
                    self._reject(pid, sym, reason)
                    raise UserError(reason)
                self.db.update("positions", pid, status="failed", note=str(e)[:300])
                self.db.event("error", f"BUY {sym} rejected: {e}")
                raise UserError(f"Broker rejected the order: {e}")
            self._log_order(pid, sym, "BUY", LIMIT, "entry", q, lim, 0, oid)
            self.db.update("positions", pid, sl_oid=None, note=f"entry order {oid}")
            self.db.event("info", f"BUY {q} {sym} @ limit {lim:.2f} placed ({source}, {b.name}, order {oid})")
        t = threading.Thread(target=self._await_entry, args=(pid, oid), daemon=True)
        t.start()
        self.threads.append(t)
        return pid

    def adopt(self, sym, price, qty):
        """Record a trade that was done outside the app (for example in the broker's own app) using the ACTUAL fill price and
        quantity. From here the system manages it like any other position: initial stop, daily stop order, trailing stop, exit."""
        sym = str(sym).strip().upper()
        try:
            price, qty = float(price), int(qty)
        except (TypeError, ValueError):
            raise UserError("Enter the fill price and the quantity")
        if not sym or price <= 0 or qty < 1:
            raise UserError("Enter the symbol, the actual fill price and the quantity")
        b = self.get_broker()
        with self.lock:
            if any(p["sym"] == sym for p in self.positions("entering", "open")):
                raise UserError(f"{sym} is already being managed")
            self.ensure_login()
            cand = self._candidate(sym)
            pid = self.db.insert("positions", sym=sym, company=(cand or {}).get("company", ""), mode=self.mode, broker=b.name, status="entering",
                                 source="external", signal_key=(cand or {}).get("key"), insider_avg=(cand or {}).get("avg_now"), qty=qty,
                                 entry_time=self.clock().strftime("%Y-%m-%d %H:%M:%S"))
            self.db.event("info", f"Recorded outside trade: {qty} {sym} @ {price:.2f}")
            self._on_fill(pid, qty, price)
            return pid

    def _await_entry(self, pid, oid):
        b = self.get_broker()
        try:
            deadline = self.clock() + dt.timedelta(minutes=self.s["fill_wait_min"])
            st = None
            while True:
                st = b.order(oid)
                if st["status"] in (COMPLETE, REJECTED, CANCELLED):
                    break
                if self.clock() >= deadline:
                    b.cancel(oid)
                    st = b.order(oid)
                    break
                self.sleep(5)
            with self.lock:
                if st["filled"] > 0:
                    self._on_fill(pid, st["filled"], st["avg"])
                elif st["status"] == REJECTED and any(w in (st.get("msg") or "").lower() for w in ("margin", "fund", "insufficient", "balance")):
                    sym = self.db.one("SELECT sym FROM positions WHERE id=?", (pid,))["sym"]
                    self._reject(pid, sym, f"Broker rejected the order for margin: {st['msg']}")
                else:
                    self.db.update("positions", pid, status="failed", note=f"entry not filled ({st['status']}) {st.get('msg', '')}"[:300])
                    self.db.event("warn", f"Entry for position {pid} did not fill ({st['status']}). No position taken.")
        except Exception as e:
            self.db.event("error", f"Entry watch for position {pid} failed: {e}. Restart the app to recover it.")

    def _on_fill(self, pid, qty, avg):
        p = self.db.one("SELECT * FROM positions WHERE id=?", (pid,))
        cand = self._candidate(p["sym"])
        lows = (cand or {}).get("lows") or []
        stop, kind = risk.initial_stop(lows, avg, self.s["pivot_bars"], self.s["pivot_lookback"], self.s["min_sl_pct"] / 100, self.s["max_sl_pct"] / 100)
        if not lows:
            kind = "15% (no price history)"
        stop = min(self.rt(stop, p["sym"], "up"), self.rt(avg * 0.99, p["sym"], "down"))
        self.db.update("positions", pid, status="open", qty=qty, entry_price=avg, initial_stop=stop, stop=stop, stop_kind=kind,
                       high_close=avg, sl_state="none", note=None)
        self.db.event("info", f"FILLED {qty} {p['sym']} @ {avg:.2f}. Initial stop {stop:.2f} ({kind}, {(1 - stop / avg) * 100:.1f}% risk)")
        self.notify(f"Bought {qty} {p['sym']} @ {avg:.2f}. Stop {stop:.2f} ({kind}).")
        self.place_stop(pid)

    # ---------------------------------------------------------------- stops and exits
    def place_stop(self, pid):
        """Put today's stop-loss order on the exchange for a position (replacing yesterday's expired one)."""
        b = self.get_broker()
        with self.lock:
            p = self.db.one("SELECT * FROM positions WHERE id=?", (pid,))
            if not p or p["status"] != "open":
                return
            today = self.today()
            if p["sl_oid"] and p["sl_state"] == "broker":
                try:
                    st = b.order(p["sl_oid"])
                except BrokerError:
                    st = None
                if st and st["status"] == OPEN:
                    if p["sl_date"] == today and abs((p["sl_trigger"] or 0) - p["stop"]) < 0.005:
                        return                                                # already protected at this level
                    b.cancel(p["sl_oid"])
                elif st and st["status"] == COMPLETE:
                    return self._close(pid, st["avg"], self._stop_reason(p))
            ltp = b.ltp(p["sym"])
            trig = self.rt(p["stop"], p["sym"], "up")
            if ltp <= trig:                                                   # already through the stop (gap down at the open)
                return self._exit_market(pid, "stop (gap)")
            limit = self.rt(trig * (1 - self.s["sl_limit_gap_pct"] / 100), p["sym"], "down")
            try:
                oid = b.place(p["sym"], "SELL", p["qty"], SL_LIMIT, price=limit, trigger=trig, tag="insider-sl")
            except BrokerError as e:
                self.db.update("positions", pid, sl_state="software", sl_oid=None)
                self.db.event("error", f"Stop order for {p['sym']} rejected ({e}). The app will watch the price and sell at market instead.")
                self.notify(f"WARNING: stop order for {p['sym']} rejected: {e}")
                return
            self._log_order(pid, p["sym"], "SELL", SL_LIMIT, "stop", p["qty"], limit, trig, oid)
            self.db.update("positions", pid, sl_oid=oid, sl_date=today, sl_trigger=trig, sl_state="broker")
            self.db.event("info", f"Stop order for {p['sym']}: trigger {trig:.2f}, limit {limit:.2f} ({p['qty']} shares)")

    def place_all_stops(self):
        for p in self.positions("open"):
            try:
                self.place_stop(p["id"])
            except Exception as e:
                self.db.event("error", f"Could not place stop for {p['sym']}: {e}")

    @staticmethod
    def _stop_reason(p):
        return "trailing stop" if p["stop"] > (p["initial_stop"] or 0) * 1.0001 else "stop"

    def _close(self, pid, price, reason):
        p = self.db.one("SELECT * FROM positions WHERE id=?", (pid,))
        if p["status"] == "closed":
            return
        pnl = (price - p["entry_price"]) * p["qty"]
        self.db.update("positions", pid, status="closed", exit_price=price, exit_time=self.clock().strftime("%Y-%m-%d %H:%M:%S"),
                       exit_reason=reason, pnl=pnl)
        msg = f"EXIT {p['sym']} @ {price:.2f} ({reason}): {pnl:+,.0f} Rs, {(price / p['entry_price'] - 1) * 100:+.1f}%"
        self.db.event("info", msg)
        self.notify(msg)

    def _exit_market(self, pid, reason):
        """Sell everything at market now. Waits up to a minute for the fill; the monitor finishes the job if it is slow."""
        b = self.get_broker()
        p = self.db.one("SELECT * FROM positions WHERE id=?", (pid,))
        if p["sl_oid"] and p["sl_state"] == "broker":
            try:
                b.cancel(p["sl_oid"])
            except BrokerError:
                pass
        oid = b.place(p["sym"], "SELL", p["qty"], MARKET, tag="insider-exit")
        self._log_order(pid, p["sym"], "SELL", MARKET, "exit", p["qty"], 0, 0, oid, reason)
        self.db.update("positions", pid, sl_oid=oid, sl_state="exit", exit_reason=reason)
        for _ in range(20):
            st = b.order(oid)
            if st["status"] == COMPLETE:
                return self._close(pid, st["avg"], reason)
            if st["status"] in (REJECTED, CANCELLED):
                self.db.update("positions", pid, sl_oid=None, sl_state="none", exit_reason=None)
                self.db.event("error", f"Market exit for {p['sym']} failed ({st['status']} {st.get('msg', '')}). Will retry.")
                return
            self.sleep(3)

    def sell_now(self, pid):
        """Manual override: exit a position at market."""
        with self.lock:
            p = self.db.one("SELECT * FROM positions WHERE id=?", (pid,))
            if not p or p["status"] != "open":
                raise UserError("That position is not open")
            self.ensure_login()
            self._exit_market(pid, "manual exit")

    # ---------------------------------------------------------------- monitoring (every ~30 s while the market is open)
    def monitor(self):
        b = self.get_broker()
        if not b.logged_in():
            return
        for p in self.positions("open"):
            try:
                with self.lock:
                    self._check(p["id"], b)
            except Exception as e:
                self.db.event("error", f"Monitor {p['sym']}: {e}")

    def _check(self, pid, b):
        p = self.db.one("SELECT * FROM positions WHERE id=?", (pid,))
        if p["status"] != "open":
            return
        if p["sl_oid"]:
            st = b.order(p["sl_oid"])
            if st["status"] == COMPLETE:
                return self._close(pid, st["avg"], p["exit_reason"] or self._stop_reason(p))
            if st["status"] in (REJECTED, CANCELLED) and p["sl_state"] == "broker" and p["sl_date"] == self.today():
                self.db.update("positions", pid, sl_state="software", sl_oid=None)
                self.db.event("warn", f"Stop order for {p['sym']} is {st['status']}. Watching the price instead.")
            elif st["status"] in (REJECTED, CANCELLED) and p["sl_state"] == "exit":
                self.db.update("positions", pid, sl_state="none", sl_oid=None, exit_reason=None)
        p = self.db.one("SELECT * FROM positions WHERE id=?", (pid,))
        t = self.clock()
        if not self.market_open(t):
            return
        if p["sl_state"] == "software":
            if b.ltp(p["sym"]) <= p["stop"]:
                return self._exit_market(pid, "stop (software)")
        elif p["sl_state"] in ("none", None) or p["sl_date"] != self.today():
            if t.time() >= STOPS_FROM:
                self.place_stop(pid)

    # ---------------------------------------------------------------- evening: official closes -> trailing stops
    def eod_update(self, trade_date, closes):
        """closes: {sym: (close, low)} for the trade date. Raises each stop to highest close x (1 - trail); never lowers it."""
        n = 0
        for p in self.positions("open"):
            if p["eod_date"] == trade_date or p["sym"] not in closes:
                continue
            if trade_date < (p["entry_time"] or "")[:10]:
                continue
            c, low = closes[p["sym"]]
            high = max(p["high_close"] or p["entry_price"], c)
            stop = max(p["stop"], self.rt(risk.trail_stop(p["stop"], high, self.s["trail_pct"] / 100), p["sym"], "up"))
            self.db.update("positions", p["id"], high_close=high, stop=stop, eod_date=trade_date)
            if stop > p["stop"] + 0.004:
                self.db.event("info", f"{p['sym']}: close {c:.2f}, high close {high:.2f}. Stop raised {p['stop']:.2f} -> {stop:.2f}")
            n += 1
        return n

    # ---------------------------------------------------------------- automatic buying
    def auto_buy(self):
        """Buy every Clean candidate that is inside the entry band, best (largest insider purchase) first, while slots are free."""
        if not self.s["auto_buy"]:
            return []
        if self.s["kill_switch"]:
            self.db.event("warn", "Auto-buy skipped: kill switch is on")
            return []
        scan = self.signals.load()
        if not scan or scan.get("scanned_on") != self.today():
            self.db.event("warn", "Auto-buy skipped: no scan from today. Run a scan first.")
            return []
        used = {r["signal_key"] for r in self.db.q("SELECT signal_key FROM positions WHERE status!='failed' AND signal_key IS NOT NULL")}
        held = {p["sym"] for p in self.positions("entering", "open")}
        todo = sorted((c for c in scan["candidates"] if c["clean"] and c["avg_now"] and c["sym"] not in held and c["key"] not in used),
                      key=lambda c: -(c["value_cr"] or 0))
        bought = []
        for c in todo:
            if self.s["max_positions"] and self.open_count() >= self.s["max_positions"]:
                self.db.event("info", "Auto-buy: the open-positions limit is reached")
                break
            try:
                bought.append(self.start_buy(c["sym"], source="auto"))
                self.sleep(0.5)
            except UserError as e:
                self.db.event("info", f"Auto-buy skipped {c['sym']}: {e}")
            except Exception as e:
                self.db.event("error", f"Auto-buy {c['sym']} failed: {e}")
        self.db.event("info", f"Auto-buy finished: {len(bought)} order(s) placed from {len(todo)} eligible candidate(s)")
        return bought

    # ---------------------------------------------------------------- restart recovery
    def recover(self):
        """After a restart: finish entries that were in flight and resume watching them."""
        b = self.get_broker()
        for p in self.positions("entering"):
            oid = (p["note"] or "").replace("entry order ", "").strip()
            if not oid:
                self.db.update("positions", p["id"], status="failed", note="lost during restart")
                continue
            try:
                st = b.order(oid)
            except Exception as e:
                self.db.event("error", f"Cannot recover entry {p['sym']}: {e}")
                continue
            if st["status"] == OPEN:
                t = threading.Thread(target=self._await_entry, args=(p["id"], oid), daemon=True)
                t.start()
                self.threads.append(t)
            elif st["filled"] > 0:
                with self.lock:
                    self._on_fill(p["id"], st["filled"], st["avg"])
            else:
                self.db.update("positions", p["id"], status="failed", note=f"entry {st['status']}")
