"""Download and cache ~3.5 years of NSE data for the backtest: daily prices + band hits (PR zips),
legacy insider filings, XBRL insider filings and corporate actions. Everything lands in backtest/cache/
so a re-run only fetches what is missing."""
import datetime as dt, gzip, io, json, os, pickle, shutil, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import nse_live  # noqa: E402

CACHE = os.path.join(HERE, "cache")
START = dt.date(2022, 12, 1)          # price warm-up before the 3-year test window
FILING_START = dt.date(2023, 3, 1)    # 180-day insider-sale look-back before the first signal


def log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def _pickle(name, obj=None):
    p = os.path.join(CACHE, name)
    if obj is None:
        if os.path.exists(p):
            with open(p, "rb") as f:
                return pickle.load(f)
        return None
    with open(p + ".tmp", "wb") as f:
        pickle.dump(obj, f)
    os.replace(p + ".tmp", p)


# ---------------------------------------------------------------- prices
def _pr_day(d):
    """(prices frame, band-hit set) for one session from NSE's PR zip, or None if no session."""
    b = nse_live._get(f"https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip", tries=4)
    if not b:
        return d, None
    try:
        z = zipfile.ZipFile(io.BytesIO(b))
    except zipfile.BadZipFile:
        return d, None
    px, bh = None, set()
    for n in z.namelist():
        ln = n.lower()
        if ln.startswith("pd"):
            t = pd.read_csv(z.open(n), dtype={"SERIES": str, "SYMBOL": str}, encoding="latin-1")
            t.columns = [c.strip() for c in t.columns]
            t["SERIES"] = t.SERIES.astype(str).str.strip()
            t["SYMBOL"] = t.SYMBOL.astype(str).str.strip()
            t = t[t.SERIES.isin(nse_live.EQ_SERIES)]
            t = t.rename(columns={"SYMBOL": "sym", "SERIES": "ser", "OPEN_PRICE": "o", "HIGH_PRICE": "h", "LOW_PRICE": "l",
                                  "CLOSE_PRICE": "c", "PREV_CL_PR": "pc", "NET_TRDVAL": "val"})[["sym", "ser", "o", "h", "l", "c", "pc", "val"]]
            for c in ["o", "h", "l", "c", "pc", "val"]:
                t[c] = pd.to_numeric(t[c], errors="coerce")
            t = t[(t.c > 0)]
            pri = {s: i for i, s in enumerate(nse_live.EQ_SERIES)}
            t = t.assign(p=t.ser.map(pri)).sort_values(["sym", "p"]).drop_duplicates("sym").drop(columns="p")
            t.insert(0, "date", pd.Timestamp(d))
            px = t
        elif ln.startswith("bh"):
            try:
                t = pd.read_csv(z.open(n), encoding="latin-1"); t.columns = [c.strip() for c in t.columns]
                t = t[t.SERIES.astype(str).str.strip().isin(nse_live.EQ_SERIES)]
                bh = set(t.SYMBOL.astype(str).str.strip())
            except (ValueError, KeyError):
                pass
    return d, (None if px is None or px.empty else (px, bh))


def load_prices(end, start=START):
    store = _pickle("prices.pkl") or {}
    days = [start + dt.timedelta(i) for i in range((end - start).days + 1)]
    todo = [d for d in days if d.weekday() < 5 and (d not in store or (store[d] is None and d >= end - dt.timedelta(days=4)))]
    log(f"Prices: {len(store)} days cached, {len(todo)} to fetch")
    done = 0
    with ThreadPoolExecutor(8) as ex:
        for d, r in ex.map(_pr_day, todo):
            store[d] = r
            done += 1
            if done % 50 == 0:
                log(f"  prices {done}/{len(todo)}")
                _pickle("prices.pkl", store)
    _pickle("prices.pkl", store)
    have = sorted(d for d, r in store.items() if r is not None and start <= d <= end)
    cal = pd.DatetimeIndex([pd.Timestamp(d) for d in have])
    panel = pd.concat([store[d][0] for d in have], ignore_index=True)
    bh = {pd.Timestamp(d): store[d][1] for d in have}
    log(f"Prices ready: {len(cal)} sessions {cal[0]:%d %b %Y} -> {cal[-1]:%d %b %Y}, {panel.sym.nunique()} symbols")
    return cal, panel, bh


# ---------------------------------------------------------------- filings
def load_legacy(nse, end, start=FILING_START):
    store = _pickle("legacy.pkl") or {}
    end = min(end, nse_live.NEW_PIT_START - dt.timedelta(days=1))
    rows = []
    for a, b in nse_live._months(start, end):
        if (a, b) not in store:
            store[(a, b)] = nse.json(f"/api/corporates-pit?index=equities&from_date={a:%d-%m-%Y}&to_date={b:%d-%m-%Y}").get("data", [])
            log(f"  legacy filings {a:%b %Y}: {len(store[(a, b)])}")
            _pickle("legacy.pkl", store)
            time.sleep(0.7)
        rows += store[(a, b)]
    log(f"Legacy filings: {len(rows)} rows")
    return rows


def load_xbrl(nse, end):
    fc_dir = os.path.join(CACHE, "xbrl")
    os.makedirs(fc_dir, exist_ok=True)
    seed = os.path.join(HERE, "..", "data", "filings-seed.json.gz")
    if not os.path.exists(os.path.join(fc_dir, "filings.json.gz")) and os.path.exists(seed):
        shutil.copy(seed, os.path.join(fc_dir, "filings.json.gz"))
    fc = nse_live.FilingCache(fc_dir)
    lst = fc.filing_list(nse, nse_live.NEW_PIT_START, end, lambda m, p: None)
    log(f"XBRL filing list: {len(lst)} filings ({sum(u in fc.xml for u in lst.xmlFileName) if len(lst) else 0} cached)")
    rows = fc.details(lst, lambda m, p: log("  " + m), max_fails=80) if len(lst) else []
    fc.save()
    log(f"XBRL filings: {len(rows)} rows")
    return rows


def load_ca(nse, end, start=START):
    name = "ca.pkl" if start == START else f"ca_{start:%Y%m%d}_{end:%Y%m%d}.pkl"
    ca = _pickle(name)
    if ca is None or ca[0] < end:
        ca = (end, nse_live.corporate_actions(nse, start, end))
        _pickle(name, ca)
    log(f"Corporate actions: {len(ca[1])} split/bonus factors")
    return ca[1]


def load_all(end=None, start=START, filing_start=FILING_START):
    os.makedirs(CACHE, exist_ok=True)
    end = end or dt.date.today()
    cal, panel, bh = load_prices(end, start)
    nse = nse_live.NSE()
    ca = load_ca(nse, end, start)
    legacy = load_legacy(nse, end, filing_start)
    xbrl = load_xbrl(nse, end) if end >= nse_live.NEW_PIT_START else []
    return cal, panel, bh, ca, legacy, xbrl


if __name__ == "__main__":
    load_all()
