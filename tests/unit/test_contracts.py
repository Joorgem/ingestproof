"""Unit ring for `ingestproof.contracts`.

The frozen acceptance test judges the criterion; this file also judges the parts of the module
the criterion does not reach -- the module-level constants, the reader's refusals, and the
quoting rule, which has a control arm because a rule against a hazard that does not exist
is green forever and proves nothing.

mutmut 3 mutates INSIDE functions only, so every module-level constant the module exports gets an
assertion on its VALUE. Without one the mutation gate is silently inert on it.
"""

from __future__ import annotations

import datetime
import unicodedata

import pytest
import yaml

from ingestproof import contracts
from ingestproof.contracts import (
    AUDIT_SCHEMA,
    BATCH_ID_COLUMN,
    CONTRACT_ID_COLUMN,
    INDENT,
    JOB_NAME_PREFIX,
    PLAIN_KEY,
    REJECTED_BY_COLUMN,
    RESERVED_PLAIN_WORDS,
    SENTINEL_BATCH_ID,
    TAG_PREFIX,
    YAML_LINE_SEPARATORS,
    ContractError,
    TableContract,
    declare,
    job_resource,
    job_yaml,
    load_job_yaml,
    register,
)


def _contract(**overrides: object) -> TableContract:
    fields: dict[str, object] = {
        "name": "incidents",
        "contract_id": "incidents@1",
        "staging": "main.staging.incidents",
        "bronze": "main.bronze.incidents",
        "quarantine": "main.quarantine.incidents",
        "landing_mode": "append",
        "prefix": "incidents_",
        "constraints": (("id_not_null", "id IS NOT NULL"),),
    }
    fields.update(overrides)
    return TableContract(**fields)  # type: ignore[arg-type]


def _named(name: str, contract_id: str, **overrides: object) -> TableContract:
    fields: dict[str, object] = {
        "name": name,
        "contract_id": contract_id,
        "staging": f"main.staging.{name}",
        "bronze": f"main.bronze.{name}",
        "quarantine": f"main.quarantine.{name}",
        "prefix": name + "_",
    }
    fields.update(overrides)
    return _contract(**fields)


# --- the module-level constants -------------------------------------------------------


def test_every_module_level_constant_holds_the_value_the_module_documents() -> None:
    assert SENTINEL_BATCH_ID == "REQUIRED-PASS-A-BATCH-ID"
    assert BATCH_ID_COLUMN == "_batch_id"
    assert CONTRACT_ID_COLUMN == "_contract_id"
    assert REJECTED_BY_COLUMN == "_rejected_by"
    assert AUDIT_SCHEMA == (
        ("_batch_id", "string"),
        ("_contract_id", "string"),
        ("_rejected_by", "string"),
    )
    assert JOB_NAME_PREFIX == "ingestproof-"
    assert TAG_PREFIX == "ingestproof_"
    assert INDENT == 2
    assert PLAIN_KEY.pattern == r"\A[A-Za-z_][A-Za-z0-9_-]*\Z"
    assert YAML_LINE_SEPARATORS == ("\u2028", "\u2029")


def test_the_reserved_word_set_is_what_a_yaml_parser_may_refuse_to_call_a_string() -> None:
    coerced = {
        word
        for word in RESERVED_PLAIN_WORDS
        if not isinstance(next(iter(yaml.safe_load(f"{word}: 'x'"))), str)
    }

    assert len(RESERVED_PLAIN_WORDS) == 25
    assert len(coerced) == 21
    assert RESERVED_PLAIN_WORDS - coerced == {"y", "Y", "n", "N"}

    # Enumerated rather than lowercased-on-lookup: YAML 1.1 spells the word `on` as `on`,
    # `On` and `ON` and NOT as `oN`, so a case-insensitive membership test would quote one
    # spelling more than any parser needs.
    assert "oN" not in RESERVED_PLAIN_WORDS
    assert isinstance(next(iter(yaml.safe_load("oN: 'x'"))), str)


