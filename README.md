# insider-research

Can publicly disclosed insider buying on NSE be used as a trading signal? This repo has the research, and a screener that applies the result every day.

## What's here

| Path | What it is |
|---|---|
| `Promoter_Buying_Study_2026-09-23.html` | The research report. Open it in any browser. |
| `Insider_Signals_2026-09-23.xlsx` | The signals that qualified on 23 Sep 2026, with every transaction. |
| `app/` | **Insider Buy Screener**, a local app that fetches NSE data live and shows today's watchlist. |

## The finding in brief

Across 332,565 NSE insider filings (Nov 2015 – Sep 2026), plain "the promoter bought shares" is **not** a reliable signal.

One kind of buy is. The signal is:

- an **individual** (a promoter as a person, a relative, a director or a key manager),
- buying in the open market,
- raising their own holding by **at least 5%**,
- in a company worth **₹10,000 crore or less**,
- with **no insider selling** in the look-back period.

Holding each qualifying stock for 120 sessions beat comparable stocks by about **15% a year after costs**. That held in both halves of the sample: +14% in 2016–21 and +17% in 2022–26.

About 6% of that also appeared on random dates in the same stocks. So the part that comes from the timing of the insider buy is closer to **9% a year**.

The worst drawdown was **66%**, in the 2018–20 small-cap crash.

## Running the screener

Requires Windows, Python 3.10+ and an internet connection.

1. Double-click `app/Start Insider Screener.bat`.
2. Your browser opens the screener. The first scan of the day takes 3–6 minutes. Reopening the app later that day shows the result instantly.

See [`app/README.txt`](app/README.txt) for how to read the watchlist.

## Data sources

All data comes from official NSE sources:

- insider-trading disclosures under SEBI (PIT) Regulations 2015, Reg. 7(2)
- daily price files (bhavcopy)
- circuit-limit files
- corporate actions

This is research, not investment advice. Don't trade stocks where you are an insider or hold unpublished price-sensitive information.
