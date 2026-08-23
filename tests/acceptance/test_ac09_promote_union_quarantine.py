"""req~ac-09~1 -- the comparison target is promote union quarantine, for one `_batch_id`.

RED TODAY. `ingestproof.promotion` does not exist. Run it on demand with:

    uv run pytest tests/acceptance/test_ac09_promote_union_quarantine.py --runxfail

The measured defect this criterion exists to prevent (docs/measurements.md section 0, and
the design's section on what the research killed): comparing the source against the LANDED
bronze table gives about 1% false positives with zero real damage, because bronze is the
parse MINUS what the quality gate rejected. Every quarantined record reads as damage.

What this file asserts is the comparison TARGET, which is what P1 item 4 owns: that
promote and quarantine partition one batch, that the target is their union, and that a
record the gate rejected is inside the target rather than reported as loss. The
differential that consumes the target is a later item, and asserting its output here would
be a test of code no queue item builds.

[utest->req~ac-09~1]
"""
from __future__ import annotations

import importlib.util

import pytest

MISSING = importlib.util.find_spec("ingestproof.promotion") is None

pytestmark = pytest.mark.xfail(
    MISSING,
    strict=True,
    reason="P1 item 4 has not landed: ingestproof.promotion does not exist",
)

BATCH_ID = "2026-08-23T00:00:00Z"

# Four parsed records and one rule. `id` 3 is what the gate REJECTS; `id` 4 is what the
# gate CANNOT EVALUATE -- it has no `name` key and the rule subscripts it, so evaluating
# the rule raises.
#
# The subscript is the whole of it. This rule was `record.get("name") is not None`, and
# `.get` answers None rather than raising: there was no unevaluable state for an
# implementation to mishandle, and all five tests below passed against a `partition_batch`
# that is `all(fn(record) for _name, fn in rules)` with no exception handling at all.
# Measured. A test for fail-closed that cannot tell fail-closed from fail-open is the
# defect this repository exists to catch, one layer up.
RECORDS = (
    {"id": "1", "name": "ok"},
    {"id": "2", "name": "also ok"},
    {"id": "3", "name": None},
    {"id": "4"},
)

RULES = (("name_not_null", lambda record: record["name"] is not None),)


def _partition():
    from ingestproof.promotion import partition_batch

    return partition_batch(RECORDS, RULES, batch_id=BATCH_ID)


def test_every_record_lands_on_exactly_one_side() -> None:
    batch = _partition()
    promoted = [r["id"] for r in batch.promote]
    quarantined = [r["id"] for r in batch.quarantine]

    assert sorted(promoted + quarantined) == ["1", "2", "3", "4"]
    assert set(promoted).isdisjoint(quarantined)


def test_the_gate_rejects_into_quarantine_and_not_into_loss() -> None:
    batch = _partition()

    assert [r["id"] for r in batch.promote] == ["1", "2"]
    assert sorted(r["id"] for r in batch.quarantine) == ["3", "4"]


def test_a_record_no_rule_can_evaluate_is_quarantined_not_promoted() -> None:
    """Fail-closed, which is TASKS item 4's own word.

    Evaluating the one rule against record 4 raises. Three things an implementation can do
    with that, and only the third is fail-closed:

    - let the exception escape: this test errors, and an error is red;
    - treat "cannot evaluate" as "passes": record 4 is promoted, the second assertion
      below goes red, and the fidelity check would then be comparing against a bronze
      table holding a record nothing vouched for;
    - quarantine it. That is the requirement, and it is the only way this passes.
    """
    batch = _partition()

    assert "4" not in [r["id"] for r in batch.promote]
    assert "4" in [r["id"] for r in batch.quarantine]


def test_the_comparison_target_is_the_union_and_carries_the_batch_id() -> None:
    from ingestproof.promotion import comparison_target

    batch = _partition()
    target = comparison_target(batch)

    assert batch.batch_id == BATCH_ID
    assert sorted(r["id"] for r in target) == ["1", "2", "3", "4"]


def test_the_quarantined_record_is_inside_the_target_and_bronze_alone_is_not_it() -> None:
    """The whole criterion in one assertion, stated as the contrast that was measured.

    `promote` alone is the landed bronze table. Comparing against it reports record 3 as
    damage, which it is not: it was routed, not lost. The union is what makes the
    difference between "the parse dropped it" and "the gate rejected it" observable.
    """
    from ingestproof.promotion import comparison_target

    batch = _partition()
    target_ids = {r["id"] for r in comparison_target(batch)}
    bronze_ids = {r["id"] for r in batch.promote}

    assert "3" in target_ids
    assert "3" not in bronze_ids
    assert target_ids - bronze_ids == {"3", "4"}
