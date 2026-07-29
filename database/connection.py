import sqlite3
import threading
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    discord_id TEXT PRIMARY KEY,
    nome TEXT,
    data_inicio TEXT,
    data_expiracao TEXT,
    status TEXT NOT NULL DEFAULT 'inativo'
);

CREATE TABLE IF NOT EXISTS pagamentos (
    payment_id TEXT PRIMARY KEY,
    discord_id TEXT NOT NULL,
    valor REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    data_pagamento TEXT,
    processado INTEGER NOT NULL DEFAULT 0
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @contextmanager
    def connect(self):
        with self._lock:
            yield self._conn

    def close(self) -> None:
        self._conn.close()


def make_database(path: str) -> Database:
    return Database(path)
