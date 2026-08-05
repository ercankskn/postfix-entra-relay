from __future__ import annotations

import datetime as dt
import unittest

from src.postfix_entra_daily_origin_report import parse_events, summarize


class DailyReportTests(unittest.TestCase):
    def test_parse_iso_log_event(self):
        lines = [
            "2026-08-05T09:30:02+03:00 relay postfix-entra-hve-submit[1]: "
            "status=sent queue_id=ABC123 recipient=user@example.com original_sender=report@example.com\n"
        ]
        events = parse_events(lines, dt.date(2026, 8, 5))
        self.assertEqual(events[0]["queue"], "ABC123")
        self.assertEqual(events[0]["sender"], "report@example.com")

    def test_parse_ignores_other_date(self):
        lines = [
            "2026-08-04T09:30:02+03:00 relay postfix-entra-hve-submit[1]: "
            "status=sent queue_id=ABC123 recipient=user@example.com original_sender=report@example.com\n"
        ]
        self.assertEqual(parse_events(lines, dt.date(2026, 8, 5)), [])

    def test_summarize_counts_senders_case_insensitively(self):
        events = [
            {"sender": "Report@Example.com"},
            {"sender": "report@example.com"},
            {"sender": "scanner@example.com"},
        ]
        counts = summarize(events)
        self.assertEqual(counts["report@example.com"], 2)
        self.assertEqual(counts["scanner@example.com"], 1)


if __name__ == "__main__":
    unittest.main()
