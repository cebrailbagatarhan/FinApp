"""Read-only coverage/quality report for the bundled monthly EVDS inflation CSV."""

import argparse
import csv
from datetime import date
import json
import math
from pathlib import Path
import sys

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "evds_inflation.csv"


def parse_month(value):
    """Accept a canonical first-of-month ISO date, never a partial date."""
    parsed = date.fromisoformat(value)
    if parsed.day != 1 or parsed.isoformat() != value:
        raise ValueError("expected YYYY-MM-01")
    return parsed


def next_month(month):
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def audit_csv(path, as_of=None):
    """Return metadata only; never modify the source CSV or echo cell values."""
    seen = set()
    duplicates = set()
    invalid = []
    count = 0
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or "Tarih" not in columns or "Genel TÜFE" not in columns:
            raise ValueError("CSV requires unique columns including Tarih and Genel TÜFE")
        numeric_columns = [column for column in columns if column != "Tarih"]
        for line_number, row in enumerate(reader, start=2):
            count += 1
            if None in row or any(value is None for value in row.values()):
                invalid.append({"line": line_number, "reason": "column count mismatch"})
                continue
            try:
                month = parse_month(row["Tarih"].strip())
            except (ValueError, TypeError):
                invalid.append({"line": line_number, "reason": "invalid month"})
                continue
            if month in seen:
                duplicates.add(month)
            seen.add(month)
            for column in numeric_columns:
                try:
                    value = float(row[column].strip())
                    if not math.isfinite(value):
                        raise ValueError("non-finite")
                except (ValueError, TypeError):
                    invalid.append({"line": line_number, "reason": f"invalid number in {column}"})
    ordered = sorted(seen)
    missing = []
    if ordered:
        cursor = ordered[0]
        while cursor < ordered[-1]:
            cursor = next_month(cursor)
            if cursor not in seen:
                missing.append(cursor.strftime("%Y-%m"))
    reference = as_of or date.today().replace(day=1)
    if reference.day != 1:
        raise ValueError("as_of must be a first-of-month date")
    stale = None
    if ordered:
        stale = max(0, (reference.year - ordered[-1].year) * 12 + reference.month - ordered[-1].month)
    return {
        "ok": bool(ordered) and not duplicates and not missing and not invalid,
        "rows": count,
        "first_month": ordered[0].strftime("%Y-%m") if ordered else None,
        "last_month": ordered[-1].strftime("%Y-%m") if ordered else None,
        "missing_months": missing,
        "duplicate_months": [item.strftime("%Y-%m") for item in sorted(duplicates)],
        "invalid_rows": invalid,
        "months_since_last": stale,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", nargs="?", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--as-of", help="Reference month (YYYY-MM), defaults to current month")
    parser.add_argument("--json", action="store_true", help="Print machine-readable report")
    args = parser.parse_args(argv)
    try:
        reference = None
        if args.as_of is not None:
            if len(args.as_of) != 7 or args.as_of[4] != "-":
                raise ValueError("--as-of must be YYYY-MM")
            reference = parse_month(args.as_of + "-01")
        report = audit_csv(args.csv_file, as_of=reference)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Rows: {report['rows']} | Coverage: {report['first_month']} .. {report['last_month']}")
        print(f"Missing: {len(report['missing_months'])} | Duplicates: {len(report['duplicate_months'])} | Invalid rows: {len(report['invalid_rows'])}")
        print(f"Months since latest data: {report['months_since_last']}")
        print("PASS" if report["ok"] else "FAIL (review CSV coverage/quality)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
