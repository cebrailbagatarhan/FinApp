"""Read-only structural audit for the bundled Migros product basket CSV."""

import argparse
import csv
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "urunler.csv"
REQUIRED = {"Ürün Adı", "Migros_Link", "Kategori"}
ALLOWED_HOSTS = {"migros.com.tr", "www.migros.com.tr"}


def valid_link(value):
    """Validate a direct HTTPS Migros product link without making network calls."""
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname in ALLOWED_HOSTS
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and bool(parsed.path.strip("/"))
        )
    except ValueError:
        return False


def audit_basket(path):
    """Return counts and row numbers only; never echo product names or URLs."""
    categories = {}
    seen_names = set()
    seen_links = set()
    invalid = []
    rows = 0
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or set(fields) != REQUIRED:
            raise ValueError("CSV must have unique columns: Ürün Adı, Migros_Link, Kategori")
        for row in reader:
            rows += 1
            line = reader.line_num
            if None in row or any(value is None for value in row.values()):
                invalid.append({"line": line, "reason": "column count mismatch"})
                continue
            name = row["Ürün Adı"].strip()
            link = row["Migros_Link"].strip()
            category = row["Kategori"].strip()
            if not name or not category:
                invalid.append({"line": line, "reason": "missing name or category"})
            if not valid_link(link):
                invalid.append({"line": line, "reason": "invalid Migros HTTPS link"})
            if name:
                normalized_name = name.casefold()
                if normalized_name in seen_names:
                    invalid.append({"line": line, "reason": "duplicate product name"})
                seen_names.add(normalized_name)
            if link:
                if link in seen_links:
                    invalid.append({"line": line, "reason": "duplicate product link"})
                seen_links.add(link)
            if category:
                categories[category] = categories.get(category, 0) + 1
    return {
        "ok": rows > 0 and not invalid,
        "rows": rows,
        "categories": dict(sorted(categories.items())),
        "invalid_rows": invalid,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", nargs="?", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json", action="store_true", help="Print machine-readable report")
    args = parser.parse_args(argv)
    try:
        report = audit_basket(args.csv_file)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Products: {report['rows']} | Categories: {len(report['categories'])}")
        print(f"Invalid findings: {len(report['invalid_rows'])}")
        print("PASS" if report["ok"] else "FAIL (review basket CSV)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
