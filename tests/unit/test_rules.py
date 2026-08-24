"""Unit ring for `ingestproof.rules`.

The frozen acceptance file judges the criterion from outside — two of its three tests in a
subprocess with `pyspark` and `py4j` refused by a meta-path finder, and the third
in-process, asserting the callable is never invoked. This file judges what those do not
reach: the refusals, the order, the dunders a caller could use to walk past a guard, and
the no-Spark property read off the package's own imports rather than off a process that
happens not to have imported one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ingestproof import rules as rules_module
from ingestproof.contracts import ContractError
from ingestproof.rules import quality_rules

PACKAGE = Path(rules_module.__file__).parent
FROZEN_AC07 = (
    Path(__file__).resolve().parents[1]
    / "acceptance"
    / "test_ac07_declaration_layer_needs_no_jvm.py"
)


def _frozen_banned() -> tuple[str, ...]:
    """The banned list, READ from the frozen acceptance file rather than copied.

    Copying it would give two sources of truth and the frozen one is authoritative, so if
    that list ever grows this one grows with it. Read rather than imported: pytest imports
    test modules by basename, and importing an acceptance module from a unit module would
    make a second module object for a file pytest has already collected.
    """
    for node in ast.walk(ast.parse(FROZEN_AC07.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "BANNED" for target in node.targets
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("the frozen acceptance file no longer defines BANNED")


IMPORTING_CALLS = ("__import__", "importlib.import_module", "import_module")


def _dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _dotted(node.value) + "." + node.attr
    return ""


def _imported_roots(source: str) -> set[str]:
    """Every top-level package `source` names an import of, at any nesting depth.

    `ast.walk` rather than a line scan, so an import moved inside a function -- which is
    how a lazy Spark seam would be written -- is still visible. `ast.Call` as well as the
    import statements, because `__import__("pyspark")` and `importlib.import_module(...)`
    are imports that no `ast.Import` node records.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])
            else:
                # `from . import pyspark` -- the module is the alias, not `node.module`,
                # which is None for a bare relative import.
                roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Call) and _dotted(node.func) in IMPORTING_CALLS:
            for argument in node.args[:1]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    roots.add(argument.value.split(".")[0])
    return roots


# --- the no-Spark property ---------------------------------------------------------------


def test_the_banned_list_is_read_from_the_frozen_file_and_not_copied() -> None:
    assert _frozen_banned() == ("pyspark", "py4j")


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("import pyspark", "pyspark"),
        ("def f():\n    from pyspark.sql import functions", "pyspark"),
        ("def f():\n    import py4j.java_gateway", "py4j"),
        ("class C:\n    def m(self):\n        import pyspark", "pyspark"),
        ('def f(): return __import__("pyspark")', "pyspark"),
        ('import importlib\ndef f(): importlib.import_module("py4j")', "py4j"),
        ('from importlib import import_module\ndef f(): import_module("pyspark")', "pyspark"),
        ("from . import pyspark", "pyspark"),
    ),
    ids=(
        "module-level",
        "inside-a-function",
        "dotted-inside-a-function",
        "inside-a-method",
        "dunder-import",
        "importlib-dotted",
        "importlib-bare",
        "bare-relative",
    ),
)
def test_the_import_check_finds_every_form_it_claims_to(source: str, expected: str) -> None:
    """The control arm. Without it the scan below is green for a checker that finds nothing.

    A lazy Spark seam is written as an import in a function body, so a checker that only
    looked at module level would report clean on exactly the code it exists to catch.
    """
    assert expected in _imported_roots(source)


@pytest.mark.parametrize(
    "source",
    ('exec("import pyspark")', 'import importlib\nm = "pysp" + "ark"\nimportlib.import_module(m)'),
    ids=("exec", "computed-name"),
)
def test_the_import_check_cannot_see_these_and_the_subprocess_is_what_covers_them(
    source: str,
) -> None:
    """The known limit, pinned so nobody reads the scan as exhaustive.

    A static walk cannot follow a string built at runtime. The frozen acceptance file's
    subprocess catches both, because its meta-path finder refuses at import time however
    the import was spelled.
    """
    assert not _imported_roots(source).intersection(_frozen_banned())


