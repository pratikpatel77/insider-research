"""Live data access to official NSE sources. Everything is kept in memory; nothing is written to disk."""
import calendar, datetime as dt, io, re, time, zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HDR = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9",
       "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading"}
NEW_PIT_START = dt.date(2026, 5, 3)   # NSE moved insider filings to per-filing XBRL on this date
EQ_SERIES = ["EQ", "BE", "BZ", "SM", "ST", "SZ"]


class NSE:
    """Cookie-backed session for www.nseindia.com JSON endpoints."""

    def __init__(self):
        self._new()

    def _new(self):
        self.s = requests.Session()
        self.s.headers.update(HDR)
        try:
            self.s.get("https://www.nseindia.com/companies-listing/corporate-filings-insider-trading", timeout=30)
        except requests.RequestException:
            pass

    def json(self, path, tries=5):
        for k in range(tries):
            try:
                r = self.s.get("https://www.nseindia.com" + path, timeout=90)
                if r.status_code == 200:
                    return r.json()
            except (requests.RequestException, ValueError):
                pass
            time.sleep(2 * (k + 1))
            self._new()
        raise RuntimeError(f"NSE did not respond for {path.split('?')[0]}. Check your internet connection and try again.")


def _get(url, tries=4):
    for k in range(tries):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=40)
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        time.sleep(1.5 * (k + 1))
    return None


