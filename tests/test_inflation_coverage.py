import csv
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

from scripts.inflation_coverage import audit_csv, main, parse_month


class InflationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sample.csv"

    def write(self, rows, header=("Tarih", "Genel TÜFE", "Gıda")):
        with self.path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    def audit(self):
        return audit_csv(self.path, as_of=date(2025, 5, 1))

    def test_contiguous_months_and_staleness(self):
        self.write([["2025-01-01", "10.1", "11"], ["2025-02-01", "10.2", "12"], ["2025-03-01", "10.3", "13"]])
        report = self.audit()
        self.assertTrue(report["ok"])
        self.assertEqual((report["rows"], report["months_since_last"]), (3, 2))
        self.assertEqual((report["first_month"], report["last_month"]), ("2025-01", "2025-03"))

    def test_missing_month(self):
        self.write([["2025-01-01", "10", "11"], ["2025-03-01", "12", "13"]])
        self.assertEqual(self.audit()["missing_months"], ["2025-02"])
        self.assertFalse(self.audit()["ok"])

    def test_duplicate_month(self):
        self.write([["2025-01-01", "10", "11"], ["2025-01-01", "12", "13"]])
        self.assertEqual(self.audit()["duplicate_months"], ["2025-01"])

    def test_invalid_numbers_and_dates(self):
        self.write([["2025-01-02", "10", "11"], ["2025-02-01", "nan", "11"], ["2025-03-01", "12", ""]])
        report = self.audit()
        self.assertEqual(len(report["invalid_rows"]), 3)
        self.assertFalse(report["ok"])

    def test_malformed_header_and_row(self):
        self.write([["2025-01-01", "10"]], header=("Tarih", "Genel TÜFE", "Gıda"))
        self.assertEqual(self.audit()["invalid_rows"][0]["reason"], "column count mismatch")
        self.write([], header=("Tarih", "Tarih", "Genel TÜFE"))
        with self.assertRaises(ValueError):
            self.audit()

    def test_empty_data_is_not_ok(self):
        self.write([])
        self.assertFalse(self.audit()["ok"])
        self.assertIsNone(self.audit()["months_since_last"])

    def test_cli_json_and_exit_status(self):
        self.write([["2025-01-01", "10", "11"]])
        output = io.StringIO()
        with redirect_stdout(output):
            code = main([str(self.path), "--as-of", "2025-02", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["months_since_last"], 1)
        self.assertEqual(main([str(self.path), "--as-of", "2025-99"]), 2)

    def test_strict_month_format(self):
        for value in ("2025-1-01", "2025-01-02", "2025-13-01"):
            with self.assertRaises(ValueError):
                parse_month(value)


if __name__ == "__main__":
    unittest.main()
