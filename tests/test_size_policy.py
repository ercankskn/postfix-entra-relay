from __future__ import annotations

import io
import unittest

from src.postfix_entra_size_policy import (
    decide_action,
    parse_size,
    read_request,
    write_action,
)


class SizePolicyTests(unittest.TestCase):
    def test_reads_postfix_policy_request(self):
        request = read_request(
            io.StringIO(
                "request=smtpd_access_policy\n"
                "protocol_state=END-OF-MESSAGE\n"
                "size=9100000\n\n"
            )
        )
        self.assertEqual(request["size"], "9100000")

    def test_oversize_message_uses_exo_filter(self):
        action = decide_action(
            {"size": "9100000"},
            9_000_000,
            "smtp:[smtp.office365.com]:587",
        )
        self.assertEqual(action, "FILTER smtp:[smtp.office365.com]:587")

    def test_safe_message_uses_normal_transport_map(self):
        action = decide_action(
            {"size": "8999999"},
            9_000_000,
            "smtp:[smtp.office365.com]:587",
        )
        self.assertEqual(action, "DUNNO")

    def test_invalid_size_is_safe_default(self):
        self.assertEqual(parse_size("not-a-number"), 0)

    def test_response_format(self):
        output = io.StringIO()
        write_action(output, "DUNNO")
        self.assertEqual(output.getvalue(), "action=DUNNO\n\n")


if __name__ == "__main__":
    unittest.main()
