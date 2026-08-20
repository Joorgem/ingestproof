"""The review-drift equivalent OFT does not provide.

Measured: OFT only notices a changed requirement if a human increments its revision. So CI
keeps a SHA-256 of each item's text. Change the words and leave `~1` alone and this fails;
change the words and bump to `~2` and it passes, because the old id disappeared and a new
one arrived -- which is what a revision is for.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterable
from pathlib import Path

from tools.spec_parse import SpecItem, parse_dir

HASHES = ".spec/hashes.json"


def item_hash(item: SpecItem) -> str:
    payload = "\n".join([item.title.strip(), item.body.strip(), ",".join(item.needs)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _current(root: Path) -> dict[str, str]:
    return {item.id: item_hash(item) for item in parse_dir(root)}


def _recorded(root: Path) -> dict[str, str]:
    target = root / HASHES
    if not target.exists():
        return {}
    loaded: dict[str, str] = json.loads(target.read_text(encoding="utf-8"))
    return loaded


def _split_id(item_id: str) -> tuple[str, int]:
    """`req~ac-01~1` -> ("ac-01", 1). Anything else keeps its id and sorts below rev 0."""
    parts = item_id.split("~")
    if len(parts) == 3 and parts[2].isdigit():
        return parts[1], int(parts[2])
    return item_id, -1


def _revisions_by_name(ids: Iterable[str]) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for item_id in ids:
        name, revision = _split_id(item_id)
        out.setdefault(name, set()).add(revision)
    return out


def write(root: Path) -> None:
    (root / HASHES).write_text(
        json.dumps(_current(root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def verify(root: Path) -> list[str]:
    recorded = _recorded(root)
    current = _current(root)
    was, now = _revisions_by_name(recorded), _revisions_by_name(current)

    # Same id, different text. The silent edit this module exists to catch.
    drifted = {i for i, h in current.items() if i in recorded and recorded[i] != h}
    for item_id in set(current) - set(recorded):
        # A new id is legitimate only as the successor of a recorded LOWER revision. A
        # name that was never recorded is an addition nobody hashed, and reporting it is
        # what forces `update` to run when a criterion is added.
        name, revision = _split_id(item_id)
        if not any(r < revision for r in was.get(name, ())):
            drifted.add(item_id)
    for item_id in set(recorded) - set(current):
        # A vanished id is legitimate only if the same name returned at a HIGHER
        # revision. Otherwise the criterion was deleted, which is not a silent act.
        name, revision = _split_id(item_id)
        if not any(r > revision for r in now.get(name, ())):
            drifted.add(item_id)
    return sorted(drifted)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    mode = args[0] if args else "verify"
    root = Path(".")
    current = _current(root)
    if not current:
        # "0 criterion hashes verified" as a SUCCESS line is backwards for this project:
        # a .spec/ that is missing, empty, or unreadable would go green exactly as loudly
        # as a verified one, and `update` would pin an empty set over the top of it.
        print(f"no specification items found under {(root / '.spec').as_posix()}",
              file=sys.stderr)
        return 1
    if mode == "update":
        write(root)
        print(f"wrote {HASHES} for {len(current)} items")
        return 0
    drifted = verify(root)
    if drifted:
        print("criterion text moved without its revision moving:", file=sys.stderr)
        for item_id in drifted:
            print(f"  {item_id}", file=sys.stderr)
        return 1
    print(f"{len(current)} criterion hashes verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
