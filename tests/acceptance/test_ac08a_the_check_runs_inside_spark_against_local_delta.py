"""req~ac-08a~1 -- the check runs inside Spark against local open-source Delta.

The criterion, verbatim (`.spec/acceptance.md:101-102`): "The check runs inside Spark
against local open-source Delta and fails the task, with no credential and no workspace.
`databricks/resources/*.yml` is committed." `Ring: nightly` (line 104),
`Needs: impl, utest` (line 106).

RED TODAY. `ingestproof.spark` does not exist, `ingestproof.report` carries `Misaligned`
(line 46) and `Report` (line 96) but no `DamageFound`, `ingestproof.contracts` carries
`job_yaml` (line 265) but no `table_yaml`, and `databricks/` is not a directory in this
repository at all. The two commands that show it:

    uv run pytest -m nightly \
        tests/acceptance/test_ac08a_the_check_runs_inside_spark_against_local_delta.py
    uv run pytest --runxfail -m nightly \
        tests/acceptance/test_ac08a_the_check_runs_inside_spark_against_local_delta.py

`-m nightly` is required in BOTH: `pyproject.toml`'s `addopts` is
`-m 'not external and not nightly'`, so a plain `uv run pytest` deselects this whole file by
construction. `--strict-markers` is on and `nightly` is declared in `pyproject.toml`'s
`markers`, so the module-level marker below is neither a typo nor optional.

THIS FILE IS THE ONE THAT ACTUALLY STARTS SPARK, and that is the criterion rather than a
choice. "The check runs INSIDE Spark against local open-source Delta" is not observable from
a test that never opens a session: every assertion about a reader that does not read is an
assertion about a signature. So a session is built, a Delta table is written, and the entry
point reads it back. That is also the whole reason `req~ac-08a~1` is `Ring: nightly` while
P1's and P2's gates are inner, and the reason `pyproject.toml` carries a `spark` dependency
group the inner ring does not install.

NOTHING HERE IMPORTS `pyspark`, `delta` OR `ingestproof.spark` AT MODULE SCOPE, AND THAT IS
A RULE ABOUT THE INNER RING RATHER THAN ABOUT THIS CRITERION. Deselection happens AFTER
collection: `-m nightly` does not stop this module from being imported by every plain
`uv run pytest` anyone runs, on a machine whose venv does not have Spark in it. So whatever
this module executes at import, the inner ring pays -- and if it throws, the inner ring does
not merely slow down, it takes the whole acceptance directory down as a collection error.
Every Spark import below is inside a test body or the lazy builder a test body calls --
never in a fixture, for a measured reason `_session`'s docstring gives in full.
`importlib.util.find_spec`
answers whether a module is importable WITHOUT importing it, and that is why the seven other
frozen files that wait on something use it and none of them imports what it is waiting for.

THE MARKER MACHINERY IS `test_ac18`'S, DUPLICATED RATHER THAN SHARED, AND THE DUPLICATION IS
THE POINT. `_binds` and `_source_lacks` below are the same predicates that file carries, to
the character. A shared helper would have to live somewhere, and the only somewhere outside
the frozen set is `tests/unit/**` -- which is WRITABLE BY A TURN. A frozen gate importing its
own predicate from a path the thing being gated may edit is the shape `docs/design.md`
section 14 calls "o agente atacar o gate", and it is the shape the container audit found
thirteen times: a guard that depends on something the watched party controls. Two copies that
can only drift by a human editing both is the cheaper failure.

WHAT EACH MARKER ASKS, and they are three different questions because the rows land
separately:

- `check_batch` is read out of `ingestproof.spark`'s SOURCE, never imported, exactly as
  `test_ac18` reads `audit_rows` out of `ingestproof.audit`. The module is the one that
  imports Spark, so importing it here to ask a question about it is the collection error
  above with extra steps.
- `DamageFound` is an ATTRIBUTE of `ingestproof.report`, which has existed since P2 and which
  every ring already imports. Asking costs the inner ring nothing it was not already paying.
  It is keyed separately from `check_batch` because rows 1 and 2 are separate turns and a
  turn landing one must not red the other's case -- `classify` reads that red as RED and
  undoes an otherwise good turn.
- the committed bundle needs BOTH `contracts.table_yaml` and the file on disk, and it is the
  only marker in the frozen set that reads a PATH. That is row 6's deliverable and there is
  nothing else to key on: the file is the thing being asserted.

HOW THE CASES LINE UP WITH THE QUEUE (`TASKS.md:84-89`), because both files are frozen and
can only be fixed together:

    row 1, "the local-Delta reading case"  -> test_the_check_reads_promote_union_...
    row 2, "the failed-task case"          -> test_damage_fails_the_task_and_a_clean_...
                                              test_the_entry_point_takes_no_credential
    row 6, criterion whole                 -> test_the_committed_bundle_is_what_the_...
                                              and the fixture control

THE COMMITTED-BUNDLE CASE ASSERTS THE FILE EQUALS THE EMITTER'S OUTPUT, and that is the
queue's instruction rather than a preference (`TASKS.md:242-245`): "with `ac-18` checking
content and `ac-08a` checking that the tracked file is that content, a hand-edited
`databricks/resources/*.yml` fails a gate instead of passing quietly." The two files divide
the criterion between them and neither is complete alone -- `test_ac18` may not open a path
under the bundle directory at all, on pain of making row 5 depend on row 6 and deadlocking
the phase, and a unit test asked for in `TASKS.md:247-254` holds it to that mechanically.

IT ASSERTS ONE FILE AND NOT THE DIRECTORY, and the difference is deliberate. Requiring every
`.yml` under `databricks/resources/` to be emitter output for THIS declaration would freeze
the directory against a second contract ever being added -- a frozen test failing on
legitimate growth, which is a gate nobody can obey. So the assertion is on the path this
declaration names, and it is exact: same text, no BOM, byte-for-byte after the newline
normalisation `contracts.load_job_yaml` already documents.

WHAT THIS FILE DOES NOT ASSERT.

- **That the audit rows are written.** `req~ac-18~1` owns the rows, the address and the
  bundle declaration, and `test_ac18`'s module docstring records the open question there:
  whether the criterion demands a REAL write is the owner's call and is not made in either
  file. What a local open-source Delta session can observe is a write addressed by a
  three-level name into a LOCAL catalog; a Unity Catalog write needs a metastore, and this
  criterion's own sentence puts its ring beyond one -- "with no credential and no workspace".
- **The resynchronisation.** `TASKS.md`'s P2 rows 6 and 7 are human or adjudicated by
  `docs/design.md` section 15, and the source and the landed stream here are ALIGNED by
  construction. What is exercised is the entry point reading Delta and handing the
  differential two streams, not the differential's own hard case.
- **Byte-position location.** `docs/design.md` section 5 puts the span tokeniser in layer 3
  and `TASKS.md` says explicitly that P3 is where it would be tempting because a Spark reader
  has the offsets. It is not a row and it is not asserted here.

MEASURED, AND NOT ONLY ON THE MACHINE THAT WROTE IT, because a file that freezes a Spark
contract without one session having started is the defect this repository already carries
once.

Satisfiable: **6 passed in 192.94s** against a plausible implementation, with a real session
and a real local Delta table on disk. Seven mutants, seven killed, each by the case that owns
it -- reading only the promote side, ignoring the batch id, handing the differential the
stamped columns, logging instead of raising, raising on a clean batch, an exception carrying
an emptied report, and a hand-edited bundle file.

ON THE RUNNER, which is the ring this file lives in and the only measurement that settles the
one question that could have hung it. A throwaway probe declared in the nightly `ring` job
(run 33225216543) came back `1 passed, 480 deselected in 42.69s`: session, cold Ivy
resolution, Delta write and Delta read, all inside a CAPTURED pytest on ubuntu-latest. That
matters because the same thing deadlocks on the development machine -- three runs with
capture hung in `JavaSparkContext(jconf)` on the py4j socket, one of them for 420 seconds
producing not a single line, while `-s` got past it every time. The deadlock is the
development machine's and not pytest's, which is what lets `_session` stay as it is.

`configure_spark_with_delta_pip` resolves `io.delta:delta-spark_4.2_2.13:4.4.0`, read off the
builder's own options rather than out of a running session. It matches the installed pyspark
4.2.0 and delta-spark 4.4.0 exactly. Neither the `delta` package nor pyspark's 276 jars
carries a Delta jar, so those come from Maven when the session starts -- THIS FILE NEEDS
NETWORK on a cold cache, and the nightly is the only ring that has it.

RUNNING IT ON WINDOWS NEEDS TWO THINGS THIS FILE DOES NOT SET, and neither is a defect in it.
`-s`, for the capture deadlock above; and `PYSPARK_PYTHON` pointed at the venv interpreter,
without which the JVM reports "Timed out while waiting for the Python worker to connect
back". Both are the development machine's, both are absent on the runner, and a frozen test
may not set either: `-s` is a command-line option and the nightly's command is a gate.

[utest->req~ac-08a~1]
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import pathlib
import re

import pytest

pytestmark = pytest.mark.nightly


def _binds(source: str, name: str) -> bool:
    """Does `source` bind `name` -- as a definition, an assignment or an import?

    By PARSE and never by substring, so a mention in a comment or a docstring does not count
    as a landing. This is `test_ac18`'s predicate to the character, and the duplication is
    argued in the module docstring: the only place a shared copy could live is writable by
    the thing these files gate.

    A file that does not parse cannot be imported either, so the substring fallback keeps
    that red visible rather than turning it into a silent xfail. `SyntaxError` is the right
    guard and not `ValueError`: on 3.12 a NUL byte in the source raises
    "source code string cannot contain null bytes" as a SyntaxError.
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

    WITHOUT IMPORTING IT, and here that constraint is at its sharpest: `ingestproof.spark` is
    by design the one module in this package that imports pyspark, and the inner ring's venv
    does not have pyspark in it. An import at collection would be a `ModuleNotFoundError`
    taking the whole acceptance directory down, on every plain `uv run pytest`.

    Answers ABSENT for the four states in which the import would genuinely fail anyway: no
    spec, `find_spec` raising (`ImportError` for a missing parent, `ValueError` for a
    `sys.modules` entry whose `__spec__` is None), a spec with no `origin` -- a namespace
    package, which defines nothing -- and a file that cannot be read. None of them may become
    a collection error, so none of them raises.
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


