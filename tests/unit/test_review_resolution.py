"""Spec section 7.10: a turn may mark a review finding resolved only when its own diff
touched the file and the line range the finding cites. Without that, closing the thread
and fixing the code look the same from outside.
"""
from __future__ import annotations

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


def test_an_addition_hunk_reports_its_new_side_lines() -> None:
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
