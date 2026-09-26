"""End-to-end tests against a simulated market. Run:  python -m pytest tests -q   (from the trader folder)."""
import datetime as dt, os, sys, threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config, risk                                         # noqa: E402
from brokers import BrokerError, SL_LIMIT                   # noqa: E402
from brokers.paper import PaperBroker                       # noqa: E402
from core import Trader, UserError                          # noqa: E402
from db import DB                                           # noqa: E402

MON = dt.datetime(2026, 9, 28, 10, 0, tzinfo=config.IST)    # a Monday, market open


class Clock:
    def __init__(self):
        self.t = MON

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += dt.timedelta(seconds=s)

    def set(self, h, m, day=0):
        self.t = (MON + dt.timedelta(days=day)).replace(hour=h, minute=m)


class FakeSignals:
    def __init__(self, cands, on):
        self.cands, self.on = cands, on

    def load(self):
        return {"scanned_on": self.on.strftime("%Y-%m-%d"), "candidates": self.cands}


def cand(sym, avg=100.0, clean=True, value=1.0, lows=None):
    lows = lows or [96, 95, 94, 92, 93, 95, 96, 97, 98, 99, 99, 100, 101, 100, 102, 101, 103, 104, 103, 105]
    return {"sym": sym, "company": sym.title(), "key": f"{sym}|2026-09-25 17:00", "avg_now": avg, "clean": clean, "value_cr": value,
            "lows": lows, "notes": [] if clean else ["Small ticket"], "close": avg, "vs_insider": 0.0, "last_disclosed": "2026-09-25 17:00"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    prices, clock = {"AAA": 101.0, "BBB": 50.0, "CCC": 200.0}, Clock()
    paper = PaperBroker(price_fn=lambda s: prices[s], path=None)
    db = DB(tmp_path / "t.db")
    sig = FakeSignals([cand("AAA"), cand("BBB", avg=50), cand("CCC", avg=200, clean=False)], clock.t)
    tr = Trader(db, signals=sig, broker=paper, clock=clock, sleep=clock.sleep, env={}, tick_fn=lambda s: 0.05)
    tr.s.update(auto_buy=False, position_amount=50000, max_positions=10)
    return tr, prices, clock, paper, db


def join(tr):
    for t in tr.threads:
        t.join(5)


def pos(db, sym):
    return db.one("SELECT * FROM positions WHERE sym=? ORDER BY id DESC", (sym,))


# ------------------------------------------------------------------ risk maths
def test_initial_stop_uses_pivot_but_ignores_ones_too_close_and_caps_at_15pct():
    lows = [100, 98, 96, 90, 96, 98, 100, 101, 102, 103, 104, 105]        # pivot low 90 at index 3
    stop, kind = risk.initial_stop(lows, 105, n=3, min_sl=0.05, max_sl=0.15)
    assert (stop, kind) == (90, "pivot")
    stop, kind = risk.initial_stop(lows, 105, n=3, min_sl=0.05, max_sl=0.05)      # 90 is 14% away: capped
    assert kind == "15% cap" and stop == pytest.approx(105 * 0.95)
    stop, kind = risk.initial_stop([100] * 12, 100, n=3)                          # no pivot below entry -> 15% rule
    assert kind == "15% (no pivot)" and stop == pytest.approx(85)
    lows2 = [100, 99, 98, 97.5, 98, 99, 100, 100, 100, 100, 100, 100]              # pivot only 2.5% below: ignored (min 5%)
    assert risk.initial_stop(lows2, 100, n=3)[1] == "15% (no pivot)"


def test_trail_never_lowers_the_stop():
    assert risk.trail_stop(90, 150, 0.20) == 120
    assert risk.trail_stop(130, 150, 0.20) == 130


# ------------------------------------------------------------------ entry
def test_buy_fills_computes_quantity_and_places_stop(env):
    tr, prices, clock, paper, db = env
    tr.start_buy("AAA")
    join(tr)
    p = pos(db, "AAA")
    assert p["status"] == "open" and p["qty"] == int(50000 // risk.round_tick(101 * 1.003, "up"))
    assert p["stop"] < p["entry_price"] and p["sl_state"] == "broker" and p["sl_oid"]
    o = paper.orders[p["sl_oid"]]
    assert o["side"] == "SELL" and o["kind"] == SL_LIMIT and o["qty"] == p["qty"] and o["trigger"] == p["stop"]


def test_skips_when_price_is_more_than_5pct_above_insider_average(env):
    tr, prices, *_ = env
    prices["AAA"] = 106.0
    with pytest.raises(UserError, match="above the entry limit"):
        tr.start_buy("AAA")
    prices["AAA"] = 104.9
    tr.start_buy("AAA")                                                         # inside the band
    join(tr)


def test_manual_buy_uses_your_quantity_but_only_inside_the_range(env):
    tr, prices, clock, paper, db = env
    tr.start_buy("AAA", qty=7)
    join(tr)
    assert pos(db, "AAA")["qty"] == 7
    prices["BBB"] = 60.0                                                        # 20% over the insiders' average
    with pytest.raises(UserError, match="Not allowed"):
        tr.start_buy("BBB", qty=7)
    assert pos(db, "BBB") is None


def test_only_clean_signals_on_the_list_can_be_bought(env):
    tr, *_ = env
    with pytest.raises(UserError, match="not a Clean signal"):
        tr.start_buy("CCC")
    with pytest.raises(UserError, match="not on today's signal list"):
        tr.start_buy("ZZZ")


def test_a_limit_price_above_the_entry_range_is_refused(env):
    tr, *_ = env
    with pytest.raises(UserError, match="above the entry limit"):
        tr.start_buy("AAA", qty=5, limit=110.0)


def test_a_signal_already_traded_cannot_be_bought_again_by_hand(env):
    tr, prices, clock, paper, db = env
    tr.start_buy("AAA")
    join(tr)
    tr.sell_now(pos(db, "AAA")["id"])
    with pytest.raises(UserError, match="already traded"):
        tr.start_buy("AAA")


def test_one_position_per_stock_and_slot_limit(env):
    tr, prices, *_ , db = env
    tr.s["max_positions"] = 1
    tr.start_buy("AAA")
    join(tr)
    with pytest.raises(UserError, match="already held"):
        tr.start_buy("AAA")
    with pytest.raises(UserError, match="open positions"):
        tr.start_buy("BBB")


def test_kill_switch_blocks_buys_but_not_exits(env):
    tr, prices, clock, paper, db = env
    tr.start_buy("AAA")
    join(tr)
    tr.s["kill_switch"] = True
    with pytest.raises(UserError, match="Kill switch"):
        tr.start_buy("BBB")
    tr.sell_now(pos(db, "AAA")["id"])
    assert pos(db, "AAA")["status"] == "closed"


def test_order_value_cap(env):
    tr, *_ = env
    with pytest.raises(UserError, match="safety cap"):
        tr.start_buy("AAA", qty=5000)


def test_unfilled_entry_is_cancelled_after_the_wait(env):
    tr, prices, clock, paper, db = env
    tr.start_buy("AAA", qty=10, limit=90.0)                   # below the market: never fills
    join(tr)
    p = pos(db, "AAA")
    assert p["status"] == "failed" and "not filled" in p["note"]
    assert tr.open_count() == 0


# ------------------------------------------------------------------ exits
def test_stop_hit_closes_position_with_loss(env):
    tr, prices, clock, paper, db = env
    tr.start_buy("AAA")
    join(tr)
    stop = pos(db, "AAA")["stop"]
    prices["AAA"] = stop - 0.5
    tr.monitor()
    p = pos(db, "AAA")
    assert p["status"] == "closed" and p["exit_reason"] == "stop" and p["pnl"] < 0


def test_trailing_stop_ratchets_up_then_exits_at_profit(env):
    tr, prices, clock, paper, db = env
    tr.start_buy("AAA")
    join(tr)
    entry, first_stop = pos(db, "AAA")["entry_price"], pos(db, "AAA")["stop"]
    prices["AAA"] = 150.0
    tr.eod_update("2026-09-28", {"AAA": (150.0, 140.0)})
    assert pos(db, "AAA")["stop"] == 120.0 and pos(db, "AAA")["high_close"] == 150.0
    tr.eod_update("2026-09-29", {"AAA": (140.0, 138.0)})                          # lower close: stop must not fall
    assert pos(db, "AAA")["stop"] == 120.0
    clock.set(9, 16, day=1)
    prices["AAA"] = 140.0
    tr.place_all_stops()                                                          # next morning: new stop order at 120
    p = pos(db, "AAA")
    assert paper.orders[p["sl_oid"]]["trigger"] == 120.0 and p["sl_date"] == "2026-09-29"
    prices["AAA"] = 119.0
    tr.monitor()
    p = pos(db, "AAA")
    assert p["status"] == "closed" and p["exit_reason"] == "trailing stop" and p["pnl"] > 0 and p["exit_price"] > entry


def test_gap_down_through_the_stop_exits_at_market(env):
    tr, prices, clock, paper, db = env
    tr.start_buy("AAA")
    join(tr)
    clock.set(9, 16, day=1)
    prices["AAA"] = 60.0                                                          # opens far below the stop
    tr.place_all_stops()
    p = pos(db, "AAA")
    assert p["status"] == "closed" and p["exit_reason"] == "stop (gap)" and p["exit_price"] == 60.0


def test_rejected_stop_order_falls_back_to_watching_the_price(env):
    tr, prices, clock, paper, db = env
    real_place = paper.place

    def place(sym, side, qty, kind, **kw):
        if kind == SL_LIMIT:
            raise BrokerError("RMS: stop orders not allowed")
        return real_place(sym, side, qty, kind, **kw)
    paper.place = place
    tr.start_buy("AAA")
    join(tr)
    p = pos(db, "AAA")
    assert p["sl_state"] == "software"
    prices["AAA"] = p["stop"] - 1
    tr.monitor()
    assert pos(db, "AAA")["exit_reason"] == "stop (software)"


def test_restart_recovers_a_filled_entry(env):
    tr, prices, clock, paper, db = env
    oid = paper.place("AAA", "BUY", 10, "LIMIT", price=102)
    pid = db.insert("positions", sym="AAA", mode="paper", broker="paper", status="entering", source="manual", qty=10,
                    entry_time=clock().strftime("%Y-%m-%d %H:%M:%S"), note=f"entry order {oid}")
    tr.recover()
    p = db.one("SELECT * FROM positions WHERE id=?", (pid,))
    assert p["status"] == "open" and p["sl_state"] == "broker"


# ------------------------------------------------------------------ automatic buying
def test_auto_buy_takes_clean_candidates_best_first_within_slots_and_never_rebuys(env):
    tr, prices, clock, paper, db = env
    tr.s.update(auto_buy=True, max_positions=1)
    bought = tr.auto_buy()
    join(tr)
    assert len(bought) == 1 and pos(db, "AAA")["status"] == "open" and pos(db, "BBB") is None   # one slot: the first of two equal candidates
    tr.s["max_positions"] = 5
    tr.auto_buy()
    join(tr)
    syms = sorted(p["sym"] for p in tr.positions("open"))
    assert syms == ["AAA", "BBB"]                                                 # CCC is not Clean: never bought
    assert tr.auto_buy() == []                                                    # same signals: no repeat
    tr.sell_now(pos(db, "AAA")["id"])
    assert tr.auto_buy() == []                                                    # exited stock waits for a fresh insider buy


def test_auto_buy_needs_a_scan_from_today_and_the_switch(env):
    tr, prices, clock, paper, db = env
    assert tr.auto_buy() == []                                                    # switch off
    tr.s["auto_buy"] = True
    tr.signals.on = MON - dt.timedelta(days=1)
    assert tr.auto_buy() == []                                                    # stale scan


# ------------------------------------------------------------------ live safety
def test_live_is_locked_without_env_flag_and_needs_confirmation(env):
    tr, *_ = env
    with pytest.raises(UserError, match="locked"):
        tr.set_mode("live", "GO LIVE")
    tr.env["TRADER_ALLOW_LIVE"] = "1"
    with pytest.raises(UserError, match="Choose a broker"):
        tr.set_mode("live", "GO LIVE")
    tr.db.set("broker", "definedge")
    with pytest.raises(UserError, match="GO LIVE"):
        tr.set_mode("live", "yes")


def test_orders_use_the_stocks_own_tick_size(env):
    tr, prices, clock, paper, db = env
    tr._tick_fn, tr._ticks = (lambda s: 0.10), {}
    prices["AAA"] = 101.07
    tr.start_buy("AAA")
    join(tr)
    p = pos(db, "AAA")
    prices_sent = [o["price"] for o in paper.orders.values()] + [o["trigger"] for o in paper.orders.values()]
    assert len(prices_sent) == 4
    for x in prices_sent:
        assert round(x * 10) == pytest.approx(x * 10, abs=1e-6)         # every price is a multiple of 0.10
    assert round(p["stop"] * 10) == pytest.approx(p["stop"] * 10, abs=1e-6)


# ------------------------------------------------------------------ margin
def test_no_position_cap_by_default_and_margin_is_the_limit(env):
    tr, *_ = env
    assert config.DEFAULTS["max_positions"] == 0
    tr.start_buy("AAA")
    tr.start_buy("BBB")
    join(tr)
    assert tr.open_count() == 2


def test_insufficient_margin_rejects_the_trade_and_keeps_it_for_a_manual_buy(env):
    tr, prices, clock, paper, db = env
    tr.s["paper_capital"] = 20000
    with pytest.raises(UserError, match="Not enough margin"):
        tr.start_buy("AAA")
    p = pos(db, "AAA")
    assert p["status"] == "rejected" and "Add funds" in p["note"] and tr.open_count() == 0
    assert not paper.orders                                                     # nothing was sent to the broker
    tr.s["paper_capital"] = 500000                                              # the user adds capital...
    tr.start_buy("AAA")                                                         # ...and buys it by hand
    join(tr)
    assert pos(db, "AAA")["status"] == "open"


def test_auto_buy_rejects_for_margin_and_never_retries_by_itself(env):
    tr, prices, clock, paper, db = env
    tr.s.update(auto_buy=True, paper_capital=60000)                             # room for one 50k trade, not two
    tr.auto_buy()
    join(tr)
    assert [p["sym"] for p in tr.positions("open")] == ["AAA"]
    assert pos(db, "BBB")["status"] == "rejected"
    tr.s["paper_capital"] = 500000
    assert tr.auto_buy() == []                                                  # the rejected one waits for a manual buy
    tr.start_buy("BBB")
    join(tr)
    assert pos(db, "BBB")["status"] == "open"


def test_a_range_check_still_applies_when_buying_a_rejected_trade_later(env):
    tr, prices, clock, paper, db = env
    tr.s["paper_capital"] = 20000
    with pytest.raises(UserError):
        tr.start_buy("AAA")
    tr.s["paper_capital"] = 500000
    prices["AAA"] = 112.0                                                       # ran away while the money was being arranged
    with pytest.raises(UserError, match="Not allowed"):
        tr.start_buy("AAA")


def test_broker_side_margin_rejection_is_recorded_as_rejected(env):
    tr, prices, clock, paper, db = env
    real = paper.place
    paper.place = lambda *a, **k: (_ for _ in ()).throw(BrokerError("RMS: Insufficient funds")) if a[1] == "BUY" else real(*a, **k)
    with pytest.raises(UserError, match="margin"):
        tr.start_buy("AAA")
    assert pos(db, "AAA")["status"] == "rejected"


# ------------------------------------------------------------------ trades done outside the app
def test_outside_trade_is_managed_from_the_actual_fill_price_and_quantity(env):
    tr, prices, clock, paper, db = env
    prices["AAA"] = 104.0
    tr.adopt("AAA", 103.35, 20)                                                # actual fill from the broker's app
    p = pos(db, "AAA")
    assert p["status"] == "open" and p["source"] == "external" and p["qty"] == 20 and p["entry_price"] == 103.35
    assert p["stop"] == 92.0 and p["stop_kind"] == "pivot"                     # 5%+ below the entry: the pivot low
    assert paper.orders[p["sl_oid"]]["qty"] == 20 and paper.orders[p["sl_oid"]]["trigger"] == 92.0
    prices["AAA"] = 160.0                                                      # trade becomes profitable -> trailing takes over
    tr.eod_update("2026-09-28", {"AAA": (160.0, 150.0)})
    assert pos(db, "AAA")["stop"] == 128.0
    with pytest.raises(UserError, match="already being managed"):
        tr.adopt("AAA", 100, 5)


def test_outside_trade_needs_valid_numbers(env):
    tr, *_ = env
    with pytest.raises(UserError):
        tr.adopt("AAA", 0, 10)
    with pytest.raises(UserError):
        tr.adopt("AAA", "abc", 10)


# ------------------------------------------------------------------ the daily routine
def test_scheduler_runs_the_day_in_order(env):
    from scheduler import Scheduler
    tr, prices, clock, paper, db = env
    tr.s["auto_buy"] = True
    calls = []
    tr.signals.scan = lambda: calls.append("scan")
    tr.signals.closes = lambda held: ("2026-09-28", {"AAA": (150.0, 140.0), "BBB": (50.0, 49.0)})
    sc = Scheduler(tr)

    def at(h, m):
        clock.set(h, m)
        sc.last_try.clear()
        sc.tick()
        for t in threading.enumerate():
            if t.name in ("scan", "eod"):
                t.join(5)

    at(8, 45)
    assert calls == ["scan"]
    at(9, 10)
    assert calls == ["scan"]                                    # scanned once per day only
    assert tr.open_count() == 0
    at(9, 21)                                                   # auto-buy window
    join(tr)
    assert sorted(p["sym"] for p in tr.positions("open")) == ["AAA", "BBB"]
    at(9, 22)
    join(tr)
    assert db.one("SELECT COUNT(*) n FROM orders WHERE purpose='entry'")["n"] == 2   # no second round
    prices["AAA"] = 150.0
    at(18, 20)                                                  # evening: trailing stop from the official close
    assert pos(db, "AAA")["stop"] == 120.0
    assert db.get("eod_last") == "2026-09-28"


def test_scheduler_does_nothing_when_auto_buy_is_off_or_on_weekends(env):
    from scheduler import Scheduler
    tr, prices, clock, paper, db = env
    tr.signals.scan = lambda: None
    sc = Scheduler(tr)
    clock.set(9, 21)
    sc.tick()
    assert tr.open_count() == 0                                 # switch is off
    clock.t = clock.t + dt.timedelta(days=5)                    # Saturday
    tr.s["auto_buy"] = True
    sc.tick()
    assert tr.open_count() == 0