# --- the quoting rule, and the hazard it exists for ------------------------------------


def test_the_hazard_the_quoting_rule_exists_for_is_real() -> None:
    """The control arm, and it is the reason the parametrised test below means anything.

    Without it, that test is equally green in a world where PyYAML coerces nothing and the
    quoting rule is inert -- this repository's recurring defect, which is a guard that
    never bit being read as a guard that held.
    """
    assert yaml.safe_load("on: 'x'") == {True: "x"}
    assert yaml.safe_load("k: 2026-08-23") == {"k": datetime.date(2026, 8, 23)}
    assert yaml.safe_load("k: 123") == {"k": 123}


@pytest.mark.parametrize("name", ["on", "no", "true", "null", "2026-08-23", "123", "1.5"])
def test_a_table_name_yaml_would_coerce_survives_as_a_string(name: str) -> None:
    contract = _named(name, f"{name}@1")
    text = job_yaml(contract)
    loaded = yaml.safe_load(text)

    assert loaded == job_resource(contract)
    assert list(loaded["resources"]["jobs"]) == [name]
    assert load_job_yaml(text) == job_resource(contract)


@pytest.mark.parametrize("name", ["it's", "a'b''c"])
def test_an_apostrophe_in_a_declaration_survives_both_parsers(name: str) -> None:
    contract = _named(name, f"{name}@1")
    text = job_yaml(contract)

    assert yaml.safe_load(text) == job_resource(contract)
    assert load_job_yaml(text) == job_resource(contract)


# --- the guards ------------------------------------------------------------------------


def test_a_prefix_that_is_not_the_name_plus_underscore_is_refused() -> None:
    with pytest.raises(ContractError, match="matches no file group"):
        declare(_contract(prefix="matches_nothing_"))


def test_a_table_with_no_landing_mode_is_refused_after_the_prefix_guard_passed() -> None:
    # `jobless_` IS the prefix rule's answer for `jobless`, so the prefix guard passes and
    # the landing-mode guard is what fires. If this ever raises the prefix message, the
    # two guards have swapped and the acceptance test's third case is proving the wrong one.
    with pytest.raises(ContractError, match="no landing mode"):
        declare(_named("jobless", "jobless@1", landing_mode=None))


def test_an_unknown_contract_id_is_refused_by_register() -> None:
    with pytest.raises(ContractError, match="unknown contract"):
        register("no-such-contract-id")


def test_register_answers_with_the_contract_declare_bound() -> None:
    contract = _named("lookup_ok", "lookup_ok@1")
    declare(contract)

    assert register("lookup_ok@1") is contract


def test_declaring_the_same_contract_twice_is_not_a_refusal() -> None:
    contract = _named("idempotent", "idempotent@1")
    declare(contract)
    declare(_named("idempotent", "idempotent@1"))

    assert register("idempotent@1") == contract


def test_one_contract_id_may_not_answer_two_different_tables() -> None:
    declare(_named("first_table", "shared@1"))

    with pytest.raises(ContractError, match="already bound to a declaration that differs in"):
        declare(_named("second_table", "shared@1"))


# --- the batch-id sentinel -------------------------------------------------------------


def test_require_batch_id_refuses_the_default_the_job_resource_ships() -> None:
    resource = job_resource(_contract())
    default = resource["resources"]["jobs"]["incidents"]["parameters"][0]["default"]  # type: ignore[index,call-overload]

    assert default == SENTINEL_BATCH_ID
    with pytest.raises(ContractError, match="still the job parameter's default"):
        contracts.require_batch_id(SENTINEL_BATCH_ID)


def test_require_batch_id_refuses_an_empty_batch_id_and_returns_any_other() -> None:
    with pytest.raises(ContractError, match="empty"):
        contracts.require_batch_id("")

    assert contracts.require_batch_id("2026-08-24T00:00:00Z") == "2026-08-24T00:00:00Z"


