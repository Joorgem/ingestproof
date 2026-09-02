# Queue

The loop takes the **first unclosed** item. It cannot write to this file, and it does not
decide when an item is closed — see the closing rule at the bottom.

## P1 — the contract layer

| # | task | closes when |
|---|---|---|
| 1 | A `TableContract` dataclass: name, contract id, the staging/bronze/quarantine triple, landing mode, prefix, constraints. Generalised out of the flagship's `registry.py`, with no CNPJ vocabulary. | `req~ac-01~1` covered and its acceptance test green |
| 2 | Import-time guards: unknown contract, prefix that does not match a file group, table with no job. Each refuses at import, not at call. | `req~ac-01~1` acceptance test covers all three refusals |
| 3 | Quality rules as `(name, callable -> Column)` pairs. The *definition* is pure Python and **must not import Spark**; only the *evaluation* touches it. | `req~ac-07~1` covered, and the no-Spark-import test passes with pyspark uninstalled |
| 4 | Fail-closed promotion and `_batch_id` quarantine, generalised. | `req~ac-09~1` covered |
| 5 | The job-YAML emitter: one declaration in, a bundle resource out. | `req~ac-01~1` acceptance test asserts a YAML round trip |

## P2 — the fidelity check

Layer 2 of `docs/design.md` section 5. The differential and the resynchronisation are
**human or adjudicated** by section 15, so they are not in this queue: the loop gets the
declared dialect and the report, and the two items marked `human` below are here so the
phase reads whole, not so a turn takes them.

| # | task | who | closes when |
|---|---|---|---|
| 1 | A `Dialect`: encoding, delimiter, quotechar, escape policy, record separator, empty semantics. No field has a default, and nothing infers one. `require_dialect` refuses a missing one with a message that says why. | loop | `req~ac-04~1` covered and its acceptance test green |
| 2 | `parse_records(source, dialect)`: bytes and a declared dialect in, records out. A wrongly declared dialect is OBEYED, never corrected. | loop | `req~ac-04~1` acceptance test's wrong-dialect case green |
| 3 | `Damage(record_index, field_index, expected, actual)` and `locate(expected, actual)` over two ALIGNED record streams, ordered by record then field. It carries no line number and no byte position. | loop | `req~ac-03~1` covered and its acceptance test green |
| 4 | `locate` refuses streams of different lengths rather than zipping them, naming resynchronisation as what has to happen first. | loop | `req~ac-03~1` acceptance test's `Misaligned` case green |
| 5 | `Report`: the damages plus `records_compared`, so a count is never published as a rate. | loop | `req~ac-03~1` acceptance test asserts the denominator |
| 6 | The differential: run the reference parse against a landed reading and produce a `Report`. | **human** | `req~ac-02a~1` covered and its acceptance test green |
| 7 | Resynchronisation: after a divergence, re-anchor on K byte-identical records and report a bounded damage span. | **human** | `req~ac-02a~1` acceptance test's multiline case green |

### Why items 6 and 7 are not the loop's

`docs/design.md` section 15 assigns the differential and the resynchronisation to a human
or to adjudication. Section 5 says why for item 7: a positional comparison after one
embedded record separator reports about 500 divergences for one damage, and choosing the
re-anchor width K and the span boundary is a judgement no frozen test captures well.

Item 3 is the loop's because `locate` over ALIGNED streams is the report's locating step
rather than the differential: the differential is running two parsers, and the resync is
what to do when they disagree on length. If that reading is wrong, items 3 to 5 move.

### What P0 owed this phase and did not leave

The three acceptance files below did not exist when P1 closed, so no P2 item could have
closed even with the code written. They are drafted at
`scratchpad/p2/` and are a human's commit, because `tests/acceptance/**` is frozen:

- `tests/acceptance/test_ac04_dialect_is_declared_never_inferred.py`
- `tests/acceptance/test_ac03_damage_is_located_by_record_and_field.py`
- `tests/acceptance/test_ac02a_the_differential_detects_the_three_incidents.py`

