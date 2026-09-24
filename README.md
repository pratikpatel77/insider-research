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

## Running the screener on your PC

Requires Windows, Python 3.10+ and an internet connection.

1. Double-click `app/Start Insider Screener.bat`.
2. Your browser opens the screener. The first scan of the day takes 3–6 minutes. Reopening the app later that day shows the result instantly.

See [`app/README.txt`](app/README.txt) for how to read the watchlist.

## Automatic daily scan (GitHub Actions)

`.github/workflows/daily-scan.yml` runs the same scan every weekday at **9:30 pm IST** on GitHub's servers, so your PC doesn't need to be on. It:

1. scans NSE and applies the rules,
2. publishes the watchlist as a web page and an Excel file (GitHub Pages),
3. sends **Telegram alerts** for anything that changed since the last run: a new stock, a fresh insider buy in a stock already on the list, an exit check, or a stock leaving the list.

**One-time setup**

1. **Turn on Pages.** Repo → Settings → Pages → Source: **GitHub Actions**.
2. **Create a Telegram bot.** In Telegram, message `@BotFather`, send `/newbot`, and copy the token it gives you.
3. **Find your chat ID.** Send any message to your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser (replace `<TOKEN>`). Copy the number after `"chat":{"id":`.
4. **Add two secrets.** Repo → Settings → Secrets and variables → Actions → New repository secret: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
5. **Test it.** Repo → Actions → Daily insider scan → Run workflow, tick "Only send a test Telegram message". You should get a message within a minute.
6. **Run the first scan.** Run the workflow again without the tick. It publishes the page at `https://<your-username>.github.io/insider-research/` and sends a "screener is live" message.

Notes:

- If a scan fails (for example NSE blocks GitHub's servers), the last good page stays online and Telegram tells you the run failed.
- GitHub pauses scheduled workflows in a public repo after 60 days with no repository activity. A commit or a manual run turns it back on.
- The page is public to anyone with the link. It contains only public NSE data, and it asks search engines not to index it.

## Data sources

All data comes from official NSE sources:

- insider-trading disclosures under SEBI (PIT) Regulations 2015, Reg. 7(2)
- daily price files (bhavcopy)
- circuit-limit files
- corporate actions

This is research, not investment advice. Don't trade stocks where you are an insider or hold unpublished price-sensitive information.
