from __future__ import annotations

import argparse
import sys

try:
    import duckdb  # type: ignore
except Exception as e:  # pragma: no cover - convenience script
    print("DuckDB not available. Install via project deps.", file=sys.stderr)
    raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze OTel traces in DuckDB")
    parser.add_argument("--db", default="../../../traces.duckdb", help="Path to DuckDB file")
    parser.add_argument(
        "--sql",
        default="../analysis/queries.sql",
        help="SQL file with queries to run",
    )
    args = parser.parse_args()

    con = duckdb.connect(args.db, read_only=False)
    with open(args.sql, "r", encoding="utf-8") as f:
        sql_text = f.read()

    # naive split by semicolon for multiple statements
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]
    for stmt in statements:
        print("\n-- QUERY --\n", stmt)
        try:
            res = con.execute(stmt).fetchall()
            for row in res:
                print(row)
        except Exception as e:  # pragma: no cover - convenience script
            print(f"Query failed: {e}", file=sys.stderr)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
