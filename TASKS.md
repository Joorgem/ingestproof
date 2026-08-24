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
