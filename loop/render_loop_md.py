"""LOOP.md is a VIEW of the ledger. The ledger is the source, and it lives outside the
work tree so that undoing a turn cannot erase the record of it.

The header exists so that a turn which edits LOOP.md by hand -- the one repository file it
is allowed to write -- is visibly overwriting generated output.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

from loop.ledger import is_turn, read_all, verify_chain

HEADER = "<!-- GENERATED FROM $LOOP_HOME/iterations.jsonl -- DO NOT EDIT BY HAND -->"


def _counts_table(title: str, counts: Counter[str]) -> list[str]:
    rows = [f"| {key} | {counts[key]} |" for key in sorted(counts)]
    return [f"### {title}", "", "| | turns |", "|---|---|", *rows, ""]


def render(entries: list[dict[str, Any]]) -> str:
    # The tip anchors the WHOLE chain, so it is the last row whatever kind of row that is.
    # The counts below are counts of turns, which is not the same thing.
    tip = entries[-1]["hash"] if entries else "(empty)"
    turns = [entry for entry in entries if is_turn(entry)]
    lines = [
        HEADER,
        "",
        "# Loop state",
        "",
        "The source of this file is `$LOOP_HOME/iterations.jsonl`, which is outside the",
        "work tree on purpose: a RED turn ends in `git reset --hard`, and a tracked ledger",
        "would lose the entry recording the turn it undid.",
        "",
        "Tool calls failing for a reason that names this project? The allowlist hook has two",
        "off switches, and they are written in `docs/allowlist-rollback.md` rather than here,",
        "because this file is regenerated: anything added to it by hand is erased by the next",
        "render, which is when nobody is watching.",
        "",
        f"Turns: **{len(turns)}**",
        f"Chain tip: `{tip}`",
        "",
        "Rows that correct an earlier row are in the chain but not in these counts. They",
        "are not turns, and counting them would grow the number of turns every time a",
        "figure is corrected.",
        "",
    ]
    lines += _counts_table("By author", Counter(str(e["author"]) for e in turns))
    lines += _counts_table("By outcome", Counter(str(e["outcome"]) for e in turns))
    return "\n".join(lines) + "\n"


def main() -> int:
    entries = read_all()
    verify_chain(entries)
    # Anchored to the repository root, not the working directory: LOOP.md has exactly one
    # correct location, and a mislocated render would leave a stray view file that reads
    # like the real thing.
    target = Path(__file__).resolve().parents[1] / "LOOP.md"
    target.write_text(render(entries), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
