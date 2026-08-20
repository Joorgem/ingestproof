"""Two things are asserted here, and the first matters more.

The fixtures must still be the exact bytes the generator wrote -- if git, an editor or a
checkout on another machine normalised one, every downstream measurement is about a
different file than the one it names.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.duckdb_baseline import CASES, probe
from tools.make_incident_fixtures import FIXTURES

INCIDENTS = Path("tests/fixtures/incidents")


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
