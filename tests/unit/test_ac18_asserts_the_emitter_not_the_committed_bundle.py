"""The split between P3's two acceptance files, asserted from the writable side.

`TASKS.md`'s P3 debt subsection puts a constraint on how the two frozen files assert, and
rule 2 of the queue is discharged by it:

- `test_ac18_...` must assert **owner and grant against what the emitter returns**, never
  against a file on disk. `req~ac-18~1`'s text says "declared in the bundle YAML" and says
  nothing about that YAML being committed; the committed-file requirement lives in
  `req~ac-08a~1`, which names `databricks/resources/*.yml` explicitly.
- `test_ac08a_...` must assert that the **committed** file equals what the emitter returns.
  That is where the drift the first constraint opens up gets closed.

**Why this file exists at all.** A stated constraint on a frozen file is only as good as the
next person's reading of it. If the `ac-18` file ever opens the committed path, queue row 5
becomes unclosable -- it is a `loop` row that would then depend on row 6, a human's -- and
nothing notices until the stall brake fires, five turns later, blaming the task wording. The
constraint does not have to stay stated: `tests/unit/**` is outside the frozen set, so the
inner ring can read the frozen file's own source and refuse the edit that would break it.

The precedent is `tests/unit/test_allowlist_hook.py`, which asserts properties of a frozen
gate from the writable side and says so in its own docstring.

**THE FIRST VERSION OF THIS FILE WAS AN INERT GUARD, AND A REVIEWER PROVED IT BY EXECUTION.**
Its `ac-08a` half asserted only that *some string literal* in that file contained
`databricks`. `POISONED_ENVIRONMENT` at `test_ac08a_...:310` carries `DATABRICKS_HOST` and
`DATABRICKS_TOKEN`, which have nothing to do with the committed bundle -- so the reviewer
deleted `BUNDLE_DIR`, `AUDIT_BUNDLE`, `_bundle_path`, `needs_committed_bundle` and the whole
committed-bundle test from `ac-08a`, and all eight tests here stayed green. **A predicate
that survives the removal of its own subject is the defect this repository keeps catching,
and this file existed to prevent one instance of it while being another.** The `ac-08a` half
now keys on the machinery by name; §"what each half keys on" below says why that is the
weaker-looking check that actually bites.

**What each half keys on, and why they differ.** The `ac-18` half is a NEGATIVE and keys on
the vendor token plus the SHAPE of a directory listing. The `ac-08a` half is a POSITIVE and
keys on behaviour: where `BUNDLE_DIR` points, that `_bundle_path` reads it, and that the
case reads what it returns. A positive cannot key on a token, because a token is present for
unrelated reasons -- `DATABRICKS_HOST` was, and it defeated two versions of this file.

**WHAT THE NEGATIVE HALF DOES NOT CATCH, MEASURED RATHER THAN CLAIMED.** An earlier draft of
this docstring said every spelling of the path "has to carry this token somewhere". That is
false. A second draft then listed five string MECHANISMS as escapes -- `%`-formatting,
`.format()`, `str.join`, a `bytes` decode, `importlib.resources` -- and a reviewer measured
that four of the five are caught in the spelling anyone would actually write, because the
token survives whole in the source text. **The hole is not the mechanism. It is splitting
the vendor token itself**, in any mechanism: `"%sbricks/resources" % "data"` evades where
`"%s/resources" % "databricks"` does not.

Caught: the literal, a `PurePosixPath` split, case changes, an f-string, implicit
concatenation, `+` concatenation, a comment, a bare `open()` whose literal carries the
token, any `glob`/`rglob`/`iterdir`/`scandir`/`listdir`/`fwalk`/`walk`, and those same
enumerators imported under another name -- `from os import listdir as ls` binds `ls`, and
matching the call name alone would have missed it.

**Genuinely not caught, all four measured:** the token split across a `%`/`.format()`/
`join`/`bytes` boundary, a name IMPORTED from `ingestproof.contracts` or from the sibling
acceptance file, a fixture in a `tests/acceptance/conftest.py` that does not exist yet, and
an enumerator reached through `getattr(os, "listdir")`, where no name is written at all.

The imports are the ones that are not adversarial -- row 5 puts `table_resource` in
`contracts.py`, so a `BUNDLE_DIR` constant beside it is the obvious next edit, and importing
the sibling's `_bundle_path` is the instinct a reviewer would praise. **A static reader of
two files cannot close those**, and a guard that claimed otherwise would be the fourth inert
version of this file. What it does close is the careless edit, which is the threat model
`TASKS.md` actually states: both files are frozen, so every edit here is a human pushing to
`main`, and the guard's job is to make that human justify it rather than to stop an
attacker.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ACCEPTANCE = REPO / "tests" / "acceptance"

AC18 = ACCEPTANCE / "test_ac18_the_audit_report_lands_in_a_unity_catalog_table.py"
AC08A = ACCEPTANCE / "test_ac08a_the_check_runs_inside_spark_against_local_delta.py"

# The directory `req~ac-08a~1` names. Matched case-insensitively on the vendor token alone:
# the path can be spelled `databricks/resources`, `databricks\\resources`, or assembled from
# parts, and every spelling of it has to carry this token somewhere.
VENDOR = "databricks"

# The `ac-08a` machinery that reads the committed bundle. Every name here is load-bearing:
# `BUNDLE_DIR`/`AUDIT_BUNDLE` spell the path, `_bundle_path` resolves it, the marker keys the
# xfail on the file's presence, and the test is the only consumer of all four.
BUNDLE_MACHINERY = ("BUNDLE_DIR", "AUDIT_BUNDLE", "_bundle_path", "needs_committed_bundle")
BUNDLE_TEST = "test_the_committed_bundle_is_what_the_emitter_returns"

# The importable name of the frozen module, so the resolver can be CALLED rather than read.
AC08A_MODULE = "tests.acceptance.test_ac08a_the_check_runs_inside_spark_against_local_delta"

# How a path's bytes reach a test. `open` is here for the spelling that does not go through
# `pathlib`, even though the frozen file uses `read_bytes`.
READS = ("read_bytes", "read_text", "open")

# Names by which a file enumerates the tree instead of spelling a path. The reviewer's
# `next(root.glob("*/resources/incidents_audit.yml"))` reached the committed bundle without
# writing the vendor token anywhere, in the source or in the tree.
#
# `walk` is handled apart from the rest, and the asymmetry is measured rather than
# stylistic: `ast.walk` is how BOTH acceptance files read module sources, so an unqualified
# `walk` fires on the legitimate use -- it did, on the first run of this file. The other
# five name no stdlib API that is not a directory listing.
#
# THE FIRST FIX FOR THAT WAS ITSELF INERT. It refused the literal spellings `os.walk` and
# `Path.walk`, and a reviewer measured that `root.walk()` -- the ordinary way anyone writes
# it -- evaded, as did `pathlib.Path(x).walk()` and a bare `walk()` imported from `os`. The
# receiver is the wrong thing to enumerate; the ONE legitimate receiver is, so `walk` is
# refused on every receiver except `ast`.
ENUMERATORS = ("glob", "rglob", "iterdir", "scandir", "listdir", "fwalk")
WALK_IS_LEGITIMATE_ON = ("ast",)


def _folded_strings(source: str) -> list[str]:
    """Every string an `ast` walk can see, with `+` and implicit concatenation folded.

    Three shapes have to collapse to one token or the sweep below is decoration:

    - `"databricks"` -- a plain `ast.Constant`.
    - `"data" "bricks"` -- implicit concatenation, which the PARSER folds, so it is already
      one `Constant` in the tree and is invisible to a sweep over the source text.
    - `"data" + "bricks"` -- an `ast.BinOp`, which the parser does NOT fold. It is invisible
      to the text sweep AND to a naive `Constant` walk, and it is the first evasion the
      reviewer landed against the previous version of this file.
    """

    return [s for node in ast.walk(ast.parse(source)) if (s := _fold(node)) is not None]


def _fold(node: ast.AST) -> str | None:
    """One node's string value, folding `+` and f-string literal parts. `None` if not static."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fold(node.left), _fold(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):  # an f-string: fold the literal parts only
        parts = [_fold(v) for v in node.values]
        return "".join(p for p in parts if p is not None)
    return None


