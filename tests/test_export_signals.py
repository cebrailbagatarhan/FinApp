import csv
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from export_signals import export_signals, main


class ExportSignalsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "signals.db"
        with sqlite3.connect(self.db) as conn:
            conn.execute("""CREATE TABLE signals (
                id INTEGER PRIMARY KEY, ticker TEXT, signal_type TEXT,
                signal_strength TEXT, reason TEXT, price_at_signal REAL, date TEXT
            )""")
            conn.executemany(
                "INSERT INTO signals (ticker, signal_type, signal_strength, reason, price_at_signal, date) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("THYAO", "Buy", "Orta", "=HYPERLINK(\"bad\")", 123.5, "2026-01-15"),
                    ("AAPL", "Sell", "Normal", "MACD", 200, "2026-01-20"),
                    ("THYAO", "Hold", "Zayıf", "RSI", 100, "2025-12-31"),
                ],
            )

    def test_filters_and_escapes_spreadsheet_formulas(self):
        output = io.StringIO()
        self.assertEqual(export_signals(self.db, output, since="2026-01-01", ticker="thyao"), 1)
        rows = list(csv.DictReader(io.StringIO(output.getvalue())))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "THYAO")
        self.assertEqual(rows[0]["reason"], "'=HYPERLINK(\"bad\")")
        self.assertEqual(rows[0]["price_at_signal"], "123.5")

    def test_limit_and_newest_first(self):
        output = io.StringIO()
        self.assertEqual(export_signals(self.db, output, limit=1), 1)
        rows = list(csv.DictReader(io.StringIO(output.getvalue())))
        self.assertEqual(rows[0]["ticker"], "AAPL")

    def test_missing_db_does_not_create_file(self):
        missing = Path(self.directory.name) / "missing.db"
        with self.assertRaises(FileNotFoundError):
            export_signals(missing, io.StringIO())
        self.assertFalse(missing.exists())

    def test_invalid_date_and_limit(self):
        with self.assertRaises(ValueError):
            export_signals(self.db, io.StringIO(), since="2026-02-30")
        with self.assertRaises(ValueError):
            export_signals(self.db, io.StringIO(), limit=0)

    def test_cli_writes_utf8_csv_file(self):
        output = Path(self.directory.name) / "signals.csv"
        self.assertEqual(main(["--db", str(self.db), "--output", str(output), "--limit", "2"]), 0)
        with output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
