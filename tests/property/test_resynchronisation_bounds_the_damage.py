"""The span a resynchronisation reports bounds the damage exactly, over streams built to split.

THE ORACLE IS THE CONSTRUCTION, and it has to be, because the alternative is comparing
`resynchronise` against a second implementation of itself. Each example takes a stream of
records and applies the ONE edit the whole module exists for: a record separator inside a
quoted field, which makes a reader emit two rows where the producer wrote one record.
Measured in `docs/measurements.md` section 3 -- one such record in a thousand makes a
reader emit 1,001 rows, and a positional comparison then reports about 500 divergences for
one damage.

The split happens at a drawn index, so the coordinate that must come back is known before
the question is asked: exactly one span, covering exactly that record.

EVERY RECORD IS DISTINCT BY CONSTRUCTION -- field 0 is the record's own index -- and that
is load-bearing rather than tidy. Without it a drawn stream can hold two identical records,
an accidental anchor lands on the wrong one, and the oracle's `Span(i, i)` is no longer the
right answer while the test still claims it is. That is the failure the `locate` property
next door already had once, where `add` and `drop` cancelled and the oracle went on
asserting a damage that was not there.

WHAT THIS CANNOT CATCH, said here because a property that reads as a guarantee and holds
less is the shape this repository keeps finding:

- Distinct records mean NO ACCIDENTAL ANCHOR EVER ARISES, and an accidental anchor is
  exactly where width 1 is weakest. This property is therefore silent on the adjudication
  it looks closest to. `req~ac-02b~1` measures that against the real corpus; the unit ring
  pins the shapes by hand.
- It never builds an ALIGNED pair, so it says nothing about value comparison. The split
  always changes the record count, on purpose: mixing the two would make every example
  either a comparison or a resynchronisation and halve both.
- It draws no field that refuses to compare. That path is a hand-built shape in the unit
  ring, because a drawn one would make every example carry it.

THE `ci` PROFILE FIXES THE SEED, NOT THE CORPUS -- Hypothesis 6.165 also harvests string
constants out of the local modules a session has imported, so the same test at the same
seed draws differently depending on import scope. This file draws text, so it is exposed;
anything measured against it was measured under the full `uv run pytest`.

[utest->req~ac-02a~1]
"""

from __future__ import annotations

from hypothesis import example, given
from hypothesis import strategies as st

from ingestproof.differential import Span, resynchronise

# Small on purpose. The values do not carry the distinctness -- field 0 does -- so a wide
# alphabet would only make the examples harder to read when one fails.
VALUE = st.text(alphabet=st.sampled_from(["a", "b", "c"]), min_size=1, max_size=3)


@st.composite
def split_at_a_drawn_record(draw: st.DrawFn) -> tuple[tuple[object, ...], tuple[object, ...], int]:
    """A reference stream, the same stream as a reader emitted it, and where they part.

    The landed side is the reference side with record `index` read as TWO rows: the part
    before the embedded separator, and the part after it. That is what a reader without
    multiline support does, and it is the only edit here.
    """
    count = draw(st.integers(min_value=1, max_value=6))
    values = draw(st.lists(VALUE, min_size=count, max_size=count))
    index = draw(st.integers(min_value=0, max_value=count - 1))
    head = draw(VALUE)
    tail = draw(VALUE)

    expected = [(str(position), value) for position, value in enumerate(values)]
    # The record separator lives INSIDE the quoted field, which is why the producer wrote
    # one record and the reader emitted two. `head` cannot contain it -- the alphabet has
    # no newline -- so the damaged record can never equal the first row of its own split.
    expected[index] = (str(index), f"{head}\n{tail}")

    landed = [
        *expected[:index],
        (str(index), head),
        (tail,),  # one field, so it can equal none of the two-field records above or below
        *expected[index + 1 :],
    ]

    return tuple(expected), tuple(landed), index


@given(split_at_a_drawn_record())
@example(((("0", "a\na"),), (("0", "a"), ("a",)), 0))  # the whole file is the damaged record
def test_the_span_is_exactly_the_record_the_separator_was_embedded_in(
    case: tuple[tuple[object, ...], tuple[object, ...], int],
) -> None:
    expected, landed, index = case

    assert resynchronise(expected, landed) == (Span(first_record=index, last_record=index),)


@given(split_at_a_drawn_record(), st.integers(min_value=1, max_value=4))
def test_the_span_does_not_move_when_the_anchor_width_is_raised(
    case: tuple[tuple[object, ...], tuple[object, ...], int], width: int
) -> None:
    """Adjudication 1 as a property rather than as a hand-built pair.

    A width above 1 can only be MORE demanding, so the risk it carries is a span that fails
    to close and runs to the end of the file -- which is precisely what happens at the end
    of a stream, where fewer than `width` records remain. `req~ac-02b~1` may raise the
    width against the real corpus, and this is the statement that raising it is not a
    change to what the frozen acceptance file expects.
    """
    expected, landed, index = case

    assert resynchronise(expected, landed, width=width) == (
        Span(first_record=index, last_record=index),
    )


@given(st.lists(st.lists(VALUE, min_size=1, max_size=3), min_size=1, max_size=6))
def test_a_stream_compared_against_itself_reports_no_span_at_all(
    stream: list[list[str]],
) -> None:
    # The negative control, and it is not decoration: every assertion above is equally
    # green for a `resynchronise` that reports a span for everything it is shown. This one
    # draws records that CAN repeat, which the split strategy deliberately does not.
    frozen = tuple(tuple(record) for record in stream)

    assert resynchronise(frozen, frozen) == ()