def _module_lacks(module: str, name: str) -> bool:
    """True while `module` is missing, or is there and lacks the attribute `name`.

    An attribute cannot be seen without executing the module, so this one does import -- and
    it is confined to modules the inner ring already pays for. `ingestproof.report` has
    existed since P2 and imports nothing heavier than the standard library;
    `ingestproof.contracts` has existed since P1 and imports `re` and `unicodedata`. Neither
    is `ingestproof.spark`, and neither may become one: `test_ac07` refuses `pyspark` and
    `py4j` in a subprocess and would go red first.
    """
    if importlib.util.find_spec(module) is None:
        return True
    return not hasattr(importlib.import_module(module), name)


# The bundle path this declaration names. A `-` is legal in `contracts.PLAIN_KEY` and so is
# an `_`; the shape here is the one the queue writes, `databricks/resources/*.yml`.
BUNDLE_DIR = pathlib.PurePosixPath("databricks/resources")
AUDIT_BUNDLE = "incidents_audit.yml"


def _bundle_path() -> pathlib.Path:
    """The committed resource, resolved from THIS file rather than from the cwd.

    `prompt.md` runs every command from the repository root, but a frozen test that reads a
    path is a frozen test that must not depend on that holding: pytest's `rootdir` and the
    process cwd are different questions, and `tests/acceptance/` is two levels down from the
    root in a layout `pyproject.toml`'s `pythonpath = ["."]` pins.
    """
    return pathlib.Path(__file__).resolve().parents[2] / BUNDLE_DIR / AUDIT_BUNDLE


