"""Quality rules as `(name, callable)` pairs. The DEFINITION, and nothing else.

TASKS item 3 says the definition is pure Python and must not import Spark; only the
evaluation touches it. This module is the definition half, and the evaluation half is not
here -- `tests/acceptance/test_ac07_declaration_layer_needs_no_jvm.py` says in its own
words that "item 3 builds the rule pairs and nothing else", and a Spark call written now
would be a line that has never run, frozen the day it was written. That is the defect this
repository already carries once, and writing it a second time to make a sentence true is
not an improvement.

WHAT THIS MODULE CANNOT CHECK, said out loud because it is the criterion rather than a
gap. A rule's callable is declared to return a Column. Checking that would mean CALLING
it, calling it needs a Column, and a Column needs the JVM -- so the check that looks most
obviously worth doing is exactly the one that would drag a workspace into the declaration
layer. `callable(fn)` is therefore where validation stops, on purpose, and
`test_a_rule_is_a_name_and_a_callable_and_the_callable_is_not_evaluated` in the frozen
acceptance file is what holds the line.

The pairs come back as a tuple, in the order they were declared. Order is meaning: an
evaluation layer reports the first rule a record failed, so a set would make the reason
depend on hashing.

[impl->req~ac-07~1]
"""

from __future__ import annotations

from collections.abc import Callable

from ingestproof.contracts import ContractError

type Rule = tuple[str, Callable[..., object]]


def quality_rules(*declared: Rule) -> tuple[Rule, ...]:
    """Judge a rule set at declaration time and return it, calling nothing.

    Refuses at the moment the rules are declared rather than at the moment they are
    evaluated, for the same reason `contracts.declare` does: a malformed rule that only
    fails when a batch runs is a rule that sits in a repository until a batch runs.
    """
    seen: dict[str, int] = {}
    judged: list[Rule] = []

    for position, rule in enumerate(declared):
        if not isinstance(rule, tuple) or len(rule) != 2:
            raise ContractError(
                f"rule {position} is not a (name, callable) pair: {rule!r}"
            )

        name, evaluate = rule

        if not isinstance(name, str) or not name:
            raise ContractError(f"rule {position} has no name: {name!r}")

        if not callable(evaluate):
            raise ContractError(
                f"rule {name!r} is not callable: {evaluate!r}. A rule is a callable this "
                "layer never calls -- calling it needs a Column, and a Column needs the JVM"
            )

        if name in seen:
            raise ContractError(
                f"rule {name!r} is declared twice, at {seen[name]} and {position}: a "
                "quarantined record names the rule that rejected it, and two rules with "
                "one name make that name answer neither"
            )

        seen[name] = position
        judged.append((name, evaluate))

    return tuple(judged)