Measured on the drafts: **23 xfailed** under `uv run pytest`, and **23 failed** under
`--runxfail`. Same conditional strict `xfail` as P1's three, conditioned on
`ingestproof.dialect`, `ingestproof.report` and `ingestproof.differential` respectively, so
each marker evaporates on its own when the module lands.

## P3 — the platform path

Layer 1's job resource and layer 2's report meet Spark here. `docs/design.md` section 15
marks P3 **mista** without saying where the line falls; the line is the allowlist in
`tools/hooks/ingestproof_allowlist.py`, and item 6 is the one thing this phase delivers
that falls outside it.

Both of P3's gates are `Ring: nightly` in `.spec/acceptance.md`. That does not change what
closes an item, but it changes where the second signal is produced and who may record it —
see the ring note below.

~~**No row here is dispatchable yet.** Three commits on frozen paths have to land first and
none of them exists; they are under "What P3 is owed". A turn that takes row 1 today has
nothing to import and no test to turn green.~~

**THE THREE COMMITS HAVE LANDED AND ROW 1 IS DISPATCHABLE.** The `spark` dependency group in
`c9182b1`'s sibling `014eb48`, the `ring` job in `c9182b1`, and the two acceptance files in
the commit that struck this paragraph. What a turn taking row 1 now has: `pyspark` and
`delta-spark` resolvable, `tests/acceptance/test_ac08a_...py` red under `--runxfail` waiting
for `ingestproof.spark`, and a nightly ring that executes it. **Read the closing rule at the
bottom before dispatching anyway** — the two signals are unchanged, and signal 2 is still
produced in no turn's own test run.

| # | task | who | closes when |
|---|---|---|---|
| 1 | The Spark entry point: read `promote ∪ quarantine` for one `_batch_id` out of a local open-source Delta table and hand the differential the two record streams it already takes. `pyspark` and `delta` are imported **inside** the function, never at module scope. | loop | `req~ac-08a~1` acceptance test's local-Delta reading case green in the nightly |
| 2 | The verdict fails the task: any damage raises out of that entry point, a clean batch returns. It does not log and continue, and it takes no credential. | loop | `req~ac-08a~1` acceptance test's failed-task case green in the nightly |
| 3 | `audit_rows(report, batch_id, contract_id)`: a `Report` becomes rows with a fixed column set carrying `records_compared`, so the denominator reaches the table and a count is never stored as a rate. Pure Python; no Spark import. | loop | `req~ac-18~1` acceptance test's denominator case green in the nightly |
| 4 | The writer targets `<catalog>.<schema>.<table>` taken from the declaration — a three-level name, never a path. | loop | `req~ac-18~1` acceptance test's three-level-name case green in the nightly |
| 5 | `table_resource`, beside `job_resource` in `src/ingestproof/contracts.py`: the audit table with `owner` and `grant`, emitted in the same small subset `load_job_yaml` reads back. | loop | `req~ac-18~1` covered and its acceptance test green in the nightly |
| 6 | `databricks/resources/*.yml` committed: what item 5 emits, checked in under that path. | **human** | `req~ac-08a~1` covered and its acceptance test green in the nightly |

Two rules govern the "closes when" column, and the second is the general form of the first.

1. Every row names a distinct **case** of one acceptance test, and the row that closes a
   whole criterion is the **last** row touching that criterion — row 5 for `req~ac-18~1`,
   row 6 for `req~ac-08a~1`.
2. **A row may not close a criterion whole if any row below it, of either `who`, delivers
   something that criterion's own text requires.** Where the criterion's text names an
   artefact no row above can produce, there are exactly two repairs: move the close down to
   the row that produces the artefact, or constrain the frozen acceptance test — in the
   debt subsection, where whoever writes it will read it — so the requirement is observed
   where it is produced rather than where it is committed. Both repairs are used below.

The other way round is a queue that cannot run: a row closing on whole-criterion coverage,
sitting above rows that deliver what the criterion needs, is a row the loop holds and
cannot green, and the loop takes first-unclosed. With row 6 being a human's, that shape
stops the phase outright rather than merely stalling it. Do not fix it by reordering the
table either — item 6 is a hand-commit of what item 5's emitter produces, and the file
cannot precede the emitter.

