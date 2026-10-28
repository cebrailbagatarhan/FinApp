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

    def test_cli_refuses_database_overwrite(self):
        with self.assertRaises(SystemExit) as error:
            main(["--db", str(self.db), "--output", str(self.db)])
        self.assertEqual(error.exception.code, 2)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0], 3)

    def test_cli_refuses_existing_export_overwrite(self):
        output = Path(self.directory.name) / "existing.csv"
        output.write_text("keep me", encoding="utf-8")
        with self.assertRaises(SystemExit) as error:
            main(["--db", str(self.db), "--output", str(output)])
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep me")

    def test_cli_writes_utf8_csv_file(self):
        output = Path(self.directory.name) / "signals.csv"
        self.assertEqual(main(["--db", str(self.db), "--output", str(output), "--limit", "2"]), 0)
        with output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)


    def test_until_is_inclusive_and_can_combine_with_since_and_ticker(self):
        output = io.StringIO()
        count = export_signals(self.db, output, since="2026-01-01", until="2026-01-15", ticker="thyao")
        self.assertEqual(count, 1)
        self.assertEqual([r['date'] for r in csv.DictReader(io.StringIO(output.getvalue()))], ['2026-01-15'])

    def test_until_without_since_excludes_newer_records(self):
        output = io.StringIO()
        self.assertEqual(export_signals(self.db, output, until="2025-12-31"), 1)
        self.assertEqual([r['date'] for r in csv.DictReader(io.StringIO(output.getvalue()))], ['2025-12-31'])

    def test_invalid_until_and_reversed_range_rejected(self):
        for until in ('2026-02-30', '2026-1-15'):
            with self.subTest(until=until), self.assertRaises(ValueError):
                export_signals(self.db, io.StringIO(), until=until)
        with self.assertRaises(ValueError):
            export_signals(self.db, io.StringIO(), since='2026-01-20', until='2026-01-15')

    def test_cli_until_flag(self):
        output = Path(self.directory.name) / 'filtered.csv'
        self.assertEqual(main(['--db', str(self.db), '--until', '2026-01-15', '--output', str(output)]), 0)
        with output.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 2)



if __name__ == "__main__":
    unittest.main()
