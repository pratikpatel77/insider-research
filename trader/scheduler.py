"""Runs the daily routine while the app is open (times are IST, weekdays):

  08:30  log in to the broker (Definedge / Kotak with a TOTP seed do this by themselves)
  08:40  scan NSE for insider buys (takes a few minutes)
  09:16  put the day's stop-loss order on every open position
  09:20  automatic buys (if switched on)
  09:15-15:30, every 30 s: check fills and stop orders, record exits
  18:15  official closes -> raise the trailing stops for tomorrow (also catches up next morning if the PC was off)
Slow jobs (scan, closes) run in their own threads so the price checks never stall.
"""
import datetime as dt, threading, time, traceback

import config


class Scheduler(threading.Thread):
    def __init__(self, trader, tick_seconds=15):
        super().__init__(daemon=True, name="scheduler")
        self.tr, self.tick_seconds, self.stop_flag = trader, tick_seconds, threading.Event()
        self.busy, self.last_try, self.last_monitor = set(), {}, 0.0

    def run(self):
        while not self.stop_flag.is_set():
            try:
                self.tick()
            except Exception:
                traceback.print_exc()
            self.stop_flag.wait(self.tick_seconds)

    # ---------------------------------------------------------------- helpers
    def _once_per_day(self, name):
        return self.tr.db.get(f"done:{name}") == self.tr.today()

    def _mark(self, name):
        self.tr.db.set(f"done:{name}", self.tr.today())

    def _spawn(self, name, fn):
        if name in self.busy:
            return
        self.busy.add(name)

        def wrap():
            try:
                fn()
            except Exception as e:
                self.tr.db.event("error", f"{name} failed: {e}")
            finally:
                self.busy.discard(name)
        threading.Thread(target=wrap, daemon=True, name=name).start()

    def _retry_ok(self, name, every):
        if time.time() - self.last_try.get(name, 0) < every:
            return False
        self.last_try[name] = time.time()
        return True

    # ---------------------------------------------------------------- the routine
    def tick(self):
        tr = self.tr
        t = tr.clock()
        tr.db.set("heartbeat", t.strftime("%Y-%m-%d %H:%M:%S"))
        now = t.time()
        at = lambda h, m: dt.time(h, m)
        if t.weekday() >= 5:
            return
        live = tr.mode == "live"

        # 1. broker login (live only; paper needs none)
        if live and at(8, 30) <= now <= at(15, 30) and self._retry_ok("login", 300):
            try:
                b = tr.get_broker()
                if not b.logged_in() and b.auto_login:
                    tr.login()
            except Exception as e:
                tr.db.event("error", f"Broker login failed: {e}")

        # 2. scan for signals
        if at(8, 40) <= now <= at(20, 0) and not self._once_per_day("scan") and self._retry_ok("scan", 600):
            def scan():
                tr.signals.scan()
                self._mark("scan")
                tr.db.event("info", "Scan finished")
            self._spawn("scan", scan)

        # 3. stop-loss orders for the day
        if at(9, 16) <= now <= at(15, 25) and not self._once_per_day("stops"):
            try:
                ready = tr.get_broker().logged_in()
            except Exception:
                ready = False
            if ready:
                tr.place_all_stops()
                self._mark("stops")

        # 4. automatic buys
        buy_at = dt.datetime.strptime(tr.s["buy_time"], "%H:%M").time()
        end = (dt.datetime.combine(t.date(), buy_at) + dt.timedelta(minutes=tr.s["buy_window_min"])).time()
        if buy_at <= now <= end and not self._once_per_day("auto_buy"):
            scan = tr.signals.load()
            if tr.s["auto_buy"] and scan and scan.get("scanned_on") == tr.today() and "scan" not in self.busy:
                try:
                    tr.ensure_login()
                    tr.auto_buy()
                finally:
                    self._mark("auto_buy")
            elif not tr.s["auto_buy"]:
                self._mark("auto_buy")

        # 5. fills and stop orders
        if at(9, 15) <= now <= at(15, 45) and time.time() - self.last_monitor >= 30:
            self.last_monitor = time.time()
            tr.monitor()

        # 6. trailing stops from official closes (evening, or next morning if the PC was off)
        if (now >= at(18, 15) or now <= at(9, 10)) and self._retry_ok("eod", 900):
            def eod():
                held = {p["sym"] for p in tr.positions("open")}
                if not held:
                    return
                day, closes = tr.signals.closes(held)
                if day and day > tr.db.get("eod_last", ""):
                    n = tr.eod_update(day, closes)
                    tr.db.set("eod_last", day)
                    tr.db.event("info", f"Trailing stops updated from the {day} close ({n} positions)")
            self._spawn("eod", eod)
