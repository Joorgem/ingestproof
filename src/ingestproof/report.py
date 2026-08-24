"""Where a damaged value is, said by record index and field index and by nothing else.

RECORD INDEX IS NOT LINE NUMBER, AND THAT IS THE WHOLE OF THIS MODULE. A record carrying a
record separator inside a quoted field occupies two lines, so the record stream and the
line stream stop agreeing at the first such record and never agree again. Recorded in
docs/measurements.md section 3: one such record makes a reader emit 1,001 lines for 1,000
records, and a positional comparison then reports about 500 divergences for one damage.

A report that located by line would be right until the first multiline record and wrong
after it, and it would be MORE wrong the larger the file. That is the failure shape this
library exists to catch, arriving in the thing that reports it -- so `Damage` carries no
line, and a test asserts the absence rather than trusting it.

Byte position belongs to layer 3, and `req~ac-03~1` says outright it is not required here.
The reason is measured, not deferred: DuckDB emits a byte position only for records it
REJECTS, and the whole damage class this library is about is parsed CLEANLY by the
reference side -- so byte attribution over clean data is not obtainable from the oracle
(docs/measurements.md section 2).

WHAT THIS MODULE IS NOT. `locate` is handed two ALIGNED record streams. Producing them --
running two parsers over a corpus, and resynchronising after a divergence -- is the
differential and the resynchronisation, which docs/design.md section 15 assigns to a human
or to adjudication. What is here is the refusal: `locate` will not zip streams of
different lengths, because a positional zip IS the 500-for-1 defect above and a report
built on one is worse than no report.

[impl->req~ac-03~1]
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, cast

type Record = Sequence[str | None]


class Misaligned(Exception):
    """Two record streams that do not line up, so nothing may be compared positionally."""


# NOT `None`. A field that is ABSENT and a field that is present and NULL are different
# facts, and `None` is already the second one -- `dialect.parse_records` returns it under
# `empty="null"`. Compared as `None` on both sides they are EQUAL, so the damage goes
# unreported: measured, a record `('a', None)` against `('a',)` yields nothing at all.
# Silent loss, in the function whose job is to lose nothing.
_ABSENT = object()


@dataclass(frozen=True)
class Damage:
    """One value that differs, and where it is.

    Four fields and no fifth. A line number is the tempting wrong one: it is available at
    the moment damage is found and it is correct for every file without an embedded
    separator, which is exactly what makes it dangerous -- it would pass every test anyone
    writes by hand and fail on the corpus this library is for.

    `expected` and `actual` are `None` both for a field that is absent and for one that is
    present and null. The criterion's vocabulary is (record index, field index) and has no
    third state to say which, so the report says which VALUES differ and the record lengths
    say why. The damage is reported either way, which is what matters.
    """

    record_index: int
    field_index: int
    expected: str | None
    actual: str | None


@dataclass(frozen=True)
class Report:
    """The damages, and the denominator they were found in.

    `records_compared` is not bookkeeping. `req~ac-05~1` exists because published figures
    "reuse a denominator from a different experiment and must be re-derived before being
    cited" -- the spec's own words. A report that carries its own denominator makes that
    class of citation impossible from this side.
    """

    damages: tuple[Damage, ...]
    records_compared: int


def locate(expected: Sequence[Record], actual: Sequence[Record]) -> tuple[Damage, ...]:
    """Every value that differs, in reading order, over two streams that must line up.

    Ordered by record and then by field, so a triager reads a report the way they read the
    file. Refuses rather than zips when the lengths differ -- see `Misaligned`.
    """
    left = _snapshot(expected, "expected stream")
    right = _snapshot(actual, "actual stream")

    if len(left) != len(right):
        raise Misaligned(
            f"the two record streams are {len(left)} and {len(right)} records long, so "
            "they do not line up and a positional comparison would report the "
            "misalignment rather than the damage -- about 500 divergences for one, "
            "measured. Resynchronise first: re-anchor on records that agree byte for byte "
            "and compare the bounded span between them"
        )

    damages: list[Damage] = []

    # `strict=True` cannot fire after the length check above, and it is here anyway --
    # not as a live guard but so that an edit removing that check turns into a raise
    # rather than into a silent truncation. Unlike a dead term in a boolean, it does
    # not make the expression read as though it decides something today.
    for index, (before, after) in enumerate(zip(left, right, strict=True)):
        one = _snapshot(before, f"record {index} of the expected stream")
        two = _snapshot(after, f"record {index} of the actual stream")

        for position in range(max(len(one), len(two))):
            here = one[position] if position < len(one) else _ABSENT
            there = two[position] if position < len(two) else _ABSENT
            if here is _ABSENT and there is _ABSENT:
                continue
            if here is not _ABSENT and there is not _ABSENT and here == there:
                continue
            damages.append(
                Damage(
                    record_index=index,
                    field_index=position,
                    expected=None if here is _ABSENT else cast("str | None", here),
                    actual=None if there is _ABSENT else cast("str | None", there),
                )
            )

    return tuple(damages)


def _snapshot(values: object, what: str) -> tuple[Any, ...]:
    """Read a caller's container ONCE, and refuse rather than escape if it will not read.

    The same reason `promotion._snapshot` exists: `len` and indexing walk the caller's live
    container, and reading one is itself caller code. Nothing caller-supplied is
    interpolated into the message, because naming the type would run the very read this is
    guarding -- `what` is a literal built here.

    The VALUES are not snapshotted or type-checked, and that line is deliberate: comparing
    them is this function's job, so a value's `__eq__` running is the work rather than an
    escape. That is the difference between here and a refusal path.
    """
    try:
        return tuple(cast("Iterable[Any]", values))
    except TypeError as error:
        raise Misaligned(f"the {what} is not iterable") from error
    except Exception as error:
        raise Misaligned(f"the {what} could not be read") from error


def report(expected: Sequence[Record], actual: Sequence[Record]) -> Report:
    """`locate` plus the denominator, so a count is never published as a rate."""
    return Report(
        damages=locate(expected, actual),
        records_compared=len(_snapshot(expected, "expected stream")),
    )