Rule 2 is what row 5 has to answer for. `req~ac-18~1`'s text requires "owner and grant
declared in the bundle YAML", and the committed bundle YAML is row 6, below it. Row 5 keeps
the close only because the debt subsection pins the `ac-18` acceptance test to the
**emitter's returned string** rather than to a committed path. Without that constraint,
row 5 is unclosable for the same reason row 1 was.

### Why item 6 is not the loop's

The allowlist hook writes the line. `tools/hooks/ingestproof_allowlist.py` carries
`WRITABLE_PREFIXES = ("src/", "tests/unit/", "tests/property/", "docs/")` and
`WRITABLE_FILES = ("LOOP.md",)`, and its final branch is default-deny. `databricks/` is in
neither list, and it is in no glob of `tools/frozen.txt` either — which is the class that
hook's own docstring names: *"For a path that is neither writable nor frozen, CI never
looks, and this is the only thing that refuses."* `tests/integration/**` is the measured
example of the same class, recorded in `docs/design.md` section 7.3.

The emitter is a different question from the file, and that is why item 5 is the loop's and
item 6 is not. `job_resource` and `job_yaml` already live in `src/ingestproof/contracts.py`
(lines 239 and 265), the loop may extend them, and its output is a string. Turning that
string into a tracked file under `databricks/` is the write the hook refuses.

It refuses only the editing tools — the docstring says so: *"it cannot parse arbitrary
shell, and it is not asked to."* That is a gap, not a permission. A turn that shelled out
to write the path the hook denies is `docs/design.md` section 14's "o agente atacar o gate",
committed by the thing the gate exists to watch.

Nothing in this queue touches a workspace. `prompt.md` says **"Never touch Databricks. The
quota is per-account and shared with a live lane"**, and `docs/design.md` section 8 item 8
gives the one exception: AC-08b, run by hand by Jorge, outside the loop, with the flagship
lane stopped. AC-08b is `Ring: external` in `.spec/acceptance.md` and section 15 puts it
outside the phase table entirely, so it is not a row here.

### The ring: both of P3's gates are nightly

`.spec/acceptance.md` gives `req~ac-08a~1` and `req~ac-18~1` the same two fields:
`Ring: nightly` and `Needs: impl, utest`. P3 is the first phase where that is true of every
gate — P1's `req~ac-01~1` and `req~ac-07~1` are inner, and so are all four of P2's.

The two signals part company here.

- **Signal 1 can be read inside a turn.** OFT needs only the JVM, and `CLAUDE.md`'s Java
  section records `$JAVA_HOME/bin/java` at 17.0.19 on the development machine. It is called
  nightly because CI's inner ring carries no JVM step, not because a turn cannot run it.
- **Signal 2 is produced in no turn's own test run.** The acceptance test needs Spark.
  `pyproject.toml`'s `addopts` is `-m 'not external and not nightly'`, so `uv run pytest`
  deselects it by construction; `CLAUDE.md`'s ring table says the inner ring has no JVM, no
  Spark and no network; and that table also says the nightly ring is **Linux only**, while
  turns run on Windows.

So signal 2 comes out of `.github/workflows/nightly.yml` and nowhere else. That workflow
carries `workflow_dispatch` beside its cron, so the observation is a dispatch rather than a
calendar day, and its `traceability` job uploads `oft-report.txt` and `oft-spec-count.txt`
as the `oft-report` artifact — signal 1 comes back from the same run. That upload step
carries `if: always()`, so the report returns even from a run whose `Trace` step failed,
which is what makes this readable at all while the nightly is in the state the debt
subsection records.

One asymmetry to expect while reading the two together: the id can still be in the report
when the acceptance test is already green. `Needs: impl, utest` wants both tags, and this
file's own "How signal 1 is read" table calls `(-impl, utest)` the state where "the
acceptance test cites it; nothing implements it". Writing the `[impl->req~ac-08a~1]` tag
into `src/**` is a separate edit from writing the code, and it is a turn's to make. Green
test plus present id means the tag is missing, not that the work is wrong.