# --- the plan --------------------------------------------------------------------------


def test_the_plan_carries_the_declaration_and_not_an_invention() -> None:
    contract = _named("planned", "planned@1")
    plan = declare(contract)

    assert plan.schema == AUDIT_SCHEMA
    assert plan.rules == contract.constraints
    assert plan.quarantine["table"] == contract.quarantine
    assert plan.promotion["source"] == contract.staging
    assert plan.promotion["target"] == contract.bronze
    assert plan.promotion["mode"] == "append"
    assert plan.promotion["on_rule_error"] == "quarantine"
    assert plan.job_yaml == job_yaml(contract)


# --- the reader's refusals -------------------------------------------------------------


def test_a_quoted_key_containing_a_colon_is_not_cut_in_half() -> None:
    assert load_job_yaml("'a: b': 'v'\n") == {"a: b": "v"}


def test_a_quoted_value_containing_a_colon_survives() -> None:
    assert load_job_yaml("k: 'a: b'\n") == {"k": "a: b"}


def test_a_sequence_of_scalars_round_trips() -> None:
    assert load_job_yaml("k:\n  - 'one'\n  - 'two'\n") == {"k": ["one", "two"]}


@pytest.mark.parametrize(
    ("document", "message"),
    (
        ("", "empty document"),
        ("k: 'v'\nleftover\n", "not a mapping entry"),
        ("'abc\n", "unterminated quoted scalar"),
        ("'k' 'v'\n", "not followed by a colon"),
        ("k:\n", "opens a block"),
        ("k:\nj: 'v'\n", "opens a block"),
    ),
    ids=(
        "empty",
        "no-colon",
        "unterminated",
        "quoted-key-no-colon",
        "dangling",
        "dangling-sibling",
    ),
)
def test_the_reader_refuses_what_this_module_cannot_have_emitted(
    document: str, message: str
) -> None:
    with pytest.raises(ContractError, match=message):
        load_job_yaml(document)


def test_trailing_content_below_the_document_is_refused() -> None:
    with pytest.raises(ContractError, match="trailing content"):
        load_job_yaml("k:\n  - 'one'\n- 'two'\n")


@pytest.mark.parametrize(
    "node",
    ({}, [], {"k": {}}),
    ids=("empty-mapping", "empty-sequence", "empty-nested"),
)
def test_the_emitter_refuses_a_container_with_no_round_trip(node: object) -> None:
    #  used to take , so it also needed a branch refusing a bare scalar --
    # a case reachable only by a caller mypy already rejects. Narrowing the parameter to
    #  deleted the branch and this test's fourth case with it.
    with pytest.raises(ContractError, match="empty mapping or sequence"):
        contracts._emit(node, 0)  # type: ignore[arg-type]


# --- what the review raised, each measured before it was fixed -------------------------

UNEMITTABLE = (
    "\x00",
    "\n",
    "\r",
    "\t",
    "\x7f",
    "\x85",
    "\x9f",
    "\u2028",
    "\u2029",
    "\ud800",
    "\ufffe",
    "\uffff",
)


def test_a_declaration_declare_refused_is_not_findable_through_register() -> None:
    """`declare` raising while `register` answers is a refusal that refuses nothing.

    The registry was assigned before `job_yaml` ran, so a declaration carrying a character
    with no one-line YAML scalar was rejected and registered in the same call. Measured on
    the module as it stood: `declare` raised, and `register('leaky@1').name` then returned
    'leaky'.
    """
    contract = _named("leaky", "leaky@1", staging="main.staging\nleaky")

    with pytest.raises(ContractError, match="no one-line YAML scalar"):
        declare(contract)

    with pytest.raises(ContractError, match="unknown contract"):
        register("leaky@1")


