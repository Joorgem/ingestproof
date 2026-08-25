"""Unit ring for `ingestproof.differential`.

The frozen acceptance file judges the criterion over four incident fixtures, and those
fixtures pin exactly one resynchronisation: one embedded separator, and -- measured before
this module was written -- exactly ONE re-anchor candidate at width 1 and ZERO at width 2.
This file judges what four files of thirty bytes cannot reach.

THE THREE ADJUDICATIONS, each with its own test below, because `docs/design.md` section 15
hands the differential and the resynchronisation to a human, and an adjudication nobody
wrote down is whatever the implementer happened to type:

1. END OF STREAM IS AN ANCHOR. A re-anchor needs `min(width, what is left on each side)`
   byte-identical records rather than `width` of them. Without this rule no file that ends
   in damage can close its span at any width above one, and the acceptance file's
   `[(1, 1)]` becomes an expectation about the number 1 rather than about the algorithm.
2. WIDTH IS ONE. It is one because a corpus of four files pinned it, and it is written
   as a constant with this test asserting the value because mutmut 3 mutates inside
   functions only -- a bare constant produces zero mutants and the gate is inert on it.
   Rule 1 is what lets `req~ac-02b~1` raise it against the real corpus later without
   touching a frozen expectation.
3. THE NEAREST ANCHOR WINS, nearest counted as records skipped on BOTH sides together.
   The fixtures offer one candidate, so nothing frozen defends this choice at all.

AND TWO CHOICES THAT ARE NOT SPANS. A span names REFERENCE records, so landed rows past
the end of the reference stream have nothing to name and get no span invented for them;
and `damages` is empty whenever `needs_resync` is true, because a field comparison across
a misalignment is the 500-divergences-for-1 defect the whole module exists to refuse.
"""

from __future__ import annotations

import pytest

from ingestproof.dialect import Dialect, DialectError
from ingestproof.differential import ANCHOR_WIDTH, Differential, Span, detect, resynchronise
from ingestproof.report import Damage, Misaligned

RFC4180 = Dialect(
    encoding="utf-8",
    delimiter=",",
    quotechar='"',
    escape="double",
    record_separator="\n",
    empty="empty-string",
)

THREE_RECORDS = b"id,name\n1,ok\n2,fine\n"


class Explodes:
    """A field value whose comparison raises, in the position where a match would anchor.

    The defect class this repository has now hit five times is a refusal path that asks the
    caller's object about itself and lets the caller's exception escape wearing the
    module's name. Anchoring compares caller values, so it is on that path.
    """

    def __eq__(self, other: object) -> bool:
        raise RuntimeError("a value that will not compare")

    __hash__ = None  # type: ignore[assignment]


class AgreesOnce:
    """A field value that agrees the first time it is asked and never again.

    Not a threat model -- a caller whose values answer differently on re-inspection gets a
    wrong answer from any differential. It is an INSTRUMENT: it makes "was this pair
    compared twice?" an observable fact rather than a claim about the code's shape.
    """

    def __init__(self) -> None:
        self.asked = 0

    def __eq__(self, other: object) -> bool:
        self.asked += 1
        return self.asked == 1

    __hash__ = None  # type: ignore[assignment]


# --- the adjudications --------------------------------------------------------------------


def test_the_anchor_width_is_one_and_the_number_is_asserted_not_implied() -> None:
    # mutmut 3 produces no mutant for a module-level constant, so without this line the
    # mutation gate is silently inert on the one number this module adjudicates.
    assert ANCHOR_WIDTH == 1


def test_end_of_stream_anchors_at_a_width_the_remaining_records_cannot_fill() -> None:
    """Adjudication 1, stated where it can fail.

    One reference record survives past the divergence, so a strict width of 2 finds no
    anchor anywhere and the span runs to the end of the file. Under `min(width, what is
    left)` the same pair anchors on the single record and the span closes.
    """
    expected = (("h",), ("damaged",), ("tail",))
    landed = (("h",), ("dam",), ("aged",), ("tail",))

    assert resynchronise(expected, landed, width=2) == (Span(first_record=1, last_record=1),)


def test_raising_the_width_does_not_move_the_span_the_fixtures_pinned() -> None:
    # The point of adjudication 1: `req~ac-02b~1` may raise the width against the real
    # corpus, and this shape -- the acceptance file's multiline shape -- must not move when
    # it does. A width that changed this answer would change a frozen expectation.
    expected = (("id", "note"), ("1", "line A\nline B"), ("2", "ok"))
    landed = (("id", "note"), ("1", "line A"), ('line B"', None), ("2", "ok"))

    spans = [resynchronise(expected, landed, width=width) for width in (1, 2, 3, 7)]

    assert spans == [(Span(first_record=1, last_record=1),)] * 4


