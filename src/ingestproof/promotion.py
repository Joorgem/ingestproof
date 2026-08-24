"""Fail-closed promotion, and the comparison target a fidelity check may use.

THE MEASURED DEFECT THIS EXISTS TO PREVENT (docs/measurements.md section 4): comparing a
source against the LANDED bronze table gives about 1% false positives with zero real
damage, because bronze is the parse MINUS what the quality gate rejected. Every
quarantined record reads as loss. The target is `promote` UNION `quarantine` for one
batch, and `comparison_target` is the only name this library gives that union so that
nobody has to remember to write it.

FAIL-CLOSED HAS FOUR OUTCOMES AND ONLY ONE OF THEM PROMOTES. A rule meeting a record can
say yes, say no, raise on the way in, or return a verdict whose truthiness raises -- and
the last two are what decide whether this module is fail-closed or fail-open. Letting the
exception escape loses the batch; treating "cannot evaluate" as "passes" promotes a record
nothing vouched for, and a later fidelity check would then be comparing against what a
bronze table would hold. All three non-yes outcomes quarantine, and `Rejection.error` is
what tells them apart without making them the same value in one column.

THE RECORDS ARE NOT TOUCHED. Nothing here stamps `_batch_id` onto a row: the batch id
belongs to the BATCH, which is what `Batch.batch_id` is, and writing an audit column into
a caller's record would both mutate what was handed over and silently overwrite a
`_batch_id` a record already carried -- which would defeat the same `_batch_id` idempotence
key the flagship's own job YAML documents a duplicate-append against. What a row looks like
in storage is a promotion job's business, and `contracts.declare` already names the columns
such a job would use.

[impl->req~ac-09~1]
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from ingestproof.contracts import ContractError, require_batch_id, type_name
from ingestproof.rules import Rule, quality_rules

type Record = Mapping[str, object]


@dataclass(frozen=True)
class Rejection:
    """One record the gate did not promote, and which rule stopped it.

    `error` is None when the rule ran and said no, and the exception's type name when the
    rule could not be evaluated at all. Two fields rather than one compound string,
    because a quarantine table filtered on the rule name must not miss the records the
    rule could not read -- those are the ones worth looking at first.
    """

    record: Record
    rule: str
    error: str | None


@dataclass(frozen=True)
class Batch:
    """One batch, partitioned. Every record is on exactly one side, by construction.

    Frozen, which generates a `__hash__` -- but a realistic payload holds dicts, so hashing
    a Batch or a Rejection raises `TypeError: unhashable type`. Frozen here means the
    partition cannot be edited after it was decided, not that it can go in a set.
    """

    batch_id: str
    promote: tuple[Record, ...]
    rejections: tuple[Rejection, ...]

    @property
    def quarantine(self) -> tuple[Record, ...]:
        return tuple(rejection.record for rejection in self.rejections)


def partition_batch(
    records: Sequence[Record], rules: Sequence[Rule], *, batch_id: str
) -> Batch:
    """Split one batch into what the gate promotes and what it quarantines.

    The rules go through `quality_rules` rather than being trusted: a malformed rule set
    reaching evaluation would be discovered as a batch failure, and the whole posture of
    the declaration layer is that it is discovered at declaration.
    """
    # The batch id first: two comparisons on a local, running no caller code at all. The
    # order used to be the other way round, and then a batch id this function was about to
    # refuse still got the caller's rules container iterated first -- measured.
    batch = require_batch_id(batch_id)
    judged = quality_rules(*_snapshot(rules, "rule set"))

    promote: list[Record] = []
    rejections: list[Rejection] = []

    for record in _snapshot(records, "batch"):
        rejection = _judge(record, judged)
        if rejection is None:
            promote.append(record)
        else:
            rejections.append(rejection)

    return Batch(batch_id=batch, promote=tuple(promote), rejections=tuple(rejections))


def comparison_target(batch: Batch) -> tuple[Record, ...]:
    """`promote` union `quarantine`, which is what a fidelity check may compare against.

    `promote` alone is what a promotion job would land in bronze. Comparing against that
    reports a rejected record as damage, which it is not: it was routed, not lost.

    The frozen acceptance file says "`promote` alone IS the landed bronze table"; nothing
    lands anywhere yet, so this copy says less rather than repeating it.
    """
    return batch.promote + batch.quarantine


def _snapshot(values: object, what: str) -> tuple[Any, ...]:
    """Read a caller's container ONCE, and refuse rather than escape if it will not read.

    `for record in records` walks the caller's LIVE container. Measured: a rule that
    deletes from the list it is being judged against dropped a record from both sides --
    four in, three in the comparison target -- which is "the parse dropped it", the one
    failure this module exists to make impossible; and a rule that appends never returned.
    A snapshot makes totality structural rather than a promise about caller behaviour.

    Reading a container is itself caller code, so the read is guarded. Measured: a `rules`
    of None escaped as TypeError and one whose `__iter__` raises escaped as the caller's
    own exception, and a caller writing `except ContractError` saw neither. Nothing
    caller-supplied is interpolated into the message -- naming the type would run the same
    metaclass read that broke fail-closed below -- and `from error` keeps the detail in the
    traceback without formatting it.
    """
    try:
        return tuple(cast("Iterable[Any]", values))
    except TypeError as error:
        raise ContractError(f"the {what} is not iterable") from error
    except Exception as error:
        raise ContractError(f"the {what} could not be read") from error


def _judge(record: Record, rules: tuple[Rule, ...]) -> Rejection | None:
    """The first rule that stops this record, or None if every rule passed it.

    The `try` covers the truthiness test as well as the call, because a verdict object
    whose `__bool__` raises is a rule that could not be evaluated just as surely as one
    that raised on the way in -- and the difference is invisible from here.
    """
    for name, evaluate in rules:
        try:
            verdict = bool(evaluate(record))
        # Broad on purpose, and not silent: any failure quarantines, and the exception's
        # type is carried on the Rejection rather than discarded. `BaseException` is NOT
        # caught -- a KeyboardInterrupt is not a record this batch can route.
        except Exception as error:
            return Rejection(record=record, rule=name, error=type_name(error))
        if not verdict:
            return Rejection(record=record, rule=name, error=None)
    return None
