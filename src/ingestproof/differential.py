"""Two parsers over the same bytes, and what to do when they stop agreeing on where a record ends.

`report` compares two record streams that line up. This module is what produces them: the
reference parse on one side, a reading that already landed on the other -- and the refusal
`report` raises when their lengths disagree is the entry point to the harder half.

WHY THE HARDER HALF IS NOT A DETAIL. Measured in `docs/measurements.md` section 3: one
record with a separator inside a quoted field makes a reader emit 1,001 rows for 1,000
records, and a positional comparison then reports about 500 divergences for ONE damage. A
differential that zipped would be right on every file without such a record -- which is
every file anyone writes by hand while testing it -- and progressively more wrong on the
corpus this library exists for. So after a divergence the two streams are re-anchored on
records that agree, and what gets reported is a bounded SPAN rather than a list of values.

THREE THINGS HERE ARE ADJUDICATED, and they are written down because `docs/design.md`
section 15 assigns this module to a human, and an adjudication nobody recorded is whatever
the implementer happened to type. Measured against the frozen corpus before any of this was
written: `multiline.csv` offers exactly ONE re-anchor candidate at width 1 and ZERO at a
strict width 2.

1. END OF STREAM IS AN ANCHOR. A re-anchor needs `min(width, what is left on each side)`
   agreeing records, not `width` of them. A strict width above 1 finds no anchor at all on
   that fixture, so every file ending in damage would report a span running to its end.
2. THE WIDTH IS 1, and the honest statement of why is that four files of thirty bytes
   pinned it. Rule 1 is what makes raising it later -- `req~ac-02b~1` measures the false
   positive rate against the real corpus -- not a change to a frozen expectation. Width 1
   is weakest where records repeat, because an accidental agreement re-anchors early and
   the span closes short; that is the thing the real corpus has and the fixtures do not.
3. THE NEAREST ANCHOR WINS, nearest counted as records skipped on BOTH sides together. The
   fixtures offer one candidate, so nothing frozen defends this at all. A scan that walked
   one stream to exhaustion before advancing the other would report a span as wide as the
   file for a damage one record wide.

A SPAN NAMES REFERENCE RECORDS AND NOTHING ELSE, which is the same discipline `Damage` is
under: four fields and no fifth. Landed rows past the end of the reference stream therefore
get no span invented for them -- there is no reference record to name, and `Span(3, 2)`, an
end preceding its start, reads like a record range and is not one. `needs_resync` and the
two counts carry that case instead.

`damages` IS EMPTY WHENEVER `needs_resync` IS TRUE. Not because nothing could be compared
-- the records before the divergence line up perfectly well -- but because publishing a
partial value list beside a misalignment is how the 500-for-1 number gets cited. The answer
to a misalignment is the span; a caller who wants values re-runs on the re-anchored
segments, having seen where they are.

`records_compared` IS REFERENCE RECORDS WALKED, and in the resynchronised path that is not
the same as records compared for value -- there, none were. `report.Report`'s own docstring
calls a denominator that is not what the call walked a defect, so the tension is real and
this is where it is written down rather than hidden: the number is the reference records
this call read and accounted for, and the spans say which of them went unverified. The
frozen acceptance file asserts 3 for a file whose value comparison never ran.

WHAT IS NOT HERE. The anchor search is quadratic in the DISTANCE to the anchor, not in the
file: it runs only after a divergence and stops at the first agreement. Measured on
`multiline.csv` by counting the calls: FIVE candidate comparisons in the search, seven
counting the two the walk spends finding the divergence. A file whose streams never
re-agree costs the square of what is left, and bounding that search is `req~ac-02b~1`'s
problem, on a corpus that can show what the bound should be.

(This paragraph said THREE until the calls were counted, and the commit that introduced
this module says three as well. Nothing derived from the number -- it was an estimate
written in the present indicative. It is the third claim in this one turn not to survive
being measured: a unit test that named an adjudication it did not distinguish, a mutant
filed as equivalent that was not, and this.)

[impl->req~ac-02a~1]
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ingestproof.dialect import parse_records

# `_snapshot` IS REACHED FOR ACROSS THE MODULE BOUNDARY ON PURPOSE, and the alternative was
# weighed rather than overlooked. It is fifteen lines of guard whose two refusals were each
# MEASURED -- a `str` counted five characters as records, a `Mapping` compared two records
# clean by iterating their keys -- and this module needs the same guard before it can take
# a length. A second copy would be a second place for the defect class this repository has
# now hit five times to live, and the two copies would drift the first time one is fixed.
from ingestproof.report import Damage, Record, _snapshot, report

# Adjudication 2. A module-level constant produces no mutant under mutmut 3, so
# `tests/unit/test_differential.py` asserts this value outright rather than letting the
# mutation gate be silently inert on the one number this module chooses.
ANCHOR_WIDTH = 1


@dataclass(frozen=True)
class Span:
    """A run of reference records that could not be verified, ends included.

    Two fields, both indices into the REFERENCE stream. The landed offsets are deliberately
    absent: they are what the resynchronisation is uncertain about, and a range that
    presented them as known would be the misalignment defect wearing the fix's clothes.
    """

    first_record: int
    last_record: int


@dataclass(frozen=True)
class Differential:
    """What a reading did to the bytes, said in whichever of the two vocabularies applies.

    `needs_resync` picks the vocabulary. False, and `damages` locates every differing value
    while `spans` is empty. True, and `spans` bounds the doubt while `damages` is empty --
    see the module docstring for why that is a choice rather than an omission.

    `records_compared` and `landed_records` are both here so that neither can stand in for
    the other. `req~ac-05~1` exists because published figures reuse a denominator from a
    different experiment, and one count in this dataclass would be exactly that waiting to
    happen: 3 records read as 4 rows has two right answers to "out of how many".
    """

    damages: tuple[Damage, ...]
    records_compared: int
    landed_records: int
    needs_resync: bool
    spans: tuple[Span, ...]


def detect(source: bytes, dialect: object, landed: Iterable[Record]) -> Differential:
    """Parse `source` under the declared `dialect` and say what `landed` did to it.

    The dialect is not optional and nothing here supplies one: `parse_records` refuses a
    missing dialect for `req~ac-04~1`, and a differential that defaulted one would make the
    proof circular in the entry point a caller actually reaches for.

    `landed` is read exactly ONCE. It is annotated `Iterable` rather than `Sequence`
    because a landed reading arrives as a cursor at least as often as it arrives as a list,
    and because this function needs its LENGTH before it can pick a path -- which is the
    second place in this package to make the mistake `report` measured, where a re-read for
    the denominator came back empty and published one damage out of zero records compared.
    """
    expected = parse_records(source, dialect)
    actual = _snapshot(landed, "the landed stream")

    if len(expected) == len(actual):
        aligned = report(expected, actual)
        return Differential(
            damages=aligned.damages,
            records_compared=aligned.records_compared,
            landed_records=len(actual),
            needs_resync=False,
            spans=(),
        )

    return Differential(
        damages=(),
        records_compared=len(expected),
        landed_records=len(actual),
        needs_resync=True,
        spans=resynchronise(expected, actual),
    )


def resynchronise(
    expected: Iterable[Record], actual: Iterable[Record], width: int = ANCHOR_WIDTH
) -> tuple[Span, ...]:
    """The reference records the two streams do not let you verify, as bounded runs.

    Walks both streams together while they agree. At the first disagreement it looks for
    the nearest pair of positions where `width` records agree again -- nearest by records
    skipped on both sides together -- reports the reference records passed over as one
    span, and resumes from there. Reference records left over when the landed stream runs
    out are one final span; landed rows left over when the reference stream runs out are
    not a span at all.
    """
    if width < 1:
        raise ValueError(
            f"an anchor width of {width} makes every position an anchor, because the "
            "condition it checks is a claim about no records at all -- the smallest "
            "width that anchors on evidence is 1"
        )

    left = _snapshot(expected, "the reference stream")
    right = _snapshot(actual, "the landed stream")

    spans: list[Span] = []
    here = there = 0

    while here < len(left) and there < len(right):
        if _agrees(left[here], right[there]):
            here, there = here + 1, there + 1
            continue

        anchor = _anchor(left, right, here, there, width)
        if anchor is None:
            break

        found_here, found_there = anchor
        if found_here > here:
            spans.append(Span(first_record=here, last_record=found_here - 1))

        # Past the anchor rather than onto it, so both indices strictly advance no matter
        # what a caller's `__eq__` answers the second time it is asked. An anchoring pair
        # that disagreed on re-inspection would otherwise search from where it already was.
        here, there = found_here + 1, found_there + 1

    if here < len(left):
        spans.append(Span(first_record=here, last_record=len(left) - 1))

    return tuple(spans)


def _anchor(
    left: tuple[Any, ...], right: tuple[Any, ...], here: int, there: int, width: int
) -> tuple[int, int] | None:
    """The nearest pair of positions at which the two streams agree again, or nothing.

    Nearest is `skipped on the left + skipped on the right`, so the search widens as a
    diamond rather than walking one stream to the end of the other. Both orders find an
    anchor; only this one finds the CLOSEST, and the difference between them is a span one
    record wide against a span as wide as the rest of the file.

    THE ANCHOR IS `min(width, what is left)` RECORDS, which is adjudication 1 and the line
    that makes the width raisable. At the end of a stream fewer than `width` records remain
    and a strict test could never pass, so a file ending in damage would never close its
    last span -- and the acceptance file's expectation would be pinned to the number 1
    rather than to the algorithm.
    """
    reach = (len(left) - here) + (len(right) - there)

    for distance in range(1, reach + 1):
        for skipped in range(distance + 1):
            candidate_here, candidate_there = here + skipped, there + (distance - skipped)
            if candidate_here >= len(left) or candidate_there >= len(right):
                continue

            span = min(width, len(left) - candidate_here, len(right) - candidate_there)
            if all(
                _agrees(left[candidate_here + step], right[candidate_there + step])
                for step in range(span)
            ):
                return candidate_here, candidate_there

    return None


def _agrees(one: Any, two: Any) -> bool:
    """Whether two records agree, decided by the same comparison the aligned path uses.

    Delegated to `report` rather than written again, and that is a correctness property
    rather than economy: a pair of records that anchors here is exactly a pair that `report`
    would find no damage in, so the two halves of this module cannot drift into disagreeing
    about what "the same record" means. It carries the ragged case for free -- records of
    different widths differ -- and the refusals too, so a `str` where a record belongs is
    refused here for the reason it is refused there.

    A comparison that RAISES answers not-same, inside `report._same`, and that is the
    conservative direction here for the same reason it is there. A pair this module cannot
    show to be equal must not become an anchor: the cost of refusing one is a span reported
    wider than it needed to be, and the cost of accepting one is damage certified as clean.
    """
    return report((one,), (two,)).damages == ()
