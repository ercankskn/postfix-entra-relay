from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from email.parser import BytesParser
from email import policy
from pathlib import Path
from unittest import mock

from src.postfix_entra_hve_submit import (
    ConfigError,
    HveConfig,
    Token,
    TokenCache,
    load_config,
    normalize_address,
    rewrite_message,
    should_refresh_after_error,
)
import smtplib


class HveSubmitTests(unittest.TestCase):
    def config(self, state_dir: str = "/tmp") -> HveConfig:
        return HveConfig(
            tenant_id="tenant.example",
            client_id="client.example",
            client_secret="unit-test-secret",
            auth_user="hve-relay@example.com",
            display_name="Application Mail Service",
            reply_to="relay@example.com",
            state_dir=state_dir,
        )

    def test_normalize_address(self):
        self.assertEqual(normalize_address("Display <USER@Example.COM>"), "user@example.com")

    def test_rewrite_message_preserves_origin(self):
        raw = b"From: Report <report@example.net>\r\nTo: One <one@example.com>\r\nSubject: Test\r\n\r\nBody\r\n"
        payload, original, count = rewrite_message(raw, self.config(), "report@example.net", "ABC123")
        message = BytesParser(policy=policy.default).parsebytes(payload)
        self.assertEqual(original, "Report <report@example.net>")
        self.assertEqual(message["X-Postfix-Entra-Original-Envelope-From"], "report@example.net")
        self.assertEqual(message["X-Postfix-Entra-Route"], "internal-hve")
        self.assertIn("hve-relay@example.com", message["From"])
        self.assertEqual(count, 1)

    def test_authentication_error_requests_refresh(self):
        error = smtplib.SMTPAuthenticationError(535, b"5.7.143 token expired")
        self.assertTrue(should_refresh_after_error(error))

    def test_generic_57127_authentication_error_requests_refresh(self):
        error = smtplib.SMTPAuthenticationError(
            535,
            b"5.7.127 XOAUTH2 authentication failed",
        )
        self.assertTrue(should_refresh_after_error(error))

    def test_token_cache_reads_valid_token(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = TokenCache(self.config(directory))
            cache._ensure_dir()
            cache._write(Token("cached-token", int(time.time()) + 7200))
            with mock.patch("src.postfix_entra_hve_submit.request_token") as request:
                token = cache.get()
            self.assertEqual(token.access_token, "cached-token")
            request.assert_not_called()

    def test_config_rejects_placeholders(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({
                "tenant_id": "<TENANT_ID>",
                "client_id": "client",
                "client_secret": "secret",
                "auth_user": "hve@example.com",
            }))
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
