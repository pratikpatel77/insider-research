"""Headless daily scan for GitHub Actions.

  python app/daily_scan.py --out site          scan NSE, write the web page + Excel + state, work out alerts
  python app/daily_scan.py --send-alerts FILE  send the alerts from a previous run to Telegram
  python app/daily_scan.py --telegram-test     send one test message
  python app/daily_scan.py --notify-failure    tell Telegram the scheduled run failed

Telegram credentials come from the TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables
(GitHub secrets). Without them, messages are printed instead of sent.
"""
import argparse, datetime as dt, html, json, os, sys, time, traceback, urllib.error, urllib.parse, urllib.request, warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings("ignore")

import app as appmod
import engine, nse_live, static_page

ROLE = {"Promoters": "promoter", "Promoter": "promoter", "Promoter and Director": "promoter & director", "Promoter Group": "promoter group",
        "Immediate relative": "relative", "Immediate Relative": "relative", "Promoter Immediate Relative": "promoter's relative",
        "Director": "director", "Directors Immediate Relative": "director's relative", "KMP": "key manager", "Key Managerial Personnel": "key manager"}
FLAG = [("exit", "exit check"), ("small ticket", "small buy"), ("5–10k", "₹5–10k cr size"), ("far above", "already ran up"),
        ("nearly over", "window ending"), ("sold before", "earlier insider sales"), ("first personal", "new holder")]
MAX_STALE_DAYS = 7


# ---------------------------------------------------------------- helpers
def esc(s):
    return html.escape(str(s), quote=False)


def cr(v):
    return "–" if v is None else f"₹{v:,.0f} cr" if v >= 100 else f"₹{v:,.1f} cr" if v >= 10 else f"₹{v:,.2f} cr"


def iso(v):
    """Sortable text for a disclosure time, whether it is a Timestamp (fresh scan) or a display string."""
    ts = appmod._parse_disp(v)
    return "" if ts is None or ts is appmod.pd.NaT else ts.strftime("%Y-%m-%d %H:%M")


def role(cat):
    return ROLE.get(cat, str(cat or "insider").lower())


def lead(s):
    people = [p for p in s["people"] if not p["entity"]] or s["people"]
    return max(people, key=lambda p: p["after"] - p["before"])


def flag_labels(s):
    out = []
    for n in s["notes"]:
        for key, label in FLAG:
            if key in n.lower():
                out.append(label)
                break
        else:
            out.append(n)
    return out


def state_of(signals, meta):
    return {"as_of": meta["as_of"], "run_at": meta["run_at"],
            "signals": {s["sym"]: {"disclosed": iso(s["last_disclosed"]), "exit": bool(s["exit_warning"])} for s in signals}}


# ---------------------------------------------------------------- alerts
def describe(s, url):
    L = lead(s)
    others = len(s["people"]) - 1
    who = f"{esc(L['name'])} ({esc(role(L['cat']))}) {L['before']:.2f}% → {L['after']:.2f}%" + (f" and {others} more" if others > 0 else "")
    own = "more than tenfold" if s["own_incr"] > 1000 else f"+{s['own_incr']:.0f}%"
    vs = "" if s["vs_insider"] is None else f" ({s['vs_insider']:+.1f}% vs insiders)"
    left = "starts next session" if s["pending"] else f"{s['sessions_left']} of 120 sessions left"
    lines = [f"{who}",
             f"Bought {cr(s['value_cr'])} at an average ₹{s['avg_price']:,.2f}; own holding {own}.",
             f"Close ₹{s['close']:,.2f}{vs}. {left}."]
    fl = flag_labels(s)
    lines.append("Cautions: " + esc(", ".join(fl)) if fl else "No cautions.")
    return "\n".join(lines)


def compute_alerts(prev, signals, meta, url):
    """Messages describing what changed since the last published scan. `prev` is None on the very first run."""
    cur = {s["sym"]: s for s in signals}
    if prev is None:
        names = ", ".join(cur) or "none yet"
        return [f"<b>Insider screener is live.</b>\n{len(cur)} stocks on watch: {esc(names)}.\nFrom now on you'll get a message when a stock is added, gets a fresh insider buy, or needs an exit check.\n{url}"]
    ps = prev.get("signals", {})
    msgs = []
    for sym, s in cur.items():
        if sym not in ps:
            msgs.append(f"<b>New signal: {esc(sym)}</b> ({esc(s['company'])})\n{describe(s, url)}")
        elif iso(s["last_disclosed"]) > ps[sym].get("disclosed", ""):
            msgs.append(f"<b>Fresh insider buy: {esc(sym)}</b> ({esc(s['company'])}). The 120-session window restarts.\n{describe(s, url)}")
    for sym, s in cur.items():
        if s["exit_warning"] and not ps.get(sym, {}).get("exit"):
            msgs.append(f"<b>Exit check: {esc(sym)}</b>\nAn insider sold after the signal: {esc(s['exit_detail'])}")
    gone = [sym for sym in ps if sym not in cur]
    if gone:
        msgs.append(f"Left the watchlist (window ended or no longer qualifies): {esc(', '.join(gone))}.")
    if msgs:
        msgs.append(f"Full list: {url}")
    return msgs


