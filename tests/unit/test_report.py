"""Unit ring for `ingestproof.report`.

The frozen acceptance file judges the criterion over the incident fixtures. This file
judges what those do not reach: the absent-versus-null distinction the sentinel exists
for, the container guards, the ordering under shapes no fixture has, and the two things
`Damage` deliberately does not carry.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from ingestproof.dialect import Dialect, parse_records
from ingestproof.report import Damage, Misaligned, Report, locate, report

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "incidents"

RFC4180 = Dialect(
    encoding="utf-8",
    delimiter=",",
    quotechar='"',
    escape="double",
    record_separator="\n",
    empty="empty-string",
)


# --- what locate finds --------------------------------------------------------------------


def test_an_identical_pair_reports_nothing() -> None:
    # The negative control. Without it every assertion below is equally green for a
    # `locate` that reports a damage for every field it is shown.
    stream = (("a", "b"), ("c", "d"))

    assert locate(stream, stream) == ()


def test_a_differing_value_is_located_and_carries_both_sides() -> None:
    assert locate((("a", "b"),), (("a", "B"),)) == (
        Damage(record_index=0, field_index=1, expected="b", actual="B"),
    )


def test_damages_come_back_ordered_by_record_then_field() -> None:
    # Reading order, so a triager reads the report the way they read the file. Asserted
    # over a pair whose damages are discovered out of order under any field-major walk.
    damages = locate((("a", "b", "c"), ("d", "e", "f")), (("a", "B", "C"), ("D", "e", "F")))

    assert [(one.record_index, one.field_index) for one in damages] == [
        (0, 1),
        (0, 2),
        (1, 0),
        (1, 2),
    ]


def test_a_field_present_on_one_side_only_is_located_at_its_index() -> None:
    assert locate((("a", "b", "c"),), (("a", "b"),)) == (
        Damage(record_index=0, field_index=2, expected="c", actual=None),
    )
    assert locate((("a", "b"),), (("a", "b", "c"),)) == (
        Damage(record_index=0, field_index=2, expected=None, actual="c"),
    )


def test_an_empty_pair_of_streams_is_no_damage_and_not_an_error() -> None:
    assert locate((), ()) == ()


def test_records_of_zero_fields_compare_clean() -> None:
    # A blank line reads as a record of no fields -- `dialect.parse_records` and
    # `csv.reader` agree on that -- so two of them must compare clean rather than raise.
    assert locate(((), ()), ((), ())) == ()


# --- the sentinel, and the silent loss it exists to prevent --------------------------------


def test_a_field_that_is_ABSENT_and_one_that_is_NULL_are_not_the_same_fact() -> None:
    """The damage that would have gone unreported, which is a silent loss.

    `dialect.parse_records` returns `None` for an unquoted empty field under
    `empty="null"`, so `None` already means "present and null". An absent field compared as
    `None` too makes the two EQUAL -- measured before the sentinel, `('a', None)` against
    `('a',)` yielded nothing at all. In the function whose job is to lose nothing.

    The `Damage` still reports `None` on both sides, because the criterion's vocabulary is
    (record index, field index) and has no third state. What matters is that it is reported.
    """
    damages = locate((("a", None),), (("a",),))

    assert damages == (Damage(record_index=0, field_index=1, expected=None, actual=None),)


def test_two_fields_that_are_both_present_and_null_compare_clean() -> None:
    # The other side of the sentinel: it must not turn every null into a damage.
    assert locate((("a", None),), (("a", None),)) == ()


def test_two_records_of_equal_length_and_equal_values_are_clean() -> None:
    # This was written claiming to cover an absent-on-BOTH-sides case, and that comment
    # described a mechanism `locate` does not have: it compares PAIRWISE, so there is no
    # third record, and these two are equal-length anyway. The branch it claimed to reach
    # could not fire at all, and the false comment is what would have stopped a reader
    # noticing. The branch is gone; this is the plain assertion it always was.
    assert locate((("a",), ("b",)), (("a",), ("b",))) == ()


# --- the refusal ---------------------------------------------------------------------------


def test_streams_of_different_lengths_are_refused_rather_than_zipped() -> None:
    """A positional zip over misaligned streams is the measured defect, not a fallback.

    One embedded record separator makes every record after it line up against its
    neighbour, so the report fills with divergences that are the misalignment rather than
    the damage -- about 500 for one, recorded in docs/measurements.md section 3.
    """
    with pytest.raises(Misaligned) as raised:
        locate((("a",),), (("a",), ("b",)))

    message = str(raised.value)

    assert "1" in message and "2" in message
    assert "resynchronise" in message.lower()


def test_the_refusal_fires_before_any_value_is_compared() -> None:
    # Not an optimisation: comparing values across misaligned streams is the thing that
    # produces the 500-for-1 report, so it must not happen at all.
    compared: list[str] = []

    class Watching(str):
        def __eq__(self, other: object) -> bool:
            compared.append("eq")
            return str.__eq__(self, other) is True

        def __hash__(self) -> int:
            return str.__hash__(self)

    with pytest.raises(Misaligned):
        locate(((Watching("a"),),), ((Watching("a"),), (Watching("b"),)))

    assert compared == []


@pytest.mark.parametrize("which", ("expected", "actual"), ids=("left", "right"))
def test_a_stream_that_is_not_iterable_is_refused_rather_than_escaping(which: str) -> None:
    # The same guard `promotion._snapshot` carries: reading a caller's container is itself
    # caller code, and a bare TypeError escaping means a caller catching Misaligned sees
    # nothing at all.
    streams = {"expected": (("a",),), "actual": (("a",),)}
    streams[which] = None  # type: ignore[assignment]

    with pytest.raises(Misaligned, match="not iterable"):
        locate(streams["expected"], streams["actual"])  # type: ignore[arg-type]


def test_a_stream_whose_iteration_raises_is_refused_rather_than_escaping() -> None:
    class Unreadable(list[object]):
        def __iter__(self) -> object:
            raise RuntimeError("the caller's container cannot be read")

    with pytest.raises(Misaligned, match="could not be read"):
        locate(Unreadable([("a",)]), (("a",),))  # type: ignore[arg-type]


def test_a_RECORD_that_is_not_iterable_is_refused_and_the_message_names_its_index() -> None:
    # A malformed record inside a well-formed stream. The index is in the message because
    # a stream of a million records needs to say which one.
    with pytest.raises(Misaligned, match="record 1 of the actual stream"):
        locate((("a",), ("b",)), (("a",), None))  # type: ignore[list-item]


# --- what Damage deliberately does not carry -----------------------------------------------


def test_the_denominator_is_what_was_compared_and_not_a_second_read() -> None:
    """A `Report` claiming ONE DAMAGE OUT OF ZERO RECORDS COMPARED, measured.

    `report` used to snapshot `expected` a second time for the denominator. For a
    generator the second read comes back empty, so the damages were right and the number
    they were out of was zero -- in the field that exists precisely so a count is never
    published as a rate. `locate` delegates to `report` now, and the stream is read once.
    """

    def stream() -> object:
        yield ("a",)
        yield ("b",)
        yield ("c",)

    result = report(stream(), (("a",), ("X",), ("c",)))  # type: ignore[arg-type]

    assert result.records_compared == 3
    assert result.damages == (
        Damage(record_index=1, field_index=0, expected="b", actual="X"),
    )


@pytest.mark.parametrize(
    "stream",
    ("hello", b"hello", bytearray(b"hi")),
    ids=("str", "bytes", "bytearray"),
)
def test_a_string_is_refused_because_a_string_is_a_sequence_of_characters(
    stream: object,
) -> None:
    """`str` IS a `Sequence[str]`, so `Sequence[Record]` accepts one and mypy says nothing.

    Measured: `report("hello", "hello")` answered zero damages out of FIVE RECORDS
    COMPARED -- a plausible, publishable, wrong denominator from a caller who passed one
    record where a stream belongs. This is a check on the CONTAINER, not on a value, so it
    does not cross the line `_snapshot` draws about comparing.
    """
    with pytest.raises(Misaligned, match="sequence of characters"):
        report(stream, stream)  # type: ignore[arg-type]


def test_a_mapping_record_is_refused_because_iterating_one_yields_its_keys() -> None:
    """Two records agreeing on every key and differing on every value compared CLEAN.

    `promotion.Record` is a `Mapping` in this same package, so handing one module's record
    to the other is a step a caller can take -- and it produced a clean bill of health on
    data where nothing matched.
    """
    with pytest.raises(Misaligned, match="yields its KEYS"):
        locate([{"id": "2", "name": "fine"}], [{"id": "2", "name": "OTHER"}])  # type: ignore[list-item]


def test_the_refusal_carries_a_reason_a_caller_can_branch_on() -> None:
    # Not a substring of the message. A length mismatch is what resynchronisation exists
    # for; a record that is not a sequence is a caller's bug. A caller telling them apart
    # by matching on prose is a caller depending on prose.
    reasons = []
    for left, right in (
        ((("a",),), (("a",), ("b",))),
        (None, (("a",),)),
        ("hello", "hello"),
    ):
        with pytest.raises(Misaligned) as raised:
            locate(left, right)  # type: ignore[arg-type]
        reasons.append(raised.value.reason)

    assert reasons == ["length", "unreadable", "not-a-sequence"]


def test_a_comparison_that_raises_does_not_discard_the_damages_already_found() -> None:
    """All-or-nothing was the defect, not the exception type.

    Measured: 999 real damages found, one bad value at record 999, and every one of the
    999 was discarded -- in a module whose docstring says the job is to lose nothing. A
    comparison that fails answers NOT SAME now, which is the conservative direction here
    for the same reason quarantine is in `promotion`: a pair this library cannot show to
    be equal is one it must not certify as equal.
    """

    class Boom(str):
        def __eq__(self, other: object) -> bool:
            raise ValueError("the caller's __eq__")

        def __hash__(self) -> int:
            return str.__hash__(self)

    damages = locate((("x",), (Boom("a"),)), (("y",), ("a",)))

    assert [(one.record_index, one.field_index) for one in damages] == [(0, 0), (1, 0)]


@pytest.mark.parametrize("value", (None, "", "a", 0, object()), ids=lambda v: type(v).__name__)
def test_a_field_present_on_one_side_is_a_damage_whatever_the_value_is(value: object) -> None:
    """No value can make an absent field compare clean, and that is now structural.

    There WAS an absent sentinel here, because a single loop over the longer record had to
    mark the absent side somehow and marking it `None` made an absent field and a null
    field equal. The sentinel fixed that and a caller could then smuggle it in and make a
    real difference vanish.

    With the prefix and the tail as two loops the tail emits a damage unconditionally, so
    there is no marker to smuggle and no value to get wrong -- measured, replacing the
    sentinel with `None` killed no test in the whole ring, which is what said it was dead.
    """
    assert locate([(value,)], [()]) == (  # type: ignore[list-item]
        Damage(record_index=0, field_index=0, expected=value, actual=None),  # type: ignore[arg-type]
    )


def test_a_damage_carries_no_line_number_and_no_byte_position() -> None:
    """Absence asserted, because a line number is the tempting wrong field.

    It is available at the moment damage is found and it is correct for every file without
    an embedded separator -- so it would pass every test anyone writes by hand and fail on
    the corpus this library is for. Byte position is layer 3's, and the criterion says
    outright it is not required here.
    """
    damage = Damage(record_index=1, field_index=0, expected="a", actual="b")

    for banned in ("line", "line_number", "lineno", "byte", "byte_position", "offset"):
        assert not hasattr(damage, banned), banned


def test_a_damage_is_immutable() -> None:
    damage = Damage(record_index=0, field_index=0, expected="a", actual="b")

    with pytest.raises((AttributeError, TypeError)):
        damage.record_index = 7  # type: ignore[misc]


# --- the denominator -------------------------------------------------------------------------


def test_the_report_carries_the_number_of_records_it_compared() -> None:
    """A count without a denominator is the defect `req~ac-05~1` exists to correct.

    The spec says in its own words that published figures "reuse a denominator from a
    different experiment and must be re-derived before being cited". A report that carries
    its own makes that class of citation impossible from this side.
    """
    result = report((("a",), ("b",), ("c",)), (("a",), ("X",), ("c",)))

    assert isinstance(result, Report)
    assert result.records_compared == 3
    assert result.damages == (
        Damage(record_index=1, field_index=0, expected="b", actual="X"),
    )


def test_a_clean_report_still_carries_its_denominator() -> None:
    # The zero-damage case is the one where a missing denominator is least noticeable and
    # most misleading: "0 damages" says nothing without "out of how many".
    result = report((("a",), ("b",)), (("a",), ("b",)))

    assert (result.damages, result.records_compared) == ((), 2)


def test_the_report_refuses_a_misaligned_pair_like_locate_does() -> None:
    with pytest.raises(Misaligned):
        report((("a",),), (("a",), ("b",)))


# --- against the real fixtures, read by the real reader --------------------------------------


def _rfc4180(name: str) -> tuple[tuple[str, ...], ...]:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return tuple(tuple(row) for row in csv.reader(io.StringIO(text)))


def test_the_extra_field_incident_is_located_at_record_3_field_2() -> None:
    """The field the parser knew about and discarded, in the corpus's own words.

    Read RFC 4180 the last record carries three fields; read with an explicit two-column
    schema the third is dropped in silence -- recorded in docs/measurements.md section 6.
    `locate` recovers what the default threw away, and says where.
    """
    expected = parse_records((FIXTURES / "extra_field.csv").read_bytes(), RFC4180)
    schema_dropped_it = (("id", "name"), ("1", "ok"), ("2", "fine"), ("3", "4"))

    assert locate(expected, schema_dropped_it) == (
        Damage(record_index=3, field_index=2, expected="EXTRA", actual=None),
    )


def test_the_multiline_incident_is_a_refusal_and_not_a_list_of_values() -> None:
    """Three records against four lines: the streams do not align, so nothing is compared.

    This is the whole reason `locate` refuses. The line stream is what a reader that does
    not honour an embedded separator produces, and comparing it positionally would report
    the misalignment rather than the damage.
    """
    records = parse_records((FIXTURES / "multiline.csv").read_bytes(), RFC4180)
    lines = tuple(
        tuple(line.split(","))
        for line in (FIXTURES / "multiline.csv").read_text(encoding="utf-8").splitlines()
    )

    assert len(records) == 3
    assert len(lines) == 4

    with pytest.raises(Misaligned, match="3 and 4"):
        locate(records, lines)


def test_the_clean_control_compares_clean_against_the_stdlib() -> None:
    # The negative control at the level of a whole fixture: this reader and the stdlib over
    # the same bytes must produce no damage at all.
    source = (FIXTURES / "clean.csv").read_bytes()

    assert report(parse_records(source, RFC4180), _rfc4180("clean.csv")) == Report(
        damages=(), records_compared=4
    )