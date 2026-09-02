"""The check, inside Spark, against a local open-source Delta table.

`req~ac-08a~1`: the check runs inside Spark against local open-source Delta and fails the
task, with no credential and no workspace.

NOTHING HERE IS IMPORTED AT MODULE SCOPE FROM SPARK OR DELTA, and that is a criterion rather
than a preference. `req~ac-07~1` proves the declaration layer needs no JVM, and it proves it
by refusing `pyspark` and `py4j` through a meta-path finder in a subprocess. A module-scope
import here would not break that test -- nothing in the declaration layer imports this
module -- but it would make the inner ring pay a JVM's import cost the moment anyone did,
and the ring is what a turn's speed rests on. The imports live inside the function.

WHAT THIS MODULE DOES NOT DECIDE. How two record streams are compared is
`ingestproof.differential`'s, gated by `req~ac-02a~1`. This module reads one batch out of a
table and hands over two streams. It is the plumbing, and the plumbing is where the reading
can go quietly wrong -- which is why every narrowing below is argued rather than assumed.
"""

from __future__ import annotations

from typing import Any

from ingestproof.contracts import (
    BATCH_ID_COLUMN,
    CONTRACT_ID_COLUMN,
    REJECTED_BY_COLUMN,
)
from ingestproof.differential import detect
from ingestproof.report import DamageFound

# The three columns this library stamps onto a landed reading. They are OURS, not the
# source's, and handing them to the differential would shift every field index by three --
# a report whose coordinates name nothing a producer can find in their own file.
STAMPS = (BATCH_ID_COLUMN, CONTRACT_ID_COLUMN, REJECTED_BY_COLUMN)

# The driver holds the whole batch, because `detect` compares positionally and `report`'s
# own docstring refuses to read either stream twice -- so both sides are in memory by
# design, and the source already is, out of `parse_records`.
#
# THE CAP REFUSES; IT DOES NOT TRUNCATE. A review suggested bounding the batch and that is
# the right worry with the wrong repair: comparing a PREFIX of a batch publishes a clean
# report over records nobody looked at, and carries a denominator that says otherwise. That
# is the exact failure `req~ac-05~1` exists to prevent, and it would be introduced by the
# fix rather than by the bug. So an oversized batch is a loud refusal.
MAX_RECORDS = 1_000_000


def check_batch(
    source: bytes,
    dialect: object,
    location: str,
    batch_id: str,
    max_records: int = MAX_RECORDS,
) -> None:
    """Compare one batch's landed reading against the source, and fail the task on damage.

    PROMOTE UNION QUARANTINE, NOT PROMOTE. The batch is every row carrying this
    `_batch_id`, whatever `_rejected_by` says. Reading only the promoted side is the
    reading `docs/design.md` calls wrong by construction, and it is the one a Spark reader
    falls into first because bronze IS the promote side: the quarantined records are
    precisely the ones a parse most often damaged, so a check that skips them reports clean
    on the population it exists to examine.

    ONE BATCH. Without the `_batch_id` filter the comparison takes every batch in the table
    and finds damage that is not this one's, against a denominator that is not this one's
    either.

    THE ORDER IS THE LANDING'S, AND THIS FUNCTION DOES NOT INVENT ONE. `detect` compares
    positionally when the lengths agree, so the landed stream must arrive in the source's
    order -- and the audit stamps carry no position. Three readings were possible and two
    are worse:

    - Sorting the landed stream by its own values is deterministic and wrong whenever the
      source is not itself sorted: every record then mismatches, and a fidelity check that
      cries damage on an intact file is worse than none.
    - Sorting BOTH streams hides a pure reordering, which is a corruption this library
      exists to see.
    - So the rows are handed over as read, and the ASSUMPTION IS DECLARED HERE rather than
      buried: **layer 2 requires a landing that preserves record order.** If that proves
      false against a real corpus, the fix is a position stamp written at read time -- and
      that is a new acceptance file and a human's commit, not a quiet sort added here.

    Raises `DamageFound` when the readings differ, `ValueError` when the batch is larger
    than `max_records`, and returns None when the readings agree.
    """
    # `delta` is NOT imported. Reading `format("delta")` needs Delta on the session's
    # classpath, which is the job's configuration rather than this module's import: a
    # `configure_spark_with_delta_pip` here would build a second opinion about the session
    # that the job already settled.
    from pyspark.sql import SparkSession  # type: ignore[import-not-found]

    session = SparkSession.getActiveSession()
    if session is None:
        raise RuntimeError(
            "check_batch needs an active SparkSession and will not build one. "
            "The job owns the session's configuration -- Delta's extensions, the catalog "
            "implementation, the master -- and a session built here would silently disagree "
            "with the one the job configured."
        )

    frame = session.read.format("delta").load(location)
    batch = frame.filter(frame[BATCH_ID_COLUMN] == batch_id).drop(*STAMPS)

    # Counted before it is collected, so an oversized batch is a message rather than a
    # driver that dies mid-collect with a stack trace naming nothing.
    size = batch.count()
    if size > max_records:
        raise ValueError(
            f"batch {batch_id!r} holds {size} records and the cap is {max_records}. "
            "This check compares whole batches -- it will not compare a prefix, because a "
            "report over records nobody read is a clean verdict that means nothing. Raise "
            "`max_records` deliberately, or split the batch upstream."
        )

    landed = tuple(_as_record(row) for row in batch.collect())
    differential = detect(source, dialect, landed)

    if differential.damages or differential.needs_resync:
        raise DamageFound(differential)


def _as_record(row: Any) -> tuple[str | None, ...]:
    """One Spark row as the record vocabulary the rest of this library speaks.

    `None` survives as `None` rather than becoming `"None"` or `""`: `Damage`'s docstring
    says `expected` and `actual` are `None` both for an absent field and for a null one, so
    flattening a null here would report a damage the source does not have.
    """
    return tuple(None if value is None else str(value) for value in row)