**Note — this is not an exception to the closing rule at the bottom of this file.** Both
signals still have to hold and neither is something a turn can write. What changes is where
signal 2 is produced, and who is allowed to record that it held.

**The close must be recorded by an agent-authored turn; a human's turn will not do it.**
`turns_since_close` (`loop/run_turn.py:90-97`) walks the ledger backwards and `continue`s
past any entry for which `is_loop_turn` is false, and `is_loop_turn`
(`loop/ledger.py:59-70`) is `is_turn(entry) and entry.get("author") != "human"`. A **human**
row carrying `closed_criterion` is therefore skipped rather than counted as a reset, and the
walk keeps counting backwards past it. Measured on `$LOOP_HOME/iterations.jsonl`, 31 rows:
seq 30 is `author=human` with `closed_criterion=req~ac-02a~1`, and `is_loop_turn` is
**False**; the counter reads 0 only because seq 28 (`author=loop`,
`closed_criterion=req~ac-03~1`) resets it. Closing a P3 criterion as a human leaves the
brake exactly where it was.

The recording turn therefore observes both signals itself rather than being told: dispatch
the workflow, wait for the run, read its conclusion, download the `oft-report` artifact, and
only then write `closed_criterion` — which is what `prompt.md` already requires, "only when
both signals in `TASKS.md`'s closing rule were observed". That a turn may do network GitHub
work is not an assumption: `prompt.md`'s Finishing section already has it opening a pull
request and waiting for a reviewer to conclude. `CLAUDE.md`'s "no network" is a property of
the inner ring's test command, not of the turn.

**The budget is turns, not rows.** `turns_since_close` counts the ledger's trailing loop
turns across the whole ledger — a row may cost more than one turn, and the count when P3
starts is whatever the phase before it left. Read the real number before dispatching rather
than counting rows in this table:

```bash
uv run python -c "from loop.ledger import read_all; from loop.run_turn import turns_since_close; print(turns_since_close(read_all()))"
```

Keep it under `STALL_LIMIT = 5` by dispatching a nightly and letting an agent-authored turn
record the close. **Fallback:** let `stall_report` fire at five and have a human restart the
loop. It is the fallback and not the plan — its text blames the task wording, and for P3
that diagnosis would be false.

### What P3 is owed before any item here can close

~~Three commits, all on frozen paths, all a human's. None of them exists today.~~
**All three have landed.** This subsection is kept because it is the reasoning that produced
them, and because every constraint it states on HOW the two files assert is still binding —
the constraints outlived the debt. What follows is struck where it describes a tree that no
longer exists and left standing where it states a rule.

~~**The two frozen acceptance tests do not exist.** `tests/acceptance/` holds nine files —
`test_ac01`, `test_ac02a`, `test_ac03`, `test_ac04`, `test_ac07`, `test_ac09`, `test_ac10`,
`test_ac17` and `test_frozen_pins` — and `tools/frozen.sha256` lists exactly those nine.
Nothing cites `req~ac-08a~1` or `req~ac-18~1`.~~ It holds **eleven**, the manifest lists
**49 frozen paths**, and both ids are cited — which is why `oft-report.txt` now reads
`(-impl, utest)` for both rather than `(-impl, -utest)`. `tests/acceptance/**` is frozen by
`tools/frozen.txt`, so those two files were a human's commit:

- `tests/acceptance/test_ac08a_the_check_runs_inside_spark_against_local_delta.py`
- `tests/acceptance/test_ac18_the_audit_report_lands_in_a_unity_catalog_table.py`

Each has to carry the cases the rows above name, or a row has nothing to close against.
Two of those cases carry a constraint on **how** they assert, and it is not decoration —
rule 2 above is discharged by it:

- **The `ac-18` owner-and-grant case must assert against what `table_resource`/`job_yaml`
  return, not against a file on disk.** `req~ac-18~1`'s text
  (`.spec/acceptance.md:211-214`) says "with owner and grant declared in the bundle YAML"
  and says nothing about that YAML being committed; the committed-file requirement lives in
  `req~ac-08a~1`, which names `databricks/resources/*.yml` explicitly. Reading the emitter's
  output is therefore the criterion's literal reading, not a weakening of it. A test that
  instead opened the committed path would make row 5 — a `loop` row — depend on row 6, a
  human's, and the phase would deadlock exactly as it did before round 1.
- **The `ac-08a` committed-bundle case should assert that the committed file equals what the
  emitter returns.** That is where the drift the first constraint opens up gets closed: with
  `ac-18` checking content and `ac-08a` checking that the tracked file is that content, a
  hand-edited `databricks/resources/*.yml` fails a gate instead of passing quietly.

**Make the first constraint mechanical, in the same commit.** A stated constraint on a
frozen file is only as good as the next person's reading of it, and that is the queue's
worst remaining residual: if the `ac-18` file opens the committed path, row 5 becomes
unclosable and nothing in the queue notices until the brake fires. It does not have to stay
stated. `tests/unit/**` is outside the frozen set, so a unit test may read the `ac-18`
acceptance file's own source and assert it does not reference `databricks/resources` —
after which the frozen file cannot be written or later edited to open that path without a
red inner ring. The precedent is in the tree: `tests/unit/test_allowlist_hook.py` asserts
properties of a frozen gate from the writable side, and its docstring says so in as many
words.

**IT LANDED, IN THAT COMMIT, AS
`tests/unit/test_ac18_asserts_the_emitter_not_the_committed_bundle.py`.** Do not write a
second one: this paragraph reads as an imperative and it is discharged. The reasoning below
is NOT struck -- it is why the guard was a human's commit rather than a queue row, and that
argument holds unchanged; only its tense moves.

**It took four versions, and the three failures were one failure.** A token check that
`POISONED_ENVIRONMENT`'s `DATABRICKS_HOST` satisfied; then a name check that survived
`_bundle_path` being hollowed to a tmp path; then a check on which tokens sat in which
subtrees, which a one-character `.yml` -> `.yaml` walked past. **Every one of them read the
SOURCE of the machinery instead of asking what the machinery does.** The version that landed
calls `_bundle_path()` and looks at the path that comes back, and RUNS the frozen case
against a staged bundle it then hand-edits. Static reading survives only for what neither a
call nor a run can reach: a fixture that rebinds the resolver after import, and a marker
condition hardcoded to a constant. Its own
docstring lists, measured, the four classes of spelling it does NOT catch.

**And the fourth version was wrong about its own remaining half.** It said reading the case's
source was "the one thing a call cannot show". A call shows it: stage a bundle that IS the
emitter's output and the frozen case must pass, hand-edit that bundle and it must fail. Ten
one-line edits satisfied the static approximation while leaving a case that could not fail on
a hand edit -- `assert raw == raw` among them. **Run the case, do not read it** is the whole
lesson of this guard, and it took four rounds to apply it to both halves instead of one.

**That guard belonged in the human's acceptance-file commit, not in a row of this queue**,
for two reasons that are both mechanical rather than stylistic:

- **A row closing no criterion cannot close at all.** Nothing in `.spec/acceptance.md`
  requires a unit test about another test's source, so such a row would name no criterion,
  and the closing rule at the bottom of this file admits no other way to close an item. The
  loop takes first-unclosed: the row would jam the queue permanently, not merely stall it.
  Carrying it as a row would therefore cost P3 an explicit exception to the closing rule,
  and a guard is not worth spending that on.
- **It is needed before row 1, and a row cannot be there.** The guard's value is at the
  moment the frozen file is written. Committed alongside the two acceptance files, it is in
  place before anything is dispatchable — and a human-authored turn is invisible to
  `turns_since_close` (`is_loop_turn` is false for `author=human`), so it costs the stall
  budget nothing.

