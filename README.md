# Pocket Warehouse ETL

How often does a lending library's science or music kit go out, and for how long? This small Python and SQLite project turns a CSV of fictional kit checkouts into a monthly report. The eight sample loans span four kits and total 32 loan days.

## Run the demo

From the repository root, use Python 3.9 or later. The pipeline uses the standard library.

```sh
python run.py
```

The command creates `build/lending.sqlite` and prints a summary. For example, the two Astronomy loans in April 2025 account for ten loan days. A loan counts toward the month of checkout, including its full duration if it crosses a month boundary.

## Follow one checkout

1. **Stage.** The pipeline reads `data/checkouts.csv` into `checkout_stage`, validating the six fields, ISO checkout date and positive loan duration. Each ticket identifies one checkout.
2. **Transform.** `sql/refresh.sql` builds `kit_catalog` with one row per kit and `kit_loan` with one row per checkout. A foreign key connects each loan to its kit.
3. **Report.** The `monthly_lending` view groups the loans by checkout month and kit family. To explore the result, open the generated database in a SQLite client and run:

```sql
SELECT loan_month, kit_family, loan_count, loan_days
FROM monthly_lending
ORDER BY loan_month, kit_family;
```

## Load another snapshot

```sh
python run.py --source example.csv --database build/example.sqlite
```

Use `data/checkouts.csv` as the header template. Each input is the entire snapshot. A successful refresh replaces the previous rows, so rerunning the same file gives the same report. A header-only file clears the snapshot. A duplicate ticket, inconsistent kit description or invalid row rolls back the refresh and preserves the previous snapshot.

## Run the tests

```sh
python -m unittest discover -s tests -v
```

The tests exercise repeat runs, smaller snapshots, and failures during both staging and transformation. Each test creates a temporary database.
