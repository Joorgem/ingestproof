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

IT ASKS `tuple` AND `str`, NEVER THE OBJECT ABOUT ITSELF. `len(x)`, `not x`,
`isinstance(x, tuple)`, `x in seen` and `f"{x!r}"` all dispatch to code the CALLER wrote,
which is the one thing a layer whose promise is "no JVM here" must not do. Measured on the
version that used them: an object whose `__repr__` raised replaced `ContractError` with
the caller's own exception, so a caller catching `ContractError` never saw the refusal --
a guard that does not guard; a `tuple` subclass reporting `__len__` of 2 for three
elements escaped as `ValueError`; a `str` subclass reporting `__len__` of 1 got an EMPTY
name accepted; and a `str` subclass whose `__eq__` answers False put two rules named `dup`
straight through the duplicate guard. Every check below therefore goes through the base
type's own slot, and `_describe` names a value without running its `__repr__`.

The realistic trigger is not exotic. It is `("id_not_null", F.col("id").isNotNull())` --
a Column where a lambda belongs, which is the mistake `callable()` exists to catch. That
Column is not callable, so the refusal formats it, and `Column.__repr__` in pyspark is a
py4j round trip: the layer would need the JVM to explain why it does not need the JVM.

The pairs come back as a tuple, in the order they were declared, and rebuilt as PLAIN
tuples. Rebuilding is not tidiness: every check above reads the pair through `tuple`'s own
slots, so returning the caller's object would mean validating one thing and handing back
another, which answers `__getitem__` to whoever asks next. The cost is that a rule
declared as a NamedTuple comes back without its field names.

Order is preserved because an evaluation layer that reported which rule rejected a record
would name the first one that did -- there is no evaluation layer yet, and nothing in
`.spec/acceptance.md` fixes that semantics, so this is a design intent rather than a
measured fact.

[impl->req~ac-07~1]
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ingestproof.contracts import ContractError

type Rule = tuple[str, Callable[..., object]]


def _as_pair(value: object) -> tuple[object, ...]:
    """Read a value through `tuple`'s own slots, after `type(value)` proved it is one."""
    return cast("tuple[object, ...]", value)


def _describe(value: object) -> str:
    """Name a value in a refusal without running code the caller wrote.

    An exact `str` is safe to `repr`, because the slot reached is `str`'s own.

    Everything else is named by its type -- through `type`'s OWN `__name__` descriptor
    rather than through `type(value).__name__`, because a METACLASS may define `__name__`
    as a property. Measured: such a property ran during a refusal, and one that raises
    replaced `ContractError` with the caller's `RuntimeError`. That is the same
    guard-that-does-not-guard the `!r` interpolations caused, one level up the type
    hierarchy, and it is why "does not run its `__repr__`" was too narrow a promise.
    """
    if type(value) is str:
        return repr(value)
    return "<" + cast("str", type.__dict__["__name__"].__get__(type(value))) + ">"


def quality_rules(*declared: object) -> tuple[Rule, ...]:
    """Judge a rule set at declaration time and return it, calling nothing.

    Refuses at the moment the rules are declared rather than at the moment they are
    evaluated, for the same reason `contracts.declare` does: a malformed rule that only
    fails when a batch runs is a rule that sits in a repository until a batch runs.

    THE PARAMETER IS `object` ON PURPOSE. Annotating it `Rule` told mypy that six of the
    seven malformed shapes below cannot arrive -- measured -- and the body then spent
    twenty-five lines refusing them, so the signature advertised a precondition the
    function did not believe and every test had to lie to the checker to reach a guard.
    This is a system boundary: the frozen acceptance file calls it from inside a
    `python -c`, and the consumer is a notebook. Wide in, narrow out.
    """
    judged: list[Rule] = []
    names: list[str] = []

    for position, rule in enumerate(declared):
        # `cast` rather than `# type: ignore`: the line above it PROVES the type, by a
        # route mypy cannot follow, and a cast says which type was proved. The `or`
        # short-circuits, so the cast is only reached once `type(rule)` is a tuple.
        if not issubclass(type(rule), tuple) or tuple.__len__(_as_pair(rule)) != 2:
            raise ContractError(
                f"rule {position} is not a (name, callable) pair: {_describe(rule)}"
            )

        pair = _as_pair(rule)
        raw_name = tuple.__getitem__(pair, 0)
        evaluate = tuple.__getitem__(pair, 1)

        if not issubclass(type(raw_name), str):
            raise ContractError(
                f"rule {position} has a name that is not a string: {_describe(raw_name)}"
            )

        name = cast("str", raw_name)

        if str.__len__(name) == 0:
            raise ContractError(f"rule {position} has an empty name")

        if not callable(evaluate):
            raise ContractError(
                f"rule {_describe(name)} is not callable: {_describe(evaluate)}. A rule is "
                "a callable this layer never calls -- calling it needs a Column, and a "
                "Column needs the JVM"
            )

        # A list scan with `str.__eq__` rather than a dict: `in` and `[]` on a set or a
        # dict run the caller's `__hash__` and `__eq__`, and a `str` subclass answering
        # False to both put two rules named `dup` through. Rule sets are a handful per
        # table, so the quadratic scan costs nothing measurable.
        for earlier, earlier_name in enumerate(names):
            if str.__eq__(earlier_name, name) is True:
                raise ContractError(
                    f"rule {_describe(name)} is declared twice, at {earlier} and "
                    f"{position}: a quarantine row is expected to name the rule that "
                    "rejected a record, and two rules under one name make that name "
                    "answer neither"
                )

        names.append(name)
        judged.append((name, evaluate))

    return tuple(judged)
