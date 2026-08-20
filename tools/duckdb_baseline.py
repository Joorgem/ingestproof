"""The free baseline. This is what you get without this library, and it opens the README.

Measured claim (docs/measurements.md section 9): a twelve-line DuckDB script catches the
three CSV incidents with a clean negative control. The number is a claim about DuckDB, not
a target for this file -- if it takes more lines, the README says so.

Measured limit (section 2, re-probed): `reject_errors` populates only for rows DuckDB
REJECTS. The incident row `1,"say ""hi"", bye"` it parses correctly and emits no position
for. That is why DuckDB is this project's oracle of VALUE and never of position.

Measured RESULT, 2026-08-19, duckdb 1.5.5 (docs/duckdb-baseline-output.txt): the section 9
claim is FALSE. This script catches ONE of the three -- `extra_field`, the only file that
is malformed against its declared schema. `multiline` and `escape` it parses correctly and
silently, which is section 2 arriving at its conclusion: the incidents are damage done by
the PRODUCTION reader, not by the file, and a correct parser has nothing to reject. That
gap is the measured size of the problem this library solves, and it opens the README.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

INCIDENTS = Path("tests/fixtures/incidents")

CASES: tuple[tuple[str, dict[str, str]], ...] = (
    ("multiline.csv", {"id": "VARCHAR", "note": "VARCHAR"}),
    ("escape.csv", {"id": "VARCHAR", "name": "VARCHAR"}),
    ("extra_field.csv", {"id": "VARCHAR", "name": "VARCHAR"}),
    ("clean.csv", {"id": "VARCHAR", "name": "VARCHAR"}),
)


def _columns_clause(columns: dict[str, str]) -> str:
    # `columns` is a STRUCT literal in DuckDB's grammar, not a bindable parameter -- a
    # Python dict passed as `?` does not become one. The names and types are ours, never
    # user input, so building the clause as text is safe here.
    return "{" + ", ".join(f"'{name}': '{dtype}'" for name, dtype in columns.items()) + "}"


def probe(path: Path, columns: dict[str, str]) -> tuple[int, list[tuple[object, ...]]]:
    con = duckdb.connect()
    # Two measured details, both load-bearing on duckdb 1.5.5, and each one on its own is
    # enough to make the next statement raise CatalogException instead of returning rows.
    # The subquery: a bare `SELECT count(*) FROM read_csv(...)` is optimised into the scan,
    # which then never materialises the rejects tables at all. And `fetchall`, not
    # `fetchone`: the tables are registered when the result is drained, and a one-row
    # aggregate read with `fetchone` leaves it open.
    rows = con.execute(
        f"SELECT count(*) FROM (SELECT * FROM read_csv(?, header=true, "
        f"columns={_columns_clause(columns)}, store_rejects=true, strict_mode=true))",
        [str(path)],
    ).fetchall()
    rejects = con.execute(
        "SELECT line, column_idx, error_type, csv_line FROM reject_errors ORDER BY line"
    ).fetchall()
    con.close()
    return (int(rows[0][0]) if rows else 0, rejects)


def main() -> int:
    print(f"duckdb {duckdb.__version__}")
    for name, columns in CASES:
        count, rejects = probe(INCIDENTS / name, columns)
        print(f"\n{name}: {count} rows accepted, {len(rejects)} rejected")
        for reject in rejects:
            print(f"    line={reject[0]} col={reject[1]} {reject[2]}: {reject[3]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
