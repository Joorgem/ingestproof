"""req~ac-17~1 -- an interrupted turn must not contaminate the next one.

Measured (docs/measurements.md section 7): `git reset --hard` does NOT remove untracked
files. A `conftest.py` left at the root by a dead turn survives into the next one, and it
was verified to turn a RED acceptance suite GREEN -- the exact failure this project's
gates exist to prevent. The rule is `reset --hard` AND `clean -fdx`, with .venv excluded
so the next turn does not pay for a reinstall.

This test asserts both halves: that reset alone is insufficient (so nobody "simplifies"
the runner later), and that reset+clean is sufficient.

The bracketed token below is an OpenFastTrace coverage tag, read by the JAR's tag importer
out of any SOURCE file it traces. Measured: the same brackets in markdown are inert, in
`.spec/` and under `tests/` alike. It is what makes this file the `utest` half of
req~ac-17~1 in `oft-report.txt`; the criterion also Needs `impl`, so it stays a `not ok [`
line reading `(-impl, utest)` until something under `src/`, `loop/` or `tools/` carries
the impl tag.

[utest->req~ac-17~1]
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RESET = ("git", "reset", "--hard")
CLEAN = ("git", "clean", "-fdx", "-e", ".venv")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(args, cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "git", "init", "-b", "main")
    _git(root, "git", "config", "user.email", "test@example.invalid")
    _git(root, "git", "config", "user.name", "test")
    (root / "kept.txt").write_text("tracked\n", encoding="utf-8")
    # The .gitignore is load-bearing, not scenery. `git clean -fd` already removes an
    # untracked directory, so without an IGNORED one in the fixture nothing here would
    # distinguish `-fd` from `-fdx` -- and the real repository's `.hypothesis/` is
    # gitignored, which is exactly the case that needs `-x`.
    (root / ".gitignore").write_text(".hypothesis/\n", encoding="utf-8")
    _git(root, "git", "add", "kept.txt", ".gitignore")
    _git(root, "git", "commit", "-m", "base")
    return root


def test_reset_hard_alone_leaves_the_orphan_conftest_behind(repo: Path) -> None:
    orphan = repo / "conftest.py"
    orphan.write_text("collect_ignore_glob = ['*']\n", encoding="utf-8")

    _git(repo, *RESET)

    assert orphan.exists(), (
        "if this ever passes, `reset --hard` started removing untracked files and the "
        "whole clean-slate rule can be re-derived -- but until then, do not simplify it"
    )


def test_reset_then_clean_removes_a_planted_untracked_file(repo: Path) -> None:
    orphan = repo / "conftest.py"
    orphan.write_text("collect_ignore_glob = ['*']\n", encoding="utf-8")
    stray_dir = repo / ".hypothesis"
    stray_dir.mkdir()
    (stray_dir / "leftover").write_text("x", encoding="utf-8")

    _git(repo, *RESET)
    _git(repo, *CLEAN)

    assert not orphan.exists()
    assert not stray_dir.exists()
    assert (repo / "kept.txt").read_text(encoding="utf-8") == "tracked\n"


def test_clean_without_x_leaves_the_ignored_directory(repo: Path) -> None:
    """The `-x` in CLEAN is load-bearing, and this is the only test that says so.

    `.hypothesis/` is gitignored in the real repository too. Without `-x`, `git clean`
    walks straight past it and a dead turn's cached examples survive into the next one.
    Every other test here passes under `-fd`, so if this one is ever deleted, weakening
    the runner to `-fd` becomes invisible.
    """
    stray_dir = repo / ".hypothesis"
    stray_dir.mkdir()
    (stray_dir / "leftover").write_text("x", encoding="utf-8")

    _git(repo, *RESET)
    _git(repo, "git", "clean", "-fd")  # deliberately without -x

    assert stray_dir.exists(), "-fd spares ignored paths; that is why CLEAN carries -x"


def test_clean_spares_the_virtualenv(repo: Path) -> None:
    venv = repo / ".venv"
    venv.mkdir()
    (venv / "marker").write_text("expensive", encoding="utf-8")
    (repo / "junk.txt").write_text("cheap", encoding="utf-8")

    _git(repo, *RESET)
    _git(repo, *CLEAN)

    assert (venv / "marker").exists(), "-e .venv must survive; reinstalling every turn is the cost"
    assert not (repo / "junk.txt").exists()


def test_the_runner_has_not_weakened_the_clean_slate() -> None:
    from loop import run_turn

    assert run_turn.RESET == RESET
    assert run_turn.CLEAN == CLEAN
