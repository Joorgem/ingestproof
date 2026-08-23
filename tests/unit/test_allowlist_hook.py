"""The hook is default-deny inside this repository: it says yes to the set a turn may write
and no to the rest, which is not a list. Both halves are tested, because a hook that says no
to too much is how a lane deadlocks and a hook that says no to too little is how the gate
becomes advice.

The asymmetry is not symmetric, though: this file is installed globally, so a refusal that
is too wide stops work in every other repository on this machine. Too narrow is the cheaper
mistake, but it is not a free one -- CI re-checks the frozen paths, and most of what this
hook refuses is in none of them. The measurement is at the bottom of this file.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools.hooks.ingestproof_allowlist import decide, main

REPO = Path("C:/repo") if Path("C:/").exists() else Path("/repo")
INGESTPROOF = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point LOOP_HOME at an empty directory for every test in this file.

    Without it the suite reads `~/.ingestproof-loop/allowlist.off`, which is the soft
    rollback LOOP.md documents. Touching that file would turn the refusal tests red for an
    environment reason -- and a turn that goes red for an environment reason is exactly the
    INDETERMINATE case spec section 7.5 exists to keep rare.
    """
    monkeypatch.setenv("LOOP_HOME", str(tmp_path / "loop-home"))
    monkeypatch.setenv("INGESTPROOF_REPO", str(REPO))
    yield


def payload(tool: str, path: str, repo: Path = REPO) -> dict[str, object]:
    return {"tool_name": tool, "tool_input": {"file_path": str(repo / path)}}


@pytest.mark.parametrize(
    "path",
    [
        "src/ingestproof/reader.py",
        "tests/unit/test_reader.py",
        "tests/unit/conftest.py",
        "tests/property/test_dialect.py",
        "docs/adoption-dry-run.md",
        "LOOP.md",
    ],
)
def test_the_writable_set_is_allowed(path: str) -> None:
    assert decide(payload("Write", path), REPO) is None


@pytest.mark.parametrize(
    "path",
    [
        "tests/acceptance/test_ac17_clean_slate.py",
        "tests/conftest.py",
        ".spec/acceptance.md",
        "TASKS.md",
        "prompt.md",
        "CLAUDE.md",
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        ".gitattributes",
        "tools/freeze_check.py",
        "tools/hooks/ingestproof_allowlist.py",
        "loop/run_turn.py",
    ],
)
def test_the_frozen_set_is_refused(path: str) -> None:
    assert decide(payload("Write", path), REPO) is not None


@pytest.mark.parametrize("path", ["conftest.py", "pytest.ini", "tox.ini", "setup.cfg"])
def test_the_root_escapes_are_refused_by_name(path: str) -> None:
    # Each of these is default-denied anyway. They are named so the refusal message says
    # WHICH escape was attempted -- the orphan root conftest was measured turning a red
    # acceptance suite green.
    reason = decide(payload("Write", path), REPO)

    assert reason is not None
    assert path in reason
    # The generic refusal interpolates the path too, so `path in reason` alone passes with
    # ROOT_ESCAPES deleted entirely. Measured. This is the phrase only the escape can produce.
    assert "refused at the repository root" in reason


def test_a_test_file_outside_tests_is_refused() -> None:
    assert decide(payload("Write", "src/ingestproof/test_sneaky.py"), REPO) is not None


def test_a_document_whose_name_begins_with_test_is_still_a_document() -> None:
    # Spec section 7.3 names `test_*.py`, not `test_*`. docs/** is writable, and refusing a
    # document there would deadlock the lane for a filename.
    assert decide(payload("Write", "docs/test_plan.md"), REPO) is None


def test_a_path_outside_the_repository_is_none_of_the_hooks_business() -> None:
    # This file is global. The flagship lane runs beside this one and must not be touched.
    other = {"tool_name": "Write",
             "tool_input": {"file_path": str(REPO.parent / "open-payments-lakehouse" / "x.py")}}

    assert decide(other, REPO) is None


def test_a_sibling_whose_name_extends_the_root_is_outside_it() -> None:
    # The single property that keeps every other repository on this machine safe: the scope
    # check compares path COMPONENTS, not string prefixes. Swapping relative_to for a
    # str.startswith left every other test in this file green. Measured.
    sibling = {"tool_name": "Write", "tool_input": {"file_path": str(REPO) + "-notes/TASKS.md"}}

    assert decide(sibling, REPO) is None


def test_a_non_editing_tool_is_ignored() -> None:
    assert decide({"tool_name": "Read", "tool_input": {"file_path": str(REPO / "TASKS.md")}},
                  REPO) is None


