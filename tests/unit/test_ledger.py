"""The ledger's job is to be un-editable in a way that leaves no trace. These tests are
the whole argument for the design, so they test the tampering, not just the happy path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.ledger import GENESIS, LedgerTampered, append, entry_hash, read_all, verify_chain


def _turn(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ts": "2026-08-19T12:00:00Z",
        "task": "T-01",
        "criterion": "req~ac-17~1",
        "outcome": "GREEN",
        "diff_lines": 42,
        "cost_usd": 0.31,
        "pragmas": 0,
        "author": "human",
    }
    base.update(overrides)
    return base


def test_the_first_entry_chains_to_genesis(tmp_path: Path) -> None:
    ledger = tmp_path / "iterations.jsonl"

    written = append(_turn(), path=ledger)

    assert written["seq"] == 0
    assert written["prev"] == GENESIS
    assert written["hash"] == entry_hash(written)


def test_each_entry_chains_to_the_previous_one(tmp_path: Path) -> None:
    ledger = tmp_path / "iterations.jsonl"

    first = append(_turn(), path=ledger)
    second = append(_turn(outcome="RED", author="loop"), path=ledger)

    assert second["seq"] == 1
    assert second["prev"] == first["hash"]
    verify_chain(read_all(ledger))


def test_editing_an_entry_in_place_breaks_the_chain(tmp_path: Path) -> None:
    ledger = tmp_path / "iterations.jsonl"
    append(_turn(outcome="RED"), path=ledger)
    append(_turn(), path=ledger)

    entries = read_all(ledger)
    entries[0]["outcome"] = "GREEN"  # the edit a turn would want to make
    ledger.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in entries) + "\n", encoding="utf-8"
    )

    with pytest.raises(LedgerTampered):
        verify_chain(read_all(ledger))


def test_deleting_an_entry_from_the_middle_breaks_the_chain(tmp_path: Path) -> None:
    ledger = tmp_path / "iterations.jsonl"
    append(_turn(), path=ledger)
    append(_turn(outcome="RED"), path=ledger)
    append(_turn(), path=ledger)

    entries = read_all(ledger)
    del entries[1]
    ledger.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in entries) + "\n", encoding="utf-8"
    )

    with pytest.raises(LedgerTampered):
        verify_chain(read_all(ledger))


def test_truncating_the_tail_is_survivable_but_appending_after_it_is_not(tmp_path: Path) -> None:
    # Truncation alone cannot be detected from the file itself -- nothing outside it
    # remembers how long it was. What IS detectable: the entry appended afterwards
    # chains to the surviving tail, so the SHA of any entry quoted earlier (in LOOP.md,
    # in a PR body, in the README's measured split) no longer appears anywhere.
    ledger = tmp_path / "iterations.jsonl"
    append(_turn(), path=ledger)
    dropped = append(_turn(outcome="RED"), path=ledger)

    ledger.write_text(
        json.dumps(read_all(ledger)[0], sort_keys=True) + "\n", encoding="utf-8"
    )
    resumed = append(_turn(), path=ledger)

    verify_chain(read_all(ledger))  # the truncated file is internally consistent
    assert resumed["prev"] != dropped["hash"]


def test_an_entry_without_an_author_is_refused(tmp_path: Path) -> None:
    # AC-12 publishes the measured human/loop split. An entry that may omit `author`
    # makes that number a guess.
    record = _turn()
    del record["author"]

    with pytest.raises(ValueError, match="author"):
        append(record, path=tmp_path / "iterations.jsonl")


def test_appending_onto_a_tampered_ledger_is_refused(tmp_path: Path) -> None:
    ledger = tmp_path / "iterations.jsonl"
    append(_turn(outcome="RED"), path=ledger)
    entries = read_all(ledger)
    entries[0]["outcome"] = "GREEN"
    ledger.write_text(json.dumps(entries[0], sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(LedgerTampered):
        append(_turn(), path=ledger)


def test_the_default_location_is_outside_any_work_tree(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOOP_HOME", str(tmp_path / "elsewhere"))
    from loop.ledger import ledger_path

    assert ledger_path() == tmp_path / "elsewhere" / "iterations.jsonl"
