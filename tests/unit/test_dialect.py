"""Unit ring for `ingestproof.dialect`.

The frozen acceptance file judges the criterion over `escape.csv` and `clean.csv`. This
file judges what those two do not reach: every refusal `__post_init__` makes, the other
two incidents, the record separators nobody wrote a fixture for, and the empty semantics.

mutmut 3 mutates INSIDE functions only, so every module-level constant gets an assertion
on its VALUE. Without one the mutation gate is silently inert on it.
"""

from __future__ import annotations

import csv
import io
import itertools
from pathlib import Path

import pytest

from ingestproof import dialect as module
from ingestproof.dialect import (
    EMPTY_SEMANTICS,
    ESCAPE_POLICIES,
    FIELD_NAMES,
    RECORD_SEPARATORS,
    Dialect,
    DialectError,
    parse_records,
    require_dialect,
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


def _dialect(**overrides: object) -> Dialect:
    fields = dict(RFC4180)
    fields.update(overrides)
    return Dialect(**fields)  # type: ignore[arg-type]


# --- the module-level constants -----------------------------------------------------------


def test_every_module_level_constant_holds_the_value_the_module_documents() -> None:
    assert ESCAPE_POLICIES == ("double", "backslash", "none")
    assert RECORD_SEPARATORS == ("\n", "\r\n", "\r")
    assert EMPTY_SEMANTICS == ("empty-string", "null")
    assert FIELD_NAMES == (
        "encoding",
        "delimiter",
        "quotechar",
        "escape",
        "record_separator",
        "empty",
    )


def test_the_six_fields_are_the_six_the_acceptance_file_declares() -> None:
    # FIELD_NAMES is derived from the dataclass, so this is the assertion that the
    # dataclass and the frozen test have not drifted apart.
    assert set(FIELD_NAMES) == set(RFC4180)


# --- what a Dialect refuses at declaration -------------------------------------------------


def test_an_encoding_python_has_no_codec_for_is_refused_where_it_is_declared() -> None:
    # Not at parse time. A typo in an encoding name discovered when a batch runs is the
    # defect `contracts.declare` refuses at import for the same reason.
    with pytest.raises(DialectError, match="no codec"):
        _dialect(encoding="utf-9")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("delimiter", ",,"),
        ("delimiter", ""),
        ("quotechar", "''"),
        ("quotechar", ""),
        ("delimiter", 7),
    ),
    ids=("two-delimiters", "no-delimiter", "two-quotes", "no-quote", "not-a-string"),
)
def test_a_delimiter_or_quotechar_that_is_not_one_character_is_refused(
    field: str, value: object
) -> None:
    with pytest.raises(DialectError, match="exactly one character"):
        _dialect(**{field: value})


def test_a_delimiter_equal_to_the_quotechar_is_refused() -> None:
    # A field could not then be told from the quote that opens it.
    with pytest.raises(DialectError, match="could not then be told"):
        _dialect(delimiter='"')


def test_a_delimiter_that_occurs_in_the_record_separator_is_refused() -> None:
    # No record could end: every separator would first be read as a field break.
    with pytest.raises(DialectError, match="no record could end"):
        _dialect(delimiter="\n")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("escape", "backslashes"),
        ("escape", None),
        ("record_separator", "\n\n"),
        ("record_separator", "|"),
        ("empty", "null-string"),
    ),
    ids=("escape-typo", "escape-none", "double-newline", "pipe-separator", "empty-typo"),
)
def test_a_policy_this_reader_cannot_honour_is_refused_at_declaration(
    field: str, value: object
) -> None:
    with pytest.raises(DialectError, match="must be one of"):
        _dialect(**{field: value})


def test_every_policy_the_module_names_is_actually_constructible() -> None:
    # The control arm for the five refusals above: without it they are equally green for a
    # `__post_init__` that refuses every value it is shown.
    for escape in ESCAPE_POLICIES:
        assert _dialect(escape=escape).escape == escape
    for separator in RECORD_SEPARATORS:
        assert _dialect(record_separator=separator).record_separator == separator
    for empty in EMPTY_SEMANTICS:
        assert _dialect(empty=empty).empty == empty


def test_a_dialect_is_not_validated_for_being_TRUE_of_any_bytes() -> None:
    """The line between what is checked and what is not, asserted so it stays there.

    A dialect declaring `;` over a comma-delimited file is perfectly constructible. Whether
    it is true of the bytes is the producer's assertion, and checking it here would be the
    inference the whole module refuses.
    """
    wrong = _dialect(delimiter=";")

    assert parse_records(b"a,b\n", wrong) == (("a,b",),)


