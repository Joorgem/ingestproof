"""req~ac-18~1 -- the audit report lands in a Unity Catalog table, owner and grant declared.

The criterion, verbatim (`.spec/acceptance.md:213-214`): "The report is written to a Unity
Catalog table (`<catalog>.<schema>.<table>`), with owner and grant declared in the bundle
YAML." `Ring: nightly` (line 216), `Needs: impl, utest` (line 218).

RED TODAY. `ingestproof.audit` does not exist, and `ingestproof.contracts` carries
`job_resource` (line 239) and `job_yaml` (line 265) but neither `audit_table` nor
`table_resource`. The two commands that show it:

    uv run pytest -m nightly \
        tests/acceptance/test_ac18_the_audit_report_lands_in_a_unity_catalog_table.py
    uv run pytest --runxfail -m nightly \
        tests/acceptance/test_ac18_the_audit_report_lands_in_a_unity_catalog_table.py

The first reports `xfailed` and CI stays green; the second makes the markers inert and
reports the real failure. `-m nightly` is required in BOTH, and that is not decoration:
`pyproject.toml`'s `addopts` is `-m 'not external and not nightly'`, so a plain
`uv run pytest` deselects this whole file by construction. `--strict-markers` is on and
`nightly` is declared in `pyproject.toml`'s `markers`, so the module-level marker below is
neither a typo nor optional -- without it this file lands in the inner ring, where
`CLAUDE.md`'s ring table says there is no JVM, no Spark and no network.

NOTHING HERE IMPORTS `ingestproof.audit`, AT MODULE SCOPE OR ANYWHERE OUTSIDE A TEST BODY,
AND THAT IS A RULE ABOUT THE INNER RING RATHER THAN ABOUT THIS CRITERION. Deselection
happens AFTER collection: `-m nightly` does not stop this module from being imported by
every plain `uv run pytest` anyone runs. So whatever this module executes at import, the
inner ring pays -- and if it throws, the inner ring does not merely slow down, it takes the
whole acceptance directory down as a collection error. `TASKS.md` row 1 names a module-scope
`pyspark` import as the mistake to avoid, and this file will not be the thing that finds
out. `importlib.util.find_spec` answers whether a module is importable
WITHOUT importing it, and that is why all seven of the other frozen files use it and none of
them imports the module it is waiting for.

WHAT THE MARKER FOR ROW 3 READS, AND WHY IT IS NOT THE MODULE. `ingestproof.audit` holding
SOMETHING is not the same fact as row 3 having landed: a module half-written -- a docstring,
a constant, an import block, a `# TODO` -- exists without `audit_rows` existing. Under a
module-keyed marker that state turns row 3's strict xfail inert while `audit_rows` is still
missing, and the nightly goes red for work nobody dispatched -- which `classify` reads as
RED and which undoes an otherwise good turn.

An earlier round of this file made that argument differently, and the difference is now
recorded rather than quietly dropped: it said the module was ALSO where the Spark writer
belonged, so it could exist with a writer in it and no `audit_rows`. That is no longer the
plan. The owner ruled that everything touching Spark goes to `ingestproof.spark` and that
`ingestproof.audit` holds `audit_rows` alone, which is what makes `TASKS.md` row 3's "Pure
Python; no Spark import" a property of a MODULE rather than a promise about a function. The
predicate below is unchanged, because the half-written module was always the larger of the
two reasons and is the one that survives. So the marker asks the question it actually
means: does row 3's deliverable exist. `find_spec` hands back a spec whose `origin` is the
module's path, and the predicate READS that file rather than importing it. The never-import
discipline above is untouched; what changes is only what is being asked.

THIS IS A SEVENTH PATTERN AND IT IS DECLARED RATHER THAN LEFT TO BE DISCOVERED. Measured:
six of the SEVEN other frozen files that carry an xfail key it on `find_spec(...) is None`
and nothing finer -- `test_ac01`, `test_ac02a`, `test_ac03`, `test_ac04`, `test_ac07` and
`test_ac09` alike. The seventh is `test_ac08a`, which lands beside this file and is the one
counterexample: its markers key on an AST binding walk, on `hasattr`, and on a path
existing, which is exactly the "finer" this sentence excludes.

Of the three `hasattr` calls elsewhere in `tests/acceptance/`, two are
assertions inside test bodies (`test_ac03:198`, `test_ac04:199`) and the third is a marker
key: `test_ac08a:226`'s `_module_lacks`, which lands in the SAME COMMIT as this file and
copies this pattern deliberately. So this file is not the only one keying a marker on an
attribute -- it is the first, and its sibling is the second, and the paragraph below says
why the machinery is duplicated rather than shared. Module presence is a PROXY for "the
deliverable landed", and it is an exact proxy in all six of those files because each waits
on a module that does not exist yet and arrives whole. It is not exact here, for the reason
above, and this file is the only
one that needs the difference.

WHICH WAY THE PREDICATE ERRS, AND WHY THAT WAY. THERE IS NO SAFE DIRECTION HERE, and an
earlier draft of this docstring claimed there was. Under `strict=True` both errors end red,
measured: a false PRESENT lets the test run and it fails with an ImportError naming what is
missing; a false ABSENT xfails a case that would have passed, and strict reports that as
`[XPASS(strict)]` -- red as well, but red at a distance from its cause.

The choice is therefore between two reds, and it was made on which is likelier and which is
legible. False present is much the likelier shape -- every way of half-writing this module
produces one -- and its message names the missing thing at the import line. So the predicate
reads BINDINGS and errs toward present within them: a `def`, a class, an assignment, an
import alias, at any depth, and a star-import too, because one can bind anything.

What it does NOT count is prose, and that distinction was measured rather than assumed: a
first version of this predicate asked only whether the name appeared anywhere in the source,
and a writer module whose DOCSTRING mentioned `audit_rows` read as present and turned the
case red -- the exact failure this predicate exists to prevent, arriving through the
predicate itself. A `# TODO: audit_rows goes here` in a half-written writer is not an exotic
shape.

There is one state in which a false absent is worse than red rather than merely distant, and
it is the reason the direction matters at all: if the implementation is ALSO wrong, the test
fails under an active xfail and is reported `xfailed`, which is green. Measured -- a
re-export binding the name only through `globals()`, over a deliberately broken
`audit_rows`, gives `5 passed, 1 xfailed` and nothing anywhere says so. That combination is
the only way this file can hide work, and the limits below bound it.

It answers ABSENT in four cases, and all four are states in which the import would genuinely
fail: no spec at all, `find_spec` raising (`ImportError` for a missing parent, `ValueError`
for a `sys.modules` entry with no `__spec__`), a spec with no `origin` -- a namespace package,
which defines nothing -- and a file that cannot be read. None of them raises at collection.
A file that does not PARSE falls back to the substring, because such a module cannot be
imported at all and a visible red is the better answer than a silent xfail.

WHERE EACH OF THE THREE SUBJECTS LIVES, because the answer is what lets each queue row
close on its own turn. `audit_rows` is `ingestproof.audit`, keyed by `find_spec` and never
imported here. `audit_table` and `table_resource` are both ATTRIBUTES of
`ingestproof.contracts`, which every ring already imports, so asking whether they exist
costs the inner ring nothing new and each keeps a condition of its own.

That `audit_table` is declared in `contracts` rather than beside `audit_rows` is not
filing. `contracts` is this package's DECLARATION module and the base of its import graph
-- measured: `dialect`, `rules` and `promotion` all import from it and it imports nothing
from `ingestproof` at all -- and it already answers what a thing is called and how it is
declared: `TableContract`, `declare`, `job_resource`, `job_yaml`, and `table_resource` by
row 5's own instruction. Naming the audit table is that same question, and it needs nothing
`contracts` does not already hold. Turning a `Report` into rows is not: it is computation
over a result, `TASKS.md:86` (row 3) fixes that name, and it stays where the queue put it.

And it puts `audit_table` behind a guard that already exists. `src/ingestproof/rules.py:54`
imports `contracts`, and `test_ac07_declaration_layer_needs_no_jvm.py` imports `rules` in a
SUBPROCESS with a meta-path finder refusing `pyspark` and `py4j` outright, then asserts
neither leaked into `sys.modules`. So a module-scope Spark import added to `contracts` --
the exact creep `TASKS.md` row 1 warns about -- turns an existing frozen test red.
`ingestproof.audit` inherits no such guard from this file, and under the owner's ruling it
does not need one from here: the module that imports Spark is `ingestproof.spark`, and
nothing in this file names it.

The alternative was measured and rejected. With `audit_table` in `ingestproof.audit`, rows
3 and 4 share one condition -- an attribute cannot be seen without executing the module --
so a turn landing row 3 alone reds row 4's case, reds its own inner ring, and `classify`
returns RED and undoes the turn. Row 3 would not be closable as a standalone turn, and
`prompt.md` has a turn take the first unclosed item and do only that. A frozen file that
forced two rows into one turn would contradict the frozen queue it exists to gate.

THE MARKERS ARE CONDITIONAL, STRICT, AND PER TEST. Conditional: the moment the module or
the attribute a case needs exists, that case's marker evaporates and the nightly runs it
for real -- nobody has to remember to remove it, and nobody could, this file being frozen.
Strict: a case that passes while its subject is still missing is passing for a reason that
has nothing to do with the criterion, and that is reported as a failure.

PER TEST rather than as a module-level `pytestmark`, for the reason
`test_ac03_damage_is_located_by_record_and_field.py` and
`test_ac07_declaration_layer_needs_no_jvm.py` both record in those words: the two controls
at the bottom of this file pass TODAY and must go on passing. Under a module-level strict
xfail they are reported XPASS(strict) -- a failure -- and the nightly is red for the two
tests here that are already right.

Every import of the code under test is INSIDE a test function or a one-module helper. At
module level a missing module is a collection error, and a collection error is red no
matter what a marker says.

HOW THE CASES LINE UP WITH THE QUEUE, because both files are frozen and can only be fixed
together (`TASKS.md:86-88`, rows 3 to 5):

    row 3, "the denominator case"        -> test_the_denominator_reaches_the_rows_...
                                            test_a_clean_batch_leaves_a_row_...
    row 4, "the three-level-name case"   -> test_the_report_is_addressed_by_a_three_...
    row 5, whole test green              -> test_owner_and_grant_are_declared_...
                                            test_the_table_the_report_goes_to_is_the_...
                                            and the two controls

Row 4 names one case and gets one test under the row's own word. Row 3 names one case and
gets two, because the owner ruled in round 4 that a clean batch leaves a row: the denominator
reaching the rows and the denominator reaching them WHEN THERE IS NO DAMAGE are the same
requirement over disjoint inputs, they are both `audit_rows`, and one turn delivers both.

Row 5's cell does not name a case -- it says "`req~ac-18~1` covered and its acceptance
test green" -- so row 5 owns everything else in this file, which is what makes it the
row that closes the criterion whole.

THE OWNER-AND-GRANT CASE ASSERTS AGAINST WHAT THE EMITTER RETURNS, never against a file on
disk, and this is a constraint the queue imposes rather than a preference
(`TASKS.md:234-241`). The criterion's own text says "declared in the bundle YAML" and says
nothing about that YAML being committed; the committed-file requirement lives in
`req~ac-08a~1` (`.spec/acceptance.md:101-102`), which names the bundle directory
explicitly. A case here that opened a committed path would make row 5 -- a `loop` row --
depend on row 6, a human's, and the phase deadlocks with nothing noticing until the stall
brake fires. So no path under the bundle directory appears anywhere in this file, and
`TASKS.md:247-254` asks for a unit test that mechanically holds this file to that, and
`tests/unit/test_ac18_asserts_the_emitter_not_the_committed_bundle.py` is it.

THE NEGATIVE CONTROL IS `job_resource`, AND IT IS THE RIGHT ONE FOR THIS CRITERION. What
this file has to be able to say is "this resource declares no owner and no grant" -- and
an assertion that cannot say NO is the defect this repository was founded on. The control
has to be a real bundle resource out of the same emitter, in the same YAML subset, built
from the same declaration, differing in exactly the property the criterion names. There is
one already in the tree and it is `job_resource`: measured over the declaration below, it
carries ten distinct keys -- `resources`, `jobs`, `incidents`, `name`, `parameters`,
`default`, `tags` and the three `ingestproof_` tags -- and none of them is `owner` and none
begins with `grant`. A hand-built dict would not do the same work: it would be a
counterexample this file invented, and the emitter could then grow an owner-shaped hole
this file never sees.

WHAT THAT CONTROL DOES AND DOES NOT CATCH, said with the measurement rather than left to
sound stronger than it is. It does NOT catch a substring sweep: measured, the strings
`owner`, `own` and `grant` appear nowhere in `job_yaml`'s output for this declaration, so a
sweep over the text would come back empty here too. What it catches is a search that never
consults the key -- the inert guard this repository keeps finding. Measured: the same walk
with its predicate ignored yields 13 values out of this one resource, and the two emptiness
assertions in the control are what make that visible instead of silently green.

WHAT THIS FILE DOES NOT ASSERT, AND THE QUESTION THAT IS OPEN. The criterion says the
report IS WRITTEN TO a Unity Catalog table. Whether that demands a real write -- a session,
a table created, rows read back -- is not settled by anything in the tree: the ring is
nightly, the nightly has no credential and no workspace, and the sentence that scopes "no
credential and no workspace" belongs to `req~ac-08a~1` and not to this criterion. It is the
repository owner's call, and it is not made here.

So what is here is the half that holds under either answer: the rows the report becomes,
the name the write is addressed by, and the owner and grant the bundle declares -- all of
it pure Python, all of it true whether or not a session ever opens. What is NOT here is the
write itself. If the owner rules that a real write is demanded, the nearest place for it is
the nightly Spark case in
`test_ac08a_the_check_runs_inside_spark_against_local_delta.py`, which is unwritten, is a
human's commit in the same batch as this one, and is the only file in the frozen set that
will already have a session and a local Delta table in hand. Read that as the nearest place
and not as a solution: what a local open-source Delta session can observe is a write
ADDRESSED by a three-level name into a local catalog. A Unity Catalog write needs a
metastore, and `req~ac-08a~1` puts its own ring explicitly beyond one. That is a
consequence for the owner to weigh, not a question this file answers.

[utest->req~ac-18~1]
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import pathlib
import re
from collections.abc import Callable, Iterator, Mapping

import pytest

pytestmark = pytest.mark.nightly

def _binds(source: str, name: str) -> bool:
    """Does `source` bind `name` -- as a definition, an assignment or an import?

    By PARSE and never by substring, so a mention in a comment or a docstring does not count
    as a landing. Measured, and it is why this is not the one-line version: a writer module
    whose docstring merely said `audit_rows` read as present under a substring test and
    turned row 3's case red while row 3 was still undispatched.

    Bindings ANYWHERE rather than at module level only, because a name bound inside a
    `try` or an `if` is a shape optional dependencies produce, and reading that as absent
    would xfail a case that would have passed. A star-import counts for the same reason --
    it can bind anything, so it cannot be read as a refusal. Neither choice is the "safe"
    one; see the module docstring for why erring toward present is the one taken.

    A file that does not parse cannot be imported either, so the substring fallback keeps
    that red visible. Measured, and it is the one input whose exception is not the one a
    reader expects: a NUL byte in the source raises SyntaxError on 3.12 -- "source code
    string cannot contain null bytes" -- and not the ValueError older Pythons raised, so
    `except SyntaxError` is what covers it and nothing escapes at collection.

    KNOWN LIMITS, EACH ONE MEASURED AGAINST THIS FILE RATHER THAN REASONED ABOUT.

    Reads PRESENT while the import still fails, and every one of them gives a plain
    `1 failed` with a legible message: `audit_rows: int`, because an annotation binds
    nothing at runtime; `audit_rows = None`; a binding local to a function, a comprehension
    or a class body; and `import audit_rows`, which names a module rather than this
    function. Only one of the five is plausible in practice -- the
    `try: from ... import audit_rows` / `except ImportError: audit_rows = None`
    placeholder -- and it gives the same `1 failed`.

    Reads ABSENT while the name is really reachable, which is narrower than it looks. A
    PEP 562 lazy module that re-imports by name inside `__getattr__` reads PRESENT and
    passes (`6 passed`), because the import alias is a binding. What remains is a re-export
    that binds the name only through `globals()` or a module-level `exec`. That is
    contrived, and it lands as `[XPASS(strict)]` -- unless the implementation is also
    wrong, which is the silent case the module docstring names.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return name in source
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return True
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id == name:
                return True
        elif isinstance(node, ast.alias) and (node.asname or node.name.split(".")[0]) in (
            name,
            "*",
        ):
            return True
    return False


