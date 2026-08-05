#!/usr/bin/env python3
"""Incremental Postfix log collector for the optional read-only dashboard."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
from pathlib import Path

QUEUE_RE = re.compile(
    r"postfix/qmgr\[\d+\]:\s+(?P<qid>[A-F0-9]+):.*?"
    r"from=<(?P<sender>[^>]*)>.*?size=(?P<size>\d+).*?nrcpt=(?P<nrcpt>\d+)"
)
DELIVERY_RE = re.compile(
    r"postfix/(?P<process>smtp|pipe)\[\d+\]:\s+(?P<qid>[A-F0-9]+):.*?"
    r"to=<(?P<recipient>[^>]*)>.*?relay=(?P<relay>[^,\s]+).*?status=(?P<status>\w+)"
)
HVE_RE = re.compile(
    r"postfix-entra-hve-submit\[\d+\]:\s+status=(?P<status>\w+)\s+"
    r"queue_id=(?P<qid>\S+)\s+recipient=(?P<recipient>\S+)"
)

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  queue_id TEXT,
  sender TEXT,
  recipient TEXT,
  route TEXT,
  status TEXT,
  size INTEGER,
  recipients INTEGER,
  raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_queue ON events(queue_id);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    return connection


def state_get(connection: sqlite3.Connection, key: str, default: str = "") -> str:
    row = connection.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def state_set(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT INTO state(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def timestamp_from_line(line: str) -> str:
    first = line.split(" ", 1)[0]
    if "T" in first and len(first) >= 19:
        return first[:19].replace("T", " ")
    return time.strftime("%Y-%m-%d %H:%M:%S")


def parse_line(line: str) -> dict | None:
    match = QUEUE_RE.search(line)
    if match:
        data = match.groupdict()
        return {
            "event_type": "queue",
            "queue_id": data["qid"],
            "sender": data["sender"].lower(),
            "recipient": "",
            "route": "",
            "status": "queued",
            "size": int(data["size"]),
            "recipients": int(data["nrcpt"]),
        }

    match = DELIVERY_RE.search(line)
    if match:
        data = match.groupdict()
        relay = data["relay"].lower()
        route = "internal-hve" if data["process"] == "pipe" or "hve" in relay else "external"
        return {
            "event_type": "delivery",
            "queue_id": data["qid"],
            "sender": "",
            "recipient": data["recipient"].lower(),
            "route": route,
            "status": data["status"].lower(),
            "size": None,
            "recipients": None,
        }

    match = HVE_RE.search(line)
    if match:
        data = match.groupdict()
        return {
            "event_type": "hve",
            "queue_id": data["qid"],
            "sender": "",
            "recipient": data["recipient"].lower(),
            "route": "internal-hve",
            "status": data["status"].lower(),
            "size": None,
            "recipients": None,
        }
    return None


def collect_once(connection: sqlite3.Connection, log_path: Path) -> int:
    stat = log_path.stat()
    inode = str(stat.st_ino)
    old_inode = state_get(connection, "inode")
    offset = int(state_get(connection, "offset", "0") or 0)
    if old_inode != inode or offset > stat.st_size:
        offset = 0

    inserted = 0
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(offset)
        for line in handle:
            event = parse_line(line)
            if not event:
                continue
            connection.execute(
                """
                INSERT INTO events(
                  created_at,event_type,queue_id,sender,recipient,route,status,size,recipients,raw
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    timestamp_from_line(line),
                    event["event_type"], event["queue_id"], event["sender"],
                    event["recipient"], event["route"], event["status"],
                    event["size"], event["recipients"], line.rstrip(),
                ),
            )
            inserted += 1
        state_set(connection, "offset", str(handle.tell()))
        state_set(connection, "inode", inode)
    connection.commit()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=os.environ.get("POSTFIX_ENTRA_LOG", "/var/log/mail.log"))
    parser.add_argument("--db", default=os.environ.get("POSTFIX_ENTRA_DB", "/var/lib/postfix-entra-relay/metrics.db"))
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    connection = connect(Path(args.db))
    try:
        while True:
            try:
                collect_once(connection, Path(args.log))
            except FileNotFoundError:
                pass
            if not args.follow:
                break
            time.sleep(max(0.2, args.interval))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
