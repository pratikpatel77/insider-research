"""Insider Trader: entry point. Starts the daily scheduler and the local dashboard (http://127.0.0.1:8760)."""
import os, sys, webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings
warnings.filterwarnings("ignore")

import config
from core import Trader
from db import DB
from scheduler import Scheduler
from server import PORT, serve


def main():
    config.DATA.mkdir(parents=True, exist_ok=True)
    tr = Trader(DB())
    sched = Scheduler(tr)
    print("=" * 60)
    print(" Insider Trader")
    print(f"  mode: {tr.mode.upper()}   broker: {tr.broker_name}   data folder: {config.DATA}")
    print("  Keep this window open. The daily routine runs while it is open;")
    print("  stop-loss orders already at the broker protect you if it is closed.")
    print("=" * 60, flush=True)
    try:
        tr.recover()
    except Exception as e:
        tr.db.event("error", f"Recovery failed: {e}")
    sched.start()
    try:
        srv = serve(tr, sched, PORT)
    except OSError:
        sys.exit(f"Port {PORT} is busy. Is Insider Trader already running?")
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Dashboard: {url}", flush=True)
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
