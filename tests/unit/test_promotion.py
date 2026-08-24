"""Unit ring for `ingestproof.promotion`.

The frozen acceptance file judges the criterion over one four-record fixture. This file
judges what that fixture does not reach: the third door of fail-closed, the reason carried
on a rejection, the wiring into `require_batch_id` and `quality_rules`, and the promise
that a caller's records come back as the same objects.
"""

from __future__ import annotations

import pytest

from ingestproof.contracts import SENTINEL_BATCH_ID, ContractError
from ingestproof.promotion import Batch, Rejection, comparison_target, partition_batch

BATCH = "2026-08-24T00:00:00Z"

PASSES = ("always", lambda record: True)
REJECTS = ("says_no", lambda record: False)
CANNOT_EVALUATE = ("subscripts", lambda record: record["absent"])


# --- the wiring into the two modules this one sits on -------------------------------------


def test_the_batch_id_sentinel_the_job_resource_ships_is_refused_here() -> None:
    # The sentinel is a value `contracts.job_resource` writes as a job parameter's default
    # precisely so an un-parameterised run fails. This is the call that makes that true.
    with pytest.raises(ContractError, match="still the job parameter's default"):
        partition_batch([], [], batch_id=SENTINEL_BATCH_ID)

    with pytest.raises(ContractError, match="empty"):
        partition_batch([], [], batch_id="")


def test_a_malformed_rule_set_is_refused_before_any_record_is_read() -> None:
    """`quality_rules` is called, rather than the rules being trusted.

    A malformed rule reaching evaluation would be discovered as a batch failure. The whole
    posture of the declaration layer is that it is discovered at declaration.
    """
    read: list[object] = []

    class Watching(dict[str, object]):
        def __getitem__(self, key: str) -> object:
            read.append(key)
            return super().__getitem__(key)

    with pytest.raises(ContractError, match="is not callable"):
        partition_batch([Watching(id="1")], [("bad", "not callable")], batch_id=BATCH)

    assert read == []


# --- the partition ------------------------------------------------------------------------


def test_every_record_lands_on_exactly_one_side_and_keeps_its_identity() -> None:
    # The records come back as the SAME objects: nothing here stamps an audit column onto
    # a caller's row, so there is nothing to copy and nothing to overwrite.
    first, second = {"id": "1"}, {"id": "2"}
    batch = partition_batch([first, second], [REJECTS], batch_id=BATCH)

    assert batch.promote == ()
    assert batch.quarantine == (first, second)
    assert batch.quarantine[0] is first
    assert first == {"id": "1"}


def test_the_batch_carries_the_id_it_was_given() -> None:
    assert partition_batch([], [], batch_id=BATCH).batch_id == BATCH


def test_with_no_rules_every_record_promotes() -> None:
    # A gate with no rules rejects nothing. `quality_rules` allows an empty rule set and
    # this module does not second-guess it.
    records = [{"id": "1"}, {"id": "2"}]
    batch = partition_batch(records, [], batch_id=BATCH)

    assert batch.promote == tuple(records)
    assert batch.quarantine == ()


def test_an_empty_batch_is_a_batch() -> None:
    batch = partition_batch([], [PASSES], batch_id=BATCH)

    assert (batch.promote, batch.quarantine, comparison_target(batch)) == ((), (), ())


def test_the_comparison_target_is_promote_then_quarantine_and_nothing_else() -> None:
    kept, dropped = {"id": "1"}, {"id": "2"}
    batch = partition_batch(
        [kept, dropped], [("only_1", lambda record: record["id"] == "1")], batch_id=BATCH
    )

    assert batch.promote == (kept,)
    assert batch.quarantine == (dropped,)
    assert comparison_target(batch) == (kept, dropped)


def test_quarantine_is_derived_from_the_rejections_rather_than_stored_beside_them() -> None:
    # Two fields that must agree are two fields that can disagree. `quarantine` is a view.
    batch = partition_batch([{"id": "1"}], [REJECTS], batch_id=BATCH)

    assert batch.quarantine == tuple(rejection.record for rejection in batch.rejections)
    assert "quarantine" not in {field for field in vars(batch)}


def test_a_batch_is_immutable() -> None:
    batch = partition_batch([], [], batch_id=BATCH)

    with pytest.raises((AttributeError, TypeError)):
        batch.batch_id = "something else"  # type: ignore[misc]


