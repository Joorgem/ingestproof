"""req~ac-01~1 -- a new table enters through one declaration.

RED TODAY, AND DELIBERATELY SO. `ingestproof.contracts` does not exist: this file is the
frozen half of the closing rule for P1 items 1, 2 and 5, and `tests/acceptance/**` is
frozen precisely so the turn that writes the library cannot also write the test that
judges it.

How a turn observes the transition, which is signal 2 of the closing rule in TASKS.md:

    uv run pytest tests/acceptance/test_ac01_one_declaration.py --runxfail

`--runxfail` makes the marker below inert and reports the real failure. Without it the
whole file reports `xfailed` and CI stays green, which is the only way a test for an
unwritten feature can sit in a repository whose CI is the authoritative gate.

The marker is CONDITIONAL and STRICT, and both halves earn their place. Conditional: the
moment `ingestproof.contracts` imports, the marker evaporates and CI runs these for real,
so nobody has to remember to remove it -- and nobody could, because this file is frozen.
Strict: if one of these passes while the module is still missing, it is passing for a
reason that has nothing to do with the criterion, and that is reported as a failure.

Every import of `ingestproof.contracts` is INSIDE a test function. At module level a
missing module is a collection error, and a collection error is red in CI no matter what
this marker says.

The names used below are the contract this file freezes. P1 builds to them.

[utest->req~ac-01~1]
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

MISSING = importlib.util.find_spec("ingestproof.contracts") is None

pytestmark = pytest.mark.xfail(
    MISSING,
    strict=True,
    reason="P1 items 1, 2 and 5 have not landed: ingestproof.contracts does not exist",
)


def _one_declaration():
    """The single declaration the criterion is about, with the fields TASKS item 1 names.

    Deliberately domain-free. The flagship's registry.py is where this was generalised
    from, and no CNPJ vocabulary may travel with it.
    """
    from ingestproof.contracts import TableContract

    return TableContract(
        name="incidents",
        contract_id="incidents@1",
        staging="main.staging.incidents",
        bronze="main.bronze.incidents",
        quarantine="main.quarantine.incidents",
        landing_mode="append",
        prefix="incidents_",
        constraints=(("id_not_null", "id IS NOT NULL"),),
    )


def test_the_declaration_carries_every_field_the_queue_names() -> None:
    contract = _one_declaration()

    assert contract.name == "incidents"
    assert contract.contract_id == "incidents@1"
    assert (contract.staging, contract.bronze, contract.quarantine) == (
        "main.staging.incidents",
        "main.bronze.incidents",
        "main.quarantine.incidents",
    )
    assert contract.landing_mode == "append"
    assert contract.prefix == "incidents_"
    assert contract.constraints == (("id_not_null", "id IS NOT NULL"),)


def test_the_declaration_is_immutable() -> None:
    # A declaration a caller can mutate is a contract that changes after it was agreed,
    # and the registry would then hold a different table than the one it validated.
    from ingestproof.contracts import TableContract

    contract = _one_declaration()

    with pytest.raises((AttributeError, TypeError)):
        contract.name = "something else"

    assert isinstance(contract, TableContract)


def test_one_declaration_comes_out_with_all_five_artefacts() -> None:
    """The criterion's own list: schema, rules, quarantine, promotion and a job YAML.

    Non-empty is all this asserts, and that is the point: WHICH schema and WHICH rules are
    the library's business, and pinning them here would freeze P1's internals from outside.
    That one declaration produces all five is the criterion.
    """
    from ingestproof.contracts import declare

    plan = declare(_one_declaration())

    assert plan.schema
    assert plan.rules
    assert plan.quarantine
    assert plan.promotion
    assert plan.job_yaml


def test_the_job_yaml_round_trips_through_the_resource_mapping() -> None:
    """TASKS item 5: one declaration in, a bundle resource out.

    TWO PARSERS, AND THAT IS THE WHOLE OF IT. `load_job_yaml` is the library's own reader,
    so `load_job_yaml(job_yaml(c)) == job_resource(c)` asserts only that the library
    inverts itself -- measured green with `job_yaml = repr` and `load_job_yaml =
    ast.literal_eval`, an emitter producing something no bundle could read. This
    repository's founding measurement is that a single-parser check cannot detect a
    single-parser defect, and that check was one.

    PyYAML is in the `dev` group for this assertion and nothing else. It is not a runtime
    dependency and the published wheel does not gain one. What it establishes is
    conformance to YAML; it is not the parser the Databricks CLI uses, so a green here is
    not a proof that the CLI accepts the file.

    It does pin one thing about `job_resource`: its values have to be YAML-native, because
    a sequence comes back from any YAML parser as a list and never as the tuple the
    declaration carried.

    The counterexample is not caught by its name, so do not read this as "not written by
    repr". Measured: `repr` of a mapping of strings, lists and dicts IS valid YAML flow
    syntax and PyYAML reads it back unchanged. What PyYAML refuses is a repr carrying
    anything Python-only -- a tuple, a `None`, a string needing a backslash escape.
    """
    from ingestproof.contracts import job_resource, job_yaml, load_job_yaml

    contract = _one_declaration()
    text = job_yaml(contract)
    resource = job_resource(contract)

    assert isinstance(text, str)
    assert load_job_yaml(text) == resource
    assert yaml.safe_load(text) == resource


def _import_source(tmp_path: Path, source: str) -> None:
    """Execute `source` as a module, the way an import would.

    TASKS item 2 says each guard refuses AT IMPORT, not at call. The mechanical difference
    is whether the exception comes out of `exec_module` -- executing the module body -- or
    only later, when something calls into it. Running the body is the whole test; a guard
    that fires on first use would let a malformed declaration sit in a repository until
    someone happened to touch it.
    """
    path = tmp_path / "declaration_under_test.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("declaration_under_test", path)

    assert spec is not None and spec.loader is not None

    spec.loader.exec_module(importlib.util.module_from_spec(spec))


# THE PREFIX RULE, SAID ONCE. It is implied by the three sources below read together with
# `_one_declaration` above, and a rule a reader has to derive from four places at once is
# not a contract -- it is a guess that happens to be right.
#
# No fixture in this file supplies any file groups, so the prefix guard has nothing to
# check a prefix AGAINST except the declaration's own `name`. What the four cases require:
# `incidents`/`incidents_` passes; `jobless`/`jobless_` passes, so that the landing-mode
# guard is what fires for that case and not this one; `orphan`/`matches_nothing_` raises
# ContractError. `prefix == name + "_"` gives all three, and it is what P1 should write
# unless it can name another rule that does.
PREAMBLE = "from ingestproof.contracts import TableContract, declare, register\n"

UNKNOWN_CONTRACT = PREAMBLE + 'register("no-such-contract-id")\n'

PREFIX_MATCHES_NO_FILE_GROUP = PREAMBLE + (
    'declare(TableContract(name="orphan", contract_id="orphan@1",\n'
    '                      staging="main.staging.orphan", bronze="main.bronze.orphan",\n'
    '                      quarantine="main.quarantine.orphan", landing_mode="append",\n'
    '                      prefix="matches_nothing_", constraints=()))\n'
)

TABLE_WITH_NO_JOB = PREAMBLE + (
    'declare(TableContract(name="jobless", contract_id="jobless@1",\n'
    '                      staging="main.staging.jobless", bronze="main.bronze.jobless",\n'
    '                      quarantine="main.quarantine.jobless", landing_mode=None,\n'
    '                      prefix="jobless_", constraints=()))\n'
)


@pytest.mark.parametrize(
    "source",
    (UNKNOWN_CONTRACT, PREFIX_MATCHES_NO_FILE_GROUP, TABLE_WITH_NO_JOB),
    # Named, because the default id is the whole module source and the test id is what a
    # turn reads to see WHICH refusal is still missing.
    ids=("unknown-contract", "prefix-matches-no-file-group", "table-with-no-job"),
)
def test_each_guard_refuses_while_the_module_body_is_running(
    tmp_path: Path, source: str
) -> None:
    from ingestproof.contracts import ContractError

    with pytest.raises(ContractError):
        _import_source(tmp_path, source)