# --- require_dialect -----------------------------------------------------------------------


@pytest.mark.parametrize("absent", (None, {}, "", 0, [], ()), ids=lambda v: repr(v))
def test_anything_falsy_is_no_declaration_at_all(absent: object) -> None:
    with pytest.raises(DialectError, match="no source dialect was declared"):
        require_dialect(absent)


def test_the_refusal_names_what_to_do_and_what_the_library_will_not_do() -> None:
    # The criterion's own words are "with a message that says why". A message stating only
    # the rule withholds the reason, and the reason is the thesis.
    with pytest.raises(DialectError) as raised:
        require_dialect(None)

    message = str(raised.value).lower()

    assert "declare" in message
    assert "infer" in message
    assert "circular" in message or "cannot then be evidence" in message


def test_a_mapping_is_refused_because_a_mapping_can_infer_by_omission() -> None:
    with pytest.raises(DialectError, match="not a Dialect"):
        require_dialect(dict(RFC4180))


def test_the_refusal_names_the_type_without_running_its_repr() -> None:
    # `contracts.type_name`, for the third-occurrence reason recorded there. A caller's
    # `__repr__` running inside a refusal is a refusal that can be made to raise.
    ran: list[str] = []

    class Recording:
        def __repr__(self) -> str:
            ran.append("repr")
            return "<recording>"

    with pytest.raises(DialectError, match="Recording"):
        require_dialect(Recording())

    assert ran == []


def test_a_declared_dialect_comes_back_as_the_same_object() -> None:
    declared = _dialect()

    assert require_dialect(declared) is declared


# --- the reader --------------------------------------------------------------------------


def _reference(name: str) -> tuple[tuple[str, ...], ...]:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return tuple(tuple(row) for row in csv.reader(io.StringIO(text)))


@pytest.mark.parametrize(
    "name", ("clean.csv", "escape.csv", "extra_field.csv", "multiline.csv")
)
def test_every_incident_fixture_reads_the_same_as_the_stdlib(name: str) -> None:
    """Two parsers, and the second one is not this repository's.

    The stdlib implements exactly the declared dialect below -- comma, double quote, RFC
    4180 doubling -- so a disagreement here is this reader's and not the fixture's.
    """
    source = (FIXTURES / name).read_bytes()

    assert parse_records(source, _dialect()) == _reference(name)


def test_a_record_separator_inside_a_quoted_field_belongs_to_the_field() -> None:
    """The multiline incident, stated as the property rather than as a fixture.

    THREE records, not four lines. Everything in `req~ac-03~1` rests on this: the two
    streams stop agreeing here, and a reader that got it wrong would put the misalignment
    into every report after the first multiline record.
    """
    records = parse_records((FIXTURES / "multiline.csv").read_bytes(), _dialect())

    assert len(records) == 3
    assert records[1] == ("1", "line A\nline B")


def test_a_trailing_record_separator_does_not_invent_an_empty_last_record() -> None:
    assert parse_records(b"a,b\n", _dialect()) == (("a", "b"),)
    assert parse_records(b"a,b", _dialect()) == (("a", "b"),)


@pytest.mark.parametrize(
    "separator", RECORD_SEPARATORS, ids=("lf", "crlf", "cr")
)
def test_each_declared_record_separator_is_honoured(separator: str) -> None:
    source = f"a,b{separator}c,d{separator}".encode()

    assert parse_records(source, _dialect(record_separator=separator)) == (
        ("a", "b"),
        ("c", "d"),
    )


def test_a_separator_that_was_not_declared_is_an_ordinary_character() -> None:
    # Obeyed, not corrected: declared LF, a CRLF file keeps its CR inside the field. This
    # is the shape `req~ac-05~1` measures, so it must be reachable.
    assert parse_records(b"a,b\r\nc,d\r\n", _dialect()) == (("a", "b\r"), ("c", "d\r"))


# --- the escape policies -------------------------------------------------------------------


def test_double_is_rfc4180_and_backslash_is_obeyed_into_the_wrong_answer() -> None:
    source = (FIXTURES / "escape.csv").read_bytes()

    assert parse_records(source, _dialect()) == (("id", "name"), ("1", 'say "hi", bye'))

    # OUTSIDE the quotes a quotechar is an ordinary character, so the second quote of
    # the pair lands in the field too. Measured, not predicted: I traced this by hand as
    # `say "hi"` and the run said `say "hi""`. Three fields where the truth is two, which
    # is the shape the criterion needs; matching any particular production reader is not,
    # and `req~ac-02a~1` holds Spark's recorded output separately for that.
    wrong = parse_records(source, _dialect(escape="backslash"))

    assert wrong[1] == ("1", 'say "hi""', ' bye"')
    assert len(wrong[1]) == 3


