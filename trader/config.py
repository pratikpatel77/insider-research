"""Paths, settings and credentials for the trader. Nothing here depends on any folder outside this repo."""
import datetime as dt, json, os, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DATA = Path(os.environ.get("TRADER_DATA_DIR") or ROOT / "data")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))   # India has no daylight saving

DEFAULTS = {
    # sizing
    "position_amount": 50000,      # Rs per new position when the quantity is chosen automatically
    "max_positions": 0,            # optional cap on open positions (0 = no cap: the available margin is the limit)
    "paper_capital": 500000,       # paper mode only: the pretend account balance that the margin check uses
    # entry (from the backtest)
    "entry_band_pct": 5.0,         # buy only if the price is at most this % above the insiders' average price
    "buy_time": "09:20",           # automatic buys are placed at this time
    "buy_window_min": 30,          # ...and skipped if the app was not running within this many minutes of it
    "limit_buffer_pct": 0.3,       # limit price = last price + this %, never above the entry-band cap
    "fill_wait_min": 15,           # cancel an unfilled entry order after this many minutes
    # exits
    "trail_pct": 20.0,             # trailing stop: this % below the highest close since entry
    "max_sl_pct": 15.0,            # the initial stop is never wider than this
    "min_sl_pct": 5.0,             # pivot lows closer than this to the entry are ignored (helped in both backtest periods)
    "pivot_bars": 3,               # a pivot low is the lowest low of this many bars on each side
    "pivot_lookback": 60,          # sessions to look back for it
    "sl_limit_gap_pct": 2.0,       # stop orders are stop-limit: limit price = trigger - this %
    # safety
    "auto_buy": False,             # automatic buying is off until you switch it on
    "kill_switch": False,          # blocks all new buys; exits keep working
    "max_order_value": 100000,     # no single order above this many Rs
    "max_orders_per_day": 40,
}

_lock = threading.Lock()


def load_env():
    """Read trader/.env (KEY=VALUE lines) into a dict. Real environment variables win."""
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("TRADER_", "DEFINEDGE_", "KOTAK_", "FYERS_", "TELEGRAM_"))})
    return env


def now():
    return dt.datetime.now(IST)


def load_settings():
    DATA.mkdir(parents=True, exist_ok=True)
    s = dict(DEFAULTS)
    p = DATA / "settings.json"
    if p.exists():
        try:
            s.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
    return s


def save_settings(s):
    DATA.mkdir(parents=True, exist_ok=True)
    with _lock:
        tmp = DATA / "settings.json.tmp"
        tmp.write_text(json.dumps({k: s[k] for k in DEFAULTS}, indent=2), encoding="utf-8")
        os.replace(tmp, DATA / "settings.json")


def coerce(key, value):
    """Validate one setting from the dashboard, returning the value in the right type."""
    d = DEFAULTS[key]
    if isinstance(d, bool):
        return bool(value)
    if isinstance(d, int):
        v = int(float(value))
    elif isinstance(d, float):
        v = float(value)
    else:
        v = str(value)
        if key == "buy_time":
            dt.datetime.strptime(v, "%H:%M")
        return v
    if v < 0:
        raise ValueError(f"{key} cannot be negative")
    return v
