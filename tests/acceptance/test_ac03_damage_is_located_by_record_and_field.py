"""req~ac-03~1 -- the report locates each damaged value by (record index, field index).

RED TODAY. `ingestproof.report` does not exist.

    uv run pytest tests/acceptance/test_ac03_damage_is_located_by_record_and_field.py --runxfail

RECORD INDEX IS NOT LINE NUMBER, AND THAT IS THE WHOLE OF THIS FILE. A record with an
embedded record separator inside a quoted field occupies two lines, so the two streams stop
agreeing at the first such record and never agree again. Measured (docs/measurements.md
section 3, docs/design.md section 5): one such record makes Spark emit 1,001 lines for
1,000 records, and a positional zip then reports about 500 divergences for one damage.

A report that located by line would be right until the first multiline record and wrong
after it, and it would be MORE wrong the larger the file -- which is the failure shape this
whole library exists to catch, arriving in the thing that reports it.

WHAT THIS FILE DOES NOT ASSERT, said plainly. `locate` is handed two ALIGNED record
streams. Producing them -- running two parsers over a corpus, and resynchronising after a
divergence -- is the differential and the resynchronisation, which docs/design.md section
15 assigns to a human or to adjudication rather than to the loop. What is asserted here is
that `locate` REFUSES misaligned input rather than zipping it, because a positional zip is
the defect above and a report built on one is worse than no report.

Byte position is layer 3 and the criterion says outright it is not required here.

[utest->req~ac-03~1]
"""
from __future__ import annotations

import csv
import importlib.util
import io
from pathlib import Path

import pytest

MISSING = importlib.util.find_spec("ingestproof.report") is None

