"""The partition is total, and fail-closed for every fate a rule can meet.

The frozen acceptance file fixes one four-record batch with one rule. This states the
whole function over arbitrary mixes: which side each record lands on, in which order, and
what reason each rejection carries -- so it is a complete specification rather than a
disjunction that an under-strict implementation could satisfy by refusing nothing.

FOUR FATES, because a rule meeting a record can do four things and only the first
promotes: say yes, say no, raise on the way in, or return a verdict whose truthiness
raises. The last two are the same thing from outside the call, and both are quarantine --
that is what fail-closed means here, and treating either as "passes" would put a record
nothing vouched for into the bronze table the fidelity check compares against.

THE `ci` PROFILE FIXES THE SEED, NOT THE CORPUS. `derandomize=True` makes the seed a hash
of this function's cleaned source, but Hypothesis 6.165 also harvests string constants out
of the local modules a session has imported, so the drawn corpus depends on the import
scope. Measured last turn: a mutant this kind of property killed when its file ran alone
survived it under `uv run pytest`, which is what CI runs. The pins below are therefore
chosen to reach every branch deterministically, and the mutants were re-measured in the
full ring rather than in this file alone.

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


@example(fates=[])
@example(fates=["pass", "reject", "raise", "unbooleanable"])
@example(fates=["unbooleanable", "raise", "reject", "pass"])
@example(fates=["raise"])
@given(fates=st.lists(FATE, max_size=8))
def test_every_record_lands_where_its_fate_says_and_the_target_loses_none(
    fates: list[str],
) -> None:
    records = [{"n": index} for index in range(len(fates))]

    def evaluate(record: dict[str, int]) -> object:
        fate = fates[record["n"]]
        if fate == "pass":
            return True
        if fate == "reject":
            return False
        if fate == "raise":
            raise KeyError("this record cannot be read")
        return _Unbooleanable()

    batch = partition_batch(records, [("fate", evaluate)], batch_id=BATCH)

    promoted = [index for index, fate in enumerate(fates) if fate == "pass"]
    quarantined = [index for index, fate in enumerate(fates) if fate != "pass"]

    # Which side, and in which order. Order within a side is declaration order.
    assert [record["n"] for record in batch.promote] == promoted
    assert [record["n"] for record in batch.quarantine] == quarantined

    # Fail-closed, stated per record rather than in aggregate: the reason distinguishes a
    # rule that said no from one that could not be evaluated.
    assert [rejection.error for rejection in batch.rejections] == [
        ERROR_OF[fates[index]] for index in quarantined
    ]
    assert {rejection.rule for rejection in batch.rejections} <= {"fate"}

    # The target loses nothing and invents nothing -- the criterion in one line.
    target = comparison_target(batch)
    assert sorted(record["n"] for record in target) == list(range(len(fates)))
    assert len(target) == len(records)

    # The caller's records come back as the SAME objects, not copies of them.
    assert all(any(record is original for original in records) for record in target)
