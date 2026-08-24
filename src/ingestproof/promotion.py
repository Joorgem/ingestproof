"""Fail-closed promotion, and the comparison target the fidelity check is allowed to use.

THE MEASURED DEFECT THIS EXISTS TO PREVENT (docs/measurements.md section 0): comparing a
source against the LANDED bronze table gives about 1% false positives with zero real
damage, because bronze is the parse MINUS what the quality gate rejected. Every
quarantined record reads as loss. The target is `promote` UNION `quarantine` for one
batch, and `comparison_target` is the only name this library gives that union so that
nobody has to remember to write it.

FAIL-CLOSED HAS THREE DOORS AND ONLY ONE OF THEM IS RIGHT. A rule evaluated against a
record can say no, can say yes, or can fail to say anything -- and the third is the one
that decides whether this module is fail-closed or fail-open. Letting the exception escape
loses the batch; treating "cannot evaluate" as "passes" promotes a record nothing vouched
for, and the fidelity check downstream would then be comparing against a bronze table
holding it. Both are quarantine here, and `Rejection.error` is what tells the two apart
without making them the same value in one column.

THE RECORDS ARE NOT TOUCHED. Nothing here stamps `_batch_id` onto a row: the batch id
belongs to the BATCH, which is what `Batch.batch_id` is, and writing an audit column into
a caller's record would both mutate what was handed over and silently overwrite a
`_batch_id` a record already carried -- which is the duplicate-append shape the flagship's
own job YAML documents at length. What a row looks like in storage is the promotion job's
business, and `contracts.declare` already names the columns it will use.

[impl->req~ac-09~1]
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ingestproof.contracts import ContractError, require_batch_id
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
    """One batch, partitioned. Every record is on exactly one side, by construction."""

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
    judged = quality_rules(*rules)
    batch = require_batch_id(batch_id)

    promote: list[Record] = []
    rejections: list[Rejection] = []

    for record in records:
        rejection = _judge(record, judged)
        if rejection is None:
            promote.append(record)
        else:
            rejections.append(rejection)

    return Batch(batch_id=batch, promote=tuple(promote), rejections=tuple(rejections))


def comparison_target(batch: Batch) -> tuple[Record, ...]:
    """`promote` union `quarantine`, which is what a fidelity check may compare against.

    `promote` alone is the landed bronze table. Comparing against it reports a rejected
    record as damage, which it is not: it was routed, not lost.
    """
    return batch.promote + batch.quarantine


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
            return Rejection(record=record, rule=name, error=type(error).__name__)
        if not verdict:
            return Rejection(record=record, rule=name, error=None)
    return None


__all__ = [
    "Batch",
    "ContractError",
    "Rejection",
    "comparison_target",
    "partition_batch",
]
