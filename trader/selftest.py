"""Check a broker connection WITHOUT placing any order:  python selftest.py --broker definedge   (or kotak / fyers)

Logs in, reads a price and prints the broker's raw answers, so you can confirm the field names the adapter relies on
match your account before you ever switch to live. Fyers needs its daily browser login first (use the dashboard)."""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from brokers import make


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", required=True, choices=["definedge", "kotak", "fyers"])
    ap.add_argument("--symbol", default="TCS")
    ap.add_argument("--totp", help="6-digit code (Kotak without a TOTP seed in .env)")
    a = ap.parse_args()
    b = make(a.broker, config.load_env())
    if not b.logged_in():
        if not b.auto_login and a.broker == "fyers":
            sys.exit("Fyers needs the daily browser login: start the dashboard, choose fyers, and use 'Login to Fyers'.")
        b.login(totp=a.totp)
    print(f"Logged in to {a.broker}.")
    print(f"Last price of {a.symbol}: {b.ltp(a.symbol)}")
    print("\nRaw responses (check the fields listed in the README):")
    print(json.dumps(b.raw_dump(a.symbol), indent=2, default=str)[:6000])
    print("\nNo orders were placed.")


if __name__ == "__main__":
    main()