def _source_lacks(module: str, name: str) -> bool:
    """True while `module` is missing, or its source binds no `name`. Never imports it.

    WITHOUT IMPORTING IT, and that is the whole constraint. See the module docstring: this
    module is executed by every plain `uv run pytest`, deselection or not, so importing the
    module under test here would put whatever it imports into the inner ring's collection,
    and an import that throws is a collection error rather than a slow test. That the module
    is meant to stay Spark-free does not make the import safe: this predicate has to hold
    while the module is HALF WRITTEN, which is the only state in which it is ever consulted.

    `find_spec` gives back a spec whose `origin` is the module's path (measured: an absolute
    `.py` for a plain module and the package's `__init__.py` for a package), so the file can
    be read without being run.

    `find_spec` raises rather than returning for two inputs -- `ImportError` when a parent
    package is missing, `ValueError` for a module sitting in `sys.modules` with a `__spec__`
    of None -- and neither may become a collection error, so both answer ABSENT. So does a
    spec with no `origin`, which is a namespace package and defines nothing, and so does a
    file that cannot be read. All four are states in which the import would fail anyway.
    """
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        return True
    if spec is None or spec.origin is None:
        return True
    try:
        source = pathlib.Path(spec.origin).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    return not _binds(source, name)


# ONE MORE REASON NOT TO IMPORT IT, AND IT IS RUFF RATHER THAN SPARK. Measured with this
# repository's own ruff 0.14: `ingestproof` resolves first-party through `[tool.ruff].src`,
# but a module that does not exist yet is classified THIRD-party -- so a function importing
# `ingestproof.audit` and `ingestproof.contracts` in one block is I001 today (ruff wants a
# blank line between the sections) and I001 again the day `audit` lands, with the blank line
# it just demanded now being the defect. A frozen file cannot answer both. No function below
# imports both, and nothing here should be edited into one that does.
AUDIT_ROWS_MISSING = _source_lacks("ingestproof.audit", "audit_rows")


