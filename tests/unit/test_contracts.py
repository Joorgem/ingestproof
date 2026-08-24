"""Unit ring for `ingestproof.contracts`.

The frozen acceptance test judges the criterion; this file judges the parts of the module
the criterion does not reach -- the module-level constants, the reader's refusals, and the
quoting rule, which has a control arm because a rule against a hazard that does not exist
is green forever and proves nothing.

mutmut 3 mutates INSIDE functions only, so every module-level constant here gets an
assertion on its VALUE. Without one the mutation gate is silently inert on it.
"""

from __future__ import annotations

import datetime

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
    name = fields["name"]
    assert isinstance(name, str)
    fields.setdefault("prefix", name + "_")
    return TableContract(**fields)  # type: ignore[arg-type]


def _named(name: str, contract_id: str, **overrides: object) -> TableContract:
    return _contract(
        name=name,
        contract_id=contract_id,
        staging=f"main.staging.{name}",
        bronze=f"main.bronze.{name}",
        quarantine=f"main.quarantine.{name}",
        prefix=name + "_",
        **overrides,
    )


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

    with pytest.raises(ContractError, match="already bound"):
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
    ("node", "message"),
    (
        ("scalar", "emitted by its parent"),
        ({}, "empty mapping or sequence"),
        ([], "empty mapping or sequence"),
        ({"k": {}}, "empty mapping or sequence"),
    ),
    ids=("bare-scalar", "empty-mapping", "empty-sequence", "empty-nested"),
)
def test_the_emitter_refuses_what_has_no_round_trip(node: object, message: str) -> None:
    with pytest.raises(ContractError, match=message):
        contracts._emit(node, 0)  # type: ignore[arg-type]
