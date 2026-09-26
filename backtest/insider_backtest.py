"""Backtest: buy every 'Clean' insider-buying signal the screener would have shown, day by day, over the last 3 years.

Replay (as if the app were opened after every close):
  * A stock is a candidate on session D if it has core-rule insider buys (engine.py rules) disclosed in the last
    120 sessions and none of the screener's caution notes apply *as of D* (everything uses only data known by D).
  * Entry: Rs 50,000 at D's close if the close is at most 5% above the insiders' average buy price (below is fine).
  * One open position per stock. After an exit, the stock can be bought again only on a fresh insider signal.
  * Initial stop: the last confirmed pivot low below entry, but never more than 15% below entry.
  * Exit: a trailing stop (several methods compared); the stop only ever moves up.
Prices are split/bonus adjusted; costs of 0.15% per side are charged.
"""
import datetime as dt, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import bt_data  # noqa: E402
import engine  # noqa: E402
from engine import PROMO, DIRKMP, RULES, ENTITY, clean  # noqa: E402

CAPITAL = 50_000
COST = 0.0015            # per side: STT + brokerage + charges on delivery trades
ENTRY_BAND = 0.05        # close must be <= insider average * 1.05
MAX_SL = 0.15            # initial stop never wider than 15%
PIVOT_N = 3              # a pivot low is the lowest low of N bars either side
PIVOT_LOOKBACK = 60      # sessions to look back for the initial-stop pivot
WINDOW = RULES["window"]
YEARS = 3

METHODS = {
    "Percent trail 15%": ("pct", 0.15),
    "Percent trail 20%": ("pct", 0.20),
    "Percent trail 25%": ("pct", 0.25),
    "ATR chandelier 2.5x": ("atr", 2.5),
    "ATR chandelier 3x": ("atr", 3.0),
    "ATR chandelier 4x": ("atr", 4.0),
    "Pivot trail (2-bar)": ("pivot", 2),
    "Pivot trail (3-bar)": ("pivot", 3),
    "Pivot trail (5-bar)": ("pivot", 5),
}


# ---------------------------------------------------------------- signals (engine.run_scan, minus the "today" parts)
def build(cal, panel, bh, ca, legacy, xbrl):
    tx = engine.normalize(legacy, xbrl)
    P = engine.build_prices(cal, panel, bh, ca)
    qa, ea = engine.make_events(tx, PROMO, "promo", cal, P)
    qd, ed = engine.make_events(tx, DIRKMP, "dir", cal, P)
    sells = tx[(tx.txn_n == "sell") & (tx.mode_n == "marketsale")]
    ea["insider_sold"] = engine.window_sum(sells, ea, RULES["promo_sell_days"], PROMO) > 0
    ed["insider_sold"] = engine.window_sum(sells, ed, RULES["dir_sell_days"]) > 0
    ev = pd.concat([ea, ed], ignore_index=True)
    ev["mcap_rule"] = ev.sh_out * ev.c / 1e7
    ev["tradeable"] = ((ev.ser == "EQ") & (ev.med_val60 >= RULES["min_medval"]) & (ev.n_obs60 <= RULES["max_gap60"])
                       & (ev.band20 <= RULES["max_band20"]) & (ev.c >= RULES["min_price"]))
    ev["core"] = (ev.tradeable & ~ev.insider_sold & (ev.mcap_rule <= RULES["max_mcap_cr"])
                  & (ev.own_incr > RULES["min_own_incr"]) & ev.any_individual)
    q_all = pd.concat([qa, qd], ignore_index=True)
    return tx, P, ev, q_all, sells


