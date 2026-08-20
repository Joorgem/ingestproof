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
