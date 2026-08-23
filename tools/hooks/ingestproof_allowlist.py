"""PreToolUse allowlist for the ingestproof loop (design section 7.3).

THREE PROPERTIES, EACH DELIBERATE.

Scoped. This file is installed globally, and a live flagship lane runs beside this one.
Anything outside the ingestproof clone passes untouched.

Fail-open. A hook that raises blocks every tool call in every project on this machine. On
malformed input it allows and says nothing -- CI is the gate that fails closed.

Defence in depth, not the gate. The authoritative check is CI: a pull request whose diff
names a frozen path fails, with no override. This only makes that failure immediate. The
hook covers the editing tools; it cannot parse arbitrary shell, and it is not asked to.

Standard library only: it runs outside the project's virtualenv, so it cannot read
tools/frozen.txt. tests/unit/test_allowlist_hook.py checks the one direction that matters --
nothing frozen is writable here. The two lists are not complements: a path can be refused
here and not be frozen.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Exactly the set spec section 7.3 names, and nothing beyond it.
WRITABLE_PREFIXES = ("src/", "tests/unit/", "tests/property/", "docs/")
WRITABLE_FILES = ("LOOP.md",)

# Default-denied already, but named so the refusal says which escape was tried.
ROOT_ESCAPES = ("conftest.py", "pytest.ini", "tox.ini", "setup.cfg")

EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})


def _repo_root() -> Path:
    return Path(
        os.environ.get("INGESTPROOF_REPO")
        or r"C:/Users/jorge/Documents/github/ingestproof"
    )


def _kill_switch() -> Path:
    home = os.environ.get("LOOP_HOME") or str(Path.home() / ".ingestproof-loop")
    return Path(home) / "allowlist.off"


def decide(payload: dict[str, object], repo: Path | None = None) -> str | None:
    """Return None to allow, or a one-line reason to refuse."""
    if _kill_switch().exists():
        return None

    tool = payload.get("tool_name")
    if tool not in EDIT_TOOLS:
        return None

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw:
        return None

    root = (repo or _repo_root()).resolve()
    try:
        # A relative path resolves against the hook process's working directory, which is
        # the project it was invoked for. Relative in another project therefore lands
        # outside this root and is allowed, which is the safe direction.
        rel = Path(raw).resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return None  # outside the ingestproof clone: not this hook's business

    if rel in ROOT_ESCAPES:
        return (
            f"{rel} is refused at the repository root. An orphan root conftest.py was "
            f"measured turning a red acceptance suite green."
        )
    name = rel.rsplit("/", 1)[-1]
    # `test_*.py`, not `test_*`: docs/** is writable and a document may be named for what
    # it plans.
    if name.startswith("test_") and name.endswith(".py") and not rel.startswith("tests/"):
        return f"{rel}: test files live under tests/, nowhere else."
    if rel in WRITABLE_FILES or rel.startswith(WRITABLE_PREFIXES):
        return None
    return (
        f"{rel} is frozen. A turn may write only src/**, tests/unit/**, "
        f"tests/property/**, docs/** and LOOP.md. If this file is genuinely wrong, say so "
        f"in LOOP.md and stop -- changing it is a human's push to main."
    )


def main(stdin_text: str) -> int:
    try:
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            return 0
        reason = decide(payload)
    except Exception:  # noqa: BLE001 -- see "Fail-open" above; nothing here may block.
        return 0
    if reason is None:
        return 0
    print(f"BLOCKED by the ingestproof allowlist: {reason}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