def test_no_module_in_the_shipped_package_imports_spark_at_any_depth() -> None:
    # Every `.py` under `src/ingestproof/`, not just `rules.py`: `rules.py` imports
    # `ingestproof.contracts`, so a lazy Spark import there would be invisible to a
    # one-file scan while still reaching the declaration layer.
    banned = set(_frozen_banned())
    modules = sorted(PACKAGE.glob("*.py"))

    assert [path.name for path in modules] == ["__init__.py", "contracts.py", "rules.py"]

    for path in modules:
        assert _imported_roots(path.read_text(encoding="utf-8")).isdisjoint(banned), path.name


# --- what the module accepts -------------------------------------------------------------


def test_the_pairs_come_back_in_declaration_order_as_a_tuple() -> None:
    first, second, third = ("a", bool), ("b", bool), ("c", bool)
    declared = quality_rules(third, first, second)

    assert declared == (third, first, second)
    assert isinstance(declared, tuple)


def test_the_pairs_are_rebuilt_as_plain_tuples_rather_than_handed_back() -> None:
    """Every check reads the pair through `tuple`'s own slots, so the result must too.

    Returning the caller's object would mean validating one thing and handing back
    another, which answers `__getitem__` to whoever asks next. Without this assertion a
    `return declared` passes every other test in this repository, measured.

    The cost, stated rather than discovered: a rule declared as a NamedTuple comes back
    without its field names.
    """

    class Pair(tuple):  # noqa: SLOT001 -- the point is that a subclass does not survive
        pass

    given = Pair(("a", bool))
    declared = quality_rules(given)

    assert declared == (("a", bool),)
    assert type(declared[0]) is tuple
    assert declared[0] is not given


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


