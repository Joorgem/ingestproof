"""The partition is total, and fail-closed for every fate a rule can meet.

The frozen acceptance file fixes one four-record batch with one rule. This states the
partition over arbitrary mixes of the four fates and any number of rules: which side each
record lands on, in which order, and what reason each rejection carries.

WHAT IT CANNOT CATCH, said here because the first version of this docstring called itself
"a complete specification rather than a disjunction that an under-strict implementation
could satisfy". It is not, and it was measured saying so. With a single rule drawn, an
implementation iterating `rules[:1]` -- which refuses strictly LESS, because a record only
a later rule would stop is promoted -- passed this file; the only test that killed it was
a unit test. Rules are drawn 1..3 now, which closes that instance. What remains outside it
is anything the fates cannot express: `Batch.batch_id` is asserted below for that reason,
but the plan's shape, the refusals from `quality_rules` and `require_batch_id`, and the
container guards are all pinned in the unit ring and nowhere here.

FOUR FATES, because a rule meeting a record can do four things and only the first
promotes: say yes, say no, raise on the way in, or return a verdict whose truthiness
raises. The last two are the same thing from outside the call, and both are quarantine --
that is what fail-closed means here, and treating either as "passes" would put a record
nothing vouched for into what a bronze table would hold.

THE `ci` PROFILE FIXES THE SEED, NOT THE CORPUS -- in general. `derandomize=True` makes
the seed a hash of this function's cleaned source, while Hypothesis 6.165 also harvests
string constants out of the local modules a session has imported and injects them into
strategies, so a corpus can depend on the import scope. Measured last turn on a property
that draws TEXT: two fingerprints, and a mutant it killed alone survived under `uv run
pytest`. It does not apply here and the pins do not rest on it: this file draws only
`sampled_from` over a fixed tuple and integers, so no harvested string can reach it, and
the corpus is byte-identical in both scopes -- measured. The pins are here for branch
coverage, and the mutants were re-measured in the full ring regardless.

`@example` decorators are stripped by `_clean_source` before the digest, so a pin costs no
re-draw. Editing a statement in the function below does.

[utest->req~ac-09~1]
"""

from __future__ import annotations

from hypothesis import example, given
from hypothesis import strategies as st

from ingestproof.promotion import comparison_target, partition_batch

BATCH = "2026-08-24T00:00:00Z"

FATE = st.sampled_from(("pass", "reject", "raise", "unbooleanable"))

# What each fate must produce in `Rejection.error`: None when the rule ran and said no,
# and the exception's type name when it could not be evaluated at all.
ERROR_OF = {"reject": None, "raise": "KeyError", "unbooleanable": "RuntimeError"}


class _Unbooleanable:
    def __bool__(self) -> bool:
        raise RuntimeError("this verdict cannot be read")


def _rule(index: int, fates: list[str]) -> tuple[str, object]:
    """Rule `index` decides only the records whose fate list names it, and passes the rest.

    A record's fate is `fates[n]` and the rule that carries it out is the one at position
    `n % rule_count`, so with more than one rule the deciding rule is spread across the
    set -- which is what makes FIRST-STOP-WINS visible to a property that would otherwise
    only ever see rule zero. Measured: `rules[:1]` used to survive this file and now dies
    in it.

    The ORDER rules are evaluated in is still invisible here, and that is a consequence of
    this construction rather than an oversight: exactly one rule decides each record and
    every other rule passes it, so `reversed(rules)` produces the same partition --
    measured, it survives this file and dies only in the unit ring.
    """

    def evaluate(record: dict[str, int]) -> object:
        position = record["n"]
        if position % record["rules"] != index:
            return True
        fate = fates[position]
        if fate == "pass":
            return True
        if fate == "reject":
            return False
        if fate == "raise":
            raise KeyError("this record cannot be read")
        return _Unbooleanable()

    return (f"rule_{index}", evaluate)


@example(fates=[], rule_count=1)
@example(fates=["pass", "reject", "raise", "unbooleanable"], rule_count=1)
@example(fates=["unbooleanable", "raise", "reject", "pass"], rule_count=3)
@example(fates=["raise"], rule_count=2)
@example(fates=["reject", "pass", "reject", "pass"], rule_count=2)
@given(fates=st.lists(FATE, max_size=8), rule_count=st.integers(min_value=1, max_value=3))
def test_every_record_lands_where_its_fate_says_and_the_target_loses_none(
    fates: list[str], rule_count: int
) -> None:
    records = [{"n": index, "rules": rule_count} for index in range(len(fates))]
    rules = [_rule(index, fates) for index in range(rule_count)]

    batch = partition_batch(records, rules, batch_id=BATCH)

    promoted = [index for index, fate in enumerate(fates) if fate == "pass"]
    quarantined = [index for index, fate in enumerate(fates) if fate != "pass"]

    # Which side, and in which order. Order within a side is declaration order.
    assert [record["n"] for record in batch.promote] == promoted
    assert [record["n"] for record in batch.quarantine] == quarantined

    # Fail-closed, stated per record rather than in aggregate: the reason distinguishes a
    # rule that said no from one that could not be evaluated. And the rule NAMED is the
    # one that decided, which is what makes a multi-rule set worth drawing.
    assert [rejection.error for rejection in batch.rejections] == [
        ERROR_OF[fates[index]] for index in quarantined
    ]
    assert [rejection.rule for rejection in batch.rejections] == [
        f"rule_{index % rule_count}" for index in quarantined
    ]

    # The batch id is carried rather than invented.
    assert batch.batch_id == BATCH

    # The target loses nothing and invents nothing -- the criterion in one line.
    target = comparison_target(batch)
    assert sorted(record["n"] for record in target) == list(range(len(fates)))
    assert len(target) == len(records)

    # The caller's records come back as the SAME objects, not copies of them.
    assert all(any(record is original for original in records) for record in target)