**The stall budget, stated.** Rows 1-4 close cases rather than criteria, so they are four
consecutive non-closing loop turns; row 5 is the first to write `closed_criterion`. Against
`STALL_LIMIT = 5` that is **one turn of margin**: any single row among 1-4 costing two turns
fires the brake before P3's first close. A guard row placed anywhere before row 5 would
consume that margin outright and make the brake fire by construction; placed after row 5 it
would be free but would arrive after the moment it exists to protect. Neither is worth it,
which is the second half of why the guard is a human's commit. The margin does not change
under this decision, and it is thin: read `turns_since_close(read_all())` before dispatching
rather than assuming P2 left the counter at zero.

This is P2's lesson repeating, with one difference that makes it more dangerous rather than
less. `tests/property/**` is writable by a turn and already carries real `[utest->...]`
tags — `tests/property/test_locate_is_exact.py:39` is one — so the loop can move
`req~ac-18~1` from `(-impl, -utest)` to absent from the report on its own. **Signal 1 can
go covered here with no acceptance file in the tree at all**, and covered is not closed.

Whoever writes those two files: `--strict-markers` is on, and `nightly` is declared in
`pyproject.toml`'s `markers`. A P3 acceptance file without `pytest.mark.nightly` lands in
the inner ring, where there is no Spark.

~~**Spark is not a dependency.** `pyproject.toml`'s `[dependency-groups].dev` is hypothesis,
mypy, pytest, pytest-cov, pytest-timeout, pyyaml and ruff. Grepping `uv.lock` for `pyspark`,
`delta-spark` and `delta_spark` returns nothing. Both files are frozen. Until that commit
lands, item 1 has nothing to import and nothing to be type-checked against.~~

**It is one now, and NOT in `dev`.** `014eb48` added a separate `spark` group —
`pyspark>=4.2,<5`, `delta-spark>=4.4,<5` — because pyspark ships no wheel and the 450 MB
sdist would be downloaded on every push if the inner ring installed it. `ci.yml` and the two
nightly jobs that need no Spark sync `--all-groups --no-group spark`; only the nightly `ring`
job takes `--all-groups`. So "the inner ring has no Spark" is now true of the ENVIRONMENT and
not only of the imports.

There is a sequencing trap in that commit. `[tool.mypy]` sets `strict = true` over `files
= ["src", ...]`, and strict includes `--warn-unused-ignores` — measured by listing the
`strict_flag=True` arguments in `.venv/Lib/site-packages/mypy/main.py` for mypy 1.20.2. A
`# type: ignore[import-not-found]` on the Spark import is required while pyspark is absent
and becomes an *unused* ignore, and a red inner ring, the moment it resolves. The ignore
lives in `src/**`, which is the loop's; the dependency lives in `pyproject.toml`, which is
a human's. They have to move in the same direction, and they cannot move in the same
commit.

~~**No ring runs a nightly-marked test — and the trap is armed and empty.**
`.github/workflows/nightly.yml` has two jobs, `traceability` (`tools.oft`, `tools.oft
check-counts`) and `corpus` (`tools.fetch_corpus`); `CLAUDE.md`'s ring table says the same
in one line. Neither runs pytest, and `ci.yml`'s `uv run pytest` deselects `nightly`.
Nothing is marked `nightly` today: `pytest --collect-only -m nightly` collects nothing, and
the tests an inner-ring run deselects are `test_ac10`'s four, marked `external`.~~

**`c9182b1` added a third job, `ring`, and it runs `uv run pytest -m nightly`.** It does not
run that bare, and the reason is in its own comment: a bare run exits 5 on an empty
collection, which is indistinguishable from a run whose tests all lost their marker. So the
job carries a DECLARED LIST of the files that must be collected and compares it against what
pytest actually collects, failing in both directions — declared-and-missing, and
collected-and-undeclared. **A `nightly` file therefore lands in two frozen files at once**,
its own and `nightly.yml`, and they can only move together.

Measured after P3's two landed: `pytest --collect-only -m nightly` collects **13** (6 from
`ac-08a`, 7 from `ac-18`), an inner-ring run deselects **17**, and the ring is green at
`4 passed, 9 xfailed` — the nine being work no turn has done yet, red under `--runxfail`.

