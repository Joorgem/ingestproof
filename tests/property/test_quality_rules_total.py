"""`quality_rules` is total, and it never calls what it is judging.

The unit ring pins each refusal one at a time. What it cannot say is that there is no
THIRD outcome -- a rule set that is neither refused nor returned unchanged, or one that
gets refused after the callable has already run. So the property is an exhaustive
disjunction: for any sequence of candidates, `quality_rules` either raises `ContractError`
or returns exactly `tuple(candidates)` -- with `calls == []` on BOTH arms, including the
one that raised, because on the refusal path the exception is all a caller ever sees.

WHAT THIS STRUCTURALLY CANNOT CATCH, said here so it is not read as wider than it is: an
UNDER-strict validator. A guard that stops refusing something lands in the "returns
exactly tuple(candidates)" arm, which this property accepts -- measured, deleting the
`callable` guard leaves this file green. Every refusal is pinned in the unit ring for that
reason. This property is about the SHAPE of the outcome, not about which shapes are
refused.

THE `ci` PROFILE FIXES THE SEED, NOT THE CORPUS, and here that is not academic.
`derandomize=True` makes the seed a hash of this function's cleaned source. But Hypothesis
6.165 also harvests string constants out of the local modules a session has imported and
injects them into strategies, so the same test, same seed, same profile draws a DIFFERENT
corpus depending on what else was imported. Measured on this file's strategy: fingerprint
`ec1acdc1...` on its own, `9b8b2013...` with `ingestproof.rules` imported first.

That is why the pins below are not decoration, and it is not the reason the previous
version of this docstring gave. Measured: the sort mutant -- `tuple(sorted(judged))` for
`tuple(judged)` -- was killed by this property when the file ran ALONE and SURVIVED it
under `uv run pytest`, which is the scope CI runs. In that scope no drawn spec was ever
accepted carrying two differently-named rules, so `declared == tuple(built)` had no
ordering to disagree with. The two- and three-rule pins put it back, and with them the
mutant dies in the full ring.

`@example` decorators are stripped by `_clean_source` before the digest, so adding a pin
costs no re-draw. Editing a statement in the function below does.

[utest->req~ac-07~1]
"""

from __future__ import annotations

from hypothesis import example, given
from hypothesis import strategies as st

from ingestproof.contracts import ContractError
from ingestproof.rules import quality_rules

# Five shapes: well formed, too short, too long, a second element that is not callable,
# and a list where a tuple is required. They are NOT one per refusal branch -- the first
# three all reach the pair-shape guard, and the name and duplicate guards are reached
# through the separately drawn name rather than through a shape.
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


# THE ACCEPT ARM, and these pins are the whole of it. Measured under the inner ring's
# import scope: of 204 executions, 200 refused and 4 accepted -- two of them the EMPTY
# rule set and two carrying a single rule. So the half of the disjunction that pins
# behaviour ran twice, trivially, and never with two names to put in an order.
@example(spec=[("ok", "a"), ("ok", "b"), ("ok", "c")])
@example(spec=[("ok", "z"), ("ok", "a")])
@example(spec=[("ok", "a")])
@example(spec=[])
# The refusal arm. The draws reach every guard on their own -- measured, 129 pair-shape,
# 44 callable, 15 name, 5 duplicate over 200 -- so these three are cheap insurance
# against a re-drawn corpus rather than the only way in.
@example(spec=[("ok", "dup"), ("ok", "dup")])
@example(spec=[("ok", "")])
@example(spec=[("ok", "a"), ("not-callable", "b")])
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
        declared = quality_rules(*built)
    except ContractError:
        assert calls == []
        return

    assert declared == tuple(built)
    assert calls == []
