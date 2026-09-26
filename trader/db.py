"""SQLite state: positions, the order log, events and a few key/value flags. One file: data/trader.db."""
import json, sqlite3, threading

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sym TEXT NOT NULL, company TEXT, mode TEXT NOT NULL, broker TEXT,
  status TEXT NOT NULL,            -- entering | open | closed | failed
  source TEXT,                     -- auto | manual
  signal_key TEXT, insider_avg REAL,
  qty INTEGER, entry_price REAL, entry_time TEXT,
  initial_stop REAL, stop REAL, stop_kind TEXT, high_close REAL,
  sl_oid TEXT, sl_date TEXT, sl_trigger REAL, sl_state TEXT,   -- sl_state: broker | software | none
  eod_date TEXT, breached INTEGER DEFAULT 0,
  exit_price REAL, exit_time TEXT, exit_reason TEXT, pnl REAL, note TEXT
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, mode TEXT, position_id INTEGER, sym TEXT, side TEXT, kind TEXT,
  purpose TEXT, qty INTEGER, price REAL, trigger REAL, broker_oid TEXT, status TEXT, filled INTEGER, avg REAL, note TEXT
);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, level TEXT, msg TEXT);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""


class DB:
    def __init__(self, path=None):
        config.DATA.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(str(path or config.DATA / "trader.db"), check_same_thread=False, isolation_level=None)
        self.c.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.c.executescript(SCHEMA)

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.c.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        r = self.q(sql, args)
        return r[0] if r else None

    def x(self, sql, args=()):
        with self.lock:
            return self.c.execute(sql, args).lastrowid

    def insert(self, table, **kw):
        return self.x(f"INSERT INTO {table} ({','.join(kw)}) VALUES ({','.join('?' * len(kw))})", tuple(kw.values()))

    def update(self, table, id_, **kw):
        if kw:
            self.x(f"UPDATE {table} SET {','.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), id_))

    # key/value flags
    def get(self, k, default=None):
        r = self.one("SELECT v FROM kv WHERE k=?", (k,))
        return json.loads(r["v"]) if r else default

    def set(self, k, v):
        self.x("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))

    def event(self, level, msg):
        self.insert("events", ts=config.now().strftime("%Y-%m-%d %H:%M:%S"), level=level, msg=msg)
        print(f"[{config.now():%H:%M:%S}] {level.upper():5s} {msg}", flush=True)
