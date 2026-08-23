"""Spec section 7.5 gives a turn four outcomes, and the interesting one is
INDETERMINATE -- v1 defined it as 'the diff did not touch production code' without ever
defining production code, which is a get-out-of-jail card. Here it is a closed set:
docs/** and LOOP.md, and nothing else.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from loop.run_turn import (
    CLEAN,
    RESET,
    STALL_LIMIT,
    classify,
    clean_slate,
    diff_is_documentation_only,
    stall_report,
    turns_since_close,
)


def test_a_passing_turn_is_green() -> None:
    assert classify(
        tests_passed=True, timed_out=False, changed_paths=["src/ingestproof/x.py"],
        test_was_green_before=False,
    ) == "GREEN"


def test_a_failing_turn_that_touched_src_is_red() -> None:
    assert classify(
        tests_passed=False, timed_out=False, changed_paths=["src/ingestproof/x.py"],
        test_was_green_before=True,
    ) == "RED"


def test_a_failing_turn_that_touched_only_docs_is_indeterminate() -> None:
    assert classify(
        tests_passed=False, timed_out=False,
        changed_paths=["docs/design.md", "LOOP.md"], test_was_green_before=False,
    ) == "INDETERMINATE"


def test_docs_plus_one_source_file_is_still_red() -> None:
    # The whole point: "mostly docs" is not docs.
    assert classify(
        tests_passed=False, timed_out=False,
        changed_paths=["docs/design.md", "src/ingestproof/x.py"],
        test_was_green_before=False,
    ) == "RED"


def test_an_empty_diff_that_fails_is_indeterminate() -> None:
    # Nothing changed and it went red: the environment moved. That is the case
    # section 7.5 says must stop and call, and INDETERMINATE is what stops it.
    assert classify(
        tests_passed=False, timed_out=False, changed_paths=[], test_was_green_before=True,
    ) == "INDETERMINATE"


def test_a_timeout_on_a_green_test_whose_diff_is_docs_only_is_indeterminate() -> None:
    # The spec's "sob o mesmo codigo": green before AND the code did not move.
    assert classify(
        tests_passed=False, timed_out=True, changed_paths=["docs/design.md"],
        test_was_green_before=True,
    ) == "INDETERMINATE"


def test_a_hang_introduced_in_src_does_not_escape_as_indeterminate() -> None:
    # The escape the guard closes. Convert a failure into an infinite loop against a green
    # baseline and, without the diff check, the turn is never undone.
    assert classify(
        tests_passed=False, timed_out=True, changed_paths=["src/ingestproof/x.py"],
        test_was_green_before=True,
    ) == "TIMEOUT"


def test_any_other_timeout_is_a_timeout() -> None:
    assert classify(
        tests_passed=False, timed_out=True, changed_paths=["src/ingestproof/x.py"],
        test_was_green_before=False,
    ) == "TIMEOUT"


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["docs/a.md"], True),
        (["LOOP.md"], True),
        (["docs/a.md", "LOOP.md"], True),
        ([], True),
        (["docsy/a.md"], False),
        (["tests/unit/test_x.py"], False),
        (["src/ingestproof/__init__.py"], False),
    ],
)
def test_documentation_only_is_a_closed_set(paths: list[str], expected: bool) -> None:
    assert diff_is_documentation_only(paths) is expected


def test_clean_slate_removes_the_planted_orphan(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ("git", "init", "-b", "main"),
        ("git", "config", "user.email", "t@example.invalid"),
        ("git", "config", "user.name", "t"),
    ):
        subprocess.run(args, cwd=repo, check=True, capture_output=True)
    (repo / "kept.txt").write_text("x", encoding="utf-8")
    subprocess.run(("git", "add", "-A"), cwd=repo, check=True, capture_output=True)
    subprocess.run(("git", "commit", "-m", "base"), cwd=repo, check=True, capture_output=True)
    (repo / "conftest.py").write_text("collect_ignore_glob = ['*']\n", encoding="utf-8")

    clean_slate(repo)

    assert not (repo / "conftest.py").exists()
    assert (repo / "kept.txt").exists()


def test_the_runner_uses_the_literals_the_frozen_acceptance_test_pins() -> None:
    assert RESET == ("git", "reset", "--hard")
    assert CLEAN == ("git", "clean", "-fdx", "-e", ".venv")


def _e(seq: int, closed: str | None = None) -> dict[str, object]:
    entry: dict[str, object] = {
        "seq": seq, "task": f"T-{seq}", "criterion": "req~ac-01~1", "outcome": "GREEN",
    }
    if closed:
        entry["closed_criterion"] = closed
    return entry


def test_an_empty_ledger_has_not_stalled() -> None:
    assert turns_since_close([]) == 0
    assert stall_report([]) is None


def test_turns_are_counted_back_to_the_last_close() -> None:
    entries = [_e(0, "req~ac-17~1"), _e(1), _e(2), _e(3)]

    assert turns_since_close(entries) == 3


def test_a_close_on_the_last_turn_resets_the_count() -> None:
    entries = [_e(0), _e(1), _e(2), _e(3, "req~ac-01~1")]

    assert turns_since_close(entries) == 0


def test_below_the_limit_the_loop_keeps_going() -> None:
    assert stall_report([_e(i) for i in range(STALL_LIMIT - 1)]) is None


def test_at_the_limit_the_loop_stops_and_says_what_it_tried() -> None:
    report = stall_report([_e(i) for i in range(STALL_LIMIT)])

    assert report is not None
    assert "STOPPED" in report
    assert f"T-{STALL_LIMIT - 1}" in report
    assert "human's decision" in report


def test_an_empty_closed_criterion_does_not_count_as_a_close() -> None:
    # "" is what a harness bug writes when the traceability report came back empty.
    entries = [_e(0, "req~ac-17~1"), {"seq": 1, "task": "T-1", "closed_criterion": ""}]

    assert turns_since_close(entries) == 1


def _repo_with_hook_source(tmp_path: Path, body: bytes) -> Path:
    repo = tmp_path / "repo"
    (repo / "tools" / "hooks").mkdir(parents=True)
    (repo / "tools" / "hooks" / "ingestproof_allowlist.py").write_bytes(body)
    return repo


def test_a_turn_refuses_to_start_when_the_installed_hook_has_drifted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loop import run_turn

    repo = _repo_with_hook_source(tmp_path, b"the tested copy")
    installed = tmp_path / "installed.py"
    installed.write_bytes(b"a DIFFERENT copy")
    monkeypatch.setattr(run_turn, "INSTALLED_HOOK", installed)

    with pytest.raises(RuntimeError, match="drifted"):
        run_turn.assert_hook_installed(repo)


def test_a_turn_refuses_to_start_when_the_hook_was_never_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The likelier of the two: a fresh machine, or a ~/.claude restored from a backup.
    from loop import run_turn

    repo = _repo_with_hook_source(tmp_path, b"the tested copy")
    monkeypatch.setattr(run_turn, "INSTALLED_HOOK", tmp_path / "nowhere.py")

    with pytest.raises(RuntimeError, match="not installed"):
        run_turn.assert_hook_installed(repo)


def test_a_turn_accepts_an_installed_hook_that_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loop import run_turn

    repo = _repo_with_hook_source(tmp_path, b"same bytes")
    installed = tmp_path / "installed.py"
    installed.write_bytes(b"same bytes")
    monkeypatch.setattr(run_turn, "INSTALLED_HOOK", installed)

    run_turn.assert_hook_installed(repo)  # must not raise


def _correction(seq: int) -> dict[str, object]:
    return {"seq": seq, "task": "T-x", "outcome": "GREEN", "corrects_seq": 0}


def test_a_correcting_row_does_not_count_as_a_stalled_turn() -> None:
    # A row that fixes a number is not a turn that closed nothing. Counting it would walk
    # the loop toward its own stall limit for doing bookkeeping.
    entries = [_e(0, "req~ac-17~1"), _e(1), _correction(2), _e(3)]

    assert turns_since_close(entries) == 2


def test_the_stall_report_lists_the_turns_it_counted() -> None:
    # The headline counts turns, so the list under it must be turns. A correction sitting
    # in the slice would push a real turn out of a report someone is reading to find out
    # why the loop stopped.
    entries = [_e(i) for i in range(STALL_LIMIT)] + [_correction(STALL_LIMIT)]

    report = stall_report(entries)

    assert report is not None
    assert f"STOPPED: {STALL_LIMIT} consecutive turns" in report
    assert "T-x" not in report
    assert f"T-{STALL_LIMIT - 1}" in report