def test_backslash_escapes_a_quote_and_a_backslash_inside_a_quoted_field() -> None:
    source = b'a,"say \\"hi\\" and \\\\ back"\n'

    assert parse_records(source, _dialect(escape="backslash")) == (
        ("a", 'say "hi" and \\ back'),
    )


def test_under_none_a_quoted_field_has_no_way_to_contain_its_own_quote() -> None:
    # A real dialect rather than a mistake, so it is nameable -- and it reads the doubled
    # quote as an early close, exactly as `backslash` does.
    source = (FIXTURES / "escape.csv").read_bytes()

    assert parse_records(source, _dialect(escape="none"))[1] == ("1", 'say "hi""', ' bye"')


# --- the empty semantics --------------------------------------------------------------------


def test_an_unquoted_empty_field_is_the_empty_string_or_a_null_as_declared() -> None:
    source = b"a,,b\n"

    assert parse_records(source, _dialect(empty="empty-string")) == (("a", "", "b"),)
    assert parse_records(source, _dialect(empty="null")) == (("a", None, "b"),)


def test_a_QUOTED_empty_field_is_the_empty_string_under_either_policy() -> None:
    """Two delimiters around a quoted nothing is a producer saying "empty".

    Under `null` it stays the empty string, because there is nothing to guess: the
    producer wrote the quotes. Collapsing it to null would be the library deciding a value
    it was told.
    """
    source = b'a,"",b\n'

    for empty in EMPTY_SEMANTICS:
        assert parse_records(source, _dialect(empty=empty)) == (("a", "", "b"),)


# --- the encoding ---------------------------------------------------------------------------


def test_an_encoding_that_cannot_read_these_bytes_refuses_rather_than_trying_another() -> None:
    # Obeyed, not corrected. Trying a second encoding is the inference this module exists
    # to refuse, and it would make the refusal a suggestion.
    with pytest.raises(DialectError, match="cannot decode"):
        parse_records(b"\xff\xfe\x00id", _dialect(encoding="utf-8"))


def test_a_wrongly_declared_encoding_that_CAN_decode_produces_the_wrong_text() -> None:
    """The more dangerous half: latin-1 decodes every byte, so nothing raises.

    `cp1252` and `latin-1` disagree on the 0x80-0x9F range, and the flagship's corpus is
    cp1252 -- so a dialect declaring the wrong one of the two reads silently wrong, which
    is precisely the state `req~ac-05~1` measures.
    """
    source = "a,café\n".encode()

    assert parse_records(source, _dialect()) == (("a", "café"),)
    assert parse_records(source, _dialect(encoding="latin-1")) == (("a", "cafÃ©"),)


def test_the_module_offers_no_way_to_ask_it_what_the_dialect_is() -> None:
    for banned in ("sniff", "detect", "infer", "guess", "autodetect"):
        assert not hasattr(module, banned), banned


# --- what the review found, each measured on the reader before it was changed ------------


def test_the_exhaustive_differential_against_the_stdlib_finds_nothing() -> None:
    """19,531 inputs, and this is the strongest assertion in the file.

    Every string of length 0..6 over the delimiter, the quotechar, the record separator, a
    letter and a space -- so every arrangement of the four characters a CSV reader can get
    wrong, at every length the state machine has states for. `csv.reader` is the referee.

    It is here because it FOUND something: on the reader as first written, 117 of these
    lost a record outright and 5,326 disagreed on the arity of a blank line. Both are
    closed, and this is what says so and keeps saying so. It costs 0.08 seconds.
    """
    dialect = _dialect()
    disagreements: list[tuple[str, object, object]] = []
    swept = 0

    for length in range(7):
        for combination in itertools.product(("a", ",", '"', "\n", " "), repeat=length):
            text = "".join(combination)
            swept += 1
            try:
                reference = tuple(tuple(row) for row in csv.reader(io.StringIO(text)))
            except csv.Error:
                continue  # the referee refuses it; there is nothing to agree about
            if parse_records(text.encode(), dialect) != reference:
                disagreements.append((text, parse_records(text.encode(), dialect), reference))

    assert swept == 19531
    assert disagreements == []