# Applied PER TEST rather than as a module-level `pytestmark`, because one test here is a
# CONTROL that passes today and must go on passing: it compares the two readings of
# `multiline.csv` to each other and never touches `ingestproof.report`. Under a
# module-level strict xfail it is reported as XPASS(strict) -- a failure -- and CI is red
# for the one test in this file that is already right.
#
# `test_ac07_declaration_layer_needs_no_jvm.py` documents this trap in those words, and
# this file was written with a module-level marker anyway. What caught it was running in
# the repository: outside it, the fixture path does not resolve, so the control arm FAILED
# and the marker was satisfied for a reason that had nothing to do with the module.
needs_report = pytest.mark.xfail(
    MISSING,
    strict=True,
    reason="the P2 report item has not landed: ingestproof.report does not exist",
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "incidents"


def _rfc4180(name: str) -> tuple[tuple[str, ...], ...]:
    """The reference parse, by the stdlib rather than by this library.

    Two parsers or nothing: a report checked against this repository's own reader is a
    report checked against the thing that produced it.
    """
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return tuple(tuple(row) for row in csv.reader(io.StringIO(text)))


# `extra_field.csv` is `id,name` / `1,ok` / `2,fine` / `3,4,EXTRA`. Read RFC 4180 it is four
# records, the last carrying THREE fields. Read with an explicit two-column schema it is
# four records and the third field is dropped -- recorded in docs/measurements.md section 6
# as Spark 4.2.0 PERMISSIVE, "campo extra descartado EM SILENCIO", where FAILFAST over the
# same bytes raises MALFORMED_RECORD_IN_PARSING. The parser knew and discarded it.
SCHEMA_DROPPED_THE_FIELD = (
    ("id", "name"),
    ("1", "ok"),
    ("2", "fine"),
    ("3", "4"),
)


@needs_report
def test_a_field_present_on_one_side_and_absent_on_the_other_is_located() -> None:
    from ingestproof.report import Damage, locate

    damages = locate(_rfc4180("extra_field.csv"), SCHEMA_DROPPED_THE_FIELD)

    assert damages == (
        Damage(record_index=3, field_index=2, expected="EXTRA", actual=None),
    )


@needs_report
def test_a_value_that_differs_is_located_by_record_and_field_and_carries_both_sides() -> None:
    expected = (("id", "name"), ("1", "ok"), ("2", "fine"))
    actual = (("id", "name"), ("1", "ok"), ("2", "FINE"))

    from ingestproof.report import Damage, locate

    assert locate(expected, actual) == (
        Damage(record_index=2, field_index=1, expected="fine", actual="FINE"),
    )


@needs_report
def test_an_identical_pair_reports_nothing() -> None:
    # The negative control, and it is not decoration: without it every assertion above is
    # equally green for a `locate` that reports a damage for every field it is shown.
    clean = _rfc4180("clean.csv")

    from ingestproof.report import locate

    assert locate(clean, clean) == ()
    assert len(clean) == 4


@needs_report
def test_damages_come_back_ordered_by_record_then_field() -> None:
    """Order is the reading order of the file, so a triager reads top to bottom.

    Asserted over a pair whose damages are discovered out of order under any
    field-major traversal, so an implementation that walked fields first would be visible.
    """
    expected = (("a", "b", "c"), ("d", "e", "f"))
    actual = (("a", "B", "C"), ("D", "e", "F"))

    from ingestproof.report import locate

    assert [(damage.record_index, damage.field_index) for damage in locate(expected, actual)] == [
        (0, 1),
        (0, 2),
        (1, 0),
        (1, 2),
    ]


# --- the alignment trap -------------------------------------------------------------------


def _lines_not_records(name: str) -> tuple[tuple[str, ...], ...]:
    """What a reader that does not honour an embedded record separator produces.

    Recorded in docs/measurements.md section 6 as Spark 4.2.0 over this exact fixture with
    `multiLine=false`: THREE rows for two records -- `('1','line A')`, `('line B"', None)`
    and `('2','ok')`. Reproduced here by splitting on the separator, which is what such a
    reader is doing.
    """
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return tuple(tuple(line.split(",")) for line in text.splitlines())


def test_the_two_streams_really_do_disagree_on_length_for_the_multiline_incident() -> None:
    """The control arm for the refusal below, and it is what makes it mean anything.

    Without it, a `locate` that refused every pair would satisfy the next test, and the
    refusal would be proving nothing about alignment.
    """
    records = _rfc4180("multiline.csv")
    lines = _lines_not_records("multiline.csv")

    assert len(records) == 3
    assert len(lines) == 4
    assert records[1] == ("1", "line A\nline B")


@needs_report
def test_locate_refuses_streams_of_different_lengths_rather_than_zipping_them() -> None:
    """A positional zip over misaligned streams is the measured defect, not a fallback.

    One embedded separator makes every record after it line up against its neighbour, so
    the report fills with divergences that are the misalignment rather than the damage --
    about 500 for one, measured. Refusing names resynchronisation as what has to happen
    first, and resynchronisation is not this layer's.
    """
    from ingestproof.report import Misaligned, locate

    with pytest.raises(Misaligned) as raised:
        locate(_rfc4180("multiline.csv"), _lines_not_records("multiline.csv"))

    message = str(raised.value).lower()

    assert "3" in message and "4" in message
    assert "resync" in message or "resynchronis" in message


@needs_report
def test_a_damage_carries_no_line_number_because_a_line_is_not_what_it_locates_by() -> None:
    """Absence asserted on purpose, because a line number is the tempting wrong field.

    It is available at the moment the damage is found and it is right for every file
    without an embedded separator, which is exactly what makes it dangerous: it would be
    correct in every test anyone writes by hand and wrong on the corpus this library is for.
    """
    from ingestproof.report import Damage

    damage = Damage(record_index=1, field_index=0, expected="a", actual="b")

    for banned in ("line", "line_number", "lineno", "byte", "byte_position", "offset"):
        assert not hasattr(damage, banned), banned


@needs_report
def test_the_report_says_how_many_records_it_compared_so_a_count_is_never_a_rate() -> None:
    """A damage count without a denominator is the defect `req~ac-05~1` exists to correct.

    The spec says in its own words that the 452-of-459 and 39 figures "reuse a denominator
    from a different experiment and must be re-derived before being cited". A report that
    carries its own denominator makes that class of citation impossible from this side.
    """
    from ingestproof.report import Report, locate

    expected = _rfc4180("extra_field.csv")
    report = Report(
        damages=locate(expected, SCHEMA_DROPPED_THE_FIELD), records_compared=len(expected)
    )

    assert report.records_compared == 4
    assert len(report.damages) == 1
