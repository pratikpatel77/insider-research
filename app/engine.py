"""Signal engine: the exact rules from the Promoter Buying Study, applied to live NSE data."""
import datetime as dt, html, re, time

import numpy as np
import pandas as pd

import nse_live

RULES = dict(min_own_incr=5.0, max_mcap_cr=1e4, min_medval=1e7, min_price=10.0, max_band20=2, max_gap60=63,
             window=120, promo_sell_days=180, dir_sell_days=90, stale_days=120)
PROMO = ["Promoter", "Promoter Group", "Relative"]
DIRKMP = ["Director", "KMP"]
GROUP_NAME = {"promo": "Promoter / group / relative", "dir": "Director / KMP"}

CAT = {"Promoters": "Promoter", "Promoter": "Promoter", "Promoter and Director": "Promoter",
       "Promoter Group": "Promoter Group", "Immediate relative": "Relative", "Immediate Relative": "Relative",
       "Promoter Immediate Relative": "Relative", "Director": "Director", "Directors Immediate Relative": "Director",
       "Key Managerial Personnel": "KMP", "KMP": "KMP", "Employees/Designated Employees": "Employee",
       "Designated Person": "Employee", "Employee": "Employee", "Employees Immediate Relative": "Employee",
       "Other": "Other", "Trust": "Other", "Connected Person": "Other"}
ENTITY = re.compile(
    r"\b(LIMITED|LTD|PRIVATE|PVT|LLP|LLC|INC|PLC|GMBH|AG|BV|NV|SA|LP|TRUST|TRUSTEES?|CORPORATION|CORP|HOLDINGS?|INVESTMENTS?|"
    r"ENTERPRISES?|FOUNDATION|COMPANY|INDUSTRIES|VENTURES|CAPITAL|FINANCE|FINVEST|TRADING|TRADERS|SECURITIES|FAMILY|"
    r"PARTNERS|INTERNATIONAL|MANAGEMENT|INFRA|ESTATES?|AGENCIES|SERVICES|RESOURCES|PROPERTIES|FUND|SCHEME|AIF|BANK|"
    r"INSURANCE|MAURITIUS|EQUITIES|PROJECTS|MARKETING|EXPORTS?|OVERSEAS|GLOBAL|ASSOCIATES|SONS|BROTHERS|CO)\b")


def clean(s):
    return html.unescape(str(s)).replace("&AMP;", "&").strip()


def _num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(",", "").str.strip(), errors="coerce")


