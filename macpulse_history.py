"""Persistence for macpulse: the time dimension the scanner does not have on its own.

A single scan can only ever say "this is true now". That is the weakest possible thing
to say about a machine whose problems accumulate — a process pinned to a core matters
precisely *because* it has been that way for six days, and "your Mac is at 68/100" means
nothing without knowing it was 84 last week. Everything here exists to answer questions
a snapshot cannot:

  * when did this finding first appear, and has it been here every scan since?
  * is this machine getting better or worse?
  * what did that fix actually achieve — did the number move?
  * I have seen this one and I do not care; stop raising it.

Storage is one SQLite file under Application Support. It is deliberately small and
self-pruning: a health tool that grows without bound would be its own bug report.
"""

import json
import pathlib
import sqlite3
import time

DB_DIR = pathlib.Path.home() / "Library" / "Application Support" / "macpulse"
DB_PATH = DB_DIR / "history.db"
RETAIN_DAYS = 90

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    ts         REAL PRIMARY KEY,
    score      INTEGER NOT NULL,
    free_pct   INTEGER,
    swap_pct   REAL,
    findings   INTEGER,
    fixable_kb INTEGER
);
CREATE TABLE IF NOT EXISTS seen (
    key        TEXT PRIMARY KEY,
    severity   TEXT,
    title      TEXT,
    first_seen REAL NOT NULL,
    last_seen  REAL NOT NULL,
    times      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS fixes (
    ts          REAL PRIMARY KEY,
    key         TEXT,
    label       TEXT,
    result      TEXT,
    score_before INTEGER,
    score_after  INTEGER,
    freed_kb     INTEGER
);
CREATE TABLE IF NOT EXISTS muted (
    key   TEXT PRIMARY KEY,
    until REAL NOT NULL,
    note  TEXT
);
CREATE INDEX IF NOT EXISTS samples_ts ON samples(ts);
"""


def _connect():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=5)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def record(score, mem, findings):
    """Store one sample and update per-finding first/last seen.

    Returns {key: {"first_seen": ts, "times": n}} so the caller can tell the user how
    long each problem has been there — the single most useful thing history buys.
    """
    now = time.time()
    swap_pct = (mem["swap_used_mb"] / mem["swap_total_mb"] * 100) if mem["swap_total_mb"] else 0
    ages = {}
    try:
        with _connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?)",
                (now, score, mem.get("free_pct"), round(swap_pct, 1), len(findings),
                 sum(f.cost_kb for f in findings if f.fix)),
            )
            for f in findings:
                row = con.execute("SELECT first_seen, times FROM seen WHERE key=?",
                                  (f.key,)).fetchone()
                if row:
                    con.execute("UPDATE seen SET last_seen=?, times=times+1, severity=? "
                                "WHERE key=?", (now, f.sev, f.key))
                    ages[f.key] = {"first_seen": row["first_seen"], "times": row["times"] + 1}
                else:
                    con.execute("INSERT INTO seen (key,severity,title,first_seen,last_seen)"
                                " VALUES (?,?,?,?,?)", (f.key, f.sev, f.title_key, now, now))
                    ages[f.key] = {"first_seen": now, "times": 1}
            con.execute("DELETE FROM samples WHERE ts < ?", (now - RETAIN_DAYS * 86400,))
            # A finding not seen for a month is gone; keeping it would make "first seen"
            # lie the next time an unrelated process reuses the same PID.
            con.execute("DELETE FROM seen WHERE last_seen < ?", (now - 30 * 86400,))
    except sqlite3.Error:
        return {}                      # history is a nicety; never break a scan over it
    return ages


def trend(days=14, buckets=14):
    """Score over time, oldest first, as (label, score) — for a sparkline."""
    now = time.time()
    try:
        with _connect() as con:
            rows = con.execute(
                "SELECT ts, score FROM samples WHERE ts > ? ORDER BY ts",
                (now - days * 86400,)).fetchall()
    except sqlite3.Error:
        return []
    if not rows:
        return []
    width = days * 86400 / buckets
    out = []
    for i in range(buckets):
        lo = now - (buckets - i) * width
        hi = lo + width
        vals = [r["score"] for r in rows if lo <= r["ts"] < hi]
        out.append(round(sum(vals) / len(vals)) if vals else None)
    return out


def last_score():
    try:
        with _connect() as con:
            row = con.execute("SELECT score, ts FROM samples ORDER BY ts DESC LIMIT 1").fetchone()
            return (row["score"], row["ts"]) if row else (None, None)
    except sqlite3.Error:
        return (None, None)


def log_fix(key, label, result, score_before, score_after, freed_kb):
    try:
        with _connect() as con:
            con.execute("INSERT OR REPLACE INTO fixes VALUES (?,?,?,?,?,?,?)",
                        (time.time(), key, label, result, score_before, score_after, freed_kb))
    except sqlite3.Error:
        pass


def recent_fixes(limit=10):
    try:
        with _connect() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM fixes ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]
    except sqlite3.Error:
        return []


def mute(key, days=30, note=""):
    try:
        with _connect() as con:
            con.execute("INSERT OR REPLACE INTO muted VALUES (?,?,?)",
                        (key, time.time() + days * 86400, note))
    except sqlite3.Error:
        pass


def unmute(key):
    try:
        with _connect() as con:
            con.execute("DELETE FROM muted WHERE key=?", (key,))
    except sqlite3.Error:
        pass


def muted_keys():
    """Expired mutes are dropped on read, so a mute genuinely lapses."""
    now = time.time()
    try:
        with _connect() as con:
            con.execute("DELETE FROM muted WHERE until < ?", (now,))
            return {r["key"] for r in con.execute("SELECT key FROM muted").fetchall()}
    except sqlite3.Error:
        return set()