# --- what it refuses ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "message"),
    (
        (("only",), "not a .name, callable. pair"),
        (("a", bool, "extra"), "not a .name, callable. pair"),
        (["a", bool], "not a .name, callable. pair"),
        (("", bool), "has an empty name"),
        ((7, bool), "name that is not a string"),
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
        quality_rules(rule)


def test_the_refusal_names_the_position_so_a_long_rule_set_is_locatable() -> None:
    with pytest.raises(ContractError, match="rule 2 is not"):
        quality_rules(("a", bool), ("b", bool), ("broken",))


def test_two_rules_with_one_name_are_refused_and_both_positions_are_named() -> None:
    with pytest.raises(ContractError, match="declared twice, at 0 and 2"):
        quality_rules(("dup", bool), ("other", bool), ("dup", bool))


def test_the_same_callable_under_two_names_is_not_a_duplicate() -> None:
    # The name is what a quarantine row is expected to carry, so the name is what has to
    # be unique.
    declared = quality_rules(("first", bool), ("second", bool))

    assert [name for name, _ in declared] == ["first", "second"]


def test_the_shape_guard_fires_before_the_duplicate_guard() -> None:
    # Pinned so a reordering refactor cannot silently change every message a user reads.
    with pytest.raises(ContractError, match="is not callable"):
        quality_rules(("dup", bool), ("dup", "not callable"))


# --- the dunders a caller could use to walk past a guard ---------------------------------


class _LyingLength(tuple):  # noqa: SLOT001
    def __len__(self) -> int:
        return 2


class _NeverEqual(str):
    def __eq__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return str.__hash__(self)


class _LooksNonEmpty(str):
    def __len__(self) -> int:
        return 1


class _SpoofsItsClass:
    @property  # type: ignore[misc]
    def __class__(self) -> type:  # type: ignore[override]
        return tuple

    def __len__(self) -> int:
        return 2

    def __iter__(self) -> object:
        return iter(("spoofed", bool))


def test_a_caller_supplied_dunder_cannot_walk_past_a_guard() -> None:
    """Measured on the version that asked the object about itself, all four got through.

    `len(x)`, `not x`, `isinstance(x, tuple)` and `x in seen` each dispatch to code the
    CALLER wrote. A tuple subclass reporting `__len__` of 2 for three elements escaped as
    a `ValueError` -- not even a `ContractError`; a `str` subclass reporting `__len__` of
    1 got an EMPTY name accepted; a `str` subclass answering False to `__eq__` put two
    rules named `dup` through the duplicate guard; and an object with a `__class__`
    property was accepted as a tuple it is not, running three of its dunders on the way.
    """
    with pytest.raises(ContractError, match="not a .name, callable. pair"):
        quality_rules(_LyingLength(("a", bool, "extra")))

    with pytest.raises(ContractError, match="declared twice"):
        quality_rules((_NeverEqual("dup"), bool), (_NeverEqual("dup"), bool))

    with pytest.raises(ContractError, match="has an empty name"):
        quality_rules((_LooksNonEmpty(""), bool))

    with pytest.raises(ContractError, match="not a .name, callable. pair"):
        quality_rules(_SpoofsItsClass())


def test_no_refusal_runs_the_repr_of_a_caller_supplied_object() -> None:
    """The criterion, reached through the error path rather than the happy one.

    An f-string `{x!r}` CALLS `x.__repr__`. The realistic trigger is not exotic: it is
    `("id_not_null", F.col("id").isNotNull())` -- a Column where a lambda belongs, which
    is the mistake `callable()` exists to catch. Formatting that refusal would call
    `Column.__repr__`, which in pyspark is a py4j round trip, so the layer would need the
    JVM to explain why it does not need the JVM.
    """
    ran: list[str] = []

    class Recording:
        def __repr__(self) -> str:
            ran.append("repr")
            return "<recording>"

    class RecordingName(str):
        def __repr__(self) -> str:
            ran.append("repr-name")
            return "<recording-name>"

    for bad in (Recording(), ("name", Recording()), (RecordingName(""), bool)):
        with pytest.raises(ContractError):
            quality_rules(bad)

    assert ran == []


def test_a_metaclass_cannot_reach_the_refusal_through_the_type_name_either() -> None:
    """The same defect one level up, and the reason `_describe` names types the long way.

    `type(value).__name__` looks like a plain attribute read and is not: a metaclass may
    define `__name__` as a property. Measured on the version that used it -- the property
    ran while a refusal was being formatted, and one that raises replaced ContractError
    with the caller's RuntimeError.
    """
    ran: list[str] = []

    class RecordingMeta(type):
        @property
        def __name__(cls) -> str:  # noqa: N805 -- a metaclass property takes the class
            ran.append("name")
            return "Innocent"

    class Recorded(metaclass=RecordingMeta):
        pass

    class ExplodingMeta(type):
        @property
        def __name__(cls) -> str:  # noqa: N805
            raise RuntimeError("the caller's metaclass exploded")

    class Exploded(metaclass=ExplodingMeta):
        pass

    with pytest.raises(ContractError, match="not a .name, callable. pair"):
        quality_rules(Recorded())

    with pytest.raises(ContractError, match="not a .name, callable. pair"):
        quality_rules(Exploded())

    assert ran == []


def test_a_repr_that_raises_does_not_replace_the_refusal_with_the_callers_exception() -> None:
    # A guard that raises the caller's exception instead of ContractError is a guard that
    # did not guard: a caller writing `except ContractError` never sees the refusal.
    # Measured on the previous version, both of these came out as RuntimeError.
    class Exploding:
        def __repr__(self) -> str:
            raise RuntimeError("the caller's repr exploded")

    with pytest.raises(ContractError):
        quality_rules(Exploding())

    with pytest.raises(ContractError):
        quality_rules(("name", Exploding()))
