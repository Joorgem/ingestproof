"""The turn ledger: append-only, hash-chained, and OUTSIDE the work tree.

Why outside (spec section 7.11): a RED turn ends in `git reset --hard`. If the ledger were
tracked, undoing the commit would erase the record of the turn that was undone -- a
circular defect v1 of the design had. `LOOP.md` inside the repository is a *rendering* of
this file, never the source, and the harness writes here directly so the agent's editor
never touches it.

Each entry carries the SHA-256 of the one before it, so editing an entry, reordering
entries, or removing one from the MIDDLE is detectable from the file alone.

Two things are not, and the difference matters: truncating the TAIL, and re-computing every
hash from genesis. Neither is visible from inside the file, because a chain is only as
anchored as its tip. Both are caught by comparing against a tip quoted somewhere outside --
LOOP.md, a pull-request body, the README's published split. Quote the tip when it matters.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

Outcome = Literal["RED", "GREEN", "INDETERMINATE", "TIMEOUT"]
Author = Literal["human", "loop", "loop-adjudicated"]

GENESIS = "0" * 64

# `author` is required because AC-12 publishes the MEASURED human/loop split. An entry
# that may omit it turns that number into a claim about itself.
REQUIRED_FIELDS = (
    "ts",
    "task",
    "criterion",
    "outcome",
    "diff_lines",
    "cost_usd",
    "pragmas",
    "author",
)


# A row that corrects an earlier row is not a turn. The chain is append-only, so a wrong
# figure is fixed by appending a row that carries the DIFFERENCE and names the seq it
# corrects -- which means anything counting turns has to skip it, or the count of turns
# grows every time a number is fixed. Defined here because it is a property of the schema,
# and used by both things that count: the LOOP.md rendering and the stall detector.
CORRECTS = "corrects_seq"


def is_turn(entry: dict[str, Any]) -> bool:
    return entry.get(CORRECTS) is None


HUMAN = "human"


def is_loop_turn(entry: dict[str, Any]) -> bool:
    """A turn the LOOP ran.

    The stall detector exists to catch the loop spinning without closing anything, so turns
    from a phase the loop did not run must be inert to it by construction -- every P0 turn is
    one, and no instruction to a future harness would reliably survive.

    The test is "not human" rather than a list of loop author values on purpose. An author
    this code did not predict then counts as a loop turn, so the detector fires when it
    should not rather than going quiet when it should fire.
    """
    return is_turn(entry) and entry.get("author") != HUMAN


class LedgerTampered(RuntimeError):
    """The chain does not verify: an entry was edited, reordered or removed."""


def loop_home() -> Path:
    return Path(os.environ.get("LOOP_HOME") or (Path.home() / ".ingestproof-loop"))


def ledger_path() -> Path:
    return loop_home() / "iterations.jsonl"


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def entry_hash(entry: dict[str, Any]) -> str:
    body = {key: value for key, value in entry.items() if key != "hash"}
    return hashlib.sha256(_canonical(body)).hexdigest()


def read_all(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or ledger_path()
    if not target.exists():
        return []
    lines = target.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def verify_chain(entries: list[dict[str, Any]]) -> None:
    expected_prev = GENESIS
    for index, entry in enumerate(entries):
        if entry.get("prev") != expected_prev:
            raise LedgerTampered(
                f"entry {index}: prev is {entry.get('prev')!r}, the chain says {expected_prev!r}"
            )
        if entry.get("hash") != entry_hash(entry):
            raise LedgerTampered(f"entry {index}: the body does not match its own hash")
        expected_prev = entry["hash"]


def append(record: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise ValueError(f"ledger entry is missing required fields: {missing}")

    target = path or ledger_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = read_all(target)
    verify_chain(existing)

    entry = dict(record)
    entry["seq"] = len(existing)
    entry["prev"] = existing[-1]["hash"] if existing else GENESIS
    entry["hash"] = entry_hash(entry)

    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    return entry