def test_the_nearest_anchor_wins_counted_on_both_sides_together() -> None:
    """Adjudication 3, over a pair carrying two candidates that disagree about the answer.

    Two anchors are reachable from the divergence at record 1. `near` is two records away
    counting both sides; `far` is four. They are not interchangeable: anchoring on `near`
    leaves reference record 1 in one span and record 3 in another, while anchoring on `far`
    consumes the landed stream whole and blames records 2 and 3 instead.

    THE FIRST SHAPE I WROTE FOR THIS TEST DISTINGUISHED NOTHING -- a reference-major scan
    answered it identically, so the test claimed to defend an adjudication it did not
    touch. This shape was built by trying to kill that scan and failing.
    """
    expected = (("h",), ("far",), ("near",), ("r",))
    landed = (("h",), ("x",), ("near",), ("z",), ("w",), ("far",))

    assert resynchronise(expected, landed) == (
        Span(first_record=1, last_record=1),
        Span(first_record=3, last_record=3),
    )


# --- what a span is, and what it refuses to be --------------------------------------------


def test_two_identical_streams_need_no_resynchronisation_and_carry_no_span() -> None:
    # The negative control. Every assertion in this file is equally green for a
    # `resynchronise` that reports a span for everything it is shown.
    stream = (("a", "b"), ("c", "d"), ("e", "f"))

    assert resynchronise(stream, stream) == ()


def test_a_span_runs_to_the_last_reference_record_when_the_streams_never_re_agree() -> None:
    expected = (("h",), ("a",), ("b",))
    landed = (("h",), ("x",), ("y",), ("z",))

    assert resynchronise(expected, landed) == (Span(first_record=1, last_record=2),)


def test_landed_rows_past_the_reference_stream_get_no_span_invented_for_them() -> None:
    """A span names reference records, and there is no reference record here to name.

    The two extra rows are still visible -- `needs_resync` is true and the two counts
    disagree -- but naming them with a span would mean emitting `Span(3, 2)`, a range whose
    end precedes its start, which reads like a record range and is not one.
    """
    expected = (("h",), ("a",))
    landed = (("h",), ("a",), ("extra",), ("more",))

    assert resynchronise(expected, landed) == ()


def test_a_divergence_the_landed_side_alone_causes_consumes_no_reference_record() -> None:
    # One row inserted before a reference record that is otherwise intact: the re-anchor
    # lands on that same reference record, so no reference record is in doubt and the same
    # rule as above applies -- an empty span is not emitted as an inverted one.
    expected = (("h",), ("a",), ("b",))
    landed = (("h",), ("inserted",), ("a",), ("b",))

    assert resynchronise(expected, landed) == ()


def test_a_value_that_will_not_compare_does_not_anchor_and_does_not_escape() -> None:
    """The five-time defect class, in the one place this module runs caller code.

    `Explodes` sits exactly where an anchor would be found at distance 1. Three outcomes
    are distinguishable here: the exception escapes (this test errors), the comparison
    answers SAME (the span disappears), or it answers NOT SAME and the search goes on to
    the real anchor at `q`. Only the third is the conservative direction -- a pair this
    module cannot show to be equal must not be certified as an anchor.
    """
    expected = (("h",), ("z",), ("q",))
    landed = (("h",), ("x",), (Explodes(),), ("q",))

    assert resynchronise(expected, landed) == (Span(first_record=1, last_record=1),)


def test_an_anchoring_pair_is_never_asked_a_second_time() -> None:
    """The walk resumes PAST the anchor, and this is the difference that makes visible.

    Resuming ON the anchor gives the same answer for every deterministic comparison -- I
    measured that: the whole ring stayed green with the resume point moved back. It is a
    surviving mutant rather than an equivalent one, and the difference it hides is that the
    pair which just anchored would be compared a second time to decide whether to advance.

    `AgreesOnce` sits where the anchor is found. Resuming past it, the pair is never asked
    again and the streams walk out clean. Resuming onto it, the second question comes back
    NO, the search runs again from the same place, and a span appears over a record nothing
    ever found damage in.
    """
    expected = (("h",), ("a",), ("b",))
    landed = (("h",), ("x",), (AgreesOnce(),), ("b",))

    assert resynchronise(expected, landed) == ()


