import sqlite3
import unittest
from datetime import date

from analysis.data_freshness import get_market_data_freshness


class DataFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.execute("CREATE TABLE products (market_name TEXT, date TEXT)")
        self.today = date(2026, 10, 27)

    def add(self, market, day):
        self.conn.execute("INSERT INTO products VALUES (?, ?)", (market, day))

    def check(self, market=None, **kwargs):
        return get_market_data_freshness(self.conn, market, today=self.today, **kwargs)

    def test_no_data(self):
        self.assertEqual(self.check(), {"status": "missing", "latest_date": None, "age_days": None})

    def test_today_is_fresh(self):
        self.add("Migros", "2026-10-27")
        self.assertEqual(self.check()["age_days"], 0)
        self.assertEqual(self.check()["status"], "fresh")

    def test_seven_days_is_fresh(self):
        self.add("Migros", "2026-10-20")
        self.assertEqual(self.check()["status"], "fresh")

    def test_eight_days_is_stale(self):
        self.add("Migros", "2026-10-19")
        self.assertEqual(self.check()["status"], "stale")

    def test_market_filter_ignores_other_market(self):
        self.add("Migros", "2026-10-19")
        self.add("Other", "2026-10-27")
        self.assertEqual(self.check("Migros")["status"], "stale")
        self.assertEqual(self.check()["status"], "fresh")

    def test_future_date_is_not_fresh(self):
        self.add("Migros", "2026-10-28")
        self.assertEqual(self.check()["status"], "future")

    def test_invalid_date_is_not_fresh(self):
        self.add("Migros", "not-a-date")
        self.assertEqual(self.check()["status"], "invalid")

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ValueError):
            self.check(stale_after_days=-1)


if __name__ == "__main__":
    unittest.main()
