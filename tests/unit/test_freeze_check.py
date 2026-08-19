from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.freeze_check import (
    _changed_since,
    frozen_globs,
    frozen_paths,
    hash_file,
    offending_paths,
    verify,
    write_manifest,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(args, cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    # A real git repository, because frozen_paths enumerates through `git ls-files`
    # rather than walking the filesystem. Testing it against a bare directory would
    # exercise a code path that does not exist.
    _git(tmp_path, "git", "init", "-b", "main")
    _git(tmp_path, "git", "config", "user.email", "test@example.invalid")
    _git(tmp_path, "git", "config", "user.name", "test")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "frozen.txt").write_text(
        "# a comment\n\ntools/frozen.txt\npyproject.toml\ntests/acceptance/**\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "tests" / "acceptance").mkdir(parents=True)
    (tmp_path / "tests" / "acceptance" / "test_a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_b.py").write_text("y = 2\n", encoding="utf-8")
    _git(tmp_path, "git", "add", "-A")
    _git(tmp_path, "git", "commit", "-m", "base")
    return tmp_path


def test_comments_and_blank_lines_are_not_globs(fake_repo: Path) -> None:
    assert frozen_globs(fake_repo) == ["tools/frozen.txt", "pyproject.toml", "tests/acceptance/**"]


def test_globs_expand_to_real_files_and_exclude_the_writable_ones(fake_repo: Path) -> None:
    assert frozen_paths(fake_repo) == [
        "pyproject.toml",
        "tests/acceptance/test_a.py",
        "tools/frozen.txt",
    ]


def test_a_fresh_manifest_verifies_clean(fake_repo: Path) -> None:
    write_manifest(fake_repo)

    assert verify(fake_repo) == []


def test_editing_a_frozen_file_is_reported(fake_repo: Path) -> None:
    write_manifest(fake_repo)
    (fake_repo / "tests" / "acceptance" / "test_a.py").write_text("x = 2\n", encoding="utf-8")

    assert verify(fake_repo) == ["tests/acceptance/test_a.py"]


def test_deleting_a_frozen_file_is_reported(fake_repo: Path) -> None:
    write_manifest(fake_repo)
    (fake_repo / "pyproject.toml").unlink()

    assert verify(fake_repo) == ["pyproject.toml"]


def test_adding_a_file_under_a_frozen_glob_is_reported(fake_repo: Path) -> None:
    write_manifest(fake_repo)
    (fake_repo / "tests" / "acceptance" / "test_c.py").write_text("z = 3\n", encoding="utf-8")

    assert verify(fake_repo) == ["tests/acceptance/test_c.py"]


def test_a_diff_touching_a_frozen_path_is_offending(fake_repo: Path) -> None:
    changed = ["src/ingestproof/__init__.py", "tests/acceptance/test_a.py"]

    assert offending_paths(fake_repo, changed) == ["tests/acceptance/test_a.py"]


def test_a_diff_touching_the_manifest_itself_is_offending(fake_repo: Path) -> None:
    # The self-reference case: without it, one pull request can rewrite the guard and the
    # thing it guards at the same time.
    assert offending_paths(fake_repo, ["tools/frozen.txt"]) == ["tools/frozen.txt"]


def test_a_diff_that_only_touches_writable_paths_is_clean(fake_repo: Path) -> None:
    assert offending_paths(fake_repo, ["src/a.py", "tests/unit/test_b.py", "LOOP.md"]) == []


def test_a_deleted_frozen_path_still_counts_as_offending(fake_repo: Path) -> None:
    # git reports deletions in --name-only too, and a deleted acceptance test is the most
    # valuable thing an agent could remove.
    assert offending_paths(fake_repo, ["tests/acceptance/test_deleted.py"]) == [
        "tests/acceptance/test_deleted.py"
    ]


def test_the_hash_is_over_bytes_not_text(fake_repo: Path) -> None:
    crlf = fake_repo / "crlf.bin"
    lf = fake_repo / "lf.bin"
    crlf.write_bytes(b"a\r\nb\r\n")
    lf.write_bytes(b"a\nb\n")

    assert hash_file(crlf) != hash_file(lf)


def test_diff_mode_reads_the_repository_at_root_not_the_caller_cwd(
    fake_repo: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `--root` is only honest if the git invocation carries cwd=root. Standing in a
    # DIFFERENT repository is the only way to tell the two apart: without cwd=root the
    # function reports the caller's changes and never looks at `root` at all.
    (fake_repo / "tests" / "acceptance" / "test_a.py").write_text("x = 99\n", encoding="utf-8")
    _git(fake_repo, "git", "add", "-A")
    _git(fake_repo, "git", "commit", "-m", "touch a frozen path")

    caller = tmp_path_factory.mktemp("caller_repo")
    _git(caller, "git", "init", "-b", "main")
    _git(caller, "git", "config", "user.email", "test@example.invalid")
    _git(caller, "git", "config", "user.name", "test")
    (caller / "unrelated.py").write_text("a = 1\n", encoding="utf-8")
    _git(caller, "git", "add", "-A")
    _git(caller, "git", "commit", "-m", "base")
    (caller / "unrelated.py").write_text("a = 2\n", encoding="utf-8")
    _git(caller, "git", "add", "-A")
    _git(caller, "git", "commit", "-m", "an unrelated change the gate must not report")
    monkeypatch.chdir(caller)

    assert _changed_since("HEAD~1", fake_repo) == ["tests/acceptance/test_a.py"]
