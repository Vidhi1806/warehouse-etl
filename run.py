"""Refresh a local lending warehouse from a checkout CSV snapshot."""

import argparse
import csv
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ("ticket_code", "kit_code", "kit_label", "kit_family", "loan_day", "days_out")


def read_checkouts(source):
    """Yield validated rows and identify malformed records by line number."""
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"expected CSV header {','.join(FIELDS)}")
        for row in reader:
            if None in row or any(not (row[name] or "").strip() for name in FIELDS):
                raise ValueError(f"line {reader.line_num}: expected six nonempty fields")
            ticket, kit, label, family, day, duration = (row[name].strip() for name in FIELDS)
            try:
                canonical_day = date.fromisoformat(day).isoformat()
                days_out = int(duration)
                if day != canonical_day or not 1 <= days_out <= 2147483647:
                    raise ValueError
            except ValueError as error:
                raise ValueError(f"line {reader.line_num}: invalid loan_day or days_out") from error
            yield ticket, kit, label, family, canonical_day, days_out


def refresh(source, database):
    """Replace one complete snapshot and return its monthly summary."""
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    transforms = (ROOT / "sql" / "refresh.sql").read_text(encoding="utf-8")
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        # Keep schema creation, staging and publishing in a single transaction.
        with connection:
            connection.executescript("BEGIN IMMEDIATE;\n" + schema)
            connection.execute("DELETE FROM checkout_stage")
            connection.executemany(
                "INSERT INTO checkout_stage "
                "(ticket_code, kit_code, kit_label, kit_family, loan_day, days_out) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                read_checkouts(source),
            )
            # executescript can implicitly commit. Execute the individual load
            # statements to preserve the transaction opened above.
            statement = ""
            for line in transforms.splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    connection.execute(statement)
                    statement = ""
            if statement.strip():
                raise ValueError("incomplete SQL statement in refresh script")
            return connection.execute(
                "SELECT loan_month, kit_family, loan_count, loan_days "
                "FROM monthly_lending ORDER BY loan_month, kit_family"
            ).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data" / "checkouts.csv")
    parser.add_argument("--database", type=Path, default=ROOT / "build" / "lending.sqlite")
    args = parser.parse_args()
    try:
        rows = refresh(args.source, args.database)
    except (ValueError, csv.Error, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Refresh failed: {error}\n")
    print("Month    Family           Loans  Loan days")
    for month, family, loans, days in rows:
        print(f"{month}  {family:<15}  {loans:>4}  {days:>9}")


if __name__ == "__main__":
    main()
