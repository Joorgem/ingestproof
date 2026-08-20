"""Three things are asserted here, and the first matters more.

The fixtures must still be the exact bytes the generator wrote -- if git, an editor or a
checkout on another machine normalised one, every downstream measurement is about a
different file than the one it names.

The second is what DuckDB PARSED out of the two incidents it accepts in silence. The
baseline's docstring says it parses them correctly; a count of accepted rows cannot say
that, so the values are asserted here and the claim has an artefact behind it.

The third is docs/duckdb-baseline-output.txt, which a later task quotes verbatim in the
README. It is not frozen, so this is the only thing that goes red when it drifts.
"""
from __future__ import annotations

import duckdb
import pytest

from tools.duckdb_baseline import CASES, _columns_clause, main, probe
from tools.make_incident_fixtures import FIXTURES, INCIDENTS, ROOT

# Both anchored on the repository root, never on the current directory: pytest does not
# chdir, so a cwd-relative path turns `pytest` run from tests/unit into a FileNotFoundError
# that says nothing about the fixtures. INCIDENTS is imported, not redeclared -- one
# definition, in the generator that writes the directory.
BASELINE_OUTPUT = ROOT / "docs" / "duckdb-baseline-output.txt"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_the_committed_fixture_is_byte_identical_to_the_generator(name: str) -> None:
    assert (INCIDENTS / name).read_bytes() == FIXTURES[name]


def test_the_multiline_fixture_still_has_its_embedded_newline() -> None:
    # The single most rewritable byte in the repository. Named separately so a failure
    # points at the cause rather than at "bytes differ".
    payload = (INCIDENTS / "multiline.csv").read_bytes()

    assert b'"line A\nline B"' in payload
    assert b"\r" not in payload


def test_every_case_names_a_fixture_that_exists() -> None:
    for name, _ in CASES:
        assert (INCIDENTS / name).exists()


def test_the_clean_control_produces_no_rejects() -> None:
    # If the control ever rejects, the baseline is measuring the reader, not the file.
    _, rejects = probe(INCIDENTS / "clean.csv", {"id": "VARCHAR", "name": "VARCHAR"})

    assert rejects == []


def _parsed(name: str, columns: dict[str, str]) -> list[tuple[object, ...]]:
    # `probe` answers "how many rows and which rejects". The claim in the baseline's
    # docstring -- that DuckDB parses the two silent incidents CORRECTLY -- is about the
    # VALUES, and a count of 1 with 0 rejects does not say what the field contains.
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_csv(?, header=true, "
            f"columns={_columns_clause(columns)}, strict_mode=true)",
            [str(INCIDENTS / name)],
        ).fetchall()
    finally:
        con.close()


def test_duckdb_keeps_the_newline_inside_the_multiline_quoted_field() -> None:
    # Two records, not three, and the embedded newline still inside the field. This is the
    # half of "parses correctly" that the accepted-row count of 2 only implies.
    assert _parsed("multiline.csv", {"id": "VARCHAR", "note": "VARCHAR"}) == [
        ("1", "line A\nline B"),
        ("2", "ok"),
    ]


def test_duckdb_unescapes_the_doubled_quote_in_the_escape_fixture() -> None:
    # The whole incident: the doubled quote becomes one quote and the delimiter inside the
    # quoted field is NOT a delimiter. One accepted row with 0 rejects proves the field
    # boundary was honoured; only this proves the unescaping was.
    assert _parsed("escape.csv", {"id": "VARCHAR", "name": "VARCHAR"}) == [
        ("1", 'say "hi", bye'),
    ]


def test_the_committed_baseline_output_still_matches_what_main_prints(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # docs/duckdb-baseline-output.txt is quoted verbatim in the README. It is not frozen,
    # so nothing else notices a DuckDB bump, an edit to CASES, or a hand edit to the file.
    assert main() == 0

    printed = capsys.readouterr().out

    # read_text translates line endings on the way in, deliberately: `.gitattributes`
    # already pins this file to LF on checkout, and capsys always yields "\n". Comparing
    # raw bytes would make the test red on a working tree that git checked out with CRLF
    # -- a fact about the clone, not drift in the measurement this test guards.
    assert printed == BASELINE_OUTPUT.read_text(encoding="utf-8")
