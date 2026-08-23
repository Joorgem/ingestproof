"""req~ac-07~1 -- the declaration layer runs with no workspace and no JVM.

RED TODAY. `ingestproof.rules` does not exist. Run it on demand with:

    uv run pytest tests/acceptance/test_ac07_declaration_layer_needs_no_jvm.py --runxfail

WHAT THIS FILE DOES NOT ASSERT, said plainly rather than left to be discovered. The
criterion also says corpus layers A and B run in under a minute. Layers A and B are the
differential, which no P1 item in TASKS.md builds -- item 3 builds the rule pairs and
nothing else. A timing assertion over code that does not exist would be a number with no
measurement behind it, so the half of the criterion this file covers is the half item 3
can close: no workspace and no JVM in the declaration layer. The corpus half lands with
the differential.

The no-Spark check runs in a SUBPROCESS. In-process it would be worth nothing: pytest has
already imported this repository's whole test suite by the time any assertion runs, and an
import that happened in another test module is indistinguishable from one that did not
happen at all. The subprocess starts with an empty `sys.modules` and a meta-path finder
that refuses `pyspark` and `py4j` outright -- which is what "with pyspark uninstalled"
means, without uninstalling anything from the environment CI just built.

[utest->req~ac-07~1]
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

MISSING = importlib.util.find_spec("ingestproof.rules") is None

# Applied per test rather than as a module-level `pytestmark`, because one test here is a
# CONTROL that passes today and must go on passing. Under a module-level strict xfail it
# would be reported as XPASS(strict) -- a failure -- and CI would be red for the one test
# in this file that is already right.
needs_rules = pytest.mark.xfail(
    MISSING,
    strict=True,
    reason="P1 item 3 has not landed: ingestproof.rules does not exist",
)

# The banned imports, and everything under them. `py4j` is named alongside `pyspark`
# because it is the gateway that starts the JVM: a module that reaches py4j directly has
# a JVM in the declaration layer whether or not it went through pyspark to get there.
BANNED = ("pyspark", "py4j")

REFUSE_SPARK = f"""
import sys

BANNED = {BANNED!r}


class _Refuse:
    def find_module(self, name, path=None):
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        root = name.split(".")[0]
        if root in BANNED:
            raise ModuleNotFoundError("refused by req~ac-07~1: " + name)
        return None


sys.meta_path.insert(0, _Refuse())
"""

DECLARE_A_RULE = """
from pyspark.sql.functions import col  # noqa -- never reached; see the assertion below
"""

IMPORT_AND_DECLARE = """
import ingestproof.rules as rules

rule = ("id_not_null", lambda column: column.isNotNull())
declared = rules.quality_rules(rule)

assert declared, "quality_rules returned nothing"
assert [name for name, _ in declared] == ["id_not_null"]

leaked = sorted(m for m in sys.modules if m.split(".")[0] in BANNED)
assert leaked == [], "the declaration layer imported " + repr(leaked)
print("OK")
"""


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(body: str) -> subprocess.CompletedProcess[str]:
    # cwd is the repository root because `pythonpath = ["."]` in pyproject is what puts
    # `src` on the path for this project, and a subprocess started anywhere else imports a
    # different `ingestproof` or none at all.
    return subprocess.run(
        [sys.executable, "-c", REFUSE_SPARK + body],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_the_refusal_itself_works() -> None:
    """The control arm, and it is not decoration.

    Without it, `IMPORT_AND_DECLARE` passing would be consistent with a meta-path finder
    that refuses nothing -- a test green because its own guard is inert, which is this
    repository's recurring defect. This arm proves the guard bites.
    """
    result = _run(DECLARE_A_RULE)

    assert result.returncode != 0
    assert "refused by req~ac-07~1: pyspark" in result.stderr


@needs_rules
def test_the_declaration_layer_imports_and_declares_with_spark_refused() -> None:
    result = _run(IMPORT_AND_DECLARE)

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


@needs_rules
def test_a_rule_is_a_name_and_a_callable_and_the_callable_is_not_evaluated() -> None:
    """TASKS item 3: rules are `(name, callable -> Column)` pairs.

    The pair is data. Declaring it must not CALL it -- calling is what needs a Column, and
    a Column is what needs Spark. A rule whose callable ran at declaration time would drag
    the JVM into the declaration layer through a door the subprocess check above cannot
    see, because the import would look identical.
    """
    from ingestproof.rules import quality_rules

    calls: list[object] = []

    def never_called(column: object) -> object:
        calls.append(column)
        return column

    declared = quality_rules(("id_not_null", never_called))

    assert [name for name, _ in declared] == ["id_not_null"]
    assert [callable(fn) for _, fn in declared] == [True]
    assert calls == []
