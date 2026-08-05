#!/usr/bin/env python3
"""Postfix SMTP policy service for routing oversized mail away from HVE.

Use from smtpd_end_of_data_restrictions. At END-OF-DATA Postfix supplies the
actual queued message size. Messages above the configured safety threshold are
routed through the existing Exchange Online smtp transport instead of HVE.
"""

from __future__ import annotations

import argparse
import re
import sys
import syslog
from typing import TextIO

DEFAULT_THRESHOLD_BYTES = 9_000_000
DEFAULT_FALLBACK_TRANSPORT = "smtp:[smtp.office365.com]:587"
TRANSPORT_RE = re.compile(r"^[A-Za-z0-9_-]+:[^\s\x00\r\n]+$")


def read_request(stream: TextIO) -> dict[str, str] | None:
    attributes: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line == "":
            return attributes or None
        line = line.rstrip("\r\n")
        if not line:
            return attributes
        key, separator, value = line.partition("=")
        if separator:
            attributes[key] = value


def parse_size(value: str) -> int:
    try:
        return max(0, int(value or "0"))
    except (TypeError, ValueError):
        return 0


def decide_action(
    attributes: dict[str, str],
    threshold_bytes: int,
    fallback_transport: str,
) -> str:
    size = parse_size(attributes.get("size", "0"))
    if size > threshold_bytes:
        return f"FILTER {fallback_transport}"
    return "DUNNO"


def write_action(stream: TextIO, action: str) -> None:
    stream.write(f"action={action}\n\n")
    stream.flush()


def log_event(message: str, priority: int = syslog.LOG_INFO) -> None:
    syslog.openlog("postfix-entra-size-policy", syslog.LOG_PID, syslog.LOG_MAIL)
    syslog.syslog(priority, message)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold-bytes", type=int, default=DEFAULT_THRESHOLD_BYTES)
    parser.add_argument("--fallback-transport", default=DEFAULT_FALLBACK_TRANSPORT)
    args = parser.parse_args(argv)
    if args.threshold_bytes < 1_000_000:
        parser.error("--threshold-bytes must be at least 1000000")
    if not TRANSPORT_RE.fullmatch(args.fallback_transport):
        parser.error("--fallback-transport must be transport:destination without whitespace")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    while True:
        request = read_request(sys.stdin)
        if request is None:
            return 0
        try:
            action = decide_action(
                request,
                args.threshold_bytes,
                args.fallback_transport,
            )
            if action.startswith("FILTER "):
                log_event(
                    " ".join(
                        (
                            "status=oversize_fallback",
                            f"size={parse_size(request.get('size', '0'))}",
                            f"threshold={args.threshold_bytes}",
                            f"sender={request.get('sender', '-') or '-'}",
                            f"recipient_count={request.get('recipient_count', '0') or '0'}",
                            f"instance={request.get('instance', '-') or '-'}",
                            f"transport={args.fallback_transport}",
                        )
                    ),
                    syslog.LOG_NOTICE,
                )
            write_action(sys.stdout, action)
        except Exception as exc:
            log_event(
                f"status=policy_error type={type(exc).__name__}",
                syslog.LOG_ERR,
            )
            write_action(sys.stdout, "DEFER_IF_PERMIT 4.3.5 size routing policy failure")


if __name__ == "__main__":
    raise SystemExit(main())
