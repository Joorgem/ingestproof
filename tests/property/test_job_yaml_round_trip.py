"""The job-resource round trip, over declarations nobody wrote by hand.

The acceptance test round trips ONE declaration through two parsers. This file does it
over arbitrary ones, which is where the quoting rule is actually exercised: `on`, a date,
an apostrophe and a colon are all things a table name may contain and none of them appear
in a fixture anyone would think to write.

Two parsers here as well, and for the same reason. `load_job_yaml(job_yaml(c)) ==
job_resource(c)` alone is green for an emitter and a reader that share one misconception;
PyYAML is the referee that does not share it.

The `ci` Hypothesis profile is derandomised and the seed is a hash of this test's cleaned
source, so editing the body below re-draws its whole corpus. `@example` decorators are
stripped before hashing and are the safe way to pin a counterexample.

[utest->req~ac-01~1]
"""

from __future__ import annotations

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from ingestproof.contracts import (
    ContractError,
    TableContract,
    job_resource,
    job_yaml,
    load_job_yaml,
)

# Everything a one-line YAML scalar can hold, which is everything `_quote` does not
# refuse. `Cc` is the control characters -- a newline inside a single-quoted scalar folds
# into a space and would round trip through a DIFFERENT string. `Zl` and `Zp` are U+2028
# and U+2029, which YAML 1.1 section 4.1 lists as line breaks; PyYAML 6 does NOT treat
# them as such, measured, so they are excluded here for the parser that reads a bundle
# rather than for the one refereeing below. `Cs` is the surrogates, which are not
# encodable and would fail before any of this.
SCALAR = st.text(st.characters(exclude_categories=("Cc", "Cs", "Zl", "Zp")), max_size=24)


@given(
    name=SCALAR,
    contract_id=SCALAR,
    staging=SCALAR,
    bronze=SCALAR,
    quarantine=SCALAR,
)
def test_any_declaration_round_trips_through_this_module_and_through_pyyaml(
    name: str, contract_id: str, staging: str, bronze: str, quarantine: str
) -> None:
    contract = TableContract(
        name=name,
        contract_id=contract_id,
        staging=staging,
        bronze=bronze,
        quarantine=quarantine,
        landing_mode="append",
        prefix=name + "_",
        constraints=(),
    )
    resource = job_resource(contract)
    text = job_yaml(contract)

    assert load_job_yaml(text) == resource
    assert yaml.safe_load(text) == resource


@given(control=st.sampled_from(["\n", "\r", "\t", "\x00", "\x7f"]))
def test_a_declaration_carrying_a_control_character_is_refused_rather_than_folded(
    control: str,
) -> None:
    contract = TableContract(
        name="incidents",
        contract_id="incidents@1",
        staging=f"main.staging{control}incidents",
        bronze="main.bronze.incidents",
        quarantine="main.quarantine.incidents",
        landing_mode="append",
        prefix="incidents_",
        constraints=(),
    )

    with pytest.raises(ContractError, match="control character"):
        job_yaml(contract)
