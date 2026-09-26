# Insider Trader

Executes the backtested "Clean insider buy" strategy. It reads signals from the screener in `../app`, buys the ones
that qualify (automatically or by hand), and then looks after every position by itself: stop-loss order at the
broker, trailing stop, exit.

Self-contained: it needs only this repo (`trader/` + `app/`) and Python 3.10+. Nothing outside the repo is used, so it
runs on any computer you clone the repo onto. Broker logins are re-implemented here; the old `Logins` folder is not needed.

**It starts in PAPER mode** (pretend money, real NSE prices). Live trading is locked until you unlock it (see below).

## Set up (once)

1. Double-click `setup.bat`. Say which broker you'll use (definedge / kotak / fyers / none).
2. Live only: fill in your broker's lines in `trader/.env` (created from `.env.example`). Never share that file.
3. Double-click `Start Trader.bat`. The dashboard opens at http://127.0.0.1:8760 (reachable only from this computer).

Keep the window open while you want the daily routine to run.

## The rules it follows

| | |
|---|---|
| Which stocks | Only **Clean** signals from the screener (none of the 7 caution notes) |
| Entry range | Price must be at most **5% above the insiders' average price**. Outside it: never bought, by hand or automatically |
| Entry | Limit order (last price + 0.3%, never above the range cap). Auto-buys at **09:20** the morning after the scan; an unfilled order is cancelled after 15 min |
| Quantity | Automatic: Rs 50,000 / price. Manual: you type the quantity (or leave it blank for the automatic one) |
| Margin | Enough cash: order goes out. **Not enough: the trade is rejected** (nothing is sent to the broker) and stays listed as *Needs funds* |
| Initial stop | Last confirmed pivot low below the entry (3 bars each side, 60 sessions back, ignoring pivots closer than 5%), never more than 15% below the fill price |
| Trailing stop | Highest close since entry minus **20%**. It only moves up, so it takes over once the trade is in profit |
| Same stock | One position per stock; after an exit, only a fresh insider buy can re-enter it |

The percentages are the backtest's best settings (Percent trail 20% + minimum 5% initial stop). They are editable in the dashboard's Settings.

## Rejected for margin? What to do

Add funds at your broker, open the dashboard and press **Buy** on the row marked *Rejected: needs funds*. The app re-checks the
entry range first; if the price has moved outside it, the trade is refused. Auto-buy never retries a rejected trade by itself.

## A trade you did outside this app

Use **Record a trade you did outside this app**: symbol, the **actual fill price** and the **actual quantity** from your broker's app.
From then on the position is managed exactly like any other: stop-loss order, trailing stop, exit. (It can't check that you really hold the
shares, so enter only what you bought. If the sell order is rejected because the shares aren't there, the log says so.)

## What happens every day (while the app is open)

| Time (IST) | What |
|---|---|
| 08:30 | Broker login (Definedge and Kotak-with-TOTP-seed log in by themselves; Fyers needs its daily browser login: use the dashboard) |
| 08:40 | Scan NSE for insider buys |
| 09:16 | A fresh stop-loss order is placed on every open position (yesterday's expire at close: they are DAY orders) |
| 09:20 | Automatic buys, if switched on |
| 09:15-15:30 | Every 30 s: fills, stop orders, exits are checked and recorded |
| ~18:15 | Official closes are read and each trailing stop is raised for tomorrow (done next morning if the PC was off) |

**If the app or the PC is off during the day**, the stop-loss order already at the broker still protects that day's trading, but no new stop is placed the next morning
until the app runs again. If a stop order is rejected, the app watches the price itself and sells at market (only while it is running).
Stop orders are stop-limit (limit 2% below the trigger). In a gap-down through the limit the order can stay unfilled; the app then exits at market.

## Safety switches

- **Live is locked.** To unlock: add `TRADER_ALLOW_LIVE=1` to `trader/.env`, restart, pick a broker, log in, press *Go live...* and type `GO LIVE`.
- **Kill switch** button: blocks every new buy at once. Exits keep working.
- Auto-buy is **off** until you switch it on. Order-value cap (Rs 1 lakh per order) and a daily order limit.
- Every live order asks for confirmation in the dashboard.
- The dashboard only accepts requests from this computer, and order buttons need the app's own page (other websites can't trigger orders).

## Before you use real money

1. Run `python selftest.py --broker definedge` (or kotak / fyers). It logs in, reads a price and prints the broker's raw answers **without placing any order**,
   so you can confirm the field names the code relies on (order status, average price, available cash) match your account.
2. Paper-trade for a few weeks.
3. Then go live with a small position amount (for example Rs 5,000) and check that a buy, its stop order and an exit behave as expected at the broker.

The three live adapters follow each broker's documentation and SDK but **have not been run against a real account**. Treat the first live trades as the final test.
Definedge needs your `DEFINEDGE_ALGO_ID` (mandatory for API orders). Brokers may also require your computer's static IP to be registered for API orders.

## Files

| | |
|---|---|
| `main.py` | starts everything |
| `core.py` | buying, margin check, stop orders, trailing, exits |
| `risk.py` | stop-loss maths (same as the backtest) |
| `scheduler.py` | the daily routine |
| `signals.py` | runs `../app/engine.py` and prepares buy candidates |
| `brokers/` | `paper`, `definedge`, `kotak`, `fyers` adapters |
| `server.py`, `dashboard_page.py` | the dashboard |
| `tests/` | `python -m pytest` runs 30 tests on a simulated market |
| `data/` | your database, settings and logs (created on first run, not in git) |

Not investment advice. The backtest behind these rules is described in `../backtest/`; past results, even after costs and slippage, don't guarantee future ones.
