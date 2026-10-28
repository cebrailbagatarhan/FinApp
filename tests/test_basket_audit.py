import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.basket_audit import audit_basket, main, valid_link


class BasketAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "basket.csv"

    def write(self, rows, fields=("Ürün Adı", "Migros_Link", "Kategori")):
        with self.path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            writer.writerows(rows)

    def test_valid_basket_and_category_counts(self):
        self.write([
            ["Süt", "https://www.migros.com.tr/sut-p-123", "Süt"],
            ["Ekmek", "https://migros.com.tr/ekmek-p-456", "Fırın"],
        ])
        report = audit_basket(self.path)
        self.assertTrue(report["ok"])
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["categories"], {"Fırın": 1, "Süt": 1})

    def test_duplicate_names_are_case_insensitive(self):
        self.write([
            ["SÜT", "https://www.migros.com.tr/a", "Süt"],
            ["süt", "https://www.migros.com.tr/b", "Süt"],
        ])
        self.assertIn("duplicate product name", [r["reason"] for r in audit_basket(self.path)["invalid_rows"]])

    def test_duplicate_links(self):
        self.write([
            ["A", "https://www.migros.com.tr/a", "Gıda"],
            ["B", "https://www.migros.com.tr/a", "Gıda"],
        ])
        self.assertIn("duplicate product link", [r["reason"] for r in audit_basket(self.path)["invalid_rows"]])

    def test_link_rejects_http_and_lookalike_hosts(self):
        for link in (
            "http://www.migros.com.tr/a",
            "https://www.migros.com.tr.evil.test/a",
            "https://user@www.migros.com.tr/a",
            "https://www.migros.com.tr/",
            "https://www.migros.com.tr:bad/a",
        ):
            with self.subTest(link=link):
                self.assertFalse(valid_link(link))

    def test_missing_fields_and_malformed_rows(self):
        self.write([["", "https://www.migros.com.tr/a", ""], ["A", "https://www.migros.com.tr/a"]])
        report = audit_basket(self.path)
        self.assertFalse(report["ok"])
        self.assertEqual([r["line"] for r in report["invalid_rows"]], [2, 3])

    def test_rejects_duplicate_headers(self):
        self.write([], fields=("Ürün Adı", "Migros_Link", "Migros_Link"))
        with self.assertRaises(ValueError):
            audit_basket(self.path)

    def test_empty_basket_is_not_ok(self):
        self.write([])
        self.assertFalse(audit_basket(self.path)["ok"])

    def test_cli_json_and_status(self):
        self.write([["A", "https://www.migros.com.tr/a", "Gıda"]])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main([str(self.path), "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["rows"], 1)
        self.assertEqual(main([str(self.path) + ".missing"]), 2)


if __name__ == "__main__":
    unittest.main()
