from .base import Broker, BrokerError, LIMIT, MARKET, SL_LIMIT, OPEN, COMPLETE, REJECTED, CANCELLED  # noqa: F401

LIVE_BROKERS = ("definedge", "kotak", "fyers")


def make(name, env):
    """Build a broker adapter by name. Live adapters read their credentials from `env` (trader/.env)."""
    if name == "paper":
        from .paper import PaperBroker
        return PaperBroker()
    if name == "definedge":
        from .definedge import Definedge
        return Definedge(env)
    if name == "kotak":
        from .kotak import Kotak
        return Kotak(env)
    if name == "fyers":
        from .fyers import Fyers
        return Fyers(env)
    raise BrokerError(f"Unknown broker '{name}'. Choose paper, {', '.join(LIVE_BROKERS)}")
