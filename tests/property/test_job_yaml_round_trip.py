"""The job-resource round trip, over declarations nobody wrote by hand.

The acceptance test round trips ONE declaration through two parsers. This file does it
over arbitrary ones, which puts the quoting rule against inputs no fixture enumerates.

Two parsers here as well, and for the same reason. `load_job_yaml(job_yaml(c)) ==
job_resource(c)` alone is green for an emitter and a reader that share one misconception;
PyYAML is the referee that does not share it.

The `ci` Hypothesis profile is derandomised, so a test function's corpus is fixed by its
own source: `function_digest` hashes `_clean_source(inspect.getsource(fn))`. Measured on
hypothesis 6.165.10 -- adding a comment, a blank line or an `@example(...)` decorator
leaves the digest unchanged, and changing a statement or the function's name changes it.
A module-level strategy is NOT in that digest, but editing one still re-draws the corpus,
because the alphabet the draws come from is different.

[utest->req~ac-01~1]
"""

from __future__ import annotations

import pytest
import yaml
from hypothesis import example, given
from hypothesis import strategies as st

from ingestproof.contracts import (
    ContractError,
    TableContract,
    job_resource,
    job_yaml,
    load_job_yaml,
)

# What `_quote` accepts, so that the round trip below is a round trip and not a refusal.
# `Cc` is the control characters -- a newline inside a single-quoted scalar folds into a
# space and would round trip through a DIFFERENT string. `Zl` and `Zp` are U+2028 and
# U+2029, which YAML 1.1 lists as line breaks; PyYAML 6 does NOT treat them as such,
# measured, so they are excluded here for the parser that reads a bundle rather than for
# the one refereeing below. `Cs` is the surrogates and U+FFFE/U+FFFF are non-characters:
# both sit outside YAML's printable set, and PyYAML's reader refuses a document carrying
# either -- measured, and not a claim about encoding, since nothing here encodes anything.
SCALAR = st.text(
    st.characters(exclude_categories=("Cc", "Cs", "Zl", "Zp"), exclude_characters="\ufffe\uffff"),
    max_size=24,
)


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


@example(character="\ufffe")
@example(character="\uffff")
@example(character="\ud800")
@example(character="\ufdd0")
@example(character="\x85")
@example(character="\u2028")
@given(character=st.characters())
def test_every_character_is_either_refused_or_agreed_on_by_pyyaml(character: str) -> None:
    """For any character, the emitter refuses the declaration or PyYAML agrees with it.

    THE PINS ARE WHAT MAKE THIS BITE, AND THE DRAWS DO NOT. Measured against the module
    that emitted U+FFFE: with `@given` alone this test PASSED -- the `ci` profile draws
    200 examples out of 1.1 million code points and will not find two of them. Written
    that way it would have been a property that reads like a guarantee and holds nothing,
    which is the shape this repository keeps finding. With the six `@example` pins it goes
    red against that same module, on the surrogate -- Hypothesis runs pins in the reverse
    of the order they are written, so the one that fires first is not the one listed first.

    So what the `@given` half buys is not discovery; it is the frame that makes the next
    pin a one-line addition, and `_clean_source` strips decorators, so adding one does not
    re-draw the corpus.

    The six are one per class the guard has to get right: the two non-characters and a
    surrogate, which PyYAML's reader refuses; U+FDD0, which is also a non-character and
    which PyYAML reads back UNCHANGED, so it is the control arm against over-refusing;
    U+0085, which PyYAML accepts and folds; and U+2028, which PyYAML round trips and this
    module refuses anyway for a parser that is not PyYAML.

    It cannot pass vacuously by refusing everything: the round trip above is what proves
    acceptance happens, over 200 declarations of five fields each.
    """
    contract = TableContract(
        name="incidents",
        contract_id="incidents@1",
        staging=f"main.staging{character}incidents",
        bronze="main.bronze.incidents",
        quarantine="main.quarantine.incidents",
        landing_mode="append",
        prefix="incidents_",
        constraints=(),
    )

    try:
        text = job_yaml(contract)
    except ContractError:
        return

    assert yaml.safe_load(text) == job_resource(contract)
    assert load_job_yaml(text) == job_resource(contract)


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