def fetch_prev(url):
    """The state file published by the previous run. None = first run; "error" = couldn't tell."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/state.json", timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None if e.code == 404 else "error"
    except (urllib.error.URLError, ValueError, OSError):
        return "error"


# ---------------------------------------------------------------- telegram
def send_telegram(messages):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not messages:
        print("No alerts to send.")
        return True
    if not token or not chat:
        print("Telegram is not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID). Alerts that would be sent:")
        for m in messages:
            print("-" * 60 + "\n" + m)
        return False
    ok = True
    for m in messages:
        body = urllib.parse.urlencode({"chat_id": chat, "text": m[:4000], "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body), timeout=30).read()
        except urllib.error.HTTPError as e:
            # never print the request URL: it contains the bot token
            print(f"Telegram rejected a message: HTTP {e.code} {e.read().decode('utf-8', 'ignore')[:200]}")
            ok = False
        except (urllib.error.URLError, OSError) as e:
            print(f"Could not reach Telegram: {e.__class__.__name__}")
            ok = False
        time.sleep(0.4)
    return ok


# ---------------------------------------------------------------- scan
def check_fresh(meta):
    latest = dt.datetime.strptime(meta["latest_filing"], "%d %b %Y, %H:%M")
    age = (dt.datetime.now() - latest).days
    if age > MAX_STALE_DAYS:
        raise RuntimeError(f"The newest insider filing NSE returned is {age} days old, so the filing feed looks blocked or incomplete. Nothing was published.")


def scan(out_dir, alerts_file):
    last = [0.0]

    def progress(msg, pct):
        if time.time() - last[0] > 8:
            print(f"{int(pct):3d}%  {msg}", flush=True)
            last[0] = time.time()

    res = engine.run_scan(progress, nse_live.PriceCache(), nse_live.FilingCache())
    meta = res["meta"]
    print(f"Scan done in {meta['seconds']}s: {len(res['signals'])} on watch, {meta['filings']:,} filings, prices to {meta['as_of']}.")
    check_fresh(meta)

    payload = appmod.clean_nans(json.loads(json.dumps({"signals": res["signals"], "near": res["near"], "meta": meta}, default=appmod.to_json)))
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(static_page.build(payload))
    open(os.path.join(out_dir, "watchlist.xlsx"), "wb").write(appmod.excel_bytes(res))
    open(os.path.join(out_dir, ".nojekyll"), "w").close()

    url = os.environ.get("PAGES_URL", "").strip()
    prev = fetch_prev(url) if url else "error"
    state = state_of(res["signals"], meta)
    json.dump(state, open(os.path.join(out_dir, "state.json"), "w"))
    if prev == "error":
        print("Could not read the previous state, so no alerts this run.")
        msgs = []
    else:
        msgs = compute_alerts(prev, res["signals"], meta, url)
    json.dump(msgs, open(alerts_file, "w"))
    print(f"Wrote the page to {out_dir}/ and {len(msgs)} alert message(s) to {alerts_file}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    ap.add_argument("--alerts-file", default="alerts.json")
    ap.add_argument("--send-alerts")
    ap.add_argument("--telegram-test", action="store_true")
    ap.add_argument("--notify-failure", action="store_true")
    a = ap.parse_args()
    if a.telegram_test:
        return 0 if send_telegram(["<b>Test from Insider Screener.</b>\nTelegram alerts are working. You'll get a message here when a stock is added, gets a fresh insider buy, or needs an exit check."]) else 1
    if a.notify_failure:
        run = "{}/{}/actions/runs/{}".format(os.environ.get("GITHUB_SERVER_URL", "https://github.com"), os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_RUN_ID", ""))
        send_telegram([f"<b>Insider scan failed.</b>\nToday's watchlist was not updated; the last good one is still online.\nDetails: {run}"])
        return 0
    if a.send_alerts:
        msgs = json.load(open(a.send_alerts))
        return 0 if send_telegram(msgs) or not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")) else 1
    try:
        scan(a.out, a.alerts_file)
    except Exception as e:
        traceback.print_exc()
        print(f"::error::{e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