def _contracts_lacks(name: str) -> bool:
    """True while `ingestproof.contracts` is missing, or is there and lacks `name`.

    An attribute cannot be seen without executing the module, so this one does import --
    and it is confined to `ingestproof.contracts` for that reason. That module has existed
    since P1, every ring already imports it, and it imports nothing heavier than `re` and
    `unicodedata`, so asking costs the inner ring nothing it was not already paying.
    Keyed on the module alone instead, row 5's marker would already be inert and the
    nightly already red for work no turn has been dispatched to do.
    """
    if importlib.util.find_spec("ingestproof.contracts") is None:
        return True
    return not hasattr(importlib.import_module("ingestproof.contracts"), name)


needs_audit_rows = pytest.mark.xfail(
    AUDIT_ROWS_MISSING,
    strict=True,
    reason="P3 row 3 has not landed: no ingestproof.audit source defines audit_rows",
)

needs_audit_table = pytest.mark.xfail(
    _contracts_lacks("audit_table"),
    strict=True,
    reason="P3 row 4 has not landed: ingestproof.contracts.audit_table does not exist",
)

needs_table_resource = pytest.mark.xfail(
    _contracts_lacks("table_resource"),
    strict=True,
    reason="P3 row 5 has not landed: ingestproof.contracts.table_resource does not exist",
)