@pytest.mark.parametrize("character", UNEMITTABLE, ids=[f"U+{ord(c):04X}" for c in UNEMITTABLE])
def test_a_character_with_no_one_line_scalar_is_refused_rather_than_emitted(
    character: str,
) -> None:
    contract = _named("incidents", "incidents@1", staging="main.staging" + character)

    with pytest.raises(ContractError, match="no one-line YAML scalar"):
        job_yaml(contract)


def test_the_guard_asks_a_category_because_a_code_point_range_missed_the_c1_block() -> None:
    """What the range let through, measured rather than argued.

    `ord(c) < 0x20 or ord(c) == 0x7F` stood in  and admits U+0080..U+009F. Held against
    PyYAML 6: U+0085 comes back as a DIFFERENT string, and U+009F makes the reader raise.
    Both are category `Cc`, which is what the guard asks for now.
    """
    assert unicodedata.category("\x85") == "Cc"
    assert not (ord("\x85") < 0x20 or ord("\x85") == 0x7F)
    assert yaml.safe_load("k: '\x85'") != {"k": "\x85"}

    with pytest.raises(yaml.YAMLError):
        yaml.safe_load("k: '\x9f'")


def test_the_line_separators_are_refused_for_a_parser_that_is_not_the_referee() -> None:
    """The half of that finding measurement REFUTES, kept because the reason is different.

    U+2028 and U+2029 are category Zl and Zp, not Cc, and PyYAML 6 round trips both
    unchanged -- so "they prevent the round trip" is false as measured here. YAML 1.1
    section 4.1 does list them as line breaks and the parser that reads a bundle is not
    PyYAML, which is the same reason `y` and `n` stay in RESERVED_PLAIN_WORDS.
    """
    for separator in YAML_LINE_SEPARATORS:
        assert unicodedata.category(separator) in ("Zl", "Zp")
        assert yaml.safe_load("k: '" + separator + "'") == {"k": separator}


@pytest.mark.parametrize(
    "document",
    ("k: 'unterminated\n", "k: bare\n", "k: 'a' trailing\n"),
    ids=("unterminated", "bare", "trailing"),
)
def test_a_value_this_module_could_not_have_emitted_is_refused_and_not_read(
    document: str,
) -> None:
    # `_unquote` alone answered "'unterminated" for the first of these: it strips only when
    # BOTH ends are quotes, so a half-quoted token came back as data.
    with pytest.raises(ContractError):
        load_job_yaml(document)


# --- what the second review round raised, all of it measured first ---------------------


def test_the_marker_and_the_indent_are_one_number_and_not_two() -> None:
    """`INDENT` reads like configuration and is not.

    `_emit_sequence` writes `SEQUENCE_MARKER` and its children go at `indent + INDENT`, so
    the children only line up under the text after the dash while the two are equal.
    Measured at INDENT=3 and INDENT=4: this module's own reader still round trips and
    PyYAML raises ParserError -- the exact single-parser split the module exists to avoid.
    """
    assert contracts.SEQUENCE_MARKER == "- "
    assert len(contracts.SEQUENCE_MARKER) == INDENT
    assert contracts.NONCHARACTERS == ("\ufffe", "\uffff")
    assert contracts.MAX_SIMPLE_KEY == 1024


def test_a_sequence_entry_indented_by_anything_else_is_refused_and_does_not_hang() -> None:
    """One extra space after the dash used to be an unbounded loop.

    `_read` answers 0 when the line it is handed does not sit at the indent it was called
    with. `_read_sequence` then did `index += 0`, re-read the same line and appended to
    `out` forever: measured at roughly 1.2 million calls in three seconds on a two-line
    document, so unbounded memory rather than a spin. PyYAML reads both of these fine,
    which is what made it a divergence rather than merely a hang.

    The guard is on `consumed == 0` rather than on the space, because the defect is a loop
    that can fail to advance and the space is only the instance that reaches it.
    """
    for document in ("-  'a'\n", "k:\n  -  'a'\n"):
        with pytest.raises(ContractError, match="not indented by"):
            load_job_yaml(document)


