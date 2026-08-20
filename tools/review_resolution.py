"""req~ac-16~1's mechanical half.

A turn may mark a review finding resolved only when the turn's own diff touched the file
AND the line range the finding cites. The failure this prevents (spec section 7.10) is an
agent closing the thread over GraphQL without changing code -- indistinguishable from a fix
in every report anyone reads afterwards. Findings closed without a matching hunk go into
the pull-request body as dismissed, with a reason.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class Finding:
    path: str
    start_line: int
    end_line: int
    summary: str


def _strip_prefix(raw: str) -> str | None:
    if raw == "/dev/null":
        return None
    return raw[2:] if raw[:2] in ("a/", "b/") else raw


def touched_lines(diff_text: str) -> dict[str, set[int]]:
    """Lines this diff writes over, per path -- BOTH sides of every hunk.

    Both sides, because a finding cites the file as it stood at review time: a fix that
    deletes the offending lines produces a hunk whose new-side length is zero, and
    matching only the new side would score that as unresolved.
    """
    touched: dict[str, set[int]] = {}
    old_path: str | None = None
    path: str | None = None

    for line in diff_text.splitlines():
        if line.startswith("--- "):
            old_path = _strip_prefix(line[4:].strip())
            continue
        if line.startswith("+++ "):
            path = _strip_prefix(line[4:].strip()) or old_path
            if path:
                touched.setdefault(path, set())
            continue
        if line.startswith("@@") and path:
            match = HUNK.match(line)
            if not match:
                continue
            old_start, old_len = int(match.group(1)), int(match.group(2) or 1)
            new_start, new_len = int(match.group(3)), int(match.group(4) or 1)
            touched[path].update(range(old_start, old_start + old_len))
            touched[path].update(range(new_start, new_start + new_len))
    return touched


def is_resolved(finding: Finding, touched: dict[str, set[int]]) -> bool:
    lines = touched.get(finding.path)
    if not lines:
        return False
    cited = range(finding.start_line, finding.end_line + 1)
    return any(line in lines for line in cited)


def partition(
    findings: Sequence[Finding], diff_text: str
) -> tuple[list[Finding], list[Finding]]:
    touched = touched_lines(diff_text)
    resolved = [f for f in findings if is_resolved(f, touched)]
    dismissed = [f for f in findings if not is_resolved(f, touched)]
    return resolved, dismissed


def dismissal_section(dismissed: Sequence[Finding]) -> str:
    if not dismissed:
        return ""
    lines = [
        "## Review findings dismissed without a code change",
        "",
        "Each of these was closed without this branch touching the lines it cites.",
        "",
    ]
    lines += [
        f"- `{f.path}:{f.start_line}-{f.end_line}` — {f.summary}" for f in dismissed
    ]
    return "\n".join(lines) + "\n"