def _months(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        a = max(start, dt.date(y, m, 1))
        b = min(end, dt.date(y, m, calendar.monthrange(y, m)[1]))
        yield a, b
        m += 1
        if m == 13:
            y, m = y + 1, 1


# ---------------------------------------------------------------- prices
class PriceCache:
    """Daily bhavcopy + band-hit files, cached in memory for the life of the app."""

    def __init__(self):
        self.px, self.bh, self.mcap = {}, {}, None

    def _bhav(self, d):
        b = _get(f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip")
        if not b:
            return None
        z = zipfile.ZipFile(io.BytesIO(b))
        df = pd.read_csv(z.open(z.namelist()[0]))
        df = df[(df.FinInstrmTp == "STK") & df.SctySrs.isin(EQ_SERIES) & ~df.ISIN.astype(str).str.startswith("INF")]
        df = df.rename(columns={"TckrSymb": "sym", "SctySrs": "ser", "OpnPric": "o", "HghPric": "h", "LwPric": "l",
                                "ClsPric": "c", "PrvsClsgPric": "pc", "TtlTrfVal": "val"})[["sym", "ser", "o", "h", "l", "c", "pc", "val"]]
        pri = {s: i for i, s in enumerate(EQ_SERIES)}
        df = df.assign(p=df.ser.map(pri)).sort_values(["sym", "p"]).drop_duplicates("sym").drop(columns="p")
        df.insert(0, "date", pd.Timestamp(d))
        return df

    def _pr(self, d):
        b = _get(f"https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip")
        out = {}
        if not b:
            return out
        try:
            z = zipfile.ZipFile(io.BytesIO(b))
            for n in z.namelist():
                ln = n.lower()
                if ln.startswith("bh"):
                    t = pd.read_csv(z.open(n)); t.columns = [c.strip() for c in t.columns]
                    t = t[t.SERIES.astype(str).str.strip().isin(EQ_SERIES)]
                    out["bh"] = set(t.SYMBOL.astype(str).str.strip())
                if ln.startswith("mcap"):
                    t = pd.read_csv(z.open(n)); t.columns = [c.strip() for c in t.columns]
                    t = t.rename(columns={"Symbol": "sym", "Series": "ser", "Issue Size": "shares"})
                    t["sym"] = t.sym.astype(str).str.strip()
                    out["mcap"] = t[t.ser.astype(str).str.strip() == "EQ"].set_index("sym").shares
        except (zipfile.BadZipFile, KeyError, ValueError):
            pass
        return out

    def load(self, sessions, progress):
        """Make sure the last `sessions` trading days are loaded. Returns (calendar, long price frame, band-hit dict)."""
        today = dt.date.today()
        days = [today - dt.timedelta(i) for i in range(int(sessions * 1.5) + 20)]
        days = [d for d in days if d.weekday() < 5]
        todo = [d for d in days if d not in self.px]
        done = 0
        with ThreadPoolExecutor(8) as ex:
            for d, df in zip(todo, ex.map(self._bhav, todo)):
                self.px[d] = df
                done += 1
                if done % 20 == 0:
                    progress(f"Downloading NSE daily prices ({done}/{len(todo)})", 20 + 25 * done / max(1, len(todo)))
        have = sorted([d for d in self.px if self.px[d] is not None], reverse=True)[:sessions]
        cal = sorted(have)
        need_pr = [d for d in cal[-150:] if d not in self.bh]
        done = 0
        with ThreadPoolExecutor(8) as ex:
            for d, r in zip(need_pr, ex.map(self._pr, need_pr)):
                self.bh[d] = r.get("bh", set())
                if "mcap" in r and (self.mcap is None or d >= self.mcap[0]):
                    self.mcap = (d, r["mcap"])
                done += 1
                if done % 20 == 0:
                    progress(f"Downloading NSE circuit-limit files ({done}/{len(need_pr)})", 45 + 10 * done / max(1, len(need_pr)))
        panel = pd.concat([self.px[d] for d in cal], ignore_index=True)
        return pd.DatetimeIndex([pd.Timestamp(d) for d in cal]), panel, {pd.Timestamp(d): self.bh.get(d, set()) for d in cal}


def corporate_actions(nse, start, end):
    """Split / bonus / consolidation price factors by (symbol, ex-date)."""
    rows = []
    s = start  # one call per half-year keeps this light
    while s <= end:
        e = min(end, s + dt.timedelta(days=180))
        d = nse.json(f"/api/corporates-corporateActions?index=equities&from_date={s:%d-%m-%Y}&to_date={e:%d-%m-%Y}")
        rows += d if isinstance(d, list) else []
        s = e + dt.timedelta(days=1)
    out = []
    for r in rows:
        subj = str(r.get("subject", "")).strip().lower()
        f = 1.0
        m = re.search(r"(?:from|frm)\s*r[se]\.?\s*([\d.]+).*?to\s*r[se]\.?\s*([\d.]+)", subj)
        if m and re.search(r"split|splt|sub-?\s?division|consolidat|\bfv\b|face value", subj):
            a, b = float(m.group(1)), float(m.group(2))
            if a > 0 and b > 0:
                f *= b / a
        m = re.search(r"bonus\s*(\d+)\s*:\s*(\d+)", subj)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            if a > 0 and b > 0:
                f *= b / (a + b)
        if f != 1.0:
            ex = pd.to_datetime(r.get("exDate"), format="%d-%b-%Y", errors="coerce")
            if pd.notna(ex):
                out.append((str(r.get("symbol", "")).strip(), ex, f))
    return pd.DataFrame(out, columns=["sym", "ex", "f"])


# ---------------------------------------------------------------- insider filings
TAG = re.compile(r'<(?:[\w\-]+:)?(\w+)\s+([^>]*?)>([^<]*)</', re.S)


def parse_pit_xml(txt):
    main, disc = {}, {}
    for tag, attrs, val in TAG.findall(txt):
        m = re.search(r'contextRef="([^"]+)"', attrs)
        if not m:
            continue
        ctx = m.group(1)
        if ctx == "MainI":
            main[tag] = val.strip()
        else:
            disc.setdefault(ctx, {})[tag] = val.strip()
    return [{**main, "ctx": k, **v} for k, v in disc.items()]


class FilingCache:
    """Insider (PIT Reg 7(2)) filings from NSE's legacy JSON feed and its newer XBRL filings, in memory."""

    def __init__(self):
        self.legacy_months, self.xml = {}, {}

    def legacy(self, nse, start, end, progress):
        rows = []
        end = min(end, NEW_PIT_START - dt.timedelta(days=1))
        for a, b in _months(start, end):
            key = (a, b)
            if key not in self.legacy_months or b >= dt.date.today() - dt.timedelta(days=3):
                self.legacy_months[key] = nse.json(f"/api/corporates-pit?index=equities&from_date={a:%d-%m-%Y}&to_date={b:%d-%m-%Y}").get("data", [])
                time.sleep(0.5)
            rows += self.legacy_months[key]
            progress(f"Reading NSE insider filings for {a:%b %Y}", 5)
        return rows

    def filing_list(self, nse, start, end, progress):
        start = max(start, NEW_PIT_START)
        lst = []
        for a, b in _months(start, end):
            d = nse.json(f"/api/corporates-pit-gg?index=equities&from_date={a:%d-%m-%Y}&to_date={b:%d-%m-%Y}").get("data", [])
            lst += d
            progress(f"Listing NSE insider filings for {a:%b %Y}", 8)
            time.sleep(0.5)
        return pd.DataFrame(lst).drop_duplicates("xmlFileName") if lst else pd.DataFrame()

    def details(self, lst, progress, base=10, span=10):
        urls = [u for u in lst.xmlFileName if u not in self.xml]

        def dl(u):
            b = _get(u)
            return u, (b.decode("utf-8", errors="ignore") if b else None)

        done = 0
        with ThreadPoolExecutor(10) as ex:
            for u, t in ex.map(dl, urls):
                if t is not None:
                    self.xml[u] = t
                done += 1
                if done % 100 == 0:
                    progress(f"Reading insider filing details ({done}/{len(urls)})", base + span * done / max(1, len(urls)))
        rows = []
        for r in lst.itertuples(index=False):
            t = self.xml.get(r.xmlFileName)
            if not t:
                continue
            for d in parse_pit_xml(t):
                d.update(broadcast=r.broadcastDateTime, appId=r.appId, listSymbol=r.symbol)
                rows.append(d)
        return rows