def test_a_payload_with_no_file_path_is_ignored() -> None:
    assert decide({"tool_name": "Write", "tool_input": {}}, REPO) is None


def test_a_payload_with_no_tool_input_is_ignored() -> None:
    assert decide({"tool_name": "Write"}, REPO) is None


def test_a_notebook_edit_is_read_from_its_own_key() -> None:
    # NotebookEdit sends `notebook_path`, not `file_path`. Reading only `file_path` would
    # make the hook silently blind to one of the four tools its matcher names.
    frozen = {"tool_name": "NotebookEdit",
              "tool_input": {"notebook_path": str(REPO / "TASKS.md")}}

    assert decide(frozen, REPO) is not None


def test_main_returns_zero_for_an_allowed_write() -> None:
    assert main(json.dumps(payload("Write", "src/ingestproof/a.py"))) == 0


def test_main_returns_two_for_a_refused_write() -> None:
    assert main(json.dumps(payload("Edit", "TASKS.md"))) == 2


def test_main_never_blocks_on_malformed_input() -> None:
    # A hook that crashes on unexpected input blocks every tool call in every project on
    # this machine. Allowing one write it should have refused is the cheaper mistake.
    assert main("not json at all") == 0
    assert main("") == 0
    assert main("[]") == 0


def test_main_fails_open_when_decide_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # The one failure mode with a blast radius beyond this repository. json.loads is not
    # the only thing that can raise: Path.resolve and Path.home both can, on inputs this
    # hook does not choose.
    from tools.hooks import ingestproof_allowlist

    def boom(*_args: object, **_kwargs: object) -> str | None:
        raise RuntimeError("anything at all")

    monkeypatch.setattr(ingestproof_allowlist, "decide", boom)

    assert main(json.dumps(payload("Write", "TASKS.md"))) == 0


def test_the_repository_root_can_be_pointed_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both directions, because asserting only that the old root goes quiet is vacuous: it
    # goes quiet whether the override works or is ignored entirely. Measured.
    other = REPO.parent / "other-clone"
    monkeypatch.setenv("INGESTPROOF_REPO", str(other))

    assert main(json.dumps(payload("Edit", "TASKS.md", other))) == 2
    assert main(json.dumps(payload("Edit", "TASKS.md", REPO))) == 0


def test_the_kill_switch_disables_the_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOP_HOME", str(tmp_path))
    (tmp_path / "allowlist.off").write_text("", encoding="utf-8")

    assert decide(payload("Write", "TASKS.md"), REPO) is None


def test_no_frozen_path_is_writable_by_the_hook() -> None:
    """The hook cannot import tools.freeze_check -- it runs outside the virtualenv -- so it
    cannot read the frozen set it has to stay clear of. This test is what holds the two
    together: it runs in the virtualenv, where the import is free.

    One direction only, and that is the whole check: nothing frozen may be writable here.
    The two lists are not complements, so the other direction has nothing to say.

    It fails the moment a writable prefix widens over a frozen path, which is the drift that
    would let the hook allow what CI then refuses.
    """
    from tools.freeze_check import MANIFEST, frozen_paths

    frozen = sorted({*frozen_paths(INGESTPROOF), MANIFEST})
    assert len(frozen) > 20, "frozen_paths came back near-empty; the check below would be vacuous"

    allowed = [rel for rel in frozen if decide(payload("Write", rel, INGESTPROOF), INGESTPROOF)
               is None]

    assert allowed == []


def test_the_refusal_does_not_call_an_unfrozen_path_frozen() -> None:
    # tests/integration/** is refused here and is in no frozen glob, so CI never sees it.
    # Prose kept calling this path frozen; this is the guard that makes that fail instead.
    reason = decide(payload("Write", "tests/integration/test_x.py"), REPO)

    assert reason is not None
    assert "frozen" not in reason
    assert "not writable by a turn" in reason


def test_ci_does_not_see_most_of_what_this_hook_refuses() -> None:
    """The measurement behind the cost paragraph in docs/allowlist-rollback.md.

    Disarming the hook does not fall back on CI, because CI's gate reads the frozen globs
    and most of these escapes are in none of them. Pinned here so the document cannot drift
    from the mechanism: freezing one of these paths later must fail this test, not go unread.
    """
    from tools.freeze_check import offending_paths

    escapes = ["conftest.py", "pytest.ini", "tox.ini", "setup.cfg",
               "tests/integration/test_x.py", "TASKS.md"]

    refused = [rel for rel in escapes
               if decide(payload("Write", rel, INGESTPROOF), INGESTPROOF) is not None]

    assert refused == escapes
    assert offending_paths(INGESTPROOF, escapes) == ["TASKS.md"]