def _bound_names(source: str) -> set[str]:
    """Every name the module binds: assignment target, function, or class."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def _called_attributes(source: str) -> set[str]:
    """Every call, as the bare name AND as `receiver.name` where the receiver is a plain name.

    Both forms are returned because the two checks below need different resolutions:
    `.glob(...)` is a directory listing whatever it is called on, while `walk` is only one
    when its receiver says so -- `ast.walk` is not.
    """
    called: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
            if isinstance(node.func.value, ast.Name):
                called.add(f"{node.func.value.id}.{node.func.attr}")
        elif isinstance(node.func, ast.Name):
            called.add(node.func.id)
    return called


def _enumerating_calls(source: str) -> set[str]:
    """The calls in `source` that list a directory rather than name a path.

    `walk` is refused on every receiver but `ast`, which is the only one either acceptance
    file legitimately walks. A receiver that is not a plain name -- `pathlib.Path(x).walk()`
    -- is refused too, because nothing can be concluded about it from the syntax.
    """
    tree = ast.parse(source)

    # An IMPORTED enumerator answers to whatever it was bound as: `from os import listdir as
    # ls` then `ls(...)` is a bare call to a name this set would otherwise never contain.
    aliases = {
        (alias.asname or alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module in ("os", "pathlib", "glob")
        for alias in node.names
        if alias.name in (*ENUMERATORS, "walk")
    }

    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name, receiver = func.attr, func.value
        elif isinstance(func, ast.Name):
            name, receiver = func.id, None
        else:
            continue
        if name in ENUMERATORS or (receiver is None and name in aliases):
            found.add(name)
        elif name == "walk":
            on = receiver.id if isinstance(receiver, ast.Name) else "<expr>" if receiver else ""
            if on not in WALK_IS_LEGITIMATE_ON:
                found.add(f"{on}.walk".lstrip("."))
    return found


def _function_body(source: str, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _ac08a_module():
    """Load the frozen file BY PATH, so the half that reads and the half that calls agree.

    `importlib.import_module("tests.acceptance....")` resolves through `sys.path` and builds
    a module object distinct from the one pytest collected -- and a reviewer measured a probe
    in which a stale `tests/acceptance` on `sys.path[0]` silently evaluated a DIFFERENT
    tree's file. Loading from `AC08A` makes the identity structural instead of incidental:
    the bytes this file reads and the resolver this file calls are the same bytes.
    """
    spec = importlib.util.spec_from_file_location(AC08A_MODULE, AC08A)
    assert spec is not None and spec.loader is not None, f"cannot load {AC08A}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rebinds_machinery_below_module_scope(source: str) -> set[str]:
    """Machinery names a function rebinds at run time, which import-time evaluation cannot see.

    The guard calls `_bundle_path()` once, at import. A module-scoped autouse fixture that
    does `global _bundle_path` and rebinds it before `yield` leaves the guard looking at the
    correct resolver while every case uses another one -- measured green. Fixtures do not run
    during evaluation, so this one has to be read rather than called.
    """
    rebound: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Global):
                    rebound |= set(inner.names) & set(BUNDLE_MACHINERY)
                elif (
                    isinstance(inner, ast.Name)
                    and isinstance(inner.ctx, ast.Store)
                    and inner.id in BUNDLE_MACHINERY
                ):
                    rebound.add(inner.id)
    return rebound


def _marker_condition(source: str, name: str) -> ast.expr | None:
    """The first positional argument of `name = pytest.mark.xfail(...)`, unevaluated.

    Read rather than called because the value cannot tell the two cases apart: today the
    real condition evaluates to `True` (nothing implements `table_yaml`), and so does a
    hardcoded `True`. Only the syntax distinguishes a condition that will evaporate when the
    work lands from one that never will.
    """
    for node in ast.parse(source).body:
        if not (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and isinstance(node.value, ast.Call)
            and node.value.args
        ):
            continue
        return node.value.args[0]
    return None


def test_both_frozen_acceptance_files_are_where_this_guard_looks() -> None:
    """The guard is worthless if a rename makes it vacuously green.

    Every other test in this file reads one of these two paths. `Path.read_text` on a
    missing file raises, so a rename would turn them red rather than green -- but it would
    do it with a `FileNotFoundError` naming a path, which reads like a broken test rather
    than like the deliberate refusal it is. This says it once, in the file's own words.
    """
    assert AC18.is_file(), f"{AC18.relative_to(REPO)} is gone; the ac-18 guard below guards nothing"
    assert AC08A.is_file(), f"{AC08A.relative_to(REPO)} is gone; the split below is unasserted"


def test_the_ac18_acceptance_file_never_names_the_committed_bundle() -> None:
    """`req~ac-18~1` closes on the emitter's returned string, so row 5 stays the loop's.

    The moment this file opens `databricks/resources`, queue row 5 -- a `loop` row -- starts
    depending on row 6, which is a human's commit, and P3 deadlocks exactly as it did before
    round 1. The frozen file cannot be edited to do that without turning the inner ring red.
    """
    source = AC18.read_text(encoding="utf-8")

    assert VENDOR not in source.lower(), (
        f"{AC18.name} mentions {VENDOR!r}. `req~ac-18~1` is closed against what "
        "`table_resource`/`job_yaml` RETURN, never against a committed path -- see the P3 "
        "debt subsection of TASKS.md. The committed file is `req~ac-08a~1`'s to check."
    )

    offenders = [s for s in _folded_strings(source) if VENDOR in s.lower()]
    assert not offenders, f"{AC18.name} assembles {VENDOR!r} out of parts: {offenders}"


def test_the_ac18_acceptance_file_never_enumerates_the_tree() -> None:
    """The token check alone is not enough: a glob reaches the bundle without spelling it.

    `next(root.glob("*/resources/incidents_audit.yml"))` opens the committed file and writes
    the vendor token nowhere. The name check above cannot see it, so the shape is refused
    instead of the name. `ac-18` needs no directory listing for anything it legitimately
    does -- it reads module sources through `importlib`, by `spec.origin`.
    """
    used = _enumerating_calls(AC18.read_text(encoding="utf-8"))
    assert not used, (
        f"{AC18.name} calls {sorted(used)}. A file that lists a directory can reach "
        "`databricks/resources` without ever spelling it, which is how the first version "
        "of this guard was defeated. `ac-18` resolves modules by `spec.origin` and needs no "
        "enumeration; if that changes, the change is a human's to justify here."
    )


def test_the_ac08a_resolver_points_at_the_committed_bundle() -> None:
    """Where `_bundle_path()` actually resolves. EVALUATED, not parsed.

    Forbidding the path in `ac-18` and asserting nothing real about `ac-08a` leaves a tree
    in which NEITHER file reads the committed bundle -- a hand-edited
    `databricks/resources/*.yml` would then pass every gate quietly, which is the drift the
    first constraint opens and this one closes.

    FOUR VERSIONS OF THIS HALF WERE INERT, AND EACH WAS THE SAME MISTAKE: a check on the
    SOURCE of the machinery is not a check on what the machinery does.

    - v1 asked whether some string literal held `databricks`. `POISONED_ENVIRONMENT`
      (`test_ac08a_...:310`) carries `DATABRICKS_HOST` for an unrelated reason, so the whole
      bundle machinery could be deleted and every test stayed green.
    - v2 asked whether four names were bound. `_bundle_path` could return a tmp path and
      `BUNDLE_DIR` could be repointed under `src/` -- a loop-writable prefix, so row 6's
      human gate is bypassed by a file the loop writes itself.
    - v3 asked which tokens sat in which subtrees. `AUDIT_BUNDLE` `.yml` -> `.yaml` walked
      past it, and so did a second `BUNDLE_DIR` or a second `def _bundle_path`, because
      reading the FIRST module-level match is not what Python binds -- it binds the last.
    - v4 asked, statically, whether the case read the path and compared something tainted by
      it. `assert raw == raw`, `assert path.suffix == ".yml"` and a compare inside a nested
      function nobody calls all satisfy that while the case cannot fail on a hand edit.

    So the resolver is CALLED here, and the case itself is RUN in the test below. Every
    escape above ends either in a resolved path that is not the committed resource, or in a
    case that no longer fails on a hand edit; neither can lie to a call.
    """
    source = AC08A.read_text(encoding="utf-8")

    missing = [n for n in (*BUNDLE_MACHINERY, BUNDLE_TEST) if n not in _bound_names(source)]
    assert not missing, (
        f"{AC08A.name} no longer binds {missing}. `req~ac-08a~1`'s text is "
        "'`databricks/resources/*.yml` is committed' -- if this file stops reading that "
        "path, nothing in the repository checks the committed bundle against the emitter, "
        "and the ac-18 constraint above becomes a hole rather than a division."
    )

    rebound = _rebinds_machinery_below_module_scope(source)
    assert not rebound, (
        f"{AC08A.name} rebinds {sorted(rebound)} inside a function. This test evaluates the "
        "resolver ONCE, at import, and fixtures have not run then -- a module-scoped autouse "
        "fixture that rebinds `_bundle_path` before `yield` leaves this green while every "
        "case uses a different resolver."
    )

    module = _ac08a_module()

    assert not inspect.signature(module._bundle_path).parameters, (
        "`_bundle_path` grew a parameter. This test calls it with none and the frozen "
        "marker keys on the same zero-argument call, so a case passing its own root would "
        "run against a path neither of them checked."
    )

    resolved = module._bundle_path()
    assert resolved.parent == REPO / "databricks" / "resources", (
        f"`_bundle_path()` resolves to {resolved}, whose directory is not "
        f"{REPO / 'databricks' / 'resources'}. `needs_committed_bundle` keys its strict "
        "xfail on that path existing, so a wrong directory is not a red test -- it is a "
        "permanent silent xfail, and nothing ever compares the committed bundle to the "
        "emitter. Repointing it under a writable prefix also bypasses row 6's human gate."
    )
    assert resolved.suffix == ".yml", (
        f"`_bundle_path()` resolves to {resolved.name}. `req~ac-08a~1` names "
        "`databricks/resources/*.yml`; any other suffix is a file row 6 will not commit, "
        "and the case xfails forever waiting for it."
    )

    marker = module.needs_committed_bundle
    assert marker.kwargs.get("strict") is True, (
        "`needs_committed_bundle` is not strict. A non-strict xfail turns the day the "
        "bundle lands into a silent XPASS instead of a green test."
    )

    # The CONDITION, read rather than called: at run time it is `True` today either way, so
    # a computed condition and a hardcoded one are indistinguishable from the value alone.
    condition = _marker_condition(source, "needs_committed_bundle")
    assert condition is not None, "`needs_committed_bundle` is no longer a `pytest.mark.xfail`"
    assert not isinstance(condition, ast.Constant), (
        "`needs_committed_bundle`'s condition is the literal "
        f"{condition.value!r}. A constant condition never evaporates, so the case xfails "
        "for ever -- including after row 6 commits the bundle it is waiting for."
    )


def test_the_committed_bundle_case_fails_on_a_hand_edited_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RUN the frozen case. Reading its source is what failed four times.

    Every static approximation of "the case compares the committed file against the emitter"
    has been defeated by a body that satisfies the syntax and not the intent. The intent is
    one sentence and it is executable: **stage a bundle that IS the emitter's output and the
    case must pass; hand-edit that bundle and the case must fail.**

    Two substitutions make it runnable today, and neither weakens it:

    - `table_yaml`/`table_resource` are row 5's and do not exist yet, so the JOB emitter
      stands in for them. It is the same emitter family out of the same module, its round
      trip is already pinned by `test_ac01`, and the case cannot tell the difference --
      which is the point, because this asserts the case's LOGIC, not the audit schema.
    - `_bundle_path` is pointed at `tmp_path`, so nothing here touches the real
      `databricks/` directory, which does not exist until row 6.
    """
    from ingestproof import contracts

    module = _ac08a_module()
    monkeypatch.setattr(contracts, "table_yaml", contracts.job_yaml, raising=False)
    monkeypatch.setattr(contracts, "table_resource", contracts.job_resource, raising=False)

    staged = tmp_path / "incidents_audit.yml"
    monkeypatch.setattr(module, "_bundle_path", lambda: staged)

    case = module.test_the_committed_bundle_is_what_the_emitter_returns
    emitted = contracts.job_yaml(module._one_declaration())

    # POSITIVE CONTROL. Without it a case that always raises would satisfy the half below.
    staged.write_bytes(emitted.encode("utf-8"))
    case()

    # THE ONE THAT MATTERS. A hand edit is what row 6 lets in and what nothing else catches.
    hand_edited = emitted.replace("incidents", "somebody-elses-table", 1)
    assert hand_edited != emitted, "the fixture failed to alter the emitted YAML"
    staged.write_bytes(hand_edited.encode("utf-8"))

    with pytest.raises(AssertionError):
        case()