# ---------------------------------------------------------------- filings
def normalize(legacy_rows, xbrl_rows):
    parts = []
    if legacy_rows:
        d = pd.DataFrame(legacy_rows)
        parts.append(pd.DataFrame({
            "sym": d.symbol.str.strip(), "company": d.company, "person": d.acqName.str.strip().str.upper(),
            "cat_raw": d.personCategory, "mode": d.acqMode.fillna("-").str.strip(), "txn": d.tdpTransactionType.fillna("-").str.strip(),
            "sectype": d.secType.fillna("").str.strip().str.lower(), "qty": _num(d.secAcq).values, "value": _num(d.secVal).values,
            "bef_n": _num(d.befAcqSharesNo).values, "bef_pct": _num(d.befAcqSharesPer).values,
            "aft_n": _num(d.afterAcqSharesNo).values, "aft_pct": _num(d.afterAcqSharesPer).values,
            "from_dt": pd.to_datetime(d.acqfromDt, format="%d-%b-%Y", errors="coerce"),
            "to_dt": pd.to_datetime(d.acqtoDt, format="%d-%b-%Y", errors="coerce"),
            "broadcast": pd.to_datetime(d.date, format="%d-%b-%Y %H:%M", errors="coerce"),
            "exch": d.exchange, "fid": "L" + d.pid.astype(str)}))
    if xbrl_rows:
        d = pd.DataFrame(xbrl_rows)
        g = lambda c: d[c] if c in d else pd.Series([None] * len(d))
        parts.append(pd.DataFrame({
            "sym": d.listSymbol.fillna(g("Symbol")).astype(str).str.strip(), "company": g("NameOfTheCompany"),
            "person": g("NameOfThePerson").fillna("").astype(str).str.strip().str.upper(), "cat_raw": g("CategoryOfPerson"),
            "mode": g("ModeOfAcquisitionOrDisposal").fillna("-").astype(str).str.strip(),
            "txn": g("SecuritiesAcquiredOrDisposedTransactionType").fillna("-").astype(str),
            "sectype": g("TypeOfInstrument").fillna("").astype(str).str.lower(),
            "qty": _num(g("SecuritiesAcquiredOrDisposedNumberOfSecurity")).values,
            "value": _num(g("SecuritiesAcquiredOrDisposedValueOfSecurity")).values,
            "bef_n": _num(g("SecuritiesHeldPriorToAcquisitionOrDisposalNumberOfSecurity")).values,
            "bef_pct": _num(g("SecuritiesHeldPriorToAcquisitionOrDisposalPercentageOfShareholding")).values * 100,
            "aft_n": _num(g("SecuritiesHeldPostAcquistionOrDisposalNumberOfSecurity")).values,
            "aft_pct": _num(g("SecuritiesHeldPostAcquistionOrDisposalPercentageOfShareholding")).values * 100,
            "from_dt": pd.to_datetime(g("DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyFromDate"), errors="coerce"),
            "to_dt": pd.to_datetime(g("DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyToDate"), errors="coerce"),
            "broadcast": pd.to_datetime(d.broadcast, format="%d-%b-%Y %H:%M:%S", errors="coerce"),
            "exch": g("ExchangeOnWhichTheTradeWasExecuted"), "fid": "X" + d.appId.astype(str) + "_" + d.ctx}))
    t = pd.concat(parts, ignore_index=True)
    t["cat"] = t.cat_raw.map(CAT)
    cr = t.cat_raw.fillna("").astype(str).str.lower()
    t.loc[t.cat.isna() & cr.str.contains("promoter") & cr.str.contains("group|member"), "cat"] = "Promoter Group"
    t.loc[t.cat.isna() & cr.str.contains("promoter") & cr.str.contains("relative"), "cat"] = "Relative"
    t.loc[t.cat.isna() & cr.str.contains("promoter"), "cat"] = "Promoter"
    t["cat"] = t.cat.fillna("Other")
    t.loc[t.person.str.contains(r"ESOP|ESPS|EMPLOYEE|WELFARE TRUST|BENEFIT TRUST|ESOS", regex=True), "cat"] = "Other"
    t["is_equity"] = t.sectype.str.contains("equit|^shares", regex=True)
    t["mode_n"] = t["mode"].str.lower().str.replace(r"[^a-z]", "", regex=True)
    t["txn_n"] = t.txn.str.lower()
    t["price"] = t.value / t.qty
    key = ["sym", "person", "from_dt", "to_dt", "qty", "txn_n", "mode_n"]
    return t.sort_values("broadcast").drop_duplicates(key, keep="first").reset_index(drop=True)


# ---------------------------------------------------------------- prices
def build_prices(cal, panel, bh, ca):
    """Per-symbol daily frame with split-adjusted returns and the trailing stats the rules use."""
    pos = {d: i for i, d in enumerate(cal)}
    P = panel.copy()
    P["di"] = P.date.map(pos).astype(int)
    P = P.sort_values(["sym", "di"]).reset_index(drop=True)
    g = P.groupby("sym")
    prevc = g.c.shift()
    base = P.pc.where(P.pc > 0, prevc)
    P["ret"] = (P.c / base - 1)
    if len(ca):
        ca = ca.sort_values("ex").assign(ex=lambda x: x.ex.astype("datetime64[ns]"))
        tmp = P[["date", "sym"]].assign(d2=P.date).sort_values("date")
        tmp["date"] = tmp.date.astype("datetime64[ns]")
        hit = pd.merge_asof(ca.rename(columns={"ex": "date"}), tmp, on="date", by="sym", direction="forward", tolerance=pd.Timedelta(days=7))
        hit = hit.dropna(subset=["d2"]).groupby(["sym", "d2"]).f.prod().reset_index().rename(columns={"d2": "date"})
        P = P.merge(hit, on=["sym", "date"], how="left")
        ratio = P.pc / prevc
        need = P.f.notna() & ((ratio - 1).abs() < 0.03)
        P.loc[need, "ret"] = P.c / (P.pc * P.f) - 1
        P = P.drop(columns="f")
    ratios = np.array([1/2, 1/3, 1/4, 1/5, 1/10, 1/20, 2/3, 3/4, 4/5, 5/6, 1/1.5, 2/5, 1/2.5, 3/5, 1/6, 1/8, 1/100, 1/50, 1/25])
    res = (P.ret <= -0.3).values
    if res.any():
        rr = (P.c / P.pc).values[res]
        fb = ratios[np.abs(np.log(rr[:, None] / ratios[None, :])).argmin(1)]
        P.loc[res, "ret"] = P.c.values[res] / (P.pc.values[res] * fb) - 1
    P.loc[prevc.isna(), "ret"] = 0.0
    P["ret"] = P.ret.clip(-0.6, 1.5)
    g = P.groupby("sym")
    P["tri"] = (1 + P.ret).groupby(P.sym).cumprod()
    last = g.tri.transform("last"); lastc = g.c.transform("last")
    P["mult"] = (P.tri / last * lastc) / P.c            # raw price at that date -> today's share units
    P["c_adj"] = P.c * P.mult
    P["band"] = [s in bh.get(d, ()) for s, d in zip(P.sym, P.date)]
    g = P.groupby("sym")
    P["med_val60"] = g.val.transform(lambda s: s.rolling(60, min_periods=40).median())
    P["n_obs60"] = P.di - g.di.shift(59)
    P["band20"] = g.band.transform(lambda s: s.astype(int).rolling(20, min_periods=1).sum())
    P["hi250"] = g.c_adj.transform(lambda s: s.rolling(250, min_periods=60).max())
    return P


