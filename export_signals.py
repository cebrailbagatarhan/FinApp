"""Export previously saved trading signals without fetching data or modifying the DB.

Usage: python export_signals.py --since 2026-01-01 --until 2026-01-31 --ticker THYAO --output signals.csv
"""
import argparse
import csv
from datetime import date
from pathlib import Path
import sqlite3
import sys

from database import DB_PATH

COLUMNS = ("ticker", "signal_type", "signal_strength", "reason", "price_at_signal", "date")


def safe_cell(value):
    """Prevent CSV spreadsheet formula execution in user-controlled text."""
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_signals(db_path, destination, *, since=None, until=None, ticker=None, limit=1000):
    """Write saved signals as CSV; open SQLite in read-only mode."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"Veritabanı bulunamadı: {db_path}")
    if not 1 <= limit <= 10000:
        raise ValueError("limit 1 ile 10000 arasında olmalı")
    if since is not None:
        if len(since) != 10 or date.fromisoformat(since).isoformat() != since:
            raise ValueError("since YYYY-MM-DD biçiminde olmalı")
    if until is not None:
        if len(until) != 10 or date.fromisoformat(until).isoformat() != until:
            raise ValueError("until YYYY-MM-DD biçiminde olmalı")
    if since and until and since > until:
        raise ValueError("since tarihi until tarihinden sonra olamaz")

    where, params = [], []
    if since:
        where.append("date >= ?")
        params.append(since)
    if until:
        where.append("date <= ?")
        params.append(until)
    if ticker:
        where.append("UPPER(ticker) = ?")
        params.append(ticker.upper())
    sql = "SELECT " + ", ".join(COLUMNS) + " FROM signals"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(limit)

    writer = csv.writer(destination)
    writer.writerow(COLUMNS)
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        cursor = conn.execute(sql, params)
        count = 0
        for row in cursor:
            writer.writerow([safe_cell(value) for value in row])
            count += 1
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kayıtlı al/sat sinyallerini CSV olarak dışa aktar")
    parser.add_argument("--db", default=DB_PATH, help="Mevcut SQLite veritabanı yolu")
    parser.add_argument("--since", help="En erken sinyal tarihi (YYYY-MM-DD)")
    parser.add_argument("--until", help="En geç sinyal tarihi, dahil (YYYY-MM-DD)")
    parser.add_argument("--ticker", help="Hisse kodu filtresi")
    parser.add_argument("--limit", type=int, default=1000, help="En fazla 10000 kayıt")
    parser.add_argument("--output", help="CSV çıktı yolu (varsayılan: stdout)")
    args = parser.parse_args(argv)
    if args.output and Path(args.output).resolve() == Path(args.db).resolve():
        parser.error("CSV çıktı yolu veritabanıyla aynı olamaz")
    try:
        if args.output:
            with open(args.output, "x", newline="", encoding="utf-8-sig") as destination:
                count = export_signals(args.db, destination, since=args.since, until=args.until, ticker=args.ticker, limit=args.limit)
        else:
            count = export_signals(args.db, sys.stdout, since=args.since, until=args.until, ticker=args.ticker, limit=args.limit)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f"Dışa aktarma başarısız: {error}\n")
    print(f"{count} sinyal dışa aktarıldı.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
