"""The free baseline. This is what you get without this library.

Measured claim (docs/measurements.md section 9): a twelve-line DuckDB script catches the
three CSV incidents with a clean negative control. The number is a claim about DuckDB, not
a target for this file -- if it takes more lines, the number to publish is this file's own.

Measured limit (section 2, re-probed): `reject_errors` populates only for rows DuckDB
REJECTS. The incident row `1,"say ""hi"", bye"` it parses correctly and emits no position
for. That is why DuckDB is this project's oracle of VALUE, and an oracle of position only
for the rows it rejects.

Measured RESULT, 2026-08-19, duckdb 1.5.5 (docs/duckdb-baseline-output.txt): the section 9
claim is FALSE. This script catches ONE of the three -- `extra_field`, the only file that
is malformed against its declared schema. `multiline` and `escape` it parses correctly and
silently, which is section 2 arriving at its conclusion: a correct parser has nothing to
reject in a well-formed file. That the damage is done instead by the PRODUCTION reader is
a PREDICTION and is not measured here -- the differential task settles it, and
tools/make_incident_fixtures.py marks each prediction where the bytes are defined. What is
measured is the gap: one of three, with a negative control that stayed silent.

Putting that gap at the top of the README is what this file is for, and the README carries
it: docs/duckdb-baseline-output.txt is quoted there verbatim, under "Start with what you
already have for free".

Run it as `uv run python -m tools.duckdb_baseline` from the repository root -- the module
path needs the root on sys.path. The fixture directory is resolved by
tools/make_incident_fixtures.py from ITS OWN location rather than from the working
directory, so only that first hop depends on where you stand.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

# The fixture directory has ONE definition, in the generator that writes it, anchored on
# that module's own file rather than on the current directory. This script reads what that
# module wrote, so importing the location states the same fact once instead of twice.
from tools.make_incident_fixtures import INCIDENTS

CASES: tuple[tuple[str, dict[str, str]], ...] = (
    ("multiline.csv", {"id": "VARCHAR", "note": "VARCHAR"}),
    ("escape.csv", {"id": "VARCHAR", "name": "VARCHAR"}),
    ("extra_field.csv", {"id": "VARCHAR", "name": "VARCHAR"}),
    ("clean.csv", {"id": "VARCHAR", "name": "VARCHAR"}),
)


def _columns_clause(columns: dict[str, str]) -> str:
    # Built as TEXT by choice, not by necessity: measured on duckdb 1.5.5, DuckDB accepts
    # the same mapping bound as `?` and returns the same columns, rows and rejects. Text
    # keeps `_read_csv_clause` a fragment with a single bound parameter, the path. The
    # names and types are ours, never user input, so building the clause as text is safe
    # here.
    return "{" + ", ".join(f"'{name}': '{dtype}'" for name, dtype in columns.items()) + "}"


def _read_csv_clause(columns: dict[str, str]) -> str:
    # The ONE definition of the read this baseline performs, options included. Callers add
    # their own projection around it and nothing else. `store_rejects=true` is part of the
    # read rather than a reporting flag: measured on duckdb 1.5.5, without it a file that
    # violates its declared schema (extra_field.csv) fails in the CSV SNIFFER with
    # InvalidInputException instead of returning its valid rows. So the option list decides
    # WHICH ROWS COME BACK, and a second copy of it that drifted from this one would be a
    # different measurement wearing the same name -- silently, because the fixtures that
    # produce no rejects parse identically either way.
    return (
        f"read_csv(?, header=true, columns={_columns_clause(columns)}, "
        f"store_rejects=true, strict_mode=true)"
    )


def probe(path: Path, columns: dict[str, str]) -> tuple[int, list[tuple[object, ...]]]:
    con = duckdb.connect()
    try:
        # `fetchall`, not `fetchone`: the rejects tables are registered when the result is
        # DRAINED, and a one-row aggregate read with `fetchone` leaves it open, so the next
        # statement raises CatalogException instead of returning rows. Measured on duckdb
        # 1.5.5, where wrapping this read in `SELECT count(*) FROM (SELECT * FROM ...)`
        # changed neither the counts nor the rejects on these fixtures, so it is counted
        # directly.
        #
        # Draining is NECESSARY AND NOT SUFFICIENT, and whoever copies this read pattern
        # needs the second half. Re-measured on duckdb 1.5.5 against clean.csv: with
        # `store_rejects=false` the count above still returns its rows and the
        # `reject_errors` read below still raises CatalogException, because those tables
        # are never registered at all. Draining fixes one cause, not both.
        # docs/measurements.md section 12.6.
        rows = con.execute(
            f"SELECT count(*) FROM {_read_csv_clause(columns)}",
            [str(path)],
        ).fetchall()
        rejects = con.execute(
            "SELECT line, column_idx, error_type, csv_line FROM reject_errors ORDER BY line"
        ).fetchall()
    finally:
        # In a `finally` because both statements above raise on ordinary inputs. Measured
        # on duckdb 1.5.5: a path matching no file raises IOException out of the first, and
        # the second raises CatalogException when the rejects tables were never registered.
        # NOT a row that violates the declared schema: `store_rejects` diverts that one,
        # which is why extra_field.csv returns both rows and a reject rather than raising.
        # The rejects tables live inside the connection, so a leak here is a leaked catalog.
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