def price_frames(P):
    P = P.sort_values(["sym", "di"])
    for c in ["o", "h", "l"]:
        P[c + "_adj"] = P[c] * P.mult
    out = {}
    for s, x in P.groupby("sym"):
        x = x.reset_index(drop=True)
        pc = x.c_adj.shift()
        tr = np.maximum(x.h_adj - x.l_adj, np.maximum((x.h_adj - pc).abs(), (x.l_adj - pc).abs()))
        x["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        out[s] = x
    return out


def known_idx(ts, cal):
    """Index of the first session at whose close a disclosure made at `ts` is known (disclosed by 15:30)."""
    close = cal + pd.Timedelta(hours=15, minutes=30)
    return close.searchsorted(ts, side="left")


def eligibility(ev, q_all, tx, sells, cal, frames, start_idx):
    """For every (stock, session) the screener would list: is it Clean and inside the 5% entry zone?
    Returns {sym: DataFrame[di, eligible, kmax, avg_adj, flags...]}."""
    ncal = len(cal)
    core = ev[ev.core].copy()
    core = core[core.t0 >= start_idx]
    promo_dir_sells = sells[sells.cat.isin(PROMO + DIRKMP)]
    out = {}
    for sym, evs in core.groupby("sym"):
        x = frames.get(sym)
        if x is None:
            continue
        evs = evs.sort_values("t0")
        txs = q_all[(q_all.sym == sym) & q_all.t0.isin(evs.t0)].sort_values("from_dt")
        mult_at = evs.groupby("t0").mult.first().to_dict()
        s_sells = promo_dir_sells[promo_dir_sells.sym == sym]
        s_sell_k = known_idx(s_sells.broadcast, cal)
        s_tx = tx[tx.sym == sym]
        row_at = dict(zip(x.di, range(len(x))))
        rows = []
        first, last = int(evs.t0.min()), min(ncal - 1, int(evs.t0.max()) + WINDOW - 1)
        cache = {}
        for D in range(first, last + 1):
            i = row_at.get(D)
            if i is None:           # did not trade that day
                continue
            ts = tuple(evs.t0[(evs.t0 <= D) & (evs.t0 > D - WINDOW)].unique())
            if not ts:
                continue
            k = max(ts)
            if ts not in cache:     # everything that depends only on the set of signals in the window
                g = evs[evs.t0.isin(ts)]
                t = txs[txs.t0.isin(ts)]
                qty, val = t.qty.sum(), t.value.sum()
                adj_qty = (t.qty / t.t0.map(mult_at).fillna(1.0)).sum()
                first_b = g.broadcast.min()
                other = s_tx[(s_tx.broadcast >= first_b - pd.Timedelta(days=90)) & ~s_tx.fid.isin(t.fid)]
                sale_before = bool(((other.txn_n == "sell") & (other.mode_n == "marketsale") & (other.broadcast <= first_b)).any())
                indiv_before = [p.bef_pct.iloc[0] for n, p in t.groupby("person", sort=False) if not ENTITY.search(clean(n).upper())]
                first_holding = all(b < 0.005 for b in indiv_before)
                cache[ts] = dict(value_cr=val / 1e7, avg_adj=val / adj_qty if adj_qty else np.nan, shout=g.sh_out.dropna().median(),
                                 first_b=first_b, sale_before=sale_before, first_holding=first_holding,
                                 persons="; ".join(sorted(clean(p).title() for p in t.person.unique())), company=g.company.iloc[-1])
            c = cache[ts]
            later_sale = bool(((s_sells.broadcast > c["first_b"]).values & (s_sell_k <= D)).any())
            close_raw, close_adj = float(x.c.iloc[i]), float(x.c_adj.iloc[i])
            mcap = c["shout"] * close_raw / 1e7 if c["shout"] else np.nan
            left = WINDOW - (D - k)
            flags = []
            if later_sale: flags.append("insider sold after signal")
            if c["value_cr"] < 0.25: flags.append("small ticket")
            if mcap > 5000: flags.append("5-10k cr band")
            if close_adj / c["avg_adj"] - 1 > 0.5: flags.append("far above insider price")
            if left <= 10: flags.append("window nearly over")
            if c["sale_before"]: flags.append("insiders sold before")
            if c["first_holding"]: flags.append("first personal holding")
            in_zone = close_adj <= c["avg_adj"] * (1 + ENTRY_BAND)
            rows.append(dict(di=D, i=i, kmax=k, avg_adj=c["avg_adj"], close_adj=close_adj, clean=not flags, in_zone=in_zone,
                             eligible=(not flags) and in_zone, flags="; ".join(flags), first_b=c["first_b"], value_cr=c["value_cr"],
                             mcap=mcap, persons=c["persons"], company=c["company"]))
        if rows:
            out[sym] = pd.DataFrame(rows)
    return out


# ---------------------------------------------------------------- trade simulation
def pivots_low(l, n):
    """Boolean array: l[j] is the lowest of l[j-n .. j+n] (confirmed n bars later)."""
    m = len(l)
    piv = np.zeros(m, bool)
    for j in range(n, m - n):
        w = l[j - n:j + n + 1]
        piv[j] = l[j] == w.min()
    return piv


MIN_SL = 0.0             # optional: ignore pivots closer than this to the entry price


def initial_stop(x, e, entry, piv):
    lo = x.l_adj.values
    for j in range(e - PIVOT_N, max(-1, e - PIVOT_LOOKBACK), -1):
        if piv[j] and lo[j] < entry * (1 - MIN_SL):
            return max(lo[j], entry * (1 - MAX_SL)), "pivot" if lo[j] >= entry * (1 - MAX_SL) else "15% cap"
    return entry * (1 - MAX_SL), "15% (no pivot)"


def run_trade(x, e, method, sale_k=None):
    """Simulate one trade entered at the close of row e. Returns (exit row, exit price, reason, stop0, stop0 kind)."""
    kind, p = method
    o, h, l, c, atr = (x[k].values for k in ["o_adj", "h_adj", "l_adj", "c_adj", "atr"])
    entry = c[e]
    piv3 = pivots_low(l, PIVOT_N)
    stop, skind = initial_stop(x, e, entry, piv3)
    stop0 = stop
    piv_t = pivots_low(l, int(p)) if kind == "pivot" else None
    hh, hc = h[e], c[e]
    di = x.di.values
    later = [k for k in (sale_k if sale_k is not None else []) if k > di[e]]
    sale_at = min(later) if later else 10 ** 9     # session at whose close the sale is known -> exit next open
    for i in range(e + 1, len(x)):
        if di[i] > sale_at:
            return i, o[i], "insider sale disclosed", stop0, skind
        if o[i] <= stop:
            return i, o[i], "stop (gap)", stop0, skind
        if l[i] <= stop:
            return i, stop, "stop" if stop <= stop0 else "trailing stop", stop0, skind
        hh, hc = max(hh, h[i]), max(hc, c[i])
        if kind == "pct":
            trail = hc * (1 - p)
        elif kind == "atr":
            trail = hh - p * atr[i] if np.isfinite(atr[i]) else -np.inf
        else:
            j = i - int(p)
            trail = l[j] if j > e and piv_t[j] else -np.inf
        stop = max(stop, trail)
    return len(x) - 1, c[-1], "open", stop0, skind


def simulate(elig, frames, method, sells_k=None):
    trades = []
    for sym, E in elig.items():
        x = frames[sym]
        last_exit_di = -1
        open_until = -1
        for r in E[E.eligible].itertuples():
            if r.di <= open_until:
                continue                                  # already holding this stock
            if last_exit_di >= 0 and r.kmax <= last_exit_di:
                continue                                  # re-entry needs a fresh insider signal
            e = r.i
            sk = sells_k.get(sym) if sells_k is not None else None
            xi, px, why, stop0, skind = run_trade(x, e, method, sk)
            entry = x.c_adj.iloc[e]
            ret = (px / entry) * (1 - COST) - (1 + COST)
            trades.append(dict(Symbol=sym, Company=r.company, Insiders=r.persons, **{
                "Signal disclosed": r.first_b, "Insider avg (adj)": r.avg_adj, "Entry date": x.date.iloc[e], "Entry": entry,
                "Entry vs insider %": (entry / r.avg_adj - 1) * 100, "Initial stop": stop0, "Stop type": skind,
                "Risk %": (1 - stop0 / entry) * 100, "Exit date": x.date.iloc[xi], "Exit": px, "Exit reason": why,
                "Sessions held": int(x.di.iloc[xi] - x.di.iloc[e]), "Return %": ret * 100, "P&L (Rs)": ret * CAPITAL,
                "Buy value (Rs cr)": r.value_cr, "Mcap (Rs cr)": r.mcap, "_e": e, "_x": xi}))
            open_until = int(x.di.iloc[xi]) if why != "open" else 10 ** 9
            last_exit_di = int(x.di.iloc[xi])
    return pd.DataFrame(trades)


def stats(T, frames, cal, start_idx):
    if T.empty:
        return {}
    closed = T[T["Exit reason"] != "open"]
    wins, losses = T[T["P&L (Rs)"] > 0], T[T["P&L (Rs)"] <= 0]
    # daily mark-to-market P&L of the whole book
    days = cal[start_idx:]
    pnl = pd.Series(0.0, index=days)
    npos = pd.Series(0, index=days)
    for t in T.to_dict("records"):
        x = frames[t["Symbol"]].iloc[t["_e"]:t["_x"] + 1]
        mtm = pd.Series(((x.c_adj / t["Entry"]) * (1 - COST) - (1 + COST)).values * CAPITAL, index=pd.DatetimeIndex(x.date.values))
        mtm.iloc[-1] = t["P&L (Rs)"]
        mtm = mtm.reindex(days).ffill().fillna(0.0)          # 0 before entry, realised P&L carried after exit
        pnl += mtm
        is_open = t["Exit reason"] == "open"
        npos += ((days >= t["Entry date"]) & ((days < t["Exit date"]) | is_open)).astype(int)
    dd = (pnl - pnl.cummax()).min()
    peak_cap = int(npos.max()) * CAPITAL
    yrs = (days[-1] - days[0]).days / 365.25
    gp, gl = wins["P&L (Rs)"].sum(), -losses["P&L (Rs)"].sum()
    return {"Trades": len(T), "Open now": int((T["Exit reason"] == "open").sum()), "Win rate %": len(wins) / len(T) * 100,
            "Avg return %": T["Return %"].mean(), "Avg win %": wins["Return %"].mean(), "Avg loss %": losses["Return %"].mean(),
            "Profit factor": gp / gl if gl else np.inf, "Total P&L (Rs)": T["P&L (Rs)"].sum(),
            "Realised P&L (Rs)": closed["P&L (Rs)"].sum(), "Open P&L (Rs)": T["P&L (Rs)"].sum() - closed["P&L (Rs)"].sum(),
            "Max drawdown (Rs)": dd, "Peak positions": int(npos.max()), "Peak capital (Rs)": peak_cap,
            "Return on peak capital %": T["P&L (Rs)"].sum() / peak_cap * 100 if peak_cap else np.nan,
            "CAGR on peak capital %": ((1 + T["P&L (Rs)"].sum() / peak_cap) ** (1 / yrs) - 1) * 100 if peak_cap else np.nan,
            "Avg sessions held": T["Sessions held"].mean(), "Best trade %": T["Return %"].max(), "Worst trade %": T["Return %"].min(),
            "_pnl": pnl, "_npos": npos}


def main(test_from=None, test_to=None):
    """Default: the last 3 years to today. With dates: signals from test_from, prices end at test_to
    (positions still open then are marked at that close)."""
    if test_from:
        cal, panel, bh, ca, legacy, xbrl = bt_data.load_all(end=test_to, start=test_from - dt.timedelta(days=150),
                                                            filing_start=test_from - dt.timedelta(days=210))
        start = pd.Timestamp(test_from)
    else:
        cal, panel, bh, ca, legacy, xbrl = bt_data.load_all()
        start = pd.Timestamp(cal[-1]) - pd.DateOffset(years=YEARS)
    bt_data.log("Building signals with the screener's rules")
    tx, P, ev, q_all, sells = build(cal, panel, bh, ca, legacy, xbrl)
    start_idx = int(cal.searchsorted(start))
    frames = price_frames(P)
    bt_data.log(f"Core events: {int(ev.core.sum())} total, {int((ev.core & (ev.t0 >= start_idx)).sum())} since {cal[start_idx]:%d %b %Y}")
    elig = eligibility(ev, q_all, tx, sells, cal, frames, start_idx)
    bt_data.log(f"Stocks with a core signal: {len(elig)}; ever Clean: {sum(E.clean.any() for E in elig.values())}; "
                f"ever Clean + in 5% zone: {sum(E.eligible.any() for E in elig.values())}")
    sells_k = {s: list(known_idx(g.broadcast, cal)) for s, g in sells[sells.cat.isin(PROMO + DIRKMP)].groupby("sym")}

    results, trades = {}, {}
    for name, m in METHODS.items():
        T = simulate(elig, frames, m)
        trades[name], results[name] = T, stats(T, frames, cal, start_idx)
        r = results[name]
        bt_data.log(f"{name:22s} trades {r['Trades']:3d}  win {r['Win rate %']:5.1f}%  PF {r['Profit factor']:5.2f}  "
                    f"P&L Rs {r['Total P&L (Rs)']:>10,.0f} (realised {r['Realised P&L (Rs)']:>9,.0f})  maxDD Rs {r['Max drawdown (Rs)']:>9,.0f}")
    # Best = highest *realised* P&L: unrealised gains on a handful of open trades should not pick the method
    best = max(METHODS, key=lambda k: (round(results[k]["Realised P&L (Rs)"], -3), results[k]["Total P&L (Rs)"]))
    alt = best + " + exit on insider sale"
    trades[alt] = simulate(elig, frames, METHODS[best], sells_k)
    results[alt] = stats(trades[alt], frames, cal, start_idx)
    global MIN_SL
    MIN_SL, sug = 0.05, best + " + min 5% initial stop"
    trades[sug] = simulate(elig, frames, METHODS[best])
    results[sug] = stats(trades[sug], frames, cal, start_idx)
    MIN_SL = 0.0
    for k in [best, alt, sug]:
        r = results[k]
        bt_data.log(f"{k}: P&L Rs {r['Total P&L (Rs)']:,.0f} (realised {r['Realised P&L (Rs)']:,.0f}), PF {r['Profit factor']:.2f}")

    # Signals that were Clean but never came within 5% of the insider price (skipped), for reference
    skipped = [dict(Symbol=s, Company=E.company.iloc[0], **{"Signal disclosed": E.first_b.iloc[0],
                    "Insider avg (adj)": E.avg_adj.iloc[0], "Closest %": (E.close_adj[E.clean] / E.avg_adj[E.clean] - 1).min() * 100})
               for s, E in elig.items() if E.clean.any() and not E.eligible.any()]
    out = dict(cal=cal, start_idx=start_idx, results=results, trades=trades, best=best, alt=alt, sug=sug,
               skipped=pd.DataFrame(skipped), n_core=int((ev.core & (ev.t0 >= start_idx)).sum()), n_stocks=len(elig),
               n_clean=sum(E.clean.any() for E in elig.values()), n_elig=sum(E.eligible.any() for E in elig.values()))
    save(out)
    return out


def save(out):
    res_dir = os.path.join(HERE, "results")
    os.makedirs(res_dir, exist_ok=True)
    summ = pd.DataFrame({k: {m: v for m, v in r.items() if not m.startswith("_")} for k, r in out["results"].items()}).T
    cal, si = out["cal"], out["start_idx"]
    path = os.path.join(res_dir, f"Clean_Insider_Backtest_{cal[si]:%Y-%m}_to_{cal[-1]:%Y-%m}.xlsx")
    with pd.ExcelWriter(path) as xw:
        summ.round(2).to_excel(xw, sheet_name="Summary")
        for name in [out["best"], out["sug"]]:
            T = out["trades"][name].drop(columns=["_e", "_x"]).copy()
            for c in ["Signal disclosed", "Entry date", "Exit date"]:
                T[c] = pd.to_datetime(T[c]).dt.tz_localize(None).dt.date
            T.round(2).to_excel(xw, sheet_name=("Trades - " + name)[:31], index=False)
        if len(out["skipped"]):
            S = out["skipped"].copy(); S["Signal disclosed"] = pd.to_datetime(S["Signal disclosed"]).dt.date
            S.round(2).to_excel(xw, sheet_name="Clean but skipped (>5%)", index=False)
    import pickle
    with open(os.path.join(bt_data.CACHE, f"bt_out_{cal[si]:%Y%m}_{cal[-1]:%Y%m}.pkl"), "wb") as f:
        pickle.dump(out, f)
    bt_data.log(f"Saved {path}")


if __name__ == "__main__":
    # python insider_backtest.py                        -> last 3 years
    # python insider_backtest.py 2019-01-01 2022-11-30  -> a fixed period
    args = [dt.date.fromisoformat(a) for a in sys.argv[1:3]]
    main(*args)
