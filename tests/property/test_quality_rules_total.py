"""`quality_rules` is total, and it never calls what it is judging.

The unit ring pins each refusal one at a time. What it cannot say is that there is no
THIRD outcome -- a rule set that is neither refused nor returned unchanged, or one that
gets refused after the callable has already run. Both are the shapes that would let the
JVM into the declaration layer through a door the acceptance file's subprocess cannot see,
because the import would be identical either way.

So the property is stated as an exhaustive disjunction: for any sequence of candidates,
`quality_rules` either raises `ContractError` or returns exactly `tuple(candidates)` --
and `calls == []` on BOTH branches, including the one that raised.

The `ci` profile is derandomised, so the corpus is fixed by this function's cleaned
source. `@example` decorators are stripped before hashing and are the safe way to pin a
case the draws are unlikely to reach on their own -- measured last turn, 200 draws will
not find a specific needle, so a pin is not decoration.

[utest->req~ac-07~1]
"""

from __future__ import annotations

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from ingestproof.contracts import ContractError
from ingestproof.rules import quality_rules

# Five shapes, one per branch `quality_rules` has: well formed, too short, too long, a
# second element that is not callable, and a list where a tuple is required. The name is
# drawn separately so a duplicate can arise across any two of them.
SHAPE = st.sampled_from(("ok", "one", "three", "not-callable", "not-tuple"))
SPEC = st.lists(st.tuples(SHAPE, st.text(max_size=6)), max_size=6)


def _build(spec: list[tuple[str, str]], probe: object) -> list[object]:
    built: list[object] = []
    for shape, name in spec:
        if shape == "ok":
            built.append((name, probe))
        elif shape == "one":
            built.append((name,))
        elif shape == "three":
            built.append((name, probe, name))
        elif shape == "not-callable":
            built.append((name, name))
        else:
            built.append([name, probe])
    return built


@example(spec=[("ok", "dup"), ("ok", "dup")])
@example(spec=[("ok", "")])
@example(spec=[("ok", "a"), ("not-callable", "b")])
@example(spec=[])
@given(spec=SPEC)
def test_quality_rules_either_refuses_or_returns_unchanged_and_calls_nothing(
    spec: list[tuple[str, str]],
) -> None:
    calls: list[object] = []

    def probe(*arguments: object) -> object:
        calls.append(arguments)
        return arguments

    built = _build(spec, probe)

    try:
        declared = quality_rules(*built)  # type: ignore[arg-type]
    except ContractError:
        # The refusal path is the one where a call would be easiest to miss: the exception
        # is what the caller sees, so a callable invoked on the way to raising leaves no
        # trace anywhere else.
        assert calls == []
        return

    assert declared == tuple(built)
    assert calls == []


def test_the_property_above_reaches_both_branches() -> None:
    """Otherwise the disjunction is satisfied by a function that only ever raises.

    A `try/except/return` property is vacuous if one arm is unreachable, and nothing in
    the property itself can tell. This is the arm-coverage check, stated over the four
    pinned cases rather than over the draws.
    """
    probe = bool

    assert quality_rules(*_build([], probe)) == ()
    assert quality_rules(*_build([("ok", "a")], probe)) == (("a", probe),)

    for refused in ([("ok", "dup"), ("ok", "dup")], [("ok", "")], [("not-tuple", "a")]):
        with pytest.raises(ContractError):
            quality_rules(*_build(refused, probe))  # type: ignore[arg-type]
