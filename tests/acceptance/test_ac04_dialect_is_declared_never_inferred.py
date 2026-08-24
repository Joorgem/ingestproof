"""req~ac-04~1 -- the library refuses to run without a declared source dialect.

RED TODAY, AND DELIBERATELY SO. `ingestproof.dialect` does not exist: this file is the
frozen half of the closing rule for the P2 dialect item, and `tests/acceptance/**` is
frozen precisely so the turn that writes the library cannot also write the test that
judges it.

    uv run pytest tests/acceptance/test_ac04_dialect_is_declared_never_inferred.py --runxfail

`--runxfail` makes the marker below inert and reports the real failure. Without it the
whole file reports `xfailed` and CI stays green, which is the only way a test for an
unwritten feature can sit in a repository whose CI is the authoritative gate.

WHAT "NEVER INFERRED" HAS TO MEAN MECHANICALLY, because "the library does not sniff" is
not a thing a test can observe. Absence of a feature is unobservable; what IS observable is
that a WRONGLY declared dialect is OBEYED rather than quietly corrected. A library that
sniffs would read `escape.csv` correctly no matter what it was told, and that is the shape
this file pins: told the wrong thing, it must produce the wrong answer. `req~ac-05~1` then
measures the false-positive rate of exactly that state, which is why it must be reachable.

THE SIX KEYS ARE NOT THE FLAGSHIP'S SIX. `src/opl/contracts/cnpj_schemas.py` carries a
six-key `CSV_DIALECT` -- encoding, sep, quotechar, header, date_format, decimal -- of which
the design says four are used, and that it "needs to be extended with escape policy, record
separator and empty semantics before it serves" (docs/design.md section 10). Those three
are what the incidents in `tests/fixtures/incidents/` turn on, so they are required here
and `date_format`/`decimal` are not: a date format is a TYPE concern and this layer is
about bytes to fields.

[utest->req~ac-04~1]
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MISSING = importlib.util.find_spec("ingestproof.dialect") is None

pytestmark = pytest.mark.xfail(
    MISSING,
    strict=True,
    reason="the P2 dialect item has not landed: ingestproof.dialect does not exist",
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "incidents"

# The dialect every fixture in `tests/fixtures/incidents/` was generated under, by
# `tools/make_incident_fixtures.py`. Read off the bytes rather than assumed: the files are
# UTF-8, comma-delimited, double-quoted, LF-terminated, and RFC 4180 section 2.7 doubling
# is how a quote inside a quoted field is written -- `escape.csv` is exactly that case.
RFC4180 = dict(
    encoding="utf-8",
    delimiter=",",
    quotechar='"',
    escape="double",
    record_separator="\n",
    empty="empty-string",
)


def _dialect(**overrides: object):
    from ingestproof.dialect import Dialect

    fields = dict(RFC4180)
    fields.update(overrides)
    return Dialect(**fields)  # type: ignore[arg-type]


def test_the_dialect_carries_the_three_fields_the_design_says_the_flagship_lacked() -> None:
    """escape policy, record separator, empty semantics -- and each is load-bearing.

    Not a completeness checklist: each of the three decides one of the three measured
    incidents. The escape policy decides `escape.csv`; the record separator decides
    `multiline.csv`, because an embedded separator inside a quoted field is what makes a
    record and a line stop being the same thing; the empty semantics decides whether a
    zero-length field is an empty string or a null, which is the difference between a
    quality rule firing and not.
    """
    dialect = _dialect()

    assert dialect.encoding == "utf-8"
    assert dialect.delimiter == ","
    assert dialect.quotechar == '"'
    assert dialect.escape == "double"
    assert dialect.record_separator == "\n"
    assert dialect.empty == "empty-string"


def test_a_dialect_is_immutable() -> None:
    # A dialect a caller can mutate is a dialect that changes between the parse and the
    # report that cites it.
    from ingestproof.dialect import Dialect

    dialect = _dialect()

    with pytest.raises((AttributeError, TypeError)):
        dialect.delimiter = ";"

    assert isinstance(dialect, Dialect)


def test_no_field_has_a_default_so_a_dialect_cannot_be_half_declared() -> None:
    """Every field is required, and that is the criterion rather than strictness.

    A default is an inference with a nicer name: it is the library deciding a value the
    producer was supposed to state. The six below are the six the incidents turn on, so a
    dialect missing any one of them is not a declaration.
    """
    from ingestproof.dialect import Dialect

    for omitted in RFC4180:
        partial = {key: value for key, value in RFC4180.items() if key != omitted}
        with pytest.raises(TypeError):
            Dialect(**partial)  # type: ignore[arg-type]


def test_running_without_a_dialect_is_refused_with_a_message_that_says_why() -> None:
    """The criterion's own words: refuses, WITH A MESSAGE THAT SAYS WHY.

    "Says why" is asserted as: the message names what the caller must do and what the
    library will not do instead. A message reading only "dialect is required" states the
    rule and withholds the reason, and the reason is the whole thesis -- you assert what
    the producer wrote, and this library proves the reader read that.
    """
    from ingestproof.dialect import DialectError, require_dialect

    with pytest.raises(DialectError) as raised:
        require_dialect(None)

    message = str(raised.value).lower()

    assert "dialect" in message
    assert "declare" in message
    assert "infer" in message


def test_the_refusal_is_the_same_for_a_dialect_that_is_merely_falsy() -> None:
    # `require_dialect({})` and `require_dialect("")` are the shapes a caller reaches by
    # threading a config value through, and they are not declarations either.
    from ingestproof.dialect import DialectError, require_dialect

    for absent in (None, {}, "", 0):
        with pytest.raises(DialectError):
            require_dialect(absent)  # type: ignore[arg-type]


def test_a_declared_dialect_is_returned_unchanged() -> None:
    # The control arm for the four refusals above: without it they are equally green for a
    # `require_dialect` that refuses everything.
    from ingestproof.dialect import require_dialect

    dialect = _dialect()

    assert require_dialect(dialect) is dialect


# --- what "never inferred" means where a test can see it ---------------------------------


def test_a_wrongly_declared_dialect_is_obeyed_rather_than_quietly_corrected() -> None:
    """THE CRITERION, and the only observable form of "never inferred".

    `escape.csv` is `id,name` then `1,"say ""hi"", bye"`. Under the declared RFC 4180
    doubling it is ONE field whose value is `say "hi", bye`. Told instead that a quote
    inside a quoted field is written with a backslash, the doubled quote closes the field
    early and the comma inside it becomes a delimiter. Recorded in docs/measurements.md
    section 6 as Spark 4.2.0 with no escape option -- measured outside this repository and
    copied in: `Row(id='1', name='"say ""hi""')`, the delimiter swallowed.

    A library that sniffed would produce the RIGHT answer under BOTH declarations, and that
    is what this asserts against. The wrong declaration must produce the wrong parse,
    because `req~ac-05~1` measures the false-positive rate of that state and cannot measure
    a state the library refuses to enter.
    """
    from ingestproof.dialect import parse_records

    source = (FIXTURES / "escape.csv").read_bytes()

    correct = parse_records(source, _dialect())
    wrong = parse_records(source, _dialect(escape="backslash"))

    assert correct == (("id", "name"), ("1", 'say "hi", bye'))
    assert wrong != correct
    assert len(wrong[1]) > 2


def test_the_module_offers_no_way_to_ask_it_what_the_dialect_is() -> None:
    """Absence, asserted the only way absence can be: by name.

    A sniffer would arrive called `sniff`, `detect`, `infer` or `guess`, and the criterion
    is that no such thing exists. This is a weak test on its own -- a sniffer named
    `figure_out` walks past it -- which is why the strong assertion is the one above, where
    a wrong declaration must produce a wrong answer.
    """
    import ingestproof.dialect as module

    for banned in ("sniff", "detect", "infer", "guess", "autodetect"):
        assert not hasattr(module, banned), banned


def test_the_negative_control_parses_identically_under_the_declared_dialect() -> None:
    # `clean.csv` is the corpus's negative control and carries no incident. If it ever
    # parses differently from the reference below, the disagreement is in the reader and
    # not in the fixture, and every damage this layer reports is suspect.
    import csv
    import io

    from ingestproof.dialect import parse_records

    source = (FIXTURES / "clean.csv").read_bytes()
    reference = tuple(
        tuple(row) for row in csv.reader(io.StringIO(source.decode("utf-8")))
    )

    assert parse_records(source, _dialect()) == reference
    assert len(reference) == 4
