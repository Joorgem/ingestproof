"""One turn, made atomic.

`git reset --hard` does NOT remove untracked files: a `conftest.py` left by a dead turn
survives and was measured to turn a red acceptance suite green (docs/measurements.md
section 7). Every turn therefore starts with reset AND `clean -fdx -e .venv`.
"""
from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from loop.ledger import Outcome, is_turn

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
    INDETERMINATE  the environment moved rather than the code. Two doors in, and BOTH
                   require the diff to be documentation-only: a red that touched nothing
                   but docs/** and LOOP.md, or a timeout on a test that was green under
                   the previous commit AND under the same code. Stops the loop.
    TIMEOUT        any other timeout. Its disposition is RED's -- UNDO. It stays a
                   separate recorded outcome only so the ledger can tell a hang from a
                   failure; it is not a softer verdict.
    RED            anything else. Undo.

    The `diff_is_documentation_only` guard on the timeout branch is the spec's "sob o
    mesmo codigo" clause, and it is load-bearing. Without it, a turn escapes by converting
    its failure into a hang: timing out against a green baseline would read as
    INDETERMINATE and the broken diff would survive in the tree. That is the same
    argue-your-way-out shape the closed set exists to prevent, coming through a different
    door.
    """
    if tests_passed and not timed_out:
        return "GREEN"
    if timed_out:
        if test_was_green_before and diff_is_documentation_only(changed_paths):
            return "INDETERMINATE"
        return "TIMEOUT"
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
        if not is_turn(entry):
            continue  # correcting a figure is not a turn, and must not count as a stall
        if entry.get("closed_criterion"):
            return count
        count += 1
    return count


def stall_report(entries: Sequence[dict[str, object]], limit: int = STALL_LIMIT) -> str | None:
    """None while the loop is making progress; otherwise the text to write and stop on."""
    stalled = turns_since_close(entries)
    if stalled < limit:
        return None
    # Slice by `stalled`, not by `limit`: the headline counts the stalled turns, so listing
    # a different number of them makes the report disagree with itself at exactly the
    # moment a human is reading it to work out why the loop stopped.
    recent = [entry for entry in entries if is_turn(entry)][-stalled:]
    lines = [
        f"STOPPED: {stalled} consecutive turns closed no criterion (limit {limit}).",
        "",
        f"All {stalled}, and what each attempted:",
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

# The hook that refuses writes to frozen paths lives in two places: this one, which CI
# tests, and the installed copy, which is what actually refuses. Nothing keeps them in
# step on its own -- CI cannot see ~/.claude.
INSTALLED_HOOK = Path.home() / ".claude" / "hooks" / "ingestproof-allowlist.py"
HOOK_SOURCE = Path("tools") / "hooks" / "ingestproof_allowlist.py"


def assert_hook_installed(repo: Path) -> None:
    """Refuse to start a turn when the installed copy is absent or has drifted.

    This is the cheapest place to notice. It does not check that ~/.claude/settings.json
    still arms the hook, and it cannot: a turn that could read its own gate's configuration
    is a turn that could learn to edit it.
    """
    source = repo / HOOK_SOURCE
    if not INSTALLED_HOOK.exists():
        raise RuntimeError(
            f"the allowlist hook is not installed at {INSTALLED_HOOK}; "
            f"copy it from {source}"
        )
    if INSTALLED_HOOK.read_bytes() != source.read_bytes():
        raise RuntimeError(
            f"{INSTALLED_HOOK} has drifted from {source}. The installed copy is what "
            f"refuses writes, and it is no longer the copy CI tested."
        )