**And the gate that watches `.spec` traffic is currently dark.** The nightly's blocking
`check-counts` step has not run since 2026-08-24: on run 32812643761, step 7, "The JAR and
the parser see the same items", is `skipped`, because a failed `Trace` step skips
everything after it. That is being repaired separately in the same file, but it lands on
P3, because `check-counts` is the only thing watching the gap `CLAUDE.md` describes —
`tools/spec_parse.py` is deliberately narrower than OFT, so anything the JAR sees and the
inner ring does not is unhashed and never `Needs`-checked. P3 is a phase whose whole
output is new `[impl->...]` and `[utest->...]` tags, which is precisely the traffic that
moves OFT's `N total` and that `check-counts` exists to reconcile. Do not read a green
nightly as that gate having passed until step 7 runs again.

### Not in this queue

- **Byte-position location.** `docs/design.md` section 5 puts the span tokeniser first in
  Camada 3 and marks the whole layer cuttable; section 14 repeats it, and `req~ac-03~1`'s
  own text says byte position "belongs to layer 3 and is not required here". P3 is where it
  would be tempting, because a Spark reader has the offsets. It is not a P3 row.
- **JSON Lines.** Camada 3's second item, cuttable, and section 15 puts `req~ac-15~1` in
  P6.
- **AC-08b.** External, out of phase, and Jorge's — see above.

## Closing rule

An item closes when **both** hold, and neither is something a turn can write:

1. The criterion id it names moves from uncovered to covered in the OpenFastTrace report.
2. The frozen acceptance test citing that id moves from red to green.

If a turn believes an item is done and both signals disagree, the turn is wrong. Say so in
`LOOP.md`.

### How signal 1 is read

```bash
uv run python -m tools.oft        # writes oft-report.txt; needs the JVM, so nightly
grep "req~ac-01~1" oft-report.txt # COVERED when this finds nothing
```

The plain report lists **defects only**, and a covered criterion therefore *disappears from
it* rather than turning into an `ok` line. Measured with OFT 4.9.0 over this `.spec/`: with
one of the 22 criteria fully covered the report carries 21 `not ok [` lines and **zero**
`ok [` lines. For an item that `Needs: impl, utest` the three states are:

| the report says | state |
|---|---|
| `req~ac-01~1 (-impl, -utest)` | uncovered |
| `req~ac-01~1 (-impl, utest)` | the acceptance test cites it; nothing implements it |
| the id is absent | **covered** — this is signal 1 |

Do not read the summary's `N total` as a count of criteria. It counts every imported
coverage tag as a specobject too: 22 with no coverage, 23 with one tag, 24 with two.
`uv run python -m tools.oft check-counts` traces `.spec` alone for exactly that reason.

And a coverage tag written in **prose is a real tag**, in a SOURCE file: the JAR reads
`utest->req~ac-01~1` in square brackets out of any docstring or comment under `src`,
`tests`, `loop` or `tools`. Two such examples, written into a docstring as illustration,
were measured adding themselves to the count they were describing.

Markdown is the exception, and `.spec/acceptance.md` is markdown. The same bracketed tag
in its prose was measured changing `N total` by zero under both a `.spec`-only and a full
trace, with the criterion still reading `(-impl, -utest)`; so was one in a `.md` file
under `tests/`. The error is in the safe direction — such a tag is invisible rather than
double-counted — but a tag written there covers nothing.

### How signal 2 is read

```bash
uv run pytest tests/acceptance/test_ac01_one_declaration.py --runxfail
```

Every frozen acceptance test for a feature P1 has not written yet carries a **conditional,
strict `xfail`**. While the module it needs is missing, the test reports `xfailed` and CI
stays green; `--runxfail` makes the marker inert and shows the real red. The condition is
that module's existence, so the marker evaporates on its own the moment P1 lands it — after
which CI runs the test for real and red is red. Nobody has to remove the marker, and nobody
could: the file is frozen.

Signal 2 is that same command going green. The three files are
`tests/acceptance/test_ac01_one_declaration.py`,
`tests/acceptance/test_ac07_declaration_layer_needs_no_jvm.py` and
`tests/acceptance/test_ac09_promote_union_quarantine.py`.
