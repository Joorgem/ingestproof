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
    """Lines this diff writes over, per path, in REVIEW-TIME coordinates.

    A finding cites the file as it stood when the reviewer read it, which is the diff's
    OLD side. The new side is post-fix and must not be mixed in. Unioning both let a
    thirty-line insertion at the top of a file mark every finding below it resolved,
    because the new-side range swept coordinates the fix never touched -- the invisible
    false-resolve this module exists to prevent, reachable by an ordinary edit rather
    than an attack. The old side alone still handles a deletion correctly: a hunk that
    removes lines has a non-empty old range and an empty new one.

    Two shapes need care. A file the fix CREATED has no old side (`--- /dev/null`), so its
    new-side range is used; nothing can cite review-time lines in a file that did not
    exist. And a pure insertion (`old_len == 0`) writes BETWEEN two old lines rather than
    over any, so it claims the two it sits between -- a check added after line 12 does
    resolve a finding citing line 12.

    Two requirements on whoever generates the diff, and they pull opposite ways from the
    other gate in this repository, so read both before wiring a diff source.

    Rename detection ENABLED, which is git's default. Do NOT pass `--no-renames` here, even
    though tools/freeze_check.py requires exactly that: the two gates fail in opposite
    directions. Under `--no-renames` a rename becomes delete plus create, the delete side
    attributes the WHOLE old file as touched, and every finding on a renamed file resolves
    without anything having been fixed. Measured.

    Zero context, `-U0`. A hunk header spans its context lines, not only the changed ones,
    so at git's default `-U3` a deletion of lines 8-10 reports an old range of 5..13 and a
    finding three lines away from a real change resolves without being touched. `-U0`
    reports exactly 8..10. Measured both ways.
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
            if old_path is None:
                # Created by the fix: no review-time coordinates exist for this file.
                touched[path].update(range(new_start, new_start + new_len))
            elif old_len == 0:
                # A pure insertion sits between two old lines; claim both.
                touched[path].update((old_start, old_start + 1))
            else:
                touched[path].update(range(old_start, old_start + old_len))
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
