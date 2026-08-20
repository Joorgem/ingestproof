"""A minimal reader for OFT's markdown specification format.

Only enough of it to run the two checks the inner ring owes: every item has `Needs:`, and
no item's text moved without its revision moving. The JAR does the real tracing, nightly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ITEM_ID = re.compile(r"^`(?P<id>(?P<type>req)~(?P<name>[a-z0-9][a-z0-9._-]*)~(?P<rev>\d+))`\s*$")
HEADING = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")
NEEDS = re.compile(r"^Needs:\s*(?P<needs>.+?)\s*$")


@dataclass(frozen=True)
class SpecItem:
    id: str
    name: str
    revision: int
    title: str
    body: str
    source: str
    line: int
    needs: list[str] = field(default_factory=list)


def _finish(pending: dict[str, object], body: list[str]) -> SpecItem:
    text = "\n".join(line.rstrip() for line in body).strip()
    return SpecItem(
        id=str(pending["id"]),
        name=str(pending["name"]),
        revision=int(str(pending["revision"])),
        title=str(pending["title"]),
        body=text,
        source=str(pending["source"]),
        line=int(str(pending["line"])),
        # `pending` is dict[str, object], so mypy cannot see that this value is the list
        # parse_file put there. call-overload is the code strict mode actually raises.
        needs=list(pending["needs"]),  # type: ignore[call-overload]
    )


def parse_file(path: Path) -> list[SpecItem]:
    items: list[SpecItem] = []
    heading = ""
    pending: dict[str, object] | None = None
    body: list[str] = []

    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match_id = ITEM_ID.match(raw)
        if match_id:
            if pending is not None:
                items.append(_finish(pending, body))
            pending = {
                "id": match_id.group("id"),
                "name": match_id.group("name"),
                "revision": int(match_id.group("rev")),
                "title": heading,
                "source": path.as_posix(),
                "line": number,
                "needs": [],
            }
            body = []
            continue

        match_heading = HEADING.match(raw)
        if match_heading:
            if pending is not None:
                items.append(_finish(pending, body))
                pending = None
                body = []
            heading = match_heading.group("title")
            continue

        if pending is None:
            continue

        match_needs = NEEDS.match(raw)
        if match_needs:
            if pending["needs"]:
                raise ValueError(
                    f"{path.as_posix()}:{number}: {pending['id']} carries a second `Needs:` "
                    f"line. OFT accumulates them and this parser keeps only the last, so the "
                    f"discarded line would change the requirement set with no change to the "
                    f"criterion's hash."
                )
            pending["needs"] = [
                n.strip() for n in match_needs.group("needs").split(",") if n.strip()
            ]
            continue

        body.append(raw)

    if pending is not None:
        items.append(_finish(pending, body))
    return items


def parse_dir(root: Path) -> list[SpecItem]:
    items: list[SpecItem] = []
    for path in sorted((root / ".spec").rglob("*.md")):
        items.extend(parse_file(path))
    return items
