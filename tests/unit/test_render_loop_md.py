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


def test_it_points_at_the_rollback_instructions_rather_than_carrying_them() -> None:
    # The renderer emits a fixed template plus two counts tables; it carries no free text
    # from any entry. So emergency instructions cannot live in the ledger, and cannot live
    # in LOOP.md by hand either -- the next render erases them. A pointer in the template
    # is the part that survives, and this is what keeps it there.
    assert "docs/allowlist-rollback.md" in render([])


def test_a_correcting_row_is_in_the_chain_but_not_in_the_counts() -> None:
    # Two rows, one turn. Counting the correction would publish 2, which is the false
    # headline number this exclusion exists to prevent.
    out = render([_entry(), _entry(seq=1, corrects_seq=0)])

    assert "Turns: **1**" in out
    assert "| human | 1 |" in out
    assert "| GREEN | 1 |" in out


def test_the_tip_is_the_last_row_even_when_that_row_is_a_correction() -> None:
    # The tip anchors the whole chain, not the turns. Excluding corrections from it would
    # quote a hash that no longer matches the file, which is the one thing the tip is for.
    out = render([_entry(hash="a" * 64), _entry(seq=1, corrects_seq=0, hash="b" * 64)])

    assert "b" * 64 in out
    assert "a" * 64 not in out


def test_it_says_the_counts_exclude_corrections() -> None:
    # Same precedent as the rollback pointer: the paragraph is template text, and deleting
    # it left the suite green. A count whose rule is unstated is a count nobody can check.
    assert "in the chain but not in these counts" in render([])
