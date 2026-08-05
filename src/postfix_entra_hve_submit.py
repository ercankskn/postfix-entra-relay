#!/usr/bin/env python3
"""Postfix pipe helper for Microsoft 365 High Volume Email (HVE).

The helper accepts one recipient per invocation, rewrites the internal copy to the
HVE identity, preserves the original sender in non-sensitive headers, obtains an
OAuth client-credentials token, and submits with SMTP AUTH XOAUTH2.
"""

from __future__ import annotations

import argparse
import base64
import email.policy
import fcntl
import json
import os
import smtplib
import ssl
import sys
import syslog
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import formataddr, getaddresses
from pathlib import Path
from typing import Any, Mapping

EX_OK = 0
EX_TEMPFAIL = 75
EX_UNAVAILABLE = 69
DEFAULT_CONFIG = "/etc/postfix-entra-relay/hve-oauth.json"
DEFAULT_STATE_DIR = "/var/lib/postfix-entra-relay"
RETRY_SMTP_CODES = (421, 432, 450, 451, 452, 454)
RETRY_AUTH_MARKERS = ("5.7.142", "5.7.143")


class ConfigError(ValueError):
    """Raised when the runtime configuration is incomplete or unsafe."""


class TemporaryHveError(RuntimeError):
    """Raised for delivery errors that Postfix should retry."""


class PermanentHveError(RuntimeError):
    """Raised for delivery errors that should not be retried indefinitely."""


@dataclass(frozen=True)
class HveConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    auth_user: str
    display_name: str
    reply_to: str
    smtp_server: str = "smtp.hve.mx.microsoft"
    smtp_port: int = 587
    scope: str = "https://outlook.office.com/.default"
    token_refresh_margin_seconds: int = 1200
    connect_timeout_seconds: int = 30
    state_dir: str = DEFAULT_STATE_DIR
    bulk_to_threshold: int = 50
    bulk_alert_recipient: str = ""
    bulk_alert_state_max_age_seconds: int = 604800

    @property
    def token_url(self) -> str:
        return (
            "https://login.microsoftonline.com/"
            f"{self.tenant_id}/oauth2/v2.0/token"
        )


@dataclass(frozen=True)
class Token:
    access_token: str
    expires_at: int


def _required_string(data: Mapping[str, Any], key: str) -> str:
    value = str(data.get(key, "")).strip()
    if not value or value.startswith("<"):
        raise ConfigError(f"missing configuration value: {key}")
    return value