def _asof(P, q):
    """Values at (symbol, session) from the latest row at or before that session; series only if it traded that day."""
    q = q.reset_index(drop=True).assign(_o=np.arange(len(q)), di=lambda x: x.di.astype("int64"))
    Pv = P.drop(columns=["ser"]).assign(di=P.di.astype("int64")).sort_values("di")
    r = pd.merge_asof(q.sort_values("di"), Pv, on="di", by="sym", direction="backward").sort_values("_o").reset_index(drop=True)
    r["ser"] = q.merge(P[["sym", "di", "ser"]].assign(di=P.di.astype("int64")), on=["sym", "di"], how="left").ser.values
    return r


# ---------------------------------------------------------------- signals
def t0_index(broadcast, cal):
    n = len(cal)
    bd = broadcast.dt.normalize()
    pos = cal.searchsorted(bd, side="left")
    same = (pos < n) & (cal[np.minimum(pos, n - 1)] == bd) & (broadcast.dt.hour < 9)
    return np.where(same, pos, cal.searchsorted(bd, side="right"))


def make_events(tx, cats, group, cal, P):
    q = tx[(tx.txn_n == "buy") & (tx.mode_n == "marketpurchase") & tx.is_equity & tx.cat.isin(cats)
           & (tx.qty > 0) & (tx.value > 0) & tx.broadcast.notna()].copy()
    if q.empty:
        return q, pd.DataFrame()
    q["t0"] = t0_index(q.broadcast, cal)
    q = q[q.t0 >= 61].copy()
    lo, hi = [], []
    by = {s: g for s, g in P.groupby("sym")}
    for s, a_dt, b_dt, t0 in zip(q.sym, q.from_dt.fillna(q.broadcast), q.to_dt.fillna(q.broadcast), q.t0):
        x = by.get(s)
        if x is None:
            lo.append(np.nan); hi.append(np.nan); continue
        a = cal.searchsorted(a_dt.normalize()); b = cal.searchsorted(b_dt.normalize(), side="right") - 1
        a = int(max(0, min(a, t0 - 1))); b = int(max(a, min(b, t0 - 1)))
        w = x[(x.di >= a) & (x.di <= b)]
        lo.append(w.l.min() if len(w) else np.nan); hi.append(w.h.max() if len(w) else np.nan)
    q["lo"], q["hi"] = lo, hi
    ok = (q.price >= 0.8 * q.lo) & (q.price <= 1.2 * q.hi)
    for f in [1e5, 1e7, 1e3, 1e2]:
        fix = ~ok & (q.price * f >= 0.8 * q.lo) & (q.price * f <= 1.2 * q.hi)
        q.loc[fix, "value"] *= f; q.loc[fix, "price"] *= f; ok |= fix
    q = q[ok & ((q.broadcast - q.to_dt).dt.days <= RULES["stale_days"])].copy()
    q["sh_out"] = np.where((q.aft_pct > 0.01) & (q.aft_n > 0), q.aft_n / (q.aft_pct / 100), np.nan)
    rows = []
    for (s, t), g in q.groupby(["sym", "t0"]):
        pp = g.groupby("person").agg(bef=("bef_n", "min"))
        rows.append({"group": group, "sym": s, "t0": int(t), "company": clean(g.company.iloc[-1]).title(),
                     "broadcast": g.broadcast.min(), "value": g.value.sum(), "qty": g.qty.sum(), "n_persons": g.person.nunique(),
                     "persons": "; ".join(sorted(g.person.unique())), "sh_out": g.sh_out.median(),
                     "own_bef": pp.bef.fillna(0).sum()})
    ev = pd.DataFrame(rows)
    ev["own_incr"] = np.where(ev.own_bef > 0, ev.qty / ev.own_bef * 100, np.nan)
    ev["val_cr"] = ev.value / 1e7
    ev["avg_price"] = ev.value / ev.qty
    ev["n_entity"] = ev.persons.str.split("; ").apply(lambda ps: sum(bool(ENTITY.search(clean(p).upper())) for p in ps if p))
    ev["any_individual"] = ev.n_entity < ev.n_persons
    f = _asof(P[["sym", "di", "date", "ser", "c", "med_val60", "n_obs60", "band20", "mult"]], ev[["sym"]].assign(di=ev.t0 - 1))
    for c in ["ser", "c", "med_val60", "n_obs60", "band20", "mult"]:
        ev[c] = f[c].values
    return q, ev


