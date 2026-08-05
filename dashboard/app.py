#!/usr/bin/env python3
"""Read-only operations dashboard for Postfix Entra Relay."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template_string

DB_PATH = Path(os.environ.get("POSTFIX_ENTRA_DB", "/var/lib/postfix-entra-relay/metrics.db"))
app = Flask(__name__)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Postfix Entra Relay</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#0f172a;color:#e2e8f0}.wrap{max-width:1100px;margin:auto;padding:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}.card{background:#1e293b;padding:18px;border-radius:12px}
strong{font-size:2rem;display:block;margin-top:8px}table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px;border-bottom:1px solid #334155}small{color:#94a3b8}
</style></head><body><div class="wrap"><h1>Postfix Entra Relay</h1><p><small>Read-only delivery telemetry</small></p>
<div class="grid">{% for key,value in summary.items() %}<div class="card">{{ key }}<strong>{{ value }}</strong></div>{% endfor %}</div>
<h2>Recent deliveries</h2><table><tr><th>Time</th><th>Queue</th><th>Recipient</th><th>Route</th><th>Status</th></tr>
{% for row in recent %}<tr>{% for value in row %}<td>{{ value or '-' }}</td>{% endfor %}</tr>{% endfor %}</table></div></body></html>"""


def query(sql: str, params: tuple = ()) -> list[tuple]:
    if not DB_PATH.exists():
        return []
    connection = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def get_summary() -> dict[str, int]:
    rows = query(
        """
        SELECT
          SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END),
          SUM(CASE WHEN status='deferred' THEN 1 ELSE 0 END),
          SUM(CASE WHEN status='bounced' THEN 1 ELSE 0 END),
          SUM(CASE WHEN route='internal-hve' AND status='sent' THEN 1 ELSE 0 END),
          SUM(CASE WHEN route='external' AND status='sent' THEN 1 ELSE 0 END)
        FROM events WHERE created_at >= datetime('now','-24 hours')
        """
    )
    values = rows[0] if rows else (0, 0, 0, 0, 0)
    return {
        "Sent (24h)": int(values[0] or 0),
        "Deferred": int(values[1] or 0),
        "Bounced": int(values[2] or 0),
        "HVE sent": int(values[3] or 0),
        "External sent": int(values[4] or 0),
    }


def recent_deliveries(limit: int = 100) -> list[tuple]:
    return query(
        """
        SELECT created_at, queue_id, recipient, route, status
        FROM events WHERE event_type='delivery'
        ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    )


@app.get("/")
def index():
    return render_template_string(PAGE, summary=get_summary(), recent=recent_deliveries())


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "database": DB_PATH.exists()})


@app.get("/api/summary")
def api_summary():
    return jsonify(get_summary())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765)