def test_a_width_below_one_is_refused_rather_than_anchoring_on_nothing() -> None:
    """Zero would make every position an anchor, which reads as the opposite of strict.

    The anchor condition is "these `width` records all agree". At width 0 that is an `all()`
    over an empty range, which is true everywhere, so the first candidate position anchors
    and every span collapses to nothing -- a differential that answers "no damage" loudest
    exactly when it was told to be most careful. Refused rather than clamped: a caller who
    passed 0 meant something, and it was not 1.
    """
    with pytest.raises(ValueError, match="width"):
        resynchronise((("a",), ("b",)), (("a",), ("x",), ("y",)), width=0)


def test_a_string_where_a_landed_record_belongs_is_refused_not_compared() -> None:
    # A `str` is a `Sequence[str]`, so a record that is one compares character by character
    # as though those were fields. Refused at the record level, not only at the stream
    # level, because the resynchronisation reaches records the stream check never typed.
    with pytest.raises(Misaligned) as refusal:
        resynchronise((("h",), ("a",)), (("h",), "xy", ("z",)))

    assert refusal.value.reason == "not-a-sequence"


# --- detect, over bytes and a declared dialect --------------------------------------------


def test_detect_over_an_aligned_pair_is_the_report_plus_two_counts() -> None:
    landed = (("id", "name"), ("1", "OK"), ("2", "fine"))

    found = detect(THREE_RECORDS, RFC4180, landed)

    assert found == Differential(
        damages=(Damage(record_index=1, field_index=1, expected="ok", actual="OK"),),
        records_compared=3,
        landed_records=3,
        needs_resync=False,
        spans=(),
    )


def test_detect_reports_no_damages_at_all_when_resynchronisation_is_required() -> None:
    # The choice stated in this file's docstring: a field comparison across a misalignment
    # is the defect, so the answer is the span rather than a list of values -- including
    # for the records before the divergence, which are not published as a partial result.
    landed = (("id", "name"), ("1", "o"), ("k",), ("2", "fine"))

    found = detect(THREE_RECORDS, RFC4180, landed)

    assert found.needs_resync is True
    assert found.damages == ()
    assert found.spans == (Span(first_record=1, last_record=1),)


def test_the_denominator_counts_reference_records_and_never_landed_rows() -> None:
    # `req~ac-05~1` exists because published figures reuse a denominator from a different
    # experiment. A differential carries two counts precisely so neither can stand in for
    # the other, and the misaligned path is where they differ.
    found = detect(THREE_RECORDS, RFC4180, (("id", "name"), ("1", "o"), ("k",), ("2", "fine")))

    assert (found.records_compared, found.landed_records) == (3, 4)


def test_the_landed_stream_is_read_exactly_once() -> None:
    """A generator read twice comes back empty the second time.

    Measured in `ingestproof.report`: a second read for the denominator produced a report
    claiming one damage out of ZERO records compared. This module reads the landed stream
    for its own length before it can decide which path to take, which is one more place to
    make that mistake.
    """
    landed = iter((("id", "name"), ("1", "ok"), ("2", "fine")))

    found = detect(THREE_RECORDS, RFC4180, landed)

    assert (found.landed_records, found.damages, found.needs_resync) == (3, (), False)


def test_detect_refuses_bytes_without_a_declared_dialect() -> None:
    # Free from `require_dialect`, and asserted anyway: `req~ac-04~1` is a refusal the whole
    # library rests on, and a differential that quietly defaulted a dialect would make the
    # proof circular in the one entry point a caller actually reaches for.
    with pytest.raises(DialectError):
        detect(THREE_RECORDS, None, (("id", "name"),))


def test_a_string_handed_in_as_the_landed_stream_is_refused_not_counted() -> None:
    # Measured in `report`: a `str` IS a `Sequence[str]`, so mypy says nothing and the
    # characters are counted as records. Here that would be a plausible landed_records.
    with pytest.raises(Misaligned) as refusal:
        detect(THREE_RECORDS, RFC4180, "hello")  # type: ignore[arg-type]

    assert refusal.value.reason == "not-a-sequence"


def test_a_mapping_handed_in_as_the_landed_stream_is_refused_not_counted() -> None:
    # `promotion.Record` is a `Mapping` in this same package, so handing one module's
    # record to the other is a step a caller can take. Iterating it yields KEYS.
    with pytest.raises(Misaligned) as refusal:
        detect(THREE_RECORDS, RFC4180, {"id": "1", "name": "ok"})  # type: ignore[arg-type]

    assert refusal.value.reason == "not-a-sequence"