needs_both = pytest.mark.xfail(
    _contracts_lacks("audit_table") or _contracts_lacks("table_resource"),
    strict=True,
    reason="P3 rows 4 and 5 have not both landed",
)

BATCH_ID = "2026-08-26T00:00:00Z"
CONTRACT_ID = "incidents@1"

# TWO DAMAGES, AND EVERY NUMBER BELOW IS CHOSEN SO NOTHING CAN BE MISTAKEN FOR ANYTHING.
# The denominator case finds the column carrying the denominator by looking for its VALUE,
# so no other integer a row could plausibly carry may collide with it: not a field index,
# and not the number of damages. Hence indices of 7, 9, 11 and 13, denominators of 40 and
# 22, and a damage count of 2 -- pairwise distinct, and none of them derivable from
# another. Two damages rather than one because one cannot tell a row PER DAMAGE from a
# single aggregated row, and "one damage out of N" is this repository's founding defect
# arriving in the thing that reports it.
DAMAGES = (
    (7, 9, "EXTRA", None),
    (11, 13, "say hi, bye", "say hi"),
)
DENOMINATOR = 40
OTHER_DENOMINATOR = 22
LONE_DENOMINATOR = 6
# The clean batch's denominator, and it obeys the same rule as the three above: pairwise
# distinct from every other integer any row here could plausibly carry -- the denominators,
# the four indices, the damage counts 2 and 1, and the row count 1 -- because the column is
# found by its VALUE and a collision would be a false pass rather than a false failure.
CLEAN_DENOMINATOR = 31

