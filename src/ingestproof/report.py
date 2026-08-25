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
or to adjudication. What is here is the refusal: it will not zip streams of different
lengths, because a positional zip IS the 500-for-1 defect above and a report built on one
is worse than no report.

A STREAM IS READ EXACTLY ONCE, and that is a correctness rule rather than an efficiency
one. `report` used to snapshot `expected` a second time for the denominator, and for a
generator that second read came back EMPTY -- measured, a Report claiming ONE DAMAGE OUT
OF ZERO RECORDS COMPARED. `records_compared` exists so a count is never published as a
rate; a denominator re-derived from a second read is that same defect wearing the fix's
clothes.

[impl->req~ac-03~1]
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

type Record = Sequence[str | None]


class Misaligned(Exception):
    """Two record streams that cannot be compared positionally.

    `reason` is a field rather than a substring of the message, because the situations are
    not equally recoverable: a length mismatch is what resynchronisation exists for, while
    a record that is not a sequence is a caller's bug. A caller matching on `str(error)` to
    tell them apart is a caller depending on prose.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


# THERE IS NO ABSENT SENTINEL, and there was one until the loop below was split in two.
#
# The reason it existed is real and worth keeping written down: `dialect.parse_records`
# returns `None` for an unquoted empty field under `empty="null"`, so `None` already means
# "present and null". A single loop over `max(len(one), len(two))` had to mark the absent
# side somehow, and marking it `None` made an absent field and a null field compare EQUAL --
# measured, `('a', None)` against `('a',)` reported nothing at all.
#
# The sentinel fixed that and was then measured DEAD: with the prefix and the tail as two
# loops, the tail emits a damage unconditionally, so what the absent side is marked with
# cannot change the answer. Replacing the sentinel with `None` killed no test in the whole
# ring. A value that can never change the answer reads like one that can, so it is gone and
# the tail says `None` directly.

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
    class of citation impossible from this side, PROVIDED the denominator is the number of
    records this call actually walked rather than a second count of the same input.
    """

    damages: tuple[Damage, ...]
    records_compared: int


def locate(expected: Sequence[Record], actual: Sequence[Record]) -> tuple[Damage, ...]:
    """Every value that differs, in reading order, over two streams that must line up.

    Ordered by record and then by field, so a triager reads a report the way they read the
    file. Refuses rather than zips when the lengths differ -- see `Misaligned`.
    """
    return report(expected, actual).damages


def report(expected: Sequence[Record], actual: Sequence[Record]) -> Report:
    """`locate` plus the denominator, and the ONE place either stream is read.

    `locate` delegates here rather than the other way round, so the number reported as
    `records_compared` is the number of records this call actually walked.
    """
    left = _snapshot(expected, "expected stream")
    right = _snapshot(actual, "actual stream")

    if len(left) != len(right):
        raise Misaligned(
            "length",
            f"the two record streams are {len(left)} and {len(right)} records long, so "
            "they do not line up and a positional comparison would report the "
            "misalignment rather than the damage -- about 500 divergences for one, "
            "measured. Resynchronise first: re-anchor on records that agree byte for byte "
            "and compare the bounded span between them",
        )

    damages: list[Damage] = []

    # `strict=True` cannot fire after the length check above, and it is here anyway -- not
    # as a live guard but so that an edit removing that check turns into a raise rather
    # than into a silent truncation.
    for index, (before, after) in enumerate(zip(left, right, strict=True)):
        one = _snapshot(before, f"record {index} of the expected stream")
        two = _snapshot(after, f"record {index} of the actual stream")
        shared = min(len(one), len(two))

        # THE COMMON PREFIX AND THE TAIL ARE TWO LOOPS, not one loop over `max`. One loop
        # needs an absent-on-BOTH-sides branch, and that branch cannot fire -- proven by
        # enumeration over every pair of record widths. A branch that cannot fire is
        # reachable only by smuggling the sentinel in, and it made a real difference vanish
        # when someone did. Two loops delete the branch and the hole together.
        for position in range(shared):
            if not _same(one[position], two[position]):
                damages.append(
                    Damage(
                        record_index=index,
                        field_index=position,
                        expected=cast("str | None", one[position]),
                        actual=cast("str | None", two[position]),
                    )
                )

        longer, absent_on_the_right = (one, True) if len(one) > len(two) else (two, False)
        for position in range(shared, len(longer)):
            value = cast("str | None", longer[position])
            damages.append(
                Damage(
                    record_index=index,
                    field_index=position,
                    expected=value if absent_on_the_right else None,
                    actual=None if absent_on_the_right else value,
                )
            )

    return Report(damages=tuple(damages), records_compared=len(left))


def _same(here: object, there: object) -> bool:
    """Whether two values are the same, and never an escape when they cannot be compared.

    A caller's `__eq__` running here is the WORK rather than a leak: comparing values is
    this function's job, which is the line `promotion._judge` sits on the other side of.
    What was not acceptable is the consequence of letting a failure escape -- measured, one
    bad value at record 999 discarded 999 damages already found, in a module whose own
    docstring says the job is to lose nothing.

    So a comparison that fails answers NOT SAME. That is the conservative direction here
    for the same reason quarantine is the conservative direction in `promotion`: a pair
    this library cannot show to be equal is a pair it must not certify as equal.
    """
    try:
        return bool(here == there)
    except Exception:
        return False


def _snapshot(values: object, what: str) -> tuple[Any, ...]:
    """Read a caller's container ONCE, and refuse rather than escape if it will not read.

    The same reason `promotion._snapshot` exists: `len` and indexing walk the caller's live
    container, and reading one is itself caller code. Nothing caller-supplied is
    interpolated into the message, because naming the type would run the very read this is
    guarding -- `what` is a literal built at the call site.

    TWO CONTAINERS ARE REFUSED FOR READING WRONG RATHER THAN FOR FAILING TO READ, which is
    the harder case and which `promotion._snapshot` has no reason to cover:

    A `str` IS a `Sequence[str]`, so `Sequence[Record]` and `Record` both accept one and
    mypy says nothing. Measured: `report("hello", "hello")` answered zero damages out of
    FIVE RECORDS COMPARED -- a plausible, publishable, wrong denominator, from a caller who
    passed one record where a stream belongs.

    A `Mapping` iterates its KEYS. Measured: two records agreeing on every key and
    differing on every value compared CLEAN. `promotion.Record` is a `Mapping` in this same
    package, so handing one module's record to the other is a step a caller can take.
    """
    if isinstance(values, str | bytes | bytearray):
        raise Misaligned(
            "not-a-sequence",
            f"{what}: a string is a sequence of characters, so comparing one would count "
            "characters as records or as fields",
        )
    if isinstance(values, Mapping):
        raise Misaligned(
            "not-a-sequence",
            f"{what}: iterating a mapping yields its KEYS, so two records agreeing on "
            "every key and differing on every value would compare clean",
        )
    try:
        return tuple(cast("Iterable[Any]", values))
    except TypeError as error:
        raise Misaligned("unreadable", f"{what}: not iterable") from error
    except Exception as error:
        raise Misaligned("unreadable", f"{what}: could not be read") from error
