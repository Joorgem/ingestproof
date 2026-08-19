from __future__ import annotations

from loop.render_loop_md import HEADER, render


def _entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "seq": 0, "ts": "2026-08-19T12:00:00Z", "task": "T-01",
        "criterion": "req~ac-17~1", "outcome": "GREEN", "diff_lines": 10,
        "cost_usd": 0.1, "pragmas": 0, "author": "human",
        "prev": "0" * 64, "hash": "a" * 64,
    }
    base.update(overrides)
    return base


def test_the_rendering_says_it_is_generated() -> None:
    assert render([]).startswith(HEADER)


def test_it_publishes_the_measured_author_split() -> None:
    # AC-12: the README publishes the MEASURED human/loop division, not a claim about it.
    out = render([
        _entry(author="human"),
        _entry(seq=1, author="loop"),
        _entry(seq=2, author="loop"),
        _entry(seq=3, author="loop-adjudicated"),
    ])

    assert "| human | 1 |" in out
    assert "| loop | 2 |" in out
    assert "| loop-adjudicated | 1 |" in out


def test_it_publishes_the_outcome_split() -> None:
    out = render([_entry(outcome="GREEN"), _entry(seq=1, outcome="RED")])

    assert "| GREEN | 1 |" in out
    assert "| RED | 1 |" in out


def test_it_names_the_ledger_as_the_source_and_carries_the_tip_hash() -> None:
    out = render([_entry(hash="b" * 64)])

    assert "$LOOP_HOME/iterations.jsonl" in out
    assert "b" * 64 in out


def test_an_empty_ledger_renders_without_crashing() -> None:
    assert "Turns: **0**" in render([])