needs_check_batch = pytest.mark.xfail(
    _source_lacks("ingestproof.spark", "check_batch"),
    strict=True,
    reason="P3 row 1 has not landed: no ingestproof.spark source defines check_batch",
)

needs_damage_found = pytest.mark.xfail(
    _source_lacks("ingestproof.spark", "check_batch")
    or _module_lacks("ingestproof.report", "DamageFound"),
    strict=True,
    reason="P3 row 2 has not landed: check_batch or report.DamageFound does not exist",
)

needs_committed_bundle = pytest.mark.xfail(
    _module_lacks("ingestproof.contracts", "table_yaml") or not _bundle_path().is_file(),
    strict=True,
    reason="P3 row 6 has not landed: contracts.table_yaml or the committed resource is absent",
)


# --- the fixture, and the numbers it is built out of -------------------------------------

BATCH = "2026-08-26T00:00:00Z"
OTHER_BATCH = "2026-08-25T00:00:00Z"
CONTRACT_ID = "incidents@1"

# THE SOURCE, AND WHERE THE DAMAGE IS. Five records land under `BATCH`: three promoted and
# two quarantined. The damage is in a QUARANTINED one, and that is the whole design of the
# reading case -- an entry point that reads only the promote side finds nothing, reports a
# clean batch, and does not raise. Nothing else in this file can tell those two apart.
#
# `OTHER_BATCH` carries four records that would read as damaged against this source. They are
# the control on "for ONE `_batch_id`": an entry point that reads the whole table compares
# nine records instead of five and reports damage that is not this batch's.
#
# NO HEADER ROW, and that is not a simplification. `Dialect` has six fields -- encoding,
# delimiter, quotechar, escape policy, record separator, empty semantics -- and none of them
# is a header, so `parse_records` reads every line as a record. A header line here would make
# `expected` six records against five landed, `detect` would take the resynchronisation path,
# and this file would be gating `req~ac-02a~1`'s hard case by accident.
SOURCE = (
    b'1,alpha\n'
    b'2,beta\n'
    b'3,gamma\n'
    b'4,delta\n'
    b'5,epsilon\n'
)
PROMOTED = (("1", "alpha"), ("2", "beta"), ("3", "gamma"))
QUARANTINED = (("4", "delta"), ("5", "epsilon"))
RECORDS_IN_BATCH = len(PROMOTED) + len(QUARANTINED)

