"""Whatever the stdlib writes under a dialect, this reader reads back unchanged.

TWO IMPLEMENTATIONS, WRITING AND READING. `csv.writer` renders arbitrary records -- quoting
whatever needs quoting, doubling whatever quotes appear, letting a delimiter and a record
separator sit inside a quoted field -- and `parse_records` must return exactly the records
that went in. Neither half is this module's own, on one side or the other: the writer is
the stdlib's, and a disagreement is therefore this reader's.

That is the repository's own thesis pointed at itself. A round trip through one
implementation is green for a reader and a writer that share a misconception; the stdlib
does not share this one.

WHAT THE ALPHABET IS FOR. The interesting characters are exactly the three a naive reader
gets wrong -- the delimiter, the quotechar, and the record separator -- so they are in the
draw rather than in a fixture. A field holding `a,b` or `a"b` or `a\\nb` is a field only a
correct quoting rule survives, and those are the three incidents in
`tests/fixtures/incidents/` stated as a property instead of as four files.

WHAT IS EXCLUDED, AND WHY EACH. `\\r` is out because `csv.reader` is hard-coded to end a
line at `\\r` or `\\n` and ignores its own `lineterminator` on the read side, so a `\\r`
inside a field would make the referee disagree with itself rather than with this reader --
measured, and `test_dialect.py` covers CR and CRLF separators against fixed input instead.
An empty record is out because a writer renders it as a bare separator and a reader can
only read that back as one empty field: it is a genuine lossy round trip in the FORMAT,
not in this reader.

THE `ci` PROFILE FIXES THE SEED, NOT THE CORPUS. `derandomize=True` makes the seed a hash
of this function's cleaned source, while Hypothesis 6.165 also harvests string constants
out of the local modules a session has imported, so a corpus can depend on the import
scope. This file draws text, so it IS exposed to that -- which is why the mutants below
were measured under the full `uv run pytest` rather than on this file alone.

`@example` decorators are stripped by `_clean_source` before the digest, so a pin costs no
re-draw. Editing a statement in the function below does.

[utest->req~ac-04~1]
"""

from __future__ import annotations

import csv
import io

from hypothesis import example, given
from hypothesis import strategies as st

from ingestproof.dialect import Dialect, parse_records

RFC4180 = Dialect(
    encoding="utf-8",
    delimiter=",",
    quotechar='"',
    escape="double",
    record_separator="\n",
    empty="empty-string",
)

# The delimiter, the quotechar and the record separator are IN the alphabet on purpose:
# they are the three characters a field can hold that a naive reader gets wrong.
FIELD = st.text(alphabet=st.sampled_from(["a", "b", ",", '"', "\n", " "]), max_size=6)
RECORDS = st.lists(st.lists(FIELD, min_size=1, max_size=4), min_size=1, max_size=5)


def _render(records: list[list[str]]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(records)
    return buffer.getvalue()


@example(records=[["a,b"]])
@example(records=[['say "hi", bye']])
@example(records=[["line A\nline B"], ["ok"]])
@example(records=[["a", ""], ["", "b"]])
@example(records=[['"']])
@given(records=RECORDS)
def test_the_stdlib_writes_it_and_this_reader_reads_back_exactly_what_went_in(
    records: list[list[str]],
) -> None:
    text = _render(records)

    assert parse_records(text.encode("utf-8"), RFC4180) == tuple(
        tuple(record) for record in records
    )


@example(records=[["a,b"]])
@example(records=[["line A\nline B"], ["ok"]])
@given(records=RECORDS)
def test_this_reader_and_the_stdlib_reader_agree_on_the_same_text(
    records: list[list[str]],
) -> None:
    """The other direction, and it is not the same assertion.

    The test above compares against the records that went IN, so it can only speak for
    text `csv.writer` produces. This one compares two READERS over that text, which is
    what `req~ac-02a~1` will do over a corpus neither of them wrote. If they ever disagree
    here, the disagreement is between two parsers rather than against an intention.
    """
    text = _render(records)
    reference = tuple(tuple(row) for row in csv.reader(io.StringIO(text)))

    assert parse_records(text.encode("utf-8"), RFC4180) == reference