def load_config(path: str | os.PathLike[str]) -> HveConfig:
    config_path = Path(path)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration file not found: {config_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read configuration: {exc}") from exc

    cfg = HveConfig(
        tenant_id=_required_string(data, "tenant_id"),
        client_id=_required_string(data, "client_id"),
        client_secret=_required_string(data, "client_secret"),
        auth_user=_required_string(data, "auth_user").lower(),
        display_name=str(data.get("display_name", "Postfix Entra Relay")).strip(),
        reply_to=str(data.get("reply_to", "")).strip().lower(),
        smtp_server=str(data.get("smtp_server", "smtp.hve.mx.microsoft")).strip(),
        smtp_port=int(data.get("smtp_port", 587)),
        scope=str(data.get("scope", "https://outlook.office.com/.default")).strip(),
        token_refresh_margin_seconds=max(
            60, int(data.get("token_refresh_margin_seconds", 1200))
        ),
        connect_timeout_seconds=max(
            5, int(data.get("connect_timeout_seconds", 30))
        ),
        state_dir=str(data.get("state_dir", DEFAULT_STATE_DIR)).strip(),
        bulk_to_threshold=max(1, int(data.get("bulk_to_threshold", 50))),
        bulk_alert_recipient=str(data.get("bulk_alert_recipient", "")).strip().lower(),
        bulk_alert_state_max_age_seconds=max(
            3600, int(data.get("bulk_alert_state_max_age_seconds", 604800))
        ),
    )

    if cfg.smtp_port not in range(1, 65536):
        raise ConfigError("smtp_port must be between 1 and 65535")
    if "@" not in cfg.auth_user:
        raise ConfigError("auth_user must be an SMTP address")
    if cfg.reply_to and "@" not in cfg.reply_to:
        raise ConfigError("reply_to must be an SMTP address")
    return cfg


def normalize_address(value: str) -> str:
    addresses = getaddresses([value or ""])
    if not addresses:
        return ""
    return (addresses[0][1] or "").strip().lower()


def recipient_count(message: Any) -> int:
    fields: list[str] = []
    for name in ("to", "cc"):
        fields.extend(message.get_all(name, []))
    return len([addr for _, addr in getaddresses(fields) if addr])


def rewrite_message(
    raw_message: bytes,
    cfg: HveConfig,
    original_sender: str,
    queue_id: str,
) -> tuple[bytes, str, int]:
    message = BytesParser(policy=policy.SMTP).parsebytes(raw_message)
    original_header_from = str(message.get("From", "")).strip()

    for header in (
        "X-Postfix-Entra-Original-From",
        "X-Postfix-Entra-Original-Envelope-From",
        "X-Postfix-Entra-Route",
        "X-Postfix-Entra-Queue-ID",
    ):
        if header in message:
            del message[header]

    message["X-Postfix-Entra-Original-From"] = original_header_from or original_sender
    message["X-Postfix-Entra-Original-Envelope-From"] = original_sender
    message["X-Postfix-Entra-Route"] = "internal-hve"
    message["X-Postfix-Entra-Queue-ID"] = queue_id

    if "From" in message:
        del message["From"]
    message["From"] = formataddr((cfg.display_name, cfg.auth_user))

    if cfg.reply_to:
        if "Reply-To" in message:
            del message["Reply-To"]
        message["Reply-To"] = cfg.reply_to

    return message.as_bytes(policy=email.policy.SMTP), original_header_from, recipient_count(message)


class TokenCache:
    def __init__(self, cfg: HveConfig):
        self.cfg = cfg
        self.state_dir = Path(cfg.state_dir)
        self.cache_path = self.state_dir / "hve-token-cache.json"
        self.lock_path = self.state_dir / "hve-token-cache.lock"

    def _ensure_dir(self) -> None:
        self.state_dir.mkdir(mode=0o750, parents=True, exist_ok=True)

    def _read(self) -> Token | None:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            token = Token(
                access_token=str(data["access_token"]),
                expires_at=int(data["expires_at"]),
            )
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if token.expires_at - self.cfg.token_refresh_margin_seconds <= int(time.time()):
            return None
        return token

    def _write(self, token: Token) -> None:
        temp_path = self.cache_path.with_suffix(".tmp")
        payload = json.dumps(
            {"access_token": token.access_token, "expires_at": token.expires_at},
            separators=(",", ":"),
        )
        temp_path.write_text(payload, encoding="utf-8")
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, self.cache_path)

    def invalidate(self) -> None:
        try:
            self.cache_path.unlink()
        except FileNotFoundError:
            pass

    def get(self, force_refresh: bool = False) -> Token:
        self._ensure_dir()
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            os.chmod(self.lock_path, 0o600)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            if not force_refresh:
                cached = self._read()
                if cached:
                    return cached
            token = request_token(self.cfg)
            self._write(token)
            return token


