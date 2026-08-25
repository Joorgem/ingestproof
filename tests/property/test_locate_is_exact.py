"""`locate` reports every difference and invents none, over streams built to differ.

THE ORACLE IS THE CONSTRUCTION. Rather than compare `locate` against another implementation
of itself -- which would be one parser checking another parser's misconception -- each
example takes a stream and applies a KNOWN edit at a known place: change a value, drop the
last field of a record, add one. The coordinates that must come back are then computable
from the edits, so the test knows the answer before it asks.

AT MOST ONE EDIT PER RECORD, and that is not tidiness. The first version of this file drew
a list of edits that could land twice on the same record, and Hypothesis found `add` then
`drop` -- which cancel, leaving the stream identical while the oracle still claimed a
damage at the coordinate. The oracle was wrong and the property caught it. One edit per
record makes composition impossible, and the alternative -- recomputing the expected
coordinates from the two final streams -- would have been `locate` reimplemented, which
proves nothing.

A FIELD MAY BE `None`, and the first version of this file said it drew the absent-versus-
null case and did not. `FIELD` was text only, so a null value never arose, and a review
measured the consequence: replacing the module's absent sentinel with `None` left this
file GREEN. The claim was in the docstring and the coverage was not in the draws. `None` is
in the alphabet now.

(The sentinel itself is gone -- splitting the comparison into a prefix loop and a tail loop
made it dead, which the same measurement is what showed. What remains here is the shape it
was protecting: a field present on one side and null on the other must still be a damage.)

WHAT THIS CANNOT CATCH, said here because a property that reads as a guarantee and holds
less is the shape this repository keeps finding. It says nothing about the ORDER damages
come back in: the coordinates are compared as a set, so a `locate` that walked fields first
would satisfy it. Ordering is pinned in the unit ring over a shape chosen to make a
field-major walk visible. And it never builds a MISALIGNED pair -- the edits preserve the
record count on purpose, because mixing the refusal in would make every example either a
refusal or a comparison and halve both.

THE `ci` PROFILE FIXES THE SEED, NOT THE CORPUS -- Hypothesis 6.165 also harvests string
constants out of imported local modules, so a corpus depends on the import scope. This file
draws text, so it is exposed; the mutants were measured under the full `uv run pytest`.

[utest->req~ac-03~1]
"""

from __future__ import annotations

from hypothesis import example, given
from hypothesis import strategies as st

from ingestproof.report import locate

# `None` is in here because `dialect.parse_records` returns it for an unquoted empty field
# under `empty="null"`, so it is a value a real record carries -- not an exotic input.
FIELD = st.one_of(
    st.none(), st.text(alphabet=st.sampled_from(["a", "b", "c"]), min_size=1, max_size=3)
)
RECORD = st.lists(FIELD, min_size=1, max_size=4)
STREAM = st.lists(RECORD, min_size=1, max_size=5)

# One per record, positionally. `drop` and `add` change a record's LENGTH, which is how a
# field becomes absent on one side -- and with `None` in the alphabet above, how an absent
# field meets a null one, which is the pair that used to compare EQUAL.
EDIT = st.sampled_from(("none", "change", "drop", "add"))
EDITS = st.lists(EDIT, max_size=5)


def _apply(
    stream: list[list[str | None]], edits: list[str]
) -> tuple[list[list[str | None]], set[tuple[int, int]]]:
    """The edited stream, and exactly the coordinates that must be reported as damaged."""
    edited = [list(record) for record in stream]
    coordinates: set[tuple[int, int]] = set()

    for index, record in enumerate(edited):
        kind = edits[index] if index < len(edits) else "none"
        if kind == "change":
            # `"z"` is outside the alphabet and `None` is not `"z"`, so the edit always
            # changes the value whichever it was.
            record[0] = "z" if record[0] is None else record[0] + "z"
            coordinates.add((index, 0))
        elif kind == "drop" and len(record) > 1:
            coordinates.add((index, len(record) - 1))
            record.pop()
        elif kind == "add":
            coordinates.add((index, len(record)))
            record.append("z")

    return edited, coordinates


@example(stream=[["a"]], edits=["change"])
@example(stream=[["a", "b"]], edits=["drop"])
@example(stream=[["a"]], edits=["add"])
@example(stream=[["a"], ["b"]], edits=[])
@example(stream=[["a", "b"], ["c"]], edits=["drop", "add"])
@example(stream=[["a", None]], edits=["drop"])
@example(stream=[[None]], edits=["change"])
@given(stream=STREAM, edits=EDITS)
def test_locate_reports_exactly_the_coordinates_the_edits_created(
    stream: list[list[str | None]], edits: list[str]
) -> None:
    edited, expected_coordinates = _apply(stream, edits)

    damages = locate(stream, edited)
    found = {(one.record_index, one.field_index) for one in damages}

    # Both arms on every example: nothing missed, and nothing invented.
    assert found == expected_coordinates
    assert len(damages) == len(found), "a coordinate was reported twice"


@example(stream=[["a"]])
@given(stream=STREAM)
def test_a_stream_against_itself_is_always_clean(stream: list[list[str | None]]) -> None:
    # The arm that keeps the one above from being satisfied by a detector that flags
    # everything, stated over the same draws.
    assert locate(stream, stream) == ()


@example(stream=[["a", "b"]], edits=["change"])
@given(stream=STREAM, edits=EDITS)
def test_every_reported_damage_carries_the_two_values_at_its_own_coordinate(
    stream: list[list[str | None]], edits: list[str]
) -> None:
    """The coordinates are right AND they point at the values that differ.

    A `locate` returning correct coordinates with swapped or empty `expected`/`actual`
    would satisfy the first property completely. This reads each coordinate back out of
    both streams and holds the damage against them.
    """
    edited, _ = _apply(stream, edits)

    for damage in locate(stream, edited):
        row, column = damage.record_index, damage.field_index
        before = stream[row][column] if column < len(stream[row]) else None
        after = edited[row][column] if column < len(edited[row]) else None

        assert damage.expected == before
        assert damage.actual == after
