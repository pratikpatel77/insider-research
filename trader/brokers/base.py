"""The small interface every broker adapter implements. The trading logic only ever talks to this."""

# order kinds
LIMIT, MARKET, SL_LIMIT = "LIMIT", "MARKET", "SL_LIMIT"
# order states the trading logic understands (each adapter maps its broker's states onto these)
OPEN, COMPLETE, REJECTED, CANCELLED = "OPEN", "COMPLETE", "REJECTED", "CANCELLED"


class BrokerError(RuntimeError):
    pass


class Broker:
    name = "base"
    is_paper = False
    auto_login = True        # False: the broker needs a manual step each day (the dashboard shows what to do)

    def login(self, **kw):
        raise NotImplementedError

    def logged_in(self):
        return True

    def ltp(self, sym):
        """Last traded price of an NSE equity, in Rs."""
        raise NotImplementedError

    def place(self, sym, side, qty, kind, price=0.0, trigger=0.0, tag=""):
        """Place a CNC (delivery) order. side is BUY or SELL. Returns the broker's order id."""
        raise NotImplementedError

    def order(self, oid):
        """{'status': OPEN|COMPLETE|REJECTED|CANCELLED, 'filled': int, 'qty': int, 'avg': float, 'msg': str}"""
        raise NotImplementedError

    def cancel(self, oid):
        raise NotImplementedError

    def funds(self):
        """Cash available to buy shares (delivery) in Rs, or None if the broker's answer can't be read
        (the broker itself will then reject an order that is too big)."""
        return None

    def raw_dump(self, sym="TCS"):
        """For selftest.py: the broker's raw responses, so the field mapping can be checked by eye."""
        return {}


def num(x, default=0.0):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return default
