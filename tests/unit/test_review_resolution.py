"""Spec section 7.10: a turn may mark a review finding resolved only when its own diff
touched the file and the line range the finding cites. Without that, closing the thread
and fixing the code look the same from outside.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tools.review_resolution import (
    Finding,
    dismissal_section,
    is_resolved,
    partition,
    touched_lines,
)

ADDITION = """diff --git a/src/ingestproof/reader.py b/src/ingestproof/reader.py
index 1111111..2222222 100644
--- a/src/ingestproof/reader.py
+++ b/src/ingestproof/reader.py
@@ -40,6 +40,8 @@ def read(path):
     a = 1
     b = 2
+    c = 3
+    d = 4
     return a
"""

DELETION = """diff --git a/src/ingestproof/old.py b/src/ingestproof/old.py
index 3333333..4444444 100644
--- a/src/ingestproof/old.py
+++ b/src/ingestproof/old.py
@@ -10,4 +10,0 @@ def gone():
-    dead = 1
-    also_dead = 2
-    return dead
-
"""

NEW_FILE = """diff --git a/src/ingestproof/new.py b/src/ingestproof/new.py
new file mode 100644
index 0000000..5555555
--- /dev/null
+++ b/src/ingestproof/new.py
@@ -0,0 +1,3 @@
+one = 1
+two = 2
+three = 3
"""

REMOVED_FILE = """diff --git a/tools/scratch.py b/tools/scratch.py
deleted file mode 100644
index 6666666..0000000
--- a/tools/scratch.py
+++ /dev/null
@@ -1,2 +0,0 @@
-x = 1
-y = 2
"""


def test_an_addition_hunk_reports_the_lines_it_replaced() -> None:
    assert touched_lines(ADDITION)["src/ingestproof/reader.py"] >= {40, 45}


def test_a_deletion_hunk_reports_the_lines_it_removed() -> None:
    # New-side length is 0 here. Matching only the new side would score a fix that
    # DELETES the offending lines as unresolved, which is backwards.
    touched = touched_lines(DELETION)

    assert {10, 11, 12, 13} <= touched["src/ingestproof/old.py"]


def test_a_new_file_is_attributed_to_its_new_path() -> None:
    assert touched_lines(NEW_FILE)["src/ingestproof/new.py"] == {1, 2, 3}


def test_a_deleted_file_is_attributed_to_its_old_path() -> None:
    assert touched_lines(REMOVED_FILE)["tools/scratch.py"] >= {1, 2}


def test_a_finding_inside_the_hunk_is_resolved() -> None:
    finding = Finding("src/ingestproof/reader.py", 43, 43, "unchecked index")

    assert is_resolved(finding, touched_lines(ADDITION)) is True


def test_a_finding_in_an_untouched_file_is_not_resolved() -> None:
    finding = Finding("src/ingestproof/other.py", 43, 43, "unchecked index")

    assert is_resolved(finding, touched_lines(ADDITION)) is False


def test_a_finding_outside_every_hunk_of_a_touched_file_is_not_resolved() -> None:
    # The whole point: touching the file somewhere is not touching the finding.
    finding = Finding("src/ingestproof/reader.py", 900, 902, "unchecked index")

    assert is_resolved(finding, touched_lines(ADDITION)) is False


def test_an_empty_diff_resolves_nothing() -> None:
    finding = Finding("src/ingestproof/reader.py", 43, 43, "unchecked index")

    assert is_resolved(finding, touched_lines("")) is False


def test_a_multi_line_finding_overlapping_the_hunk_edge_is_resolved() -> None:
    finding = Finding("src/ingestproof/reader.py", 44, 80, "range spans out of the hunk")

    assert is_resolved(finding, touched_lines(ADDITION)) is True


def test_an_insertion_above_a_finding_does_not_resolve_it() -> None:
    """The coordinate trap, and the reason the old side alone is used.

    A hunk's new-side numbers are post-fix; a finding's are review-time. Unioning both
    let a thirty-line insertion at the top of a file mark every finding below it
    resolved -- invisibly, and through an ordinary edit rather than an attack.
    """
    diff = (
        "diff --git a/src/f.py b/src/f.py\n"
        "--- a/src/f.py\n"
        "+++ b/src/f.py\n"
        "@@ -1,3 +1,33 @@\n" + "+comment\n" * 30 + " a = 1\n b = 2\n c = 3\n"
    )
    finding = Finding("src/f.py", 12, 14, "the insertion never touched these")

    assert is_resolved(finding, touched_lines(diff)) is False


def test_a_pure_insertion_resolves_only_at_its_anchor() -> None:
    diff = (
        "diff --git a/src/f.py b/src/f.py\n"
        "--- a/src/f.py\n"
        "+++ b/src/f.py\n"
        "@@ -12,0 +13,2 @@\n"
        "+    if x is None:\n"
        "+        raise ValueError(x)\n"
    )
    touched = touched_lines(diff)

    assert is_resolved(Finding("src/f.py", 12, 12, "missing check"), touched) is True
    assert is_resolved(Finding("src/f.py", 40, 40, "elsewhere"), touched) is False


def test_partition_splits_resolved_from_dismissed() -> None:
    findings = [
        Finding("src/ingestproof/reader.py", 43, 43, "fixed one"),
        Finding("src/ingestproof/other.py", 5, 5, "closed without a hunk"),
    ]

    resolved, dismissed = partition(findings, ADDITION)

    assert [f.summary for f in resolved] == ["fixed one"]
    assert [f.summary for f in dismissed] == ["closed without a hunk"]


def test_the_dismissal_section_names_every_dismissed_finding() -> None:
    text = dismissal_section([Finding("src/a.py", 1, 2, "cosmetic")])

    assert "src/a.py:1-2" in text
    assert "cosmetic" in text


def test_the_dismissal_section_is_empty_when_nothing_was_dismissed() -> None:
    assert dismissal_section([]) == ""


# --- The generator, not just the consumer -------------------------------------------
#
# Everything above feeds `partition` a diff written by hand, and none of those diffs can
# see a wrong flag on the command that produces the real one. The previous wave ran every
# invocation form in prompt.md and `--no-renames` survived on line 101, because the diff it
# ran against contained no rename. So these two read the command OUT OF prompt.md and run
# it over a repository built to contain the two shapes the flags decide.

PROMPT = Path(__file__).resolve().parents[2] / "prompt.md"
# Everything between `git diff` and the revision range, however many flags that is --
# including none, so that DELETING a flag is caught by the assertion it weakens rather
# than by this pattern failing to match.
CONTRACT_DIFF = re.compile(
    r"^git diff (?P<flags>[^\n]*)origin/main\.\.\.HEAD > turn\.diff$", re.MULTILINE
)


def _contract_diff_flags() -> list[str]:
    """The flags prompt.md's turn-diff line actually carries.

    The revision range is the one thing substituted below -- a scratch repository has no
    `origin/main`. Everything between `git diff` and the range comes from the contract.
    """
    flags = CONTRACT_DIFF.findall(PROMPT.read_text(encoding="utf-8"))

    assert len(flags) == 1, f"prompt.md carries {len(flags)} turn-diff command lines"

    return flags[0].split()


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ("git", *args), cwd=root, check=True, capture_output=True, text=True
    )
    return out.stdout


def _repo_with_a_rename_and_an_edit(tmp_path: Path) -> Path:
    root = tmp_path / "scratch"
    root.mkdir()
    _git(root, "init", "-q", ".")
    # Pinned rather than inherited: a global autocrlf would rewrite the blob between the
    # two commits and the rename would stop being a pure one. `diff.renames` is NOT pinned
    # -- a machine that has turned it off is a machine where the contract command really
    # does false-resolve, and this test is right to go red there.
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "config", "user.email", "harness@example.invalid")
    _git(root, "config", "user.name", "harness")
    body = "".join(f"line {n}\n" for n in range(1, 41))
    (root / "old.py").write_text(body, encoding="utf-8", newline="\n")
    (root / "edited.py").write_text(body, encoding="utf-8", newline="\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")

    _git(root, "mv", "old.py", "new.py")
    (root / "edited.py").write_text(
        body.replace("line 20\n", "line 20 -- the one real fix\n"),
        encoding="utf-8",
        newline="\n",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "a pure rename, and one line changed elsewhere")
    return root


def _contract_diff(root: Path) -> str:
    return _git(root, "diff", *_contract_diff_flags(), "HEAD~1...HEAD")


def test_the_contract_command_does_not_resolve_a_finding_on_a_renamed_file(
    tmp_path: Path,
) -> None:
    """`--no-renames` on prompt.md's turn-diff line makes req~ac-16~1 fail OPEN.

    Under it a rename is a delete plus a create, and the delete side claims the WHOLE old
    file as touched -- so every finding on a renamed file resolves with nothing fixed.
    Measured on this fixture with a finding at `old.py:25-27` that nothing addresses:
    `--no-renames` resolves it, git's default dismisses it. Put the flag back and this
    goes red.
    """
    root = _repo_with_a_rename_and_an_edit(tmp_path)
    finding = Finding("old.py", 25, 27, "nothing in this diff fixed this")

    resolved, dismissed = partition([finding], _contract_diff(root))

    assert resolved == []
    assert dismissed == [finding]


def test_the_contract_command_resolves_only_the_lines_the_edit_replaced(
    tmp_path: Path,
) -> None:
    """`-U0` on the same line, and it fails open in the same direction.

    A hunk header spans its context, so at git's default `-U3` the one-line change to
    `edited.py:20` reports an old range of 17..23 and a finding three lines away resolves
    untouched. Drop `-U0` from prompt.md and the first assertion below goes red.
    """
    root = _repo_with_a_rename_and_an_edit(tmp_path)
    beside = Finding("edited.py", 17, 17, "three lines above the change")
    on_it = Finding("edited.py", 20, 20, "the line the edit replaced")

    resolved, dismissed = partition([beside, on_it], _contract_diff(root))

    assert resolved == [on_it]
    assert dismissed == [beside]
