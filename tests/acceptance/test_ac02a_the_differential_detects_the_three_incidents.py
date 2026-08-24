"""req~ac-02a~1 -- the differential detects the three CSV incidents, with a clean control.

RED TODAY. `ingestproof.differential` does not exist.

    uv run pytest --runxfail \
        tests/acceptance/test_ac02a_the_differential_detects_the_three_incidents.py

WHERE THE DAMAGED SIDE COMES FROM, because this is the inner ring and there is no Spark in
it. Each incident's landed side below is the Spark 4.2.0 output RECORDED IN
`docs/measurements.md` section 6 -- measured outside this repository and copied in, which
is what the provenance header at the top of that file says. Running the production reader
here is `req~ac-08a~1`, which is nightly and has Spark.

That distinction is the generator's own. `tools/make_incident_fixtures.py` labels each
prediction "PREDICTION, not measured -- for the differential task", and says the
differential settles it. This file is where a prediction stops being one, against the
recorded reading rather than against a fresh run.

THE NEGATIVE CONTROL IS HALF THE CRITERION. "It flagged something" proves nothing; a
detector has to be shown able to stay quiet. `clean.csv` carries a quoted field with a
delimiter inside it -- the same shape as the escape incident, correctly written -- so a
detector that flags on the mere presence of a quote fails here and only here.

[utest->req~ac-02a~1]
"""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import pytest

MISSING = importlib.util.find_spec("ingestproof.differential") is None

pytestmark = pytest.mark.xfail(
    MISSING,
    strict=True,
    reason="the P2 differential item has not landed: ingestproof.differential does not exist",
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "incidents"

RFC4180 = dict(
    encoding="utf-8",
    delimiter=",",
    quotechar='"',
    escape="double",
    record_separator="\n",
    empty="empty-string",
)


def _dialect():
    from ingestproof.dialect import Dialect

    return Dialect(**RFC4180)  # type: ignore[arg-type]


# The three landed readings, quoted from docs/measurements.md section 6.
#
#   [A] multiLine=false -> 3 rows  [('1','line A'), ('line B"', None), ('2','ok')]
#   [B] escape absent   -> [('1', '"say ""hi""')]          -- the delimiter swallowed
#   [C] explicit schema, PERMISSIVE -> the extra field dropped in silence
#
# A `None` is a field the reader emitted as null; the header row is included because a
# landed table's first record is data, not a header, once it has been read.
LANDED = {
    "multiline.csv": (
        ("id", "note"),
        ("1", "line A"),
        ('line B"', None),
        ("2", "ok"),
    ),
    "escape.csv": (
        ("id", "name"),
        ("1", '"say ""hi""'),
    ),
    "extra_field.csv": (
        ("id", "name"),
        ("1", "ok"),
        ("2", "fine"),
        ("3", "4"),
    ),
}


def _detect(name: str):
    from ingestproof.differential import detect

    return detect((FIXTURES / name).read_bytes(), _dialect(), LANDED[name])


# --- the negative control, first, because the others mean nothing without it -------------


def test_the_clean_control_reports_no_damage_at_all() -> None:
    """`clean.csv` carries `2,"quoted, but well formed"` -- a delimiter inside a quoted
    field, which is the escape incident's shape written correctly. A detector that flags on
    a quote, or on a delimiter inside one, fails here and passes everything else.
    """
    from ingestproof.differential import detect

    source = (FIXTURES / "clean.csv").read_bytes()
    landed = (
        ("id", "name"),
        ("1", "ok"),
        ("2", "quoted, but well formed"),
        ("3", "fine"),
    )

    report = detect(source, _dialect(), landed)

    assert report.damages == ()
    assert report.records_compared == 4


# --- the three incidents ------------------------------------------------------------------


def test_incident_c_the_field_the_parser_knew_about_and_discarded() -> None:
    """The best paragraph in the corpus, in the words of docs/measurements.md section 6:
    the parser knew the record was damaged and discarded that information by default.

    PERMISSIVE dropped `EXTRA`; FAILFAST over the same bytes raises
    MALFORMED_RECORD_IN_PARSING. The differential recovers what the default threw away.
    """
    report = _detect("extra_field.csv")

    assert len(report.damages) == 1
    damage = report.damages[0]

    assert (damage.record_index, damage.field_index) == (3, 2)
    assert damage.expected == "EXTRA"
    assert damage.actual is None
    assert report.records_compared == 4


def test_incident_b_the_delimiter_the_reader_swallowed() -> None:
    """`1,"say ""hi"", bye"` is ONE field under RFC 4180 section 2.7 doubling. With the
    escape character absent the doubled quote closes the field early, the comma inside it
    becomes a delimiter, and the value lands as `"say ""hi""`.
    """
    report = _detect("escape.csv")

    assert len(report.damages) == 1
    damage = report.damages[0]

    assert (damage.record_index, damage.field_index) == (1, 1)
    assert damage.expected == 'say "hi", bye'
    assert damage.actual == '"say ""hi""'


def test_incident_a_needs_resynchronisation_before_it_can_be_located() -> None:
    """The one incident that is NOT a value comparison, and the differential must say so.

    Three records read as four rows, so the streams do not align and a positional
    comparison would report the misalignment instead of the damage -- about 500
    divergences for one, measured (docs/measurements.md section 3). The differential
    reports that resynchronisation is required rather than a list of values, and the span
    it names is bounded by where the streams re-agree.
    """
    report = _detect("multiline.csv")

    assert report.needs_resync is True
    assert report.records_compared == 3
    assert report.landed_records == 4

    # The damage is reported as a bounded SPAN, not as a per-field list, because after a
    # divergence the field-level comparison is meaningless until the streams re-agree.
    assert [(span.first_record, span.last_record) for span in report.spans] == [(1, 1)]


def test_the_three_incidents_are_three_and_the_control_is_quiet() -> None:
    """The criterion in one assertion: three detected, one silent.

    Stated together rather than only one per test, so a detector that finds all three by
    flagging everything is visible in the same place as the three that pass.
    """
    detected = {name: _detect(name) for name in LANDED}

    assert sorted(detected) == ["escape.csv", "extra_field.csv", "multiline.csv"]
    assert all(report.damages or report.needs_resync for report in detected.values())


def test_the_whole_corpus_is_swept_in_under_a_minute() -> None:
    """The criterion says under a minute, in CI. On these fixtures it is milliseconds.

    So this is not a performance claim -- it is a guard against an accidental quadratic in
    the comparison, which is the one way a value differential blows up, and which would be
    invisible on four files of thirty bytes if nothing timed it at all. The bound is the
    criterion's own number rather than a tighter one measured here, because a tighter one
    would be a number about this machine.
    """
    started = time.monotonic()

    for name in LANDED:
        _detect(name)

    assert time.monotonic() - started < 60
