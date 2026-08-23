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

And a coverage tag written in **prose is a real tag**: the JAR reads `utest->req~ac-01~1`
in square brackets out of any docstring or comment under a traced path (`.spec`, `src`,
`tests`, `loop`, `tools`). Two such examples, written into a docstring as illustration,
were measured adding themselves to the count they were describing.

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