# The shape of one part of a Unity Catalog name, and it is an ALLOWLIST rather than a list
# of characters to refuse -- a denylist admits whatever it forgot, and what it forgets is
# the interesting part: a semicolon, a quote, a comma, a star, a pipe, a NUL. This is the
# same expression `contracts.PLAIN_KEY` requires of a key it will emit bare, and that is
# the point of borrowing it: a table name outside this shape is one the bundle emitter
# would have to quote, and a name that needs quoting to survive the YAML is not a name this
# criterion should be closing over.
NAME_PART = re.compile(r"\A[A-Za-z_][A-Za-z0-9_-]*\Z")


def _one_declaration():
    """The single declaration the criterion's `<catalog>.<schema>.<table>` comes out of.

    `declare` is deliberately NOT called: it registers into a process-wide mapping and
    refuses to rebind an id, and nothing in this file needs the registry. The same shape
    `test_ac01_one_declaration.py` uses, so a reader comparing the two files is comparing
    the same declaration.
    """
    from ingestproof.contracts import TableContract

    return TableContract(
        name="incidents",
        contract_id=CONTRACT_ID,
        staging="main.staging.incidents",
        bronze="main.bronze.incidents",
        quarantine="main.quarantine.incidents",
        landing_mode="append",
        prefix="incidents_",
        constraints=(("id_not_null", "id IS NOT NULL"),),
    )


def _damages():
    """The two damages above, as the dataclass `req~ac-03~1` already defines."""
    from ingestproof.report import Damage

    return tuple(
        Damage(record_index=record, field_index=field, expected=expected, actual=actual)
        for record, field, expected, actual in DAMAGES
    )


def _a_report(records_compared: int, how_many: int = len(DAMAGES)):
    """`how_many` damages found in `records_compared` records.

    `Report` is `TASKS.md` row 3's own word for what becomes rows, and P2 row 5 fixes which
    class that is: "`Report`: the damages plus `records_compared`". A `Differential` carries
    both of those attributes too, so an implementation that reads attributes rather than
    matching on a type serves both without this file having to say so.
    """
    from ingestproof.report import Report

    return Report(damages=_damages()[:how_many], records_compared=records_compared)