# --- fail-closed, which is the criterion --------------------------------------------------


def test_a_rule_that_said_no_and_a_rule_that_could_not_run_are_both_quarantined() -> None:
    """Two of the three doors, and the second is the one that decides fail-closed.

    Letting the exception escape loses the batch. Treating "cannot evaluate" as "passes"
    promotes a record nothing vouched for, and the fidelity check downstream would then
    compare against a bronze table holding it. Both are quarantine.
    """
    said_no, could_not_run = {"id": "no"}, {"id": "raises"}
    batch = partition_batch([said_no], [REJECTS], batch_id=BATCH)
    other = partition_batch([could_not_run], [CANNOT_EVALUATE], batch_id=BATCH)

    assert batch.rejections == (Rejection(record=said_no, rule="says_no", error=None),)
    assert other.rejections == (
        Rejection(record=could_not_run, rule="subscripts", error="KeyError"),
    )


def test_the_two_are_distinguishable_without_reading_one_column_two_ways() -> None:
    """`error` is a separate field rather than a suffix on the rule name.

    A quarantine table filtered on the rule name must not miss the records the rule could
    not read -- those are the ones worth looking at first -- so `rule` carries the same
    value in both cases and `error` is what tells them apart.
    """
    records = [{"id": "1"}, {"id": "2", "absent": None}]
    batch = partition_batch(
        records,
        [("subscripts", lambda record: record["absent"] is not None)],
        batch_id=BATCH,
    )

    assert [rejection.rule for rejection in batch.rejections] == ["subscripts", "subscripts"]
    assert [rejection.error for rejection in batch.rejections] == ["KeyError", None]


def test_a_verdict_whose_truthiness_raises_is_the_third_door_and_it_quarantines_too() -> None:
    """A rule that returns something unbooleanable could not be evaluated either.

    The exception arrives from `bool(...)` rather than from the call, and from outside the
    call it is indistinguishable -- so the `try` covers the truthiness test as well.
    Without that, this record escapes as a `RuntimeError` and takes the batch with it.
    """

    class Unbooleanable:
        def __bool__(self) -> bool:
            raise RuntimeError("this verdict cannot be read")

    record = {"id": "1"}
    batch = partition_batch([record], [("unreadable", lambda _: Unbooleanable())], batch_id=BATCH)

    assert batch.promote == ()
    assert batch.rejections == (
        Rejection(record=record, rule="unreadable", error="RuntimeError"),
    )


def test_a_keyboard_interrupt_is_not_a_record_this_batch_can_route() -> None:
    # `except Exception`, not `except BaseException`. Fail-closed is about records, and an
    # interrupt is not one: swallowing it would make the batch unstoppable.
    def interrupted(record: object) -> object:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        partition_batch([{"id": "1"}], [("interrupted", interrupted)], batch_id=BATCH)


def test_the_first_rule_that_stops_a_record_is_the_one_recorded() -> None:
    # Order is why `quality_rules` returns a tuple. If this ever reports the second rule,
    # the rule set is being iterated in something other than declaration order.
    record = {"id": "1"}
    batch = partition_batch(
        [record], [PASSES, REJECTS, CANNOT_EVALUATE], batch_id=BATCH
    )

    assert batch.rejections[0].rule == "says_no"
    assert batch.rejections[0].error is None


def test_a_later_rule_is_not_evaluated_once_an_earlier_one_stopped_the_record() -> None:
    # Not an optimisation: the rules after the first failure are the ones most likely to
    # raise on a record that is already known to be malformed.
    evaluated: list[str] = []

    def watch(name: str, verdict: bool) -> tuple[str, object]:
        def evaluate(record: object) -> bool:
            evaluated.append(name)
            return verdict

        return (name, evaluate)

    partition_batch([{"id": "1"}], [watch("first", False), watch("second", True)], batch_id=BATCH)

    assert evaluated == ["first"]


def test_the_type_of_the_batch_is_what_comparison_target_expects() -> None:
    batch = partition_batch([{"id": "1"}], [PASSES], batch_id=BATCH)

    assert isinstance(batch, Batch)
    assert comparison_target(batch) == batch.promote + batch.quarantine
