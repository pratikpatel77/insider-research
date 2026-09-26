"""Signal source: runs the repo's screener (app/engine.py: the same rules as the backtest) and turns its output into
buy candidates. Also fetches official daily closes for the trailing-stop update."""
import datetime as dt, json, math, os, shutil, sys, threading

import config

APP = str(config.REPO / "app")
if APP not in sys.path:
    sys.path.append(APP)          # last, so the trader's own modules always win a name clash (app/ has its own ui.py)

SCAN_FILE = "scan.json"
LOWS_KEPT = 75


def _iso(ts):
    try:
        return ts.strftime("%Y-%m-%d %H:%M")
    except AttributeError:
        return str(ts)


def _segment(closes, lows):
    """Drop everything before the last split/bonus-sized jump so pivot lows are in one price basis."""
    start = 0
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and not (1 / 1.6 <= closes[i] / closes[i - 1] <= 1.6):
            start = i
    return lows[start:]


class SignalSource:
    def __init__(self, db):
        self.db = db
        self.lock = threading.Lock()
        self.prices = self.filings = None
        self.progress_msg, self.running, self.error = "", False, None

    def _init(self):
        if self.prices is None:
            import nse_live
            cache = config.DATA / "nse_cache"
            cache.mkdir(parents=True, exist_ok=True)
            seed, dest = config.REPO / "data" / "filings-seed.json.gz", cache / "filings.json.gz"
            if seed.exists() and not dest.exists():
                shutil.copy(seed, dest)                     # saves downloading ~2,900 filings on the first run
            self.prices, self.filings = nse_live.PriceCache(), nse_live.FilingCache(str(cache))

    def _progress(self, msg, pct):
        self.progress_msg = f"{msg} ({int(pct)}%)"

    # ---------------------------------------------------------------- scan
    def scan(self):
        """Run the screener now. Returns the candidate list and saves it to data/scan.json."""
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("A scan is already running")
        try:
            self.running, self.error = True, None
            self._init()
            import engine
            res = engine.run_scan(self._progress, self.prices, self.filings)
            self.filings.save(prune=True)
            cands = [self._candidate(s) for s in res["signals"]]
            out = {"scanned_at": config.now().strftime("%Y-%m-%d %H:%M"), "scanned_on": config.now().strftime("%Y-%m-%d"),
                   "as_of": res["meta"]["as_of"], "candidates": cands}
            tmp = config.DATA / (SCAN_FILE + ".tmp")
            tmp.write_text(json.dumps(out, default=str), encoding="utf-8")
            os.replace(tmp, config.DATA / SCAN_FILE)
            return out
        except Exception as e:
            self.error = str(e) or e.__class__.__name__
            raise
        finally:
            self.running = False
            self.lock.release()

    def _candidate(self, s):
        vs = s.get("vs_insider")
        close = s.get("close")
        avg_now = close / (1 + vs / 100) if close and vs is not None and math.isfinite(vs) and vs > -99 else None
        lows = self._lows(s["sym"])
        return {"sym": s["sym"], "company": s["company"], "key": f"{s['sym']}|{_iso(s['last_disclosed'])}",
                "last_disclosed": _iso(s["last_disclosed"]), "first_disclosed": _iso(s["first_disclosed"]), "value_cr": s["value_cr"],
                "avg_now": avg_now, "close": close, "vs_insider": vs, "notes": list(s["notes"]), "clean": not s["notes"],
                "pending": bool(s["pending"]), "sessions_left": s["sessions_left"], "lows": lows}

    def _lows(self, sym):
        rows = []
        for d in sorted(self.prices.px):
            f = self.prices.px[d]
            if f is not None:
                r = f[f.sym == sym]
                if len(r):
                    rows.append((float(r.l.iloc[0]), float(r.c.iloc[0])))
        rows = rows[-LOWS_KEPT:]
        return [round(x, 2) for x in _segment([c for _, c in rows], [l for l, _ in rows])]

    @staticmethod
    def load():
        p = config.DATA / SCAN_FILE
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        return None

    # ---------------------------------------------------------------- closes for the trailing stop
    def closes(self, syms):
        """Official NSE closes from the latest bhavcopy: (trade date 'YYYY-MM-DD', {sym: (close, low)})."""
        self._init()
        self.prices.load(260, lambda m, p: None)
        for d in sorted((d for d, f in self.prices.px.items() if f is not None), reverse=True)[:1]:
            f = self.prices.px[d]
            f = f[f.sym.isin(list(syms))]
            return d.strftime("%Y-%m-%d"), {r.sym: (float(r.c), float(r.l)) for r in f.itertuples()}
        return None, {}
