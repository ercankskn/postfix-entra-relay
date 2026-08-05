#!/usr/bin/env python3
"""Generate a daily original-sender summary from Postfix Entra Relay logs."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import subprocess
import sys
from collections import Counter
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Iterator

DEFAULT_CONFIG = "/etc/postfix-entra-relay/report.json"
EVENT_RE = re.compile(
    r"status=sent\s+queue_id=(?P<queue>[A-Za-z0-9-]+)\s+"
    r"recipient=(?P<recipient>\S+)\s+original_sender=(?P<sender>\S+)"
)


def iter_text_lines(path: Path) -> Iterator[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        yield from handle


def line_matches_date(line: str, report_date: dt.date) -> bool:
    return line.startswith(report_date.isoformat()) or line.startswith(
        report_date.strftime("%b %e")
    )


def parse_events(lines: Iterable[str], report_date: dt.date) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for line in lines:
        if not line_matches_date(line, report_date):
            continue
        match = EVENT_RE.search(line)
        if not match:
            continue
        events.append(match.groupdict())
    return events


def summarize(events: Iterable[dict[str, str]]) -> Counter[str]:
    return Counter(event["sender"].lower() for event in events if event.get("sender"))


def csv_bytes(counts: Counter[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("OriginalSender", "DeliveredRecipients"))
    for sender, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        writer.writerow((sender, count))
    return output.getvalue().encode("utf-8-sig")


def load_config(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def collect_lines(config: dict) -> Iterator[str]:
    log_dir = Path(config.get("log_directory", "/var/log"))
    pattern = config.get("log_glob", "mail.log*")
    for path in sorted(log_dir.glob(pattern)):
        if path.is_file():
            yield from iter_text_lines(path)


def build_message(config: dict, report_date: dt.date, counts: Counter[str]) -> bytes:
    message = EmailMessage()
    message["From"] = config["sender"]
    message["To"] = config["recipient"]
    if config.get("reply_to"):
        message["Reply-To"] = config["reply_to"]
    prefix = config.get("subject_prefix", "[DAILY RELAY REPORT]")
    message["Subject"] = f"{prefix} {report_date.isoformat()}"
    total = sum(counts.values())
    message.set_content(
        f"Report date: {report_date.isoformat()}\n"
        f"Unique original senders: {len(counts)}\n"
        f"Delivered HVE recipients: {total}\n"
    )
    message.add_attachment(
        csv_bytes(counts),
        maintype="text",
        subtype="csv",
        filename=f"postfix-entra-origin-{report_date.isoformat()}.csv",
    )
    return message.as_bytes()


def send_report(config: dict, report_date: dt.date, payload: bytes) -> None:
    command = [
        config.get("hve_submit", "/usr/local/sbin/postfix-entra-hve-submit"),
        "--recipient",
        config["recipient"],
        "--queue-id",
        f"REPORT-{report_date.strftime('%Y%m%d')}",
        "--original-sender",
        config["sender"],
    ]
    run_user = config.get("hve_run_user", "")
    if run_user and os.geteuid() == 0:
        command = ["runuser", "-u", run_user, "--", *command]
    subprocess.run(command, input=payload, check=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("POSTFIX_ENTRA_REPORT_CONFIG", DEFAULT_CONFIG))
    parser.add_argument("--date", default=(dt.date.today() - dt.timedelta(days=1)).isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report_date = dt.date.fromisoformat(args.date)
    config = load_config(args.config)
    state_dir = Path(config.get("state_dir", "/var/lib/postfix-entra-relay/daily-origin-report"))
    state_dir.mkdir(mode=0o750, parents=True, exist_ok=True)
    state_file = state_dir / f"{report_date.isoformat()}.sent"
    if state_file.exists() and not args.force:
        print("REPORT_ALREADY_SENT")
        return 0

    events = parse_events(collect_lines(config), report_date)
    counts = summarize(events)
    payload = build_message(config, report_date, counts)
    if args.stdout:
        sys.stdout.buffer.write(payload)
        return 0
    send_report(config, report_date, payload)
    state_file.write_text(dt.datetime.now(dt.timezone.utc).isoformat() + "\n", encoding="utf-8")
    os.chmod(state_file, 0o640)
    print(f"REPORT_SENT senders={len(counts)} recipients={sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
