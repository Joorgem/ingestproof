"""The declared source dialect, and the reader that obeys it.

THE CONTRACT IN ONE SENTENCE: you assert what the producer wrote, and this library proves
the reader read that. Both halves need the same thing -- a dialect that came from you. A
dialect this library guessed would make the proof circular, because the guess would be
made from the same bytes the proof is about.

SO NOTHING HERE INFERS, AND THE OBSERVABLE FORM OF THAT IS THE ONE THAT MATTERS. "It does
not sniff" is an absence, and an absence cannot be tested. What can be tested is the
consequence: a WRONGLY declared dialect is OBEYED. Told that a quote inside a quoted field
is written with a backslash, this reader reads `1,"say ""hi"", bye"` the way that rule says
to -- the doubled quote closes the field early and the comma inside it becomes a delimiter
-- and produces three fields where the truth is two. A reader that quietly corrected that
would be a reader that had guessed, and `req~ac-05~1` measures the false-positive rate of
exactly that state, which it could not do if the state were unreachable.

WHAT IS VALIDATED AT DECLARATION, and why it is not strictness for its own sake. An
encoding Python has no codec for, a delimiter of two characters, an escape policy nobody
implements: each is a dialect this reader cannot honour, and each would otherwise be
discovered when a batch ran. `contracts.declare` refuses at import for the same reason.

WHAT IS NOT VALIDATED: whether the dialect is TRUE of the bytes. That is not knowable here
and it is the producer's assertion, which is the whole point.

THE THREE FIELDS THE FLAGSHIP'S LITERAL LACKED are `escape`, `record_separator` and
`empty`, and each decides one measured incident. The escape policy decides `escape.csv`.
The record separator decides `multiline.csv`, because a separator inside a quoted field is
what makes a record and a line stop being the same thing. The empty semantics decides
whether a zero-length field is an empty string or a null, which is the difference between
a quality rule firing and not.

[impl->req~ac-04~1]
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass, fields
from typing import cast

from ingestproof.contracts import type_name

# `double` is RFC 4180 section 2.7: a quote inside a quoted field is written twice.
# `backslash` is what most non-conforming writers do. `none` is a reader that gives a
# quoted field no way at all to contain its own quote -- rare, and it is a real dialect
# rather than a mistake, so it is nameable.
ESCAPE_POLICIES = ("double", "backslash", "none")

# CR, LF and CRLF, and nothing else. A separator this reader cannot recognise inside a
# quoted field is a separator that turns every multiline record into the alignment defect
# this library exists to catch.
RECORD_SEPARATORS = ("\n", "\r\n", "\r")

# What an UNQUOTED zero-length field means. A QUOTED one is always the empty string: the
# producer wrote two delimiters around nothing on purpose, and there is nothing to guess.
EMPTY_SEMANTICS = ("empty-string", "null")


class DialectError(Exception):
    """A source dialect this library refuses, or one it was never given."""


@dataclass(frozen=True)
class Dialect:
    """A declared source dialect. Every field is required, and that is the criterion.

    A default is an inference with a nicer name: it is the library deciding a value the
    producer was supposed to state. Frozen for the same reason a `TableContract` is -- a
    dialect a caller can mutate is a dialect that changes between the parse and the report
    that cites it.
    """

    encoding: str
    delimiter: str
    quotechar: str
    escape: str
    record_separator: str
    empty: str

    def __post_init__(self) -> None:
        # ONE GATE AT THE TOP, and everything after it operates on a real `str`.
        # `codecs.lookup`, `len`, `==` and `in` all dispatch to code the CALLER wrote, and
        # measured on the version without this: a `str` subclass whose `__len__` or
        # `__eq__` raises replaced DialectError with the caller's own exception, and one
        # whose `__repr__` records ran inside the refusal message. That is the fourth time
        # this repository has met this class -- `rules._describe`, `contracts.type_name`,
        # `promotion._judge` -- and the answer each time is to stop asking the object.
        #
        # `type(value) is str` and not `isinstance`: a subclass IS the attack, and
        # `isinstance` consults `__class__`, which can be a property.
        for name in FIELD_NAMES:
            value = getattr(self, name)
            if type(value) is not str:
                raise DialectError(
                    f"{name} must be a plain str, not a {type_name(value)}: a subclass can "
                    "answer len, equality and repr with code of its own, and this layer "
                    "refuses at declaration rather than inside a batch"
                )

        try:
            codec = codecs.lookup(self.encoding)
        except LookupError as error:
            raise DialectError(
                f"no codec for the declared encoding {self.encoding!r}"
            ) from error

        # A TEXT codec. `codecs.lookup` also resolves the byte transforms -- hex_codec,
        # base64_codec, zlib_codec, rot_13 -- and `bytes.decode` then raises LookupError,
        # which is not UnicodeDecodeError and would escape `parse_records` un-wrapped.
        # Measured. Refusing here is what the docstring above already claims happens.
        if not codec._is_text_encoding:
            raise DialectError(
                f"the declared encoding {self.encoding!r} is a byte transform and not a "
                "text encoding, so it cannot decode a source"
            )

        for name in ("delimiter", "quotechar"):
            value = getattr(self, name)
            if len(value) != 1:
                raise DialectError(f"{name} must be exactly one character, not {value!r}")

        if self.delimiter == self.quotechar:
            raise DialectError(
                f"delimiter and quotechar are both {self.delimiter!r}: a field could not "
                "then be told from the quote that opens it"
            )

        for name, allowed in (
            ("escape", ESCAPE_POLICIES),
            ("record_separator", RECORD_SEPARATORS),
            ("empty", EMPTY_SEMANTICS),
        ):
            value = getattr(self, name)
            if value not in allowed:
                raise DialectError(f"{name} must be one of {allowed}, not {value!r}")

        for name in ("delimiter", "quotechar"):
            value = getattr(self, name)
            if value in self.record_separator:
                raise DialectError(
                    f"{name} {value!r} occurs in the record separator "
                    f"{self.record_separator!r}: the same bytes would mean two things "
                    "depending on the state, and no record could end"
                )


def require_dialect(dialect: object) -> Dialect:
    """Refuse to proceed without a declared dialect, and say why rather than only that.

    The message names both halves: what the caller must do, and what this library will not
    do instead. "dialect is required" states the rule and withholds the reason, and the
    reason is the thesis -- a guessed dialect makes the proof circular, because the guess
    comes from the bytes the proof is about.
    """
    # THE TYPE FIRST, and by `type(...)` rather than by `isinstance`, which consults
    # `__class__`. Truth-testing came first here and ran the caller's `__bool__` --
    # measured, an object whose `__bool__` raises escaped as its own exception, so a
    # caller writing `except DialectError` saw nothing at all.
    if issubclass(type(dialect), Dialect):
        # `cast` rather than `# type: ignore`: the line above PROVES the type, by a route
        # mypy cannot follow, and a cast says which type was proved.
        return cast("Dialect", dialect)

    # Only an EXACT builtin is truth-tested, so "you gave me nothing" stays distinguishable
    # from "you gave me the wrong thing" without asking an arbitrary object anything.
    if dialect is None or (
        type(dialect) in (dict, str, int, bool, list, tuple, set, frozenset) and not dialect
    ):
        raise DialectError(
            "no source dialect was declared. Declare one: this library will never infer a "
            "dialect from the bytes it is about to check, because a guess made from those "
            "bytes cannot then be evidence about them"
        )

    raise DialectError(
        f"the declared dialect is a {type_name(dialect)} and not a Dialect. Declare "
        "one rather than a mapping: a mapping has no required fields, so it can infer "
        "by omission"
    )




def parse_records(source: bytes, dialect: object) -> tuple[tuple[str | None, ...], ...]:
    """Bytes and a declared dialect in, records out. RECORDS, never lines.

    A record separator inside a quoted field belongs to the field, so one record can span
    two lines -- and the whole of `req~ac-03~1` is that the two streams then stop agreeing.
    This function is on the record side of that, always.
    """
    declared = require_dialect(dialect)

    # Validated at the boundary like the dialect half, rather than left to raise an
    # AttributeError from inside: a `str` here means someone decoded already, under an
    # encoding this function was never told about.
    if not isinstance(source, bytes | bytearray):
        raise DialectError(
            f"the source is a {type_name(source)} and not bytes: this reader decodes "
            "under the DECLARED encoding, so it must be given the bytes"
        )

    try:
        text = bytes(source).decode(declared.encoding)
    except UnicodeDecodeError as error:
        # Obeyed, not corrected: a declared encoding that cannot read these bytes is a
        # refusal and never an invitation to try another one.
        raise DialectError(
            f"the declared encoding {declared.encoding!r} cannot decode this source"
        ) from error

    return _split(text, declared)


def _split(text: str, dialect: Dialect) -> tuple[tuple[str | None, ...], ...]:
    """The state machine. Four states, and the fourth is where the incidents live.

    Inside a quoted field the delimiter and the record separator are ordinary characters,
    which is the multiline incident. After a closing quote the reader is between a field
    that ended and a delimiter that has not arrived, which is the escape incident: under a
    policy where a doubled quote is NOT an escape, the field ended early and the rest of it
    is read as though the producer had written it outside the quotes.
    """
    separator = dialect.record_separator
    records: list[tuple[str | None, ...]] = []
    fields_: list[str] = []
    quoted_flags: list[bool] = []
    field: list[str] = []
    quoted = False
    in_quotes = False
    index = 0

    def started() -> bool:
        """Has anything at all been seen since the last record boundary?

        `quoted` is in here and it is the whole of the bug this replaced. The old flush
        predicate read `field or fields_ or in_quotes` and a source ending in `""` leaves
        all three false while `quoted` is true -- so the record was DISCARDED. Measured
        over an exhaustive sweep of 19,531 short inputs against `csv.reader`: 117 lost a
        record, under every escape policy, every empty semantics and every separator.

        A LOST RECORD IS THE DEFECT THIS LIBRARY EXISTS TO DETECT, and it was in the
        reader that detects it: every index after the loss shifts by one, so a
        differential built on it reports damage at the wrong record for the rest of the
        file. `req~ac-03~1` is about locating by record index; this is what makes the
        index worth anything.
        """
        # `in_quotes` is NOT a term here, and its absence was measured rather than
        # reasoned: dropping it from this expression killed no test, because opening a
        # quote sets `quoted` in the same statement and `quoted` is cleared only by
        # `end_field`, which cannot run inside the quotes. A term that can never change
        # the answer reads like one that can, which is the shape of a guard that never bit.
        return bool(field or fields_ or quoted)

    def end_field() -> None:
        nonlocal quoted
        quoted_flags.append(quoted)
        fields_.append("".join(field))
        field.clear()
        quoted = False

    def end_record() -> None:
        # A blank line is a record of NO fields, not a record of one empty field.
        # `csv.reader` answers `[]` for it, and the property in tests/property asserts the
        # two readers agree over text neither of them wrote -- so this is where they must.
        if started():
            end_field()
        records.append(_finish(tuple(fields_), quoted_flags, dialect))
        fields_.clear()
        quoted_flags.clear()

    while index < len(text):
        character = text[index]

        if in_quotes:
            if character == dialect.quotechar:
                doubled = (
                    dialect.escape == "double"
                    and text[index + 1 : index + 1 + len(dialect.quotechar)]
                    == dialect.quotechar
                )
                if doubled:
                    field.append(dialect.quotechar)
                    index += 2
                    continue
                in_quotes = False
                index += 1
                continue
            if dialect.escape == "backslash" and character == "\\":
                escaped = text[index + 1 : index + 2]
                # At end of input there is nothing to escape, so the backslash is a
                # character the producer wrote. Appending the empty slice instead made it
                # VANISH -- measured, `"a\` read identically to `"a` -- and a byte
                # disappearing without a signal is the one thing this library is about.
                field.append(escaped or character)
                index += 2
                continue
            field.append(character)
            index += 1
            continue

        if character == dialect.quotechar and not field:
            in_quotes = True
            quoted = True
            index += 1
            continue

        if character == dialect.delimiter:
            end_field()
            index += 1
            continue

        if text.startswith(separator, index):
            end_record()
            index += len(separator)
            continue

        field.append(character)
        index += 1

    if started():
        end_record()

    return tuple(records)


def _finish(
    values: tuple[str, ...], quoted_flags: list[bool], dialect: Dialect
) -> tuple[str | None, ...]:
    """Apply the empty semantics, and only to fields the producer did not quote.

    `a,,b` under `null` is three fields of which the middle is null. `a,"",b` is three
    fields of which the middle is the empty string, under either policy: two delimiters
    around a quoted nothing is a producer saying "empty", not a producer saying nothing.
    """
    if dialect.empty != "null":
        return tuple(values)
    return tuple(
        None if value == "" and not quoted_flags[position] else value
        for position, value in enumerate(values)
    )


FIELD_NAMES = tuple(field.name for field in fields(Dialect))