# The one field the landed reading gets wrong, and it is in the quarantined half.
DAMAGED_RECORD = 4
DAMAGED_FIELD = 1
EXPECTED_VALUE = "delta"
ACTUAL_VALUE = "delt"

# The other batch's rows: different values, so a reader that takes them compares more than
# five records and cannot produce the denominator this file asserts.
OTHER_ROWS = (("6", "zeta"), ("7", "eta"), ("8", "theta"), ("9", "iota"))
RECORDS_IN_TABLE = RECORDS_IN_BATCH + len(OTHER_ROWS)

# Obviously invalid, and set for the whole of the credential case. Nothing may consult them,
# and a call that reached a workspace with these would fail rather than pass quietly.
POISONED_ENVIRONMENT = {
    "DATABRICKS_HOST": "https://invalid.example.invalid",
    "DATABRICKS_TOKEN": "not-a-token",
    "DATABRICKS_CLIENT_ID": "not-a-client",
    "DATABRICKS_CLIENT_SECRET": "not-a-secret",
}

CREDENTIAL_WORDS = re.compile(r"token|secret|password|credential|api_key|apikey", re.I)


def _from_report(name: str):
    """One name out of `ingestproof.report`, fetched in a function of its own.

    NOT written as an import statement in a test body beside
    `from ingestproof.spark import check_batch`, and the reason is ruff rather than filing.
    Measured with this repository's own ruff 0.14: `ingestproof` resolves FIRST-party through
    `[tool.ruff].src`, but a module that does not exist yet is classified THIRD-party. So a
    function importing `ingestproof.report` and `ingestproof.spark` in one block is I001
    today -- ruff wants a blank line between the two sections -- and I001 again the day
    `spark` lands, with the blank line it just demanded now being the defect. A frozen file
    cannot answer both, and `tests/acceptance/**` is frozen.

    `test_ac18`'s draft carries this warning in a comment and had no occasion to hit it. This
    file did, on its first lint, in two test bodies. An `importlib` call is not an import
    STATEMENT, so it is outside I001 entirely and stays correct in both worlds.
    """
    return getattr(importlib.import_module("ingestproof.report"), name)


