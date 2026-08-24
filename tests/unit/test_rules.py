"""Unit ring for `ingestproof.rules`.

The frozen acceptance file judges the criterion from outside, in a subprocess with
`pyspark` and `py4j` refused by a meta-path finder. This file judges what that cannot
reach: the refusals, the order, and the no-Spark property read off the module's own
imports rather than off a process that happens not to have imported one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ingestproof import rules as rules_module
from ingestproof.contracts import ContractError
from ingestproof.rules import quality_rules

BANNED_ROOTS = frozenset({"pyspark", "py4j"})


def _imported_roots(source: str) -> set[str]:
    """Every top-level package an `import` in `source` names, at any nesting depth.

    `ast.walk` rather than a line scan, so an import moved inside a function -- which is
    how a lazy Spark seam would be written -- is still visible to this.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_import_check_sees_an_import_hidden_inside_a_function() -> None:
    """The control arm. Without it the test below is green for a checker that finds nothing.

    A lazy Spark seam is written as an import in a function body, so a checker that only
    looked at module level would report clean on exactly the code it exists to catch.
    """
    assert _imported_roots("import pyspark") == {"pyspark"}
    assert _imported_roots("def f():\n    from pyspark.sql import functions") == {"pyspark"}
    assert _imported_roots("def f():\n    import py4j.java_gateway") == {"py4j"}
    assert not _imported_roots("import re").intersection(BANNED_ROOTS)


def test_the_declaration_layer_imports_no_spark_at_any_depth() -> None:
    source = Path(rules_module.__file__).read_text(encoding="utf-8")

    assert _imported_roots(source).isdisjoint(BANNED_ROOTS)


# --- what the module accepts -----------------------------------------------------------


def test_the_pairs_come_back_in_declaration_order_as_a_tuple() -> None:
    # Order is meaning: an evaluation layer reports the FIRST rule a record failed, so a
    # set would make the reason depend on hashing.
    first, second, third = ("a", bool), ("b", bool), ("c", bool)
    declared = quality_rules(third, first, second)

    assert declared == (third, first, second)
    assert isinstance(declared, tuple)


def test_declaring_no_rules_is_not_a_refusal() -> None:
    # A gate with no rules rejects nothing, which is a coherent thing to declare. TASKS
    # item 3 names no guard against it and this module invents none.
    assert quality_rules() == ()


def test_the_callable_is_never_called_at_declaration_time() -> None:
    calls: list[object] = []

    def never_called(*args: object) -> object:
        calls.append(args)
        return args

    declared = quality_rules(("id_not_null", never_called), ("also", never_called))

    assert [name for name, _ in declared] == ["id_not_null", "also"]
    assert calls == []


# --- what it refuses --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "message"),
    (
        (("only",), "not a .name, callable. pair"),
        (("a", bool, "extra"), "not a .name, callable. pair"),
        (["a", bool], "not a .name, callable. pair"),
        (("", bool), "has no name"),
        ((7, bool), "has no name"),
        (("a", "not callable"), "is not callable"),
        (("a", None), "is not callable"),
    ),
    ids=(
        "one-element",
        "three-element",
        "list-not-tuple",
        "empty-name",
        "name-not-a-string",
        "callable-is-a-string",
        "callable-is-none",
    ),
)
def test_a_malformed_rule_is_refused_at_declaration_time(rule: object, message: str) -> None:
    with pytest.raises(ContractError, match=message):
        quality_rules(rule)  # type: ignore[arg-type]


def test_the_refusal_names_the_position_so_a_long_rule_set_is_locatable() -> None:
    with pytest.raises(ContractError, match="rule 2 is not"):
        quality_rules(("a", bool), ("b", bool), ("broken",))  # type: ignore[arg-type]


def test_two_rules_with_one_name_are_refused_and_both_positions_are_named() -> None:
    # A quarantined record names the rule that rejected it. Two rules with one name make
    # that name answer neither, which is a defect discovered from a quarantine table.
    with pytest.raises(ContractError, match="declared twice, at 0 and 2"):
        quality_rules(("dup", bool), ("other", bool), ("dup", bool))


def test_the_same_callable_under_two_names_is_not_a_duplicate() -> None:
    # The name is what a quarantine row carries, so the name is what has to be unique.
    declared = quality_rules(("first", bool), ("second", bool))

    assert [name for name, _ in declared] == ["first", "second"]