def _leaves(node: object) -> Iterator[object]:
    """Every value that is not a container, at any depth."""
    if isinstance(node, Mapping):
        for value in node.values():
            yield from _leaves(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _leaves(item)
    else:
        yield node


def _values_under(node: object, matches: Callable[[str], bool]) -> Iterator[object]:
    """Every value whose KEY satisfies `matches`, at any depth.

    By key and never by substring over the emitted text, because a value, a table named
    `owner_audit` and a tag would all answer a text sweep. The predicate is the whole of
    the discrimination, so the control at the bottom of this file is what shows it is
    consulted at all.
    """
    if isinstance(node, Mapping):
        for key, value in node.items():
            if isinstance(key, str) and matches(key):
                yield value
            yield from _values_under(value, matches)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _values_under(item, matches)


def _is_a_three_level_table_name(candidate: object) -> bool:
    """The criterion's `<catalog>.<schema>.<table>`, and nothing that merely looks like it.

    Three parts, each one an identifier. The path characters fall out of the allowlist
    rather than being listed: a slash, a colon and a backslash are not in `NAME_PART`, and
    neither is anything else nobody thought to forbid.
    """
    if not isinstance(candidate, str):
        return False
    parts = candidate.split(".")
    return len(parts) == 3 and all(NAME_PART.match(part) for part in parts)


def _columns_holding(rows: list, wanted: object) -> set[str]:
    """The column names under which `wanted` appears, across `rows`."""
    return {key for row in rows for key, value in row.items() if value == wanted}


# --- row 3: the denominator case ---------------------------------------------------------


@needs_audit_rows
def test_the_denominator_reaches_the_rows_as_a_count_and_not_as_a_rate() -> None:
    """`TASKS.md` row 3: a fixed column set carrying `records_compared`.

    Why a count and not a rate is the criterion's business at all: `req~ac-05~1` exists
    because published figures reuse a denominator from a different experiment, and
    `src/ingestproof/report.py` records the same defect measured inside this library --
    a Report claiming ONE DAMAGE OUT OF ZERO RECORDS COMPARED. A row that stored a rate
    would put that class of citation back on the far side of the table, where nothing here
    can reach it.

    THE COLUMN IS FOUND BY ITS VALUE, not by a name this file invents. Two reports with the
    same damages and different denominators must produce rows in which the SAME column
    carries 40 and 22 -- which a row set that dropped the denominator cannot do, and a row
    set that stored 0.05 and 0.09 cannot do either. Names are then held only to containing
    the obvious word, so `records_compared` and the `_records_compared` spelling that would
    match `contracts.BATCH_ID_COLUMN`'s underscore convention both pass, a column called
    `n` does not, and a `_batch_id` column holding the CONTRACT id does not either.

    AND THE DAMAGES HAVE TO ARRIVE. Without the last two blocks, rows carrying nothing but
    a batch id, a contract id and a denominator satisfy every other assertion here -- a
    perfectly shaped table of reports that report nothing. One row per damage is asserted
    here only for reports that HAVE damages. What a clean batch writes is the next test's,
    and it is answered rather than left open -- see there for the owner's ruling and why the
    ruling had to be made before this file froze.
    """
    from ingestproof.audit import audit_rows

    over_forty = list(audit_rows(_a_report(DENOMINATOR), BATCH_ID, CONTRACT_ID))
    over_twenty_two = list(audit_rows(_a_report(OTHER_DENOMINATOR), BATCH_ID, CONTRACT_ID))
    lone = list(audit_rows(_a_report(LONE_DENOMINATOR, how_many=1), BATCH_ID, CONTRACT_ID))

    assert over_forty, "audit_rows produced no rows at all"
    assert all(isinstance(row, Mapping) for row in over_forty + over_twenty_two + lone)

    # A fixed column set: one shape across every call, not one shape per report.
    shapes = {frozenset(row) for row in over_forty + over_twenty_two + lone}

    assert len(shapes) == 1, f"the column set is not fixed: {shapes}"

    carrying_forty = _columns_holding(over_forty, DENOMINATOR)
    carrying_twenty_two = _columns_holding(over_twenty_two, OTHER_DENOMINATOR)

    assert carrying_forty, f"no column carries the denominator {DENOMINATOR}"
    assert carrying_forty == carrying_twenty_two, (
        f"the denominator is not carried by one fixed column: {carrying_forty} then "
        f"{carrying_twenty_two}"
    )
    assert any("records_compared" in name for name in carrying_forty), carrying_forty

    # The two arguments reach the rows, each under a column named for the one it holds. A
    # row that cannot be joined back to its batch and its contract is a row the table
    # cannot be read by, and a pair of columns holding each other's value is worse: it
    # reads correctly and joins wrongly.
    holding_batch = _columns_holding(over_forty, BATCH_ID)
    holding_contract = _columns_holding(over_forty, CONTRACT_ID)

    assert any("batch" in name for name in holding_batch), holding_batch
    assert any("contract" in name for name in holding_contract), holding_contract

    # One row per damage, and every damage located in one of them.
    assert len(over_forty) == len(DAMAGES), over_forty
    assert len(over_twenty_two) == len(DAMAGES), over_twenty_two
    assert len(lone) == 1, lone

    for damage in _damages():
        located = {damage.record_index, damage.field_index, damage.expected}

        assert any(located <= set(row.values()) for row in over_forty), (damage, over_forty)


@needs_audit_rows
def test_a_clean_batch_leaves_a_row_and_the_denominator_reaches_it() -> None:
    """A `Report` with no damage becomes exactly one row. THE OWNER RULED THIS IN ROUND 4.

    It had to be ruled before this file froze, and that is the whole reason it is a case
    rather than a note. Round 3 left a clean batch UNCONSTRAINED and said so in as many
    words; but `tests/acceptance/**` is frozen, so "unconstrained" does not mean "decided
    later by whoever thinks about it hardest". It means the first turn to write `audit_rows`
    decides it alone, in passing, with no reviewer -- and after that the decision cannot be
    corrected without a human commit on a frozen path.

    THE RULING IS YES, AND THE REASON IS THE CRITERION'S OWN. `req~ac-18~1` exists so a
    count is never published as a rate, and `TASKS.md` row 3 gives the mechanism in one
    clause: "so the denominator reaches the table". A clean batch HAS a denominator -- it is
    the number of records that were compared and found intact -- and a table that writes a
    row only when something broke never receives it. Worse, such a table cannot tell
    "verified and clean" from "never verified": both are the absence of a row, and the
    absence of a row is exactly what a check that never ran also produces. A table that only
    records failure does not prove it looked.

    SO THE ASYMMETRY IS DELIBERATE: one row per damage, and one row for no damage at all.
    Zero damages does not mean zero rows. The test above asserts the first half over reports
    that HAVE damages; this one asserts the second, and the two together are what make the
    row count readable -- `len(rows)` is the damage count everywhere except at zero, where
    it is one, and the row itself says which.

    WHAT IS ASSERTED, AND WHY EACH PIECE IS NOT THE OTHERS. Exactly one row, because "at
    least one" is satisfied by a row per record compared and that is a different table. The
    same fixed column set as the damaged calls, because a clean batch landing in a shape of
    its own is two tables sharing a name, and nothing downstream could read both. The
    denominator under the SAME column the damaged calls use, found by its value exactly as
    above -- a clean row carrying its denominator somewhere new is a denominator that did
    not reach the table's denominator column. And the batch and the contract, because a row
    that cannot be joined back is a row nobody queries.

    AND IT DOES NOT CLAIM A DAMAGE, which is the assertion that keeps the ruling honest.
    The cheapest way to satisfy everything above is to return the one-damage row set with
    the damage fields left holding whatever they held -- a clean batch reported as damage,
    which is worse than the silence this case exists to end. So wherever the one-damage call
    put a damage's locator, the clean row is required to carry something ELSE. What that
    something is stays open on purpose: a null, an empty string, a zero and a dedicated
    `outcome` column all pass, and choosing between them is a schema decision this criterion
    does not make. The measured columns are asserted non-empty first, so the check cannot go
    green by finding nothing to compare -- the inert guard this repository keeps catching.

    WHAT THIS CASE STILL LETS THROUGH, said rather than left to be discovered. A clean row
    and a damaged row that differ only in a column carrying something incidental -- a
    timestamp, a row id -- pass, because this file cannot name the column that means
    "clean" without inventing the schema it refused to invent above. What it forecloses is
    the two shapes that actually cost something: no row at all, and a row that reads as
    damage.
    """
    from ingestproof.audit import audit_rows

    clean = list(audit_rows(_a_report(CLEAN_DENOMINATOR, how_many=0), BATCH_ID, CONTRACT_ID))
    lone = list(audit_rows(_a_report(LONE_DENOMINATOR, how_many=1), BATCH_ID, CONTRACT_ID))

    assert len(clean) == 1, f"a clean batch left {len(clean)} rows, not one: {clean}"
    assert isinstance(clean[0], Mapping), clean[0]

    # One shape, not one shape per report. `lone` is the nearest neighbour: same function,
    # same arguments, one damage instead of none.
    assert frozenset(clean[0]) == frozenset(lone[0]), (
        f"the clean batch has a column set of its own: {frozenset(clean[0])} against "
        f"{frozenset(lone[0])}"
    )

    # The denominator reaches it, under the column the damaged call uses.
    carrying_clean = _columns_holding(clean, CLEAN_DENOMINATOR)
    carrying_lone = _columns_holding(lone, LONE_DENOMINATOR)

    assert carrying_clean, f"no column carries the clean denominator {CLEAN_DENOMINATOR}"
    assert carrying_clean == carrying_lone, (
        f"the denominator moves column when the batch is clean: {carrying_clean} against "
        f"{carrying_lone}"
    )
    assert any("records_compared" in name for name in carrying_clean), carrying_clean

    # Joinable, like every other row.
    assert any("batch" in name for name in _columns_holding(clean, BATCH_ID))
    assert any("contract" in name for name in _columns_holding(clean, CONTRACT_ID))

    # And it does not claim a damage.
    damage = _damages()[0]

    for located in (damage.record_index, damage.field_index, damage.expected):
        columns = _columns_holding(lone, located)

        assert columns, f"the one-damage call locates nothing under {located!r}: {lone}"

        for column in columns:
            assert clean[0][column] != located, (
                f"a clean batch reports damage: column {column!r} carries {located!r}, "
                f"which is what the one-damage call put there"
            )


# --- row 4: the three-level-name case ----------------------------------------------------


@needs_audit_table
def test_the_report_is_addressed_by_a_three_level_name_and_never_by_a_path() -> None:
    """`TASKS.md` row 4, and the criterion's own parenthetical `<catalog>.<schema>.<table>`.

    WHAT IS ASSERTED IS THE ADDRESS, not the write. `audit_table` is where the writer is
    pointed; whether a write then happens against a real workspace is the open question in
    the module docstring, and this assertion is true under either answer to it.

    The declaration is passed in because row 4 says the name is "taken from the
    declaration". What is NOT asserted is that two declarations get two tables: row 3's own
    signature stamps `contract_id` into every row, which is what a SHARED audit table needs
    and a per-contract one does not, so a file that required them to differ would be
    freezing a decision the queue leaves open.
    """
    from ingestproof.contracts import audit_table

    target = audit_table(_one_declaration())

    assert _is_a_three_level_table_name(target), target


# --- row 5: the owner-and-grant case, and the criterion whole ----------------------------


@needs_table_resource
def test_owner_and_grant_are_declared_in_what_the_emitter_returns() -> None:
    """`TASKS.md` row 5, asserted against the emitter's return and never against a path.

    Owner: exactly one, and a non-BLANK string rather than a merely truthy one -- `' '` is
    truthy, and an owner of one space is an undeclared owner that reads as declared.

    Grant: at least one, and not a bare scalar. `grants: 'none'` is a string that satisfies
    "something is declared" and declares nothing; a grant names at least a principal and a
    privilege, which one scalar cannot carry. WHICH keys carry them is not asserted -- that
    is a bundle schema this repository has not chosen -- only that the declaration is a
    container with something non-blank inside it. Singular and plural are both accepted:
    the queue writes `grant`, every bundle writes `grants`, and which it is was not the
    criterion's point.

    And every leaf of the resource is a non-blank `str`. That is not tidiness:
    `job_resource`'s own docstring says every value is a string ON PURPOSE, because a
    sequence comes back from any YAML parser as a list and never as the tuple a declaration
    carried, and `contracts._quote` refuses a `None` outright. A resource carrying a tuple
    or a `None` is one the emitter cannot turn into the bundle YAML this criterion is
    about, and it would fail at emission rather than here -- a red in a later turn over a
    defect that was visible in this one.
    """
    from ingestproof.contracts import table_resource

    resource = table_resource(_one_declaration())

    owners = list(_values_under(resource, lambda key: key == "owner"))
    grants = list(_values_under(resource, lambda key: key.startswith("grant")))

    assert len(owners) == 1, f"expected exactly one declared owner, found {owners}"
    assert isinstance(owners[0], str) and owners[0].strip(), owners
    assert grants, "no grant is declared in the resource the emitter returns"

    for grant in grants:
        assert isinstance(grant, (list, Mapping)), f"a grant is a bare scalar: {grant!r}"
        assert [
            leaf for leaf in _leaves(grant) if isinstance(leaf, str) and leaf.strip()
        ], f"a grant declares nothing: {grant!r}"

    assert all(
        isinstance(leaf, str) and leaf.strip() for leaf in _leaves(resource)
    ), resource


@needs_both
def test_the_table_the_report_goes_to_is_the_table_the_resource_declares() -> None:
    """The criterion's two clauses are one sentence, and this is the joint.

    "The report is written to a Unity Catalog table (...), with owner and grant declared in
    the bundle YAML" is not two independent facts: the owner and the grant have to be
    declared on THE TABLE THE REPORT GOES TO. Rows 4 and 5 are separate turns writing
    separate functions, and without this nothing anywhere notices when the writer targets
    one table and the bundle declares another -- both cases above stay green and the audit
    table is ungoverned.

    Either representation is accepted, because which one a bundle resource uses is not
    something this criterion decides: the three-level name as one scalar, or the three
    parts as three scalars. What is refused is neither.
    """
    from ingestproof.contracts import audit_table, table_resource

    contract = _one_declaration()
    target = audit_table(contract)
    declared = {leaf for leaf in _leaves(table_resource(contract)) if isinstance(leaf, str)}

    assert target in declared or set(target.split(".")) <= declared, (
        f"the writer targets {target!r}, which the emitted resource does not declare: "
        f"{sorted(declared)}"
    )


# --- the controls, which pass today and must go on passing -------------------------------


def test_the_job_resource_declares_no_owner_and_no_grant() -> None:
    """THE NEGATIVE CONTROL. An emitter's resource that must fail the case above.

    `job_resource` is the right counterexample rather than a hand-built dict: same module,
    same declaration, same YAML subset, same emitter -- differing in exactly the property
    the criterion names. Measured, its ten keys are `resources`, `jobs`, `incidents`,
    `name`, `parameters`, `default`, `tags` and the three `ingestproof_` tags, so a search
    that answers anything at all here is answering without reading the key: the same walk
    with its predicate ignored yields 13 values out of this resource.

    The third assertion is the same control from the other side, and it is not decoration.
    Two emptiness assertions are also satisfied by a walk that yields NOTHING, ever -- a
    guard that is inert in the other direction, which would make the owner-and-grant case
    above green over a resource declaring neither. Finding `tags`, which this resource does
    declare, is what separates "the predicate said no" from "the walk is broken".

    YES, THIS FREEZES SOMETHING ABOUT `job_resource`, AND IT IS INTENDED. Nothing in
    `test_ac01_one_declaration.py` pins the absence of an owner there, so this file is the
    only place that will hold it, and adding an owner or a grant to the JOB resource later
    becomes a human's commit rather than a turn's. That is the right price: the module's
    own docstring says the job resource carries what the declaration DETERMINES, and a
    declaration determines no owner -- so the day someone wants one on a job, the question
    is worth a human. The alternative, a control built from a dict this file wrote, freezes
    nothing and proves nothing about the emitter.
    """
    from ingestproof.contracts import job_resource

    resource = job_resource(_one_declaration())

    assert list(_values_under(resource, lambda key: key == "owner")) == []
    assert list(_values_under(resource, lambda key: key.startswith("grant"))) == []
    assert list(_values_under(resource, lambda key: key == "tags")), resource


def test_the_name_check_refuses_a_path_and_a_two_level_name() -> None:
    """The guard on this file's own machinery: `_is_a_three_level_table_name` must bite.

    `main.audit/report.delta` is the case that decides the shape of the check -- it splits
    into three non-empty parts on `.` and it is a path, so a predicate that counted dots
    would pass the one value the three-level-name case exists to exclude. The rest are the
    shapes a report actually gets written to when it is not written to a table, and then
    the characters an allowlist keeps out and a denylist forgets.
    """
    assert _is_a_three_level_table_name("main.audit.incidents")
    assert _is_a_three_level_table_name("main.audit_2026.incident-reports")

    refused = (
        # paths and URIs
        "main.audit/report.delta",
        "s3://bucket/audit/report",
        "dbfs:/mnt/audit/report",
        "/Volumes/main/audit/report",
        "main.audit\\report.delta",
        # the wrong number of levels
        "main.audit",
        "main.audit.incidents.extra",
        "main..incidents",
        "",
        # what a denylist forgets
        "main.audit.report;drop",
        "main.audit.'report'",
        'main.audit."report"',
        "main.audit.re#port",
        "main.audit.re,port",
        "main.audit.*",
        "main.audit.re|port",
        "main.audit.re port",
        "main.audit.re\x00port",
        "main.audit.9report",
        # not a string at all
        None,
        ("main", "audit", "incidents"),
    )

    for candidate in refused:
        assert not _is_a_three_level_table_name(candidate), candidate