def window_sum(sells, ev, days, cats=None):
    d = sells if cats is None else sells[sells.cat.isin(cats)]
    by = {k: v for k, v in d[["sym", "broadcast", "value"]].dropna().groupby("sym")}
    out = []
    for s, b in zip(ev.sym, ev.broadcast):
        x = by.get(s)
        out.append(0.0 if x is None else x.loc[(x.broadcast < b) & (x.broadcast >= b - pd.Timedelta(days=days)), "value"].sum())
    return np.array(out)


def why_not(r):
    w = []
    if not r.tradeable:
        w.append("illiquid / trade-to-trade / circuit-bound" if r.ser == "EQ" else "not in EQ series (trade-to-trade or not traded)")
    if r.insider_sold: w.append("insider selling in look-back")
    if r.mcap_cr > RULES["max_mcap_cr"]: w.append("market cap > Rs 10,000 cr")
    if r.tiny_stake: w.append("buyer's stake under 0.01% of the company")
    if not (r.own_incr > RULES["min_own_incr"]): w.append("adds < 5% to own holding")
    if not r.any_individual: w.append("buyer is a company/holding entity")
    return "; ".join(w)


def run_scan(progress, prices, filings, nse=None):
    t_start = time.time()
    nse = nse or nse_live.NSE()
    progress("Connecting to NSE", 2)
    today = dt.date.today()
    cal, panel, bh = prices.load(260, progress)
    if len(cal) < 150:
        raise RuntimeError("Could not load enough NSE price history. Check your internet connection and try again.")
    sig_start = (cal[-RULES["window"] - 1] - pd.Timedelta(days=10)).date()
    look_start = sig_start - dt.timedelta(days=RULES["promo_sell_days"] + 5)
    progress("Reading NSE corporate actions (splits, bonuses)", 56)
    ca = nse_live.corporate_actions(nse, cal[0].date(), today)
    progress("Reading NSE insider filings", 58)
    legacy = filings.legacy(nse, look_start, today, lambda m, p: progress(m, 60)) if look_start < nse_live.NEW_PIT_START else []
    lst = filings.filing_list(nse, look_start, today, lambda m, p: progress(m, 62))
    xbrl = []
    if len(lst):
        lst["bdt"] = pd.to_datetime(lst.broadcastDateTime, format="%d-%b-%Y %H:%M:%S", errors="coerce")
        recent = lst[lst.bdt >= pd.Timestamp(sig_start)]
        xbrl = filings.details(recent, progress, base=62, span=20)
        tmp = normalize([], xbrl) if xbrl else pd.DataFrame()
        cand = set(tmp[(tmp.txn_n == "buy") & (tmp.mode_n == "marketpurchase")].sym) if len(tmp) else set()
        older = lst[(lst.bdt < pd.Timestamp(sig_start)) & lst.symbol.isin(cand)]
        if len(older):
            xbrl += filings.details(older, progress, base=82, span=5)
    progress("Applying the rules", 88)
    tx = normalize(legacy, xbrl)
    P = build_prices(cal, panel, bh, ca)
    ncal = len(cal)
    qa, ea = make_events(tx, PROMO, "promo", cal, P)
    qd, ed = make_events(tx, DIRKMP, "dir", cal, P)
    sells = tx[(tx.txn_n == "sell") & (tx.mode_n == "marketsale")]
    parts = []
    if len(ea):
        ea["insider_sold"] = window_sum(sells, ea, RULES["promo_sell_days"], PROMO) > 0
        parts.append(ea)
    if len(ed):
        ed["insider_sold"] = window_sum(sells, ed, RULES["dir_sell_days"]) > 0
        parts.append(ed)
    ev = pd.concat(parts, ignore_index=True)
    # As in the backtest, the rule's market cap comes from the filing itself (shares held / % held). When every
    # buyer holds < 0.01% the filing can't give it, and the backtest treated such buys as not qualifying.
    ev["mcap_rule"] = ev.sh_out * ev.c / 1e7
    mc = prices.mcap[1] if prices.mcap else pd.Series(dtype=float)
    ev["mcap_cr"] = ev.mcap_rule.fillna(ev.sym.map(mc) * ev.c / 1e7)
    ev["tiny_stake"] = ev.sh_out.isna()
    ev["tradeable"] = ((ev.ser == "EQ") & (ev.med_val60 >= RULES["min_medval"]) & (ev.n_obs60 <= RULES["max_gap60"])
                       & (ev.band20 <= RULES["max_band20"]) & (ev.c >= RULES["min_price"]))
    ev["core"] = (ev.tradeable & ~ev.insider_sold & (ev.mcap_rule <= RULES["max_mcap_cr"])
                  & (ev.own_incr > RULES["min_own_incr"]) & ev.any_individual)
    ev["in_window"] = ev.t0 >= ncal - RULES["window"]
    ev = ev[ev.broadcast >= pd.Timestamp(sig_start)]
    q_all = pd.concat([qa, qd], ignore_index=True)
    progress("Building the watchlist", 94)
    out = assemble(ev, q_all, tx, P, cal, sells)
    out["meta"] = {"as_of": cal[-1].strftime("%d %b %Y"), "run_at": dt.datetime.now().strftime("%d %b %Y, %H:%M"),
                   "filings": int(len(tx)), "seconds": round(time.time() - t_start),
                   "latest_filing": tx.broadcast.max().strftime("%d %b %Y, %H:%M") if len(tx) else "-",
                   "window_from": cal[max(0, ncal - RULES["window"])].strftime("%d %b %Y")}
    progress("Done", 100)
    return out


