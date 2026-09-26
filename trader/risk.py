"""Stop-loss maths, identical to the backtest (backtest/insider_backtest.py: initial_stop / run_trade).

  initial stop = the most recent confirmed pivot low below the entry price, but never more than max_sl below it;
                 pivot lows closer than min_sl to the entry are ignored; no usable pivot -> entry x (1 - max_sl).
  trailing stop = highest close since entry x (1 - trail); the stop only ever moves up.
"""
import math

TICK = 0.05


def round_tick(x, mode="nearest", tick=TICK):
    n = x / tick
    n = math.ceil(n - 1e-9) if mode == "up" else math.floor(n + 1e-9) if mode == "down" else round(n)
    return round(n * tick, 2)


def pivot_low_flags(lows, n):
    """flags[j] is True when lows[j] is the lowest of lows[j-n .. j+n] (so it is confirmed n bars later)."""
    m = len(lows)
    return [n <= j < m - n and lows[j] == min(lows[j - n:j + n + 1]) for j in range(m)]


def initial_stop(lows, entry, n=3, lookback=60, min_sl=0.05, max_sl=0.15):
    """`lows` are the daily lows up to and including the last completed session (oldest first).
    Returns (stop_price, kind)."""
    floor = entry * (1 - max_sl)
    flags = pivot_low_flags(list(lows), n)
    e = len(lows)                                  # the entry bar comes right after the last known bar
    for j in range(e - 1 - n, max(-1, e - lookback), -1):
        if flags[j] and lows[j] < entry * (1 - min_sl):
            return (max(lows[j], floor), "pivot") if lows[j] >= floor else (floor, "15% cap")
    return floor, "15% (no pivot)"


def trail_stop(stop, high_close, trail):
    """New stop after a session closes: never lower than the current one."""
    return max(stop, high_close * (1 - trail))