@pytest.mark.parametrize(
    ("sample", "caught_by"),
    [
        ('BUNDLE = "databricks/resources"', {"text", "tree"}),
        ('BUNDLE = pathlib.PurePosixPath("databricks", "resources")', {"text", "tree"}),
        ('BUNDLE = "DATABRICKS/RESOURCES"', {"text", "tree"}),
        ('BUNDLE = f"{root}/databricks/resources"', {"text", "tree"}),
        # Implicit concatenation: the PARSER folds it, so the tree sees one token and the
        # source text never contains it.
        ('BUNDLE = "data" "bricks/resources"', {"tree"}),
        # `+` is NOT folded by the parser. Only the folding walk above catches this, and it
        # is the evasion that defeated the first version of this file.
        ('BUNDLE = "data" + "bricks/resources"', {"tree"}),
        # A comment spells the token and binds nothing, so only the text sweep sees it.
        ("# reads databricks/resources/*.yml", {"text"}),
        # Spells the vendor nowhere at all: refused by shape, not by name.
        ('BUNDLE = next(ROOT.glob("*/resources/*.yml"))', {"shape"}),
    ],
)
def test_each_arm_of_the_guard_catches_what_only_that_arm_can(
    sample: str, caught_by: set[str]
) -> None:
    """The inert-guard control, with each sample's catching arm named rather than summed.

    The previous version asserted only `text or tree` and described its own samples wrongly
    -- it called the last two the ones a plain `in source` check misses, when one of those
    was caught by both arms and the concatenation case sat third of five. Naming the arm per
    sample makes the claim checkable and makes a silently-widened arm fail here: if the text
    sweep ever started catching the glob case, this asserts it does not.
    """
    arms = {
        "text": VENDOR in sample.lower(),
        "tree": any(VENDOR in s.lower() for s in _folded_strings(sample)),
        "shape": bool(_enumerating_calls(sample)),
    }

    assert {name for name, hit in arms.items() if hit} == caught_by, (
        f"the arms that catch {sample!r} moved: expected {sorted(caught_by)}, "
        f"got {sorted(name for name, hit in arms.items() if hit)}"
    )
