"""One turn, made atomic.

`git reset --hard` does NOT remove untracked files: a `conftest.py` left by a dead turn
survives and was measured to turn a red acceptance suite green (docs/measurements.md
section 7). Every turn therefore starts with reset AND `clean -fdx -e .venv`.
"""
from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from loop.ledger import Outcome

RESET = ("git", "reset", "--hard")
CLEAN = ("git", "clean", "-fdx", "-e", ".venv")

# The closed definition of "did not touch production". v1 said "production code" and never
# said what that was, so any turn could argue its way into INDETERMINATE.
DOC_ONLY_PREFIXES = ("docs/",)
DOC_ONLY_FILES = ("LOOP.md",)


def clean_slate(repo: Path) -> None:
    for command in (RESET, CLEAN):
        subprocess.run(command, cwd=repo, check=True, capture_output=True)


def diff_is_documentation_only(paths: Sequence[str]) -> bool:
    return all(
        path in DOC_ONLY_FILES or path.startswith(DOC_ONLY_PREFIXES) for path in paths
    )


def classify(
    *,
    tests_passed: bool,
    timed_out: bool,
    changed_paths: Sequence[str],
    test_was_green_before: bool,
) -> Outcome:
    """Spec section 7.5, as a pure function so it can be argued with in a test.

    GREEN          the ring passed.
    INDETERMINATE  a timeout on a test that was green under the previous commit, or a red
                   whose diff touched nothing but docs/** and LOOP.md. Both mean the
                   environment moved rather than the code, and both stop the loop.
    TIMEOUT        any other timeout.
    RED            anything else. Undo.
    """
    if tests_passed and not timed_out:
        return "GREEN"
    if timed_out:
        return "INDETERMINATE" if test_was_green_before else "TIMEOUT"
    if diff_is_documentation_only(changed_paths):
        return "INDETERMINATE"
    return "RED"


# How many consecutive turns may close nothing before the loop stops itself. Small on
# purpose: the dominant defect in this work is a defect of PLAN, and five turns of a loop
# grinding at a badly-specified task is exactly what that looks like from the outside.
STALL_LIMIT = 5


def turns_since_close(entries: Sequence[dict[str, object]]) -> int:
    """Trailing turns that closed no criterion.

    `closed_criterion` is written by the harness from two signals the agent does not
    control (spec section 7.6): the traceability report, and the frozen acceptance test
    citing that id. A turn cannot set it by writing to TASKS.md, because it cannot write
    to TASKS.md.
    """
    count = 0
    for entry in reversed(list(entries)):
        if entry.get("closed_criterion"):
            return count
        count += 1
    return count


def stall_report(entries: Sequence[dict[str, object]], limit: int = STALL_LIMIT) -> str | None:
    """None while the loop is making progress; otherwise the text to write and stop on."""
    stalled = turns_since_close(entries)
    if stalled < limit:
        return None
    recent = list(entries)[-limit:]
    lines = [
        f"STOPPED: {stalled} consecutive turns closed no criterion (limit {limit}).",
        "",
        "The last turns, and what each attempted:",
        "",
    ]
    lines += [
        f"- seq {e.get('seq')}: {e.get('task')} / {e.get('criterion')} -> {e.get('outcome')}"
        for e in recent
    ]
    lines += [
        "",
        "This is a human's decision, not the next turn's. The likeliest cause is that the "
        "task as written cannot be closed by the criterion it names.",
    ]
    return "\n".join(lines) + "\n"