def _one_declaration():
    """The same declaration `test_ac01` and `test_ac18` use, so three files read as one.

    `declare` is deliberately NOT called: it registers into a process-wide mapping and
    refuses to rebind an id, and nothing in this file needs the registry.
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


# The same six values `test_ac04` calls RFC4180, under the same name, so a reader comparing
# the two files is comparing the same dialect. Every field is given because
# `require_dialect` refuses a missing one and nothing here may infer.
RFC4180 = dict(
    encoding="utf-8",
    delimiter=",",
    quotechar='"',
    escape="double",
    record_separator="\n",
    empty="empty-string",
)


def _a_dialect():
    """The declared dialect `req~ac-04~1` refuses to infer. Every field, no defaults."""
    from ingestproof.dialect import Dialect

    return Dialect(**RFC4180)  # type: ignore[arg-type]


_SESSION: list = []


def _session():
    """One local session for the whole module, built ON FIRST USE INSIDE A TEST BODY.

    NOT A FIXTURE, AND THAT IS THE ONE STRUCTURAL DECISION IN THIS FILE THAT WAS MEASURED
    RATHER THAN REASONED. A strict `xfail` still RUNS the test, so a session built in setup
    would be built on every nightly for as long as row 1 is undispatched -- and measured on
    pytest 8.4.2, an exception raised in a fixture of an `xfail(strict=True)` test is
    reported as `xfailed`, not as an error:

        test_probe.py xx        2 xfailed in 1.67s

    So a session that could not start -- no network for the Maven resolution, no JVM, a
    Delta version that does not match -- would be INVISIBLE, and the nightly would be green
    for a reason that has nothing to do with the criterion. Built inside the body, after the
    import that xfails, none of that happens: with `ingestproof.spark` missing the test
    raises `ModuleNotFoundError` in milliseconds and no JVM is ever asked for.

    `local[1]` and one shuffle partition because this is a correctness gate over nine rows,
    not a performance one; the UI is off because a nightly runner has nobody to serve it.

    `configure_spark_with_delta_pip` is delta-spark's own entry point and it resolves the
    Delta jars from Maven -- measured, neither the `delta` package nor pyspark's 276 jars
    carries one. That is a network call on a cold cache, and it is why this file's ring is
    the only one that could run it.
    """
    if not _SESSION:
        from delta import configure_spark_with_delta_pip
        from pyspark.sql import SparkSession

        builder = (
            SparkSession.builder.master("local[1]")
            .appName("req~ac-08a~1")
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            )
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "1")
        )
        session = configure_spark_with_delta_pip(builder).getOrCreate()
        session.sparkContext.setLogLevel("ERROR")
        _SESSION.append(session)
    return _SESSION[0]


@pytest.fixture(scope="module", autouse=True)
def _stop_the_session():
    """Teardown only. Setup does NOTHING, which is what keeps the paragraph above true.

    A module-scoped autouse fixture that yields immediately costs an xfailed run nothing and
    still guarantees the JVM is not left running when the module is done -- which matters in
    the nightly, where this module shares a process with whatever else `-m nightly` selects.
    """
    yield
    while _SESSION:
        _SESSION.pop().stop()


def _write_delta(session, where: pathlib.Path, damaged: bool) -> str:
    """Two batches into one local Delta table, and return its location.

    The landed reading is DAMAGED in a quarantined record when `damaged` is true, and exact
    when it is false. Both write the same nine rows otherwise, so the clean and the damaged
    call differ in one field and in nothing else -- which is what makes the failed-task case
    a comparison rather than two unrelated runs.
    """
    from ingestproof.contracts import (
        BATCH_ID_COLUMN,
        CONTRACT_ID_COLUMN,
        REJECTED_BY_COLUMN,
    )

    rows = []
    for identifier, note in PROMOTED:
        rows.append((BATCH, CONTRACT_ID, None, identifier, note))
    for identifier, note in QUARANTINED:
        landed = note
        if damaged and int(identifier) == DAMAGED_RECORD:
            landed = ACTUAL_VALUE
        rows.append((BATCH, CONTRACT_ID, "id_not_null", identifier, landed))
    for identifier, note in OTHER_ROWS:
        rows.append((OTHER_BATCH, CONTRACT_ID, None, identifier, note))

    schema = (
        f"{BATCH_ID_COLUMN} string, {CONTRACT_ID_COLUMN} string, "
        f"{REJECTED_BY_COLUMN} string, id string, note string"
    )
    location = where.as_posix()
    session.createDataFrame(rows, schema).write.format("delta").mode("overwrite").save(
        location
    )
    return location


# THE PER-TEST TIMEOUT, AND IT IS NOT A ROUND NUMBER PULLED OUT OF THE AIR. `addopts` in
# `pyproject.toml` carries `--timeout=60` and `pyproject.toml` is frozen, so this file cannot
# raise the suite's limit and must not want to: sixty seconds is right for every other test
# in the repository. Measured on the development machine, a cold local session is 38.7s
# before a single row is written and the whole probe was 93.9s -- so the first test here
# blows the global limit on setup alone, and it did, on the first run, as a `Timeout` rather
# than as a failure that names anything.
#
# pytest-timeout's marker overrides the global for one test and `--strict-markers` accepts it
# because the plugin registers it. All three carry the same budget because only ONE of them
# pays for the session and this file cannot know which -- pytest's order is the file's, but a
# `-k` or a `--last-failed` reorders it, and a budget that assumed an order would fail for a
# reason that has nothing to do with Spark. The runner's cold Maven resolution is inside it.
#
# 600 is then chosen against the RUNNER rather than against this machine: the probe of
# run 33225216543 did session, cold Ivy resolution, write and read in 42.69s, so the
# budget is fourteen times what the ring actually costs. The slack is for the
# resolution, which is the one step here whose time is somebody else's network.
SPARK_BUDGET = 600


# --- row 1: the local-Delta reading case -------------------------------------------------


@pytest.mark.timeout(SPARK_BUDGET)
@needs_check_batch
def test_the_check_reads_promote_union_quarantine_for_one_batch_out_of_local_delta(
    tmp_path_factory,
) -> None:
    """`TASKS.md` row 1: promote UNION quarantine for ONE `_batch_id`, out of local Delta.

    THREE THINGS ARE ASSERTED AND EACH ONE HAS ITS OWN COUNTEREXAMPLE IN THE TABLE.

    The union. The damage is planted in a QUARANTINED record, so an entry point reading only
    the promote side compares three intact records, reports a clean batch, and raises
    nothing. That is the reading `docs/design.md` calls wrong by construction and it is the
    one a Spark reader falls into first, because bronze IS the promote side.

    The batch. `OTHER_BATCH` carries four records that read as damaged against this source,
    so an entry point ignoring `_batch_id` compares nine and finds damage that is not this
    batch's. The denominator is what catches it: five, never nine and never three.

    And the differential actually ran. `records_compared` coming back as five is not enough
    on its own -- a stub returning `Report(damages=(), records_compared=5)` satisfies a count
    and nothing else -- so the damage's own coordinates are asserted, out of the `Damage`
    dataclass `req~ac-03~1` already defines.

    AND THE STAMPED COLUMNS ARE OUT, asserted sideways rather than named. The Delta table
    carries `contracts.BATCH_ID_COLUMN`, `CONTRACT_ID_COLUMN` and `REJECTED_BY_COLUMN`
    alongside the two source fields, and those are this library's own stamps rather than the
    source's -- `contracts.AUDIT_SCHEMA`'s comment says so. An entry point handing all five
    to the differential shifts every field index by three, so `field_index == 1` is what
    holds it to the source's own shape without this file having to enumerate a schema.

    WHAT IS NOT ASSERTED: that the entry point calls `differential.detect` rather than
    reimplementing it. This file observes the report, which is the criterion's subject; how
    the streams are compared is `req~ac-02a~1`'s and is already gated there.
    """
    from ingestproof.spark import check_batch

    damage_found = _from_report("DamageFound")
    location = _write_delta(
        _session(), tmp_path_factory.mktemp("delta") / "landed", damaged=True
    )

    with pytest.raises(damage_found) as raised:
        check_batch(SOURCE, _a_dialect(), location, BATCH)

    report = raised.value.report

    assert report.records_compared == RECORDS_IN_BATCH, (
        f"compared {report.records_compared} records: "
        f"{RECORDS_IN_BATCH} is promote union quarantine for one batch, "
        f"{len(PROMOTED)} is promote alone, and {RECORDS_IN_TABLE} is the whole table"
    )
    assert len(report.damages) == 1, report.damages

    damage = report.damages[0]

    assert damage.record_index == DAMAGED_RECORD - 1, damage
    assert damage.field_index == DAMAGED_FIELD, damage
    assert damage.expected == EXPECTED_VALUE, damage
    assert damage.actual == ACTUAL_VALUE, damage


# --- row 2: the failed-task case ---------------------------------------------------------


@pytest.mark.timeout(SPARK_BUDGET)
@needs_damage_found
def test_damage_fails_the_task_and_a_clean_batch_returns(tmp_path_factory) -> None:
    """`TASKS.md` row 2: any damage RAISES; a clean batch returns. Never log and continue.

    "Fails the task" is a Databricks job's word for a process that exits non-zero, and any
    uncaught exception does that -- which is exactly why a bare `Exception` would be
    untestable here and a named one is not. `DamageFound` carries the `Report`, and that is
    load-bearing rather than convenient: `req~ac-18~1` turns a `Report` into audit rows, and
    a failure that discarded the report would take the denominator down with it. The row the
    owner ruled a clean batch must leave has the same source -- the value this call returns.

    THE TWO CALLS DIFFER IN ONE FIELD. Same nine rows, same table shape, same batch: one
    quarantined note reads `delt` instead of `delta`. So a "clean batch returns" that passed
    for a reason other than the batch being clean -- an entry point that never raises, or one
    that raises on everything -- fails the other half of this test.

    AND THE CLEAN RETURN CARRIES THE DENOMINATOR, which is not the same as being a `Report`.
    `req~ac-18~1` row 3 takes a `Report`, and `test_ac18` already ruled that a `Differential`
    carries what a `Report` carries -- so this file reads the two ATTRIBUTES and never the
    class. Requiring the class would forbid the return `differential.detect` most naturally
    hands back. What is refused is a bare sentinel: `None` or `True` would leave the clean row
    the owner ruled on in round 4 with no denominator to carry.
    """
    from ingestproof.spark import check_batch

    damage_found = _from_report("DamageFound")
    root = tmp_path_factory.mktemp("delta")
    damaged = _write_delta(_session(), root / "damaged", damaged=True)
    clean = _write_delta(_session(), root / "clean", damaged=False)

    with pytest.raises(damage_found) as raised:
        check_batch(SOURCE, _a_dialect(), damaged, BATCH)

    assert raised.value.report.damages, "DamageFound carries a report with no damage in it"
    assert raised.value.report.records_compared == RECORDS_IN_BATCH, raised.value.report

    outcome = check_batch(SOURCE, _a_dialect(), clean, BATCH)

    assert outcome.damages == (), outcome
    assert outcome.records_compared == RECORDS_IN_BATCH, outcome


@pytest.mark.timeout(SPARK_BUDGET)
@needs_check_batch
def test_the_entry_point_takes_no_credential(tmp_path_factory, monkeypatch) -> None:
    """The criterion's "with no credential and no workspace", asserted two ways.

    By SIGNATURE, because a credential this entry point accepts is a credential the loop can
    be asked for: no parameter may be named for one. That is a shallow check and it is the
    half that is easy to keep.

    And by BEHAVIOUR, which is the half that is worth something: the whole call runs with
    every `DATABRICKS_*` variable set to an obviously invalid value. A reader that consulted
    them would try `https://invalid.example.invalid` and fail; one that authenticated would
    fail on `not-a-token`. Passing here is passing while every credential in the environment
    is wrong, which is the nearest thing to "no credential" that a test can observe without
    asserting the absence of a network call it cannot see.

    WHAT THIS DOES NOT CATCH, said rather than left to sound stronger: a reader taking a
    credential from a file, from an instance profile, or from a parameter named something
    this file's expression does not match. The signature check is a denylist over names, and
    a denylist admits what it forgot. What makes that acceptable here rather than in
    `test_ac18`'s name check is that the environment half does not depend on the name at all.
    """
    from ingestproof.spark import check_batch

    parameters = inspect.signature(check_batch).parameters
    named = [name for name in parameters if CREDENTIAL_WORDS.search(name)]

    assert not named, f"check_batch takes a credential: {named}"

    for key, value in POISONED_ENVIRONMENT.items():
        monkeypatch.setenv(key, value)

    location = _write_delta(
        _session(), tmp_path_factory.mktemp("delta") / "clean", damaged=False
    )
    outcome = check_batch(SOURCE, _a_dialect(), location, BATCH)

    assert outcome.records_compared == RECORDS_IN_BATCH, outcome


# --- row 6: the committed bundle, and the criterion whole --------------------------------


@needs_committed_bundle
def test_the_committed_bundle_is_what_the_emitter_returns() -> None:
    """`TASKS.md` row 6, and the constraint `TASKS.md:242-245` puts on how it asserts.

    `test_ac18` may not open a path under the bundle directory -- doing so would make row 5,
    a `loop` row, depend on row 6, a human's, and the phase deadlocks with nothing noticing
    until the stall brake fires. So that file checks the emitter's CONTENT and this one
    checks that the tracked file IS that content. Together a hand-edited resource fails a
    gate; apart, either one passes it quietly.

    EXACT TEXT, and the two normalisations are the ones `contracts.load_job_yaml` already
    documents rather than new policy: a BOM and a CR are things a file acquires on the way to
    disk, and that reader strips both before parsing. A BOM is asserted ABSENT rather than
    stripped, because a resource that acquired one is a resource that went through an editor,
    and going through an editor is the drift this case exists to catch. The CR is normalised
    rather than refused: `.gitattributes` is `* text=auto eol=lf`, so a CR here is a
    checkout's doing and not an author's.

    ONE FILE, NOT THE DIRECTORY. Requiring every `.yml` under the bundle directory to be
    emitter output for THIS declaration would freeze the directory against a second contract
    ever being added -- a frozen test that fails on legitimate growth is a gate nobody can
    obey, and `req~ac-08a~1`'s own text says `databricks/resources/*.yml` is committed, not
    that nothing else is.
    """
    from ingestproof.contracts import load_job_yaml, table_resource, table_yaml

    path = _bundle_path()
    raw = path.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf"), (
        f"{path} carries a BOM: it went through an editor rather than through the emitter"
    )

    committed = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    contract = _one_declaration()

    assert committed == table_yaml(contract), (
        f"{path} is not what the emitter returns; a hand edit is the likeliest cause"
    )

    # And it is READABLE as the resource, by the reader that is not the emitter's own
    # round trip -- `contracts.load_job_yaml`'s docstring says why one parser is not enough.
    assert load_job_yaml(committed) == table_resource(contract), committed


# --- controls ----------------------------------------------------------------------------


def test_the_fixture_plants_the_damage_in_a_quarantined_record() -> None:
    """The control on this file's own setup, and it is not decoration.

    Everything the reading case proves rests on the damage being on the quarantine side. If a
    later edit moved it into `PROMOTED`, that case would go on passing while asserting
    something weaker than it claims: an entry point reading only promote would find the
    damage and the union would stop being tested. Nothing else in this file would notice.

    It runs TODAY, with nothing landed, and must go on passing -- which is why the xfail
    markers in this file are per test rather than a module-level `pytestmark`. Under a
    module-level strict xfail this control reports XPASS(strict), a failure, and the nightly
    is red for the one test here that is already right.
    """
    quarantined = {int(identifier) for identifier, _ in QUARANTINED}
    promoted = {int(identifier) for identifier, _ in PROMOTED}

    assert DAMAGED_RECORD in quarantined, DAMAGED_RECORD
    assert DAMAGED_RECORD not in promoted, DAMAGED_RECORD
    assert EXPECTED_VALUE != ACTUAL_VALUE
    assert len(PROMOTED) != RECORDS_IN_BATCH, "promote alone would give the same denominator"
    assert RECORDS_IN_TABLE != RECORDS_IN_BATCH, "the whole table would give the same one"


def test_the_credential_expression_refuses_the_names_it_is_for() -> None:
    """The control on this file's own predicate, in the shape `test_ac18` uses for its name
    check: an expression that matched nothing would make the credential case green over an
    entry point taking a token.
    """
    for name in ("token", "api_token", "secret", "client_secret", "password", "api_key"):
        assert CREDENTIAL_WORDS.search(name), name

    for name in ("source", "dialect", "table", "batch_id", "contract"):
        assert not CREDENTIAL_WORDS.search(name), name