def test_a_source_ending_in_a_quoted_empty_field_does_not_lose_the_record() -> None:
    """THE defect this reader existed to detect, found inside the reader.

    The flush predicate read `field or fields_ or in_quotes`, and `""` at end of input
    leaves all three false while `quoted` is true -- so the record was discarded. A lost
    record shifts every index after it, and `req~ac-03~1` locates damage BY record index,
    so a differential built on this would have reported damage at the wrong record for the
    whole remainder of a file.

    Reached by ordinary bytes: any file whose last line is a quoted empty field and which
    was written without a trailing separator.
    """
    assert parse_records(b'""', _dialect()) == (("",),)
    assert parse_records(b'a\n""', _dialect()) == (("a",), ("",))
    assert parse_records(b'id,name\n1,x\n""', _dialect()) == (
        ("id", "name"),
        ("1", "x"),
        ("",),
    )


def test_a_blank_line_is_a_record_of_no_fields_and_not_one_empty_field() -> None:
    # `csv.reader` answers `[]`, and the property asserts the two readers agree over text
    # neither of them wrote. They disagreed on 5,326 of the swept inputs before this.
    assert parse_records(b"\n", _dialect()) == ((),)
    assert parse_records(b"a\n\nb\n", _dialect()) == (("a",), (), ("b",))


def test_a_byte_transform_is_not_a_text_encoding_and_is_refused_at_declaration() -> None:
    # `codecs.lookup` resolves these, so `__post_init__` used to admit them and
    # `bytes.decode` then raised LookupError -- not UnicodeDecodeError, so it escaped
    # `parse_records` un-wrapped and a caller catching DialectError saw nothing.
    for transform in ("hex_codec", "base64_codec", "zlib_codec", "rot_13"):
        with pytest.raises(DialectError, match="byte transform"):
            _dialect(encoding=transform)


def test_a_quotechar_inside_the_record_separator_is_refused_like_a_delimiter_is() -> None:
    # The same two bytes would mean two things depending on the state: with quotechar
    # "\r" and separator "\r\n", `a\r\nb` splits into two records and `\r\nb` opens a
    # quote that never closes.
    with pytest.raises(DialectError, match="occurs in the record separator"):
        _dialect(quotechar="\r", record_separator="\r\n")


def test_a_source_that_is_not_bytes_is_refused_at_the_boundary() -> None:
    # It used to raise a bare AttributeError from inside. A `str` here means someone
    # decoded already, under an encoding this function was never told about.
    for wrong in ("a,b", None, 7, ["a", "b"]):
        with pytest.raises(DialectError, match="not bytes"):
            parse_records(wrong, _dialect())  # type: ignore[arg-type]

    assert parse_records(bytearray(b"a,b"), _dialect()) == (("a", "b"),)


def test_a_trailing_lone_backslash_is_a_character_and_not_a_disappearance() -> None:
    # It used to append the empty slice, so `"a\` read identically to `"a` -- a byte the
    # producer wrote vanishing with no signal, in a library whose thesis is that it did not.
    assert parse_records(b'"a\\', _dialect(escape="backslash")) == (("a\\",),)
    assert parse_records(b'"a', _dialect(escape="backslash")) == (("a",),)


# --- the four mutants the suite could not see, and the inputs that see them --------------


def test_the_flag_of_a_quoted_field_does_not_leak_into_the_next_one() -> None:
    # Kills `quoted = False` dropped from `end_field`: without it the empty field after a
    # quoted one is recorded as quoted, so `null` never fires on it.
    assert parse_records(b'"a",\n', _dialect(empty="null")) == (("a", None),)


def test_the_flags_do_not_survive_into_the_next_record() -> None:
    # Kills `quoted_flags.clear()` dropped from `end_record`: the second record then reads
    # the first record's flags by position.
    assert parse_records(b'"a",x\n,y\n', _dialect(empty="null")) == (
        ("a", "x"),
        (None, "y"),
    )


def test_a_record_that_ends_mid_quote_is_still_a_record() -> None:
    # An unterminated quote at end of input is still a record. It does NOT kill an
    # `in_quotes` term in the flush predicate -- measured, that term was dead, because
    # opening a quote sets `quoted` in the same statement. The term is gone and the
    # predicate says why.
    assert parse_records(b'a\n"', _dialect()) == (("a",), ("",))


def test_a_record_whose_last_field_is_empty_is_still_a_record() -> None:
    # Kills `fields_` dropped from the flush predicate.
    assert parse_records(b"a,", _dialect()) == (("a", ""),)