@pytest.mark.parametrize(
    "document",
    ("on: 'v'\n", "null: 'v'\n", "yes: 'v'\n", "123: 'v'\n", "2026-08-23: 'v'\n"),
    ids=("on", "null", "yes", "int", "date"),
)
def test_a_bare_key_this_module_would_have_quoted_is_refused_by_the_reader(
    document: str,
) -> None:
    """The emitter quotes these keys so the two parsers agree; the reader reopened it.

    Measured before `_read_key` existed: `load_job_yaml("on: 'v'")` answered `{'on': 'v'}`
    where PyYAML answers `{True: 'v'}`, and the same for `null`, `yes`, `123` and a date.
    Closing it on the value side with `_scalar` and leaving the key side open made the
    reader wider than the emitter in exactly the place `RESERVED_PLAIN_WORDS` exists.
    """
    with pytest.raises(ContractError, match="would emit bare"):
        load_job_yaml(document)


def test_the_quoted_form_of_those_same_keys_is_what_the_reader_accepts() -> None:
    # The control arm for the test above: without it, that one is equally green for a
    # reader that refuses every key.
    assert load_job_yaml("'on': 'v'\n") == {"on": "v"}
    assert load_job_yaml("'2026-08-23': 'v'\n") == {"2026-08-23": "v"}


def test_a_byte_order_mark_is_stripped_rather_than_read_as_part_of_the_first_key() -> None:
    """A BOM is something a file acquires on the way to disk, not something we emit.

    Measured before `load_job_yaml` normalised: a document written with
    `encoding="utf-8-sig"` and read back plainly gave a top-level key of `'\ufeffresources'`
    with no exception -- a structurally valid mapping that is simply the wrong one, which
    is the silent-mis-parse case rather than a refusal.
    """
    contract = _contract()
    text = job_yaml(contract)

    assert load_job_yaml("\ufeff" + text) == job_resource(contract)
    assert load_job_yaml(text.replace("\n", "\r\n")) == job_resource(contract)
    assert load_job_yaml("\ufeff" + text.replace("\n", "\r\n")) == job_resource(contract)


@pytest.mark.parametrize(("length", "refused"), ((1023, False), (1024, False), (1025, True)))
def test_a_table_name_past_yamls_simple_key_bound_is_refused(length: int, refused: bool) -> None:
    """YAML bounds a simple key at 1024 characters and this module emits `name` as a key.

    Measured against PyYAML 6: 1024 round trips, 1025 raises ScannerError while this
    module's own reader reads it back happily. A VALUE of 5000 characters is fine on both
    sides, so the bound belongs on the key token and nowhere else.
    """
    contract = _named("a" * length, "long@1")

    if refused:
        with pytest.raises(ContractError, match="simple key"):
            job_yaml(contract)
        return

    text = job_yaml(contract)
    assert yaml.safe_load(text) == job_resource(contract)
    assert load_job_yaml(text) == job_resource(contract)


def test_the_conflict_message_names_the_field_that_differs() -> None:
    # It used to interpolate `already.name`, so the common case -- same table, one field
    # edited -- read "is already bound to table 'incidents'" and sounded like a no-op.
    declare(_named("same_name", "conflict@1"))

    with pytest.raises(ContractError, match="differs in staging"):
        declare(_named("same_name", "conflict@1", staging="other.staging.same_name"))


def test_the_registry_is_isolated_between_unit_tests() -> None:
    """What `tests/unit/conftest.py` buys, asserted rather than assumed.

    `test_one_contract_id_may_not_answer_two_different_tables` above binds `shared@1`.
    Without the autouse fixture it is still bound here -- measured, `register("shared@1")`
    answered `first_table` for the rest of the session.
    """
    assert contracts._REGISTRY == {}

    with pytest.raises(ContractError, match="unknown contract"):
        register("shared@1")
