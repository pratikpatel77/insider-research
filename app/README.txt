INSIDER BUY SCREENER
====================

WHAT IT DOES
Every time you click "Run scan", it downloads the latest insider-trading filings and
prices from nseindia.com, applies the rules from the Promoter Buying Study, and shows a
watchlist of stocks where individual insiders bought with conviction.
The raw NSE downloads are never saved - they live in memory only while the app window is
open. The one thing that IS saved is the finished watchlist, in a small file next to this
one called ".scan_cache.json", so opening the app again later today shows it instantly
instead of re-scanning. That file is overwritten by your next scan, and ignored the moment
it's from an earlier day - you can also delete it any time, it will just be rebuilt.
An Excel file is created only if you click "Download Excel".

HOW TO USE
1. Double-click "Start Insider Screener.bat".
   A black window opens (keep it open) and your browser shows the screener.
2. The first scan of the day starts by itself and takes about 3-6 minutes.
   Reopening the app later the same day shows that scan instantly.
   Click "Run scan" any time to check for filings published since then.
3. Best time to run: after 9 pm on trading days. Most filings arrive between 4 pm and 9 pm.
4. To stop the app, close the black window.

READING THE WATCHLIST
- Enter from next session : disclosed after market hours today. The signal starts tomorrow.
- vs insider              : last close compared with the insiders' average buying price.
- Window left             : sessions left in the 120-session watch period.
- Exit warning            : an insider sold after the signal. The study's exit rule.
- Notes                   : cases that were historically weaker. Be more careful with these.
Click any row to see every transaction and the other insider filings in that stock.

THE RULES (all must pass)
1. Buy + Market Purchase of equity (NSE PIT Reg 7(2) filing)
2. Buyer is an individual promoter / promoter group / relative / director / KMP
3. Shares bought >= 5% of the buyer's prior holding
4. Market cap <= Rs 10,000 cr
5. Tradeable: EQ series, median daily value >= Rs 1 cr, few circuit hits, price >= Rs 10
6. No insider market selling in the look-back (180 days promoter side / 90 days director)
7. Watch for 120 sessions. Enter only with your own setup.

NEEDS
Windows, Python 3.10+ and an internet connection. The .bat file installs the
packages it needs (requests, pandas, openpyxl) the first time.

This is research, not investment advice. Don't trade stocks where you are an
insider or hold unpublished price-sensitive information.
