"""Every specification item must declare `Needs:`.

Measured: OFT treats an item with no `Needs:` field as a *terminating item*, which traces
clean. A specification full of them makes the coverage gate report full coverage over
nothing. This runs in the inner ring because it is pure Python and needs no JVM.
"""
from __future__ import annotations

import sys
from pathlib import Path

from tools.spec_parse import SpecItem, parse_dir


def items_without_needs(items: list[SpecItem]) -> list[SpecItem]:
    return [item for item in items if not item.needs]


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    offenders = items_without_needs(parse_dir(root))
    if offenders:
        print("specification items with no `Needs:` (they would trace clean):", file=sys.stderr)
        for item in offenders:
            print(f"  {item.id}  {item.source}:{item.line}", file=sys.stderr)
        return 1
    print("every specification item declares Needs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