def request_token(cfg: HveConfig) -> Token:
    body = urllib.parse.urlencode(
        {
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "grant_type": "client_credentials",
            "scope": cfg.scope,
        }
    ).encode("ascii")
    request = urllib.request.Request(
        cfg.token_url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=cfg.connect_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if 400 <= exc.code < 500:
            raise PermanentHveError(f"token endpoint rejected request: HTTP {exc.code}") from exc
        raise TemporaryHveError(f"token endpoint temporary error: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise TemporaryHveError(f"token endpoint unavailable: {exc}") from exc

    access_token = str(payload.get("access_token", ""))
    expires_in = int(payload.get("expires_in", 3600))
    if not access_token:
        raise TemporaryHveError("token endpoint returned no access_token")
    return Token(access_token=access_token, expires_at=int(time.time()) + expires_in)


def xoauth2_payload(auth_user: str, access_token: str) -> str:
    raw = f"user={auth_user}\x01auth=Bearer {access_token}\x01\x01".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _smtp_text(exc: BaseException) -> str:
    smtp_error = getattr(exc, "smtp_error", b"")
    if isinstance(smtp_error, bytes):
        return smtp_error.decode("utf-8", errors="replace")
    return str(smtp_error or exc)


def should_refresh_after_error(exc: BaseException) -> bool:
    text = _smtp_text(exc)
    return isinstance(exc, smtplib.SMTPAuthenticationError) or any(
        marker in text for marker in RETRY_AUTH_MARKERS
    )


def submit_message(
    cfg: HveConfig,
    token: Token,
    recipient: str,
    message_bytes: bytes,
) -> None:
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(
            cfg.smtp_server,
            cfg.smtp_port,
            timeout=cfg.connect_timeout_seconds,
        ) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            code, response = smtp.docmd(
                "AUTH", f"XOAUTH2 {xoauth2_payload(cfg.auth_user, token.access_token)}"
            )
            if code != 235:
                raise smtplib.SMTPAuthenticationError(code, response)
            smtp.sendmail(cfg.auth_user, [recipient], message_bytes)
    except smtplib.SMTPResponseException as exc:
        text = _smtp_text(exc)
        if exc.smtp_code in RETRY_SMTP_CODES or 400 <= exc.smtp_code < 500:
            raise TemporaryHveError(f"SMTP temporary failure {exc.smtp_code}: {text}") from exc
        if should_refresh_after_error(exc):
            raise
        raise PermanentHveError(f"SMTP permanent failure {exc.smtp_code}: {text}") from exc
    except (OSError, smtplib.SMTPException) as exc:
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            raise
        raise TemporaryHveError(f"SMTP connection failure: {exc}") from exc


def log_event(message: str, priority: int = syslog.LOG_INFO) -> None:
    syslog.openlog("postfix-entra-hve-submit", syslog.LOG_PID, syslog.LOG_MAIL)
    syslog.syslog(priority, message)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--queue-id", default="NOQUEUE")
    parser.add_argument("--original-sender", default="")
    parser.add_argument("--config", default=os.environ.get("POSTFIX_ENTRA_HVE_CONFIG", DEFAULT_CONFIG))
    parser.add_argument("--test-config", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    recipient = normalize_address(args.recipient)
    original_sender = normalize_address(args.original_sender)

    try:
        cfg = load_config(args.config)
        if not recipient:
            raise ConfigError("recipient is not a valid SMTP address")
        if args.test_config:
            print("HVE_CONFIG_OK")
            return EX_OK

        raw_message = sys.stdin.buffer.read()
        if not raw_message:
            raise PermanentHveError("empty message received from Postfix")
        rewritten, header_from, to_count = rewrite_message(
            raw_message, cfg, original_sender, args.queue_id
        )

        cache = TokenCache(cfg)
        for attempt in (1, 2):
            token = cache.get(force_refresh=attempt == 2)
            try:
                submit_message(cfg, token, recipient, rewritten)
                break
            except smtplib.SMTPAuthenticationError as exc:
                if attempt == 1 and should_refresh_after_error(exc):
                    cache.invalidate()
                    log_event(
                        f"status=token_retry queue_id={args.queue_id} recipient={recipient}",
                        syslog.LOG_WARNING,
                    )
                    continue
                raise TemporaryHveError(f"HVE authentication failed: {_smtp_text(exc)}") from exc

        log_event(
            " ".join(
                (
                    "status=sent",
                    f"queue_id={args.queue_id}",
                    f"recipient={recipient}",
                    f"original_sender={original_sender or '-'}",
                    f"original_header_from={normalize_address(header_from) or '-'}",
                    f"header_recipient_count={to_count}",
                )
            )
        )
        if to_count >= cfg.bulk_to_threshold:
            log_event(
                " ".join(
                    (
                        "status=bulk_recipient_threshold",
                        f"queue_id={args.queue_id}",
                        f"count={to_count}",
                        f"threshold={cfg.bulk_to_threshold}",
                    )
                ),
                syslog.LOG_WARNING,
            )
        return EX_OK
    except ConfigError as exc:
        log_event(f"status=config_error queue_id={args.queue_id} error={exc}", syslog.LOG_ERR)
        return EX_UNAVAILABLE
    except TemporaryHveError as exc:
        log_event(f"status=tempfail queue_id={args.queue_id} error={exc}", syslog.LOG_WARNING)
        return EX_TEMPFAIL
    except PermanentHveError as exc:
        log_event(f"status=failed queue_id={args.queue_id} error={exc}", syslog.LOG_ERR)
        return EX_UNAVAILABLE
    except Exception as exc:  # defensive Postfix boundary
        log_event(
            f"status=unexpected_error queue_id={args.queue_id} type={type(exc).__name__}",
            syslog.LOG_ERR,
        )
        return EX_TEMPFAIL


if __name__ == "__main__":
    raise SystemExit(main())
