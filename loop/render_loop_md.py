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

from loop.ledger import read_all, verify_chain

HEADER = "<!-- GENERATED FROM $LOOP_HOME/iterations.jsonl -- DO NOT EDIT BY HAND -->"


def _counts_table(title: str, counts: Counter[str]) -> list[str]:
    rows = [f"| {key} | {counts[key]} |" for key in sorted(counts)]
    return [f"### {title}", "", "| | turns |", "|---|---|", *rows, ""]


def render(entries: list[dict[str, Any]]) -> str:
    tip = entries[-1]["hash"] if entries else "(empty)"
    lines = [
        HEADER,
        "",
        "# Loop state",
        "",
        "The source of this file is `$LOOP_HOME/iterations.jsonl`, which is outside the",
        "work tree on purpose: a RED turn ends in `git reset --hard`, and a tracked ledger",
        "would lose the entry recording the turn it undid.",
        "",
        f"Turns: **{len(entries)}**",
        f"Chain tip: `{tip}`",
        "",
    ]
    lines += _counts_table("By author", Counter(str(e["author"]) for e in entries))
    lines += _counts_table("By outcome", Counter(str(e["outcome"]) for e in entries))
    return "\n".join(lines) + "\n"


def main() -> int:
    entries = read_all()
    verify_chain(entries)
    Path("LOOP.md").write_text(render(entries), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