def assemble(ev, q_all, tx, P, cal, sells):
    ncal = len(cal)
    last = P.sort_values("di").groupby("sym").tail(1).set_index("sym")
    core = ev[ev.core & ev.in_window]
    rows, txrows, other_rows = [], [], []
    for sym, g in core.groupby("sym"):
        k = int(g.t0.max())
        left = min(RULES["window"], RULES["window"] - (ncal - 1 - k))
        t = q_all[(q_all.sym == sym) & q_all.t0.isin(g.t0)].sort_values("from_dt")
        lp = last.loc[sym] if sym in last.index else None
        qty, val = t.qty.sum(), t.value.sum()
        avg_raw = val / qty if qty else np.nan
        mult = g.mult.iloc[-1] if pd.notna(g.mult.iloc[-1]) else 1.0
        avg_now_units = avg_raw * mult
        shout = g.sh_out.dropna().median()
        people = []
        for p, x in t.groupby("person", sort=False):
            people.append({"name": clean(p).title(), "cat": str(x.cat_raw.iloc[0]), "before": x.bef_pct.iloc[0], "after": x.aft_pct.iloc[-1],
                           "entity": bool(ENTITY.search(clean(p).upper()))})
        first_b = g.broadcast.min()
        later_sales = sells[(sells.sym == sym) & (sells.broadcast > first_b) & sells.cat.isin(PROMO + DIRKMP)]
        lo = first_b - pd.Timedelta(days=90)
        o = tx[(tx.sym == sym) & (tx.broadcast >= lo) & ~tx.fid.isin(t.fid)]
        sale_before = o[(o.txn_n == "sell") & (o.mode_n == "marketsale") & (o.broadcast <= first_b)]
        c_last = float(lp.c) if lp is not None else np.nan
        row = {
            "sym": sym, "company": g.company.iloc[-1], "groups": sorted(set(GROUP_NAME[x] for x in g.group)), "people": people,
            "first_trade": t.from_dt.min(), "last_trade": t.to_dt.max(), "first_disclosed": first_b, "last_disclosed": g.broadcast.max(),
            "filings": int(len(t)), "shares": int(qty), "value_cr": val / 1e7, "avg_price": avg_raw,
            "own_incr": float(g.own_incr.max()), "pct_company": qty / shout * 100 if shout else np.nan,
            "mcap_cr": shout * c_last / 1e7 if shout and np.isfinite(c_last) else np.nan,
            "close": c_last, "vs_insider": (c_last / avg_now_units - 1) * 100 if avg_now_units else np.nan,
            "from_high": (float(lp.c_adj) / float(lp.hi250) - 1) * 100 if lp is not None and pd.notna(lp.hi250) else np.nan,
            "liq_cr": float(lp.med_val60) / 1e7 if lp is not None and pd.notna(lp.med_val60) else np.nan,
            "sessions_left": int(left), "pending": bool(k >= ncal),
            "exit_warning": len(later_sales) > 0,
            "exit_detail": "; ".join(f"{clean(r.person).title()} ({r.cat}) sold Rs {r.value / 1e7:.2f} cr, disclosed {r.broadcast:%d %b}" for r in later_sales.itertuples()),
            "other": [],
        }
        notes = []
        if row["exit_warning"]: notes.append("Insider sold after the signal: exit rule")
        if row["value_cr"] < 0.25: notes.append("Small ticket (< Rs 25 lakh): weaker history")
        if row["mcap_cr"] > 5000: notes.append("Rs 5–10k cr band: weaker history")
        if row["vs_insider"] > 50: notes.append("Already far above insider price")
        if row["sessions_left"] <= 10: notes.append("Watch window nearly over")
        if len(sale_before): notes.append("Other insiders sold before the signal: check")
        if all(p["before"] < 0.005 for p in people if not p["entity"]): notes.append("First personal holding for the buyer(s)")
        row["notes"] = notes
        for r in o.sort_values("broadcast").itertuples():
            row["other"].append({"date": r.broadcast.strftime("%d %b %Y"), "person": clean(r.person).title(), "cat": str(r.cat_raw),
                                 "type": f"{r.txn} / {r.mode}", "shares": None if pd.isna(r.qty) else int(r.qty),
                                 "value_cr": None if pd.isna(r.value) else r.value / 1e7})
        rows.append(row)
        for r in t.itertuples():
            txrows.append({"Symbol": sym, "Company": row["company"], "Insider": clean(r.person).title(), "Category": r.cat_raw,
                           "Trade from": r.from_dt.date() if pd.notna(r.from_dt) else None, "Trade to": r.to_dt.date() if pd.notna(r.to_dt) else None,
                           "Disclosed": r.broadcast.strftime("%Y-%m-%d %H:%M"), "Mode": r.mode, "Shares": r.qty, "Price": round(r.price, 2),
                           "Value (Rs)": r.value, "Held before": r.bef_n, "Before %": r.bef_pct, "Held after": r.aft_n, "After %": r.aft_pct})
        for x in row["other"]:
            other_rows.append({"Symbol": sym, **x})
    rows.sort(key=lambda r: r["last_disclosed"], reverse=True)
    near = ev[~ev.core & ev.in_window & (ev.val_cr >= 1)].copy()
    near["why"] = near.apply(why_not, axis=1)
    near = near.sort_values("value", ascending=False).drop_duplicates("sym")
    near_rows = [{"sym": r.sym, "company": r.company, "group": GROUP_NAME[r.group], "buyers": clean(r.persons).title()[:160],
                  "value_cr": r.val_cr, "own_incr": r.own_incr, "mcap_cr": r.mcap_cr, "disclosed": r.broadcast, "why": r.why}
                 for r in near.head(40).itertuples()]
    return {"signals": rows, "near": near_rows, "tx": pd.DataFrame(txrows), "other": pd.DataFrame(other_rows)}
