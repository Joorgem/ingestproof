# Acceptance criteria — ingestproof

OpenFastTrace specification items. The grammar is OFT's, not the `AC-01` shorthand the
design document uses in prose: `req~ac-01~1`, where the trailing number is the revision.

**`Needs:` is mandatory on every item.** Measured: an OFT item without a `Needs:` field is
a *terminating item* and traces clean, so a gate over a spec full of them is inert.
`tools/needs_check.py` enforces it in the inner ring.

**Editing an item's text without incrementing its revision is a defect.** OFT does not
catch that on its own — it depends on a human bumping the number. `tools/spec_hashes.py`
holds a SHA-256 of each item's text and fails when the text moves and the revision does
not.

## A new table enters through one declaration
`req~ac-01~1`

A new table enters through one declaration and comes out with schema, rules, quarantine,
promotion and a job YAML, without editing any execution module.

Ring: inner

Needs: impl, utest

## The differential detects the three CSV incidents
`req~ac-02a~1`

The differential detects the three CSV incidents over a corpus produced by a frozen
generator script, with a clean negative control, in CI, in under a minute.

Ring: inner

Needs: impl, utest

## Zero false positives on the real corpus
`req~ac-02b~1`

Zero false positives over the real `Estabelecimentos6` (month and SHA-256 fixed by ASM-6),
measured once, with the command and its output committed as evidence. Not a CI gate.

Ring: nightly

Needs: impl, utest

## Damage is located by record and field index
`req~ac-03~1`

The report locates each damaged value by (record index, field index). Byte position
belongs to layer 3 and is not required here.

Ring: inner

Needs: impl, utest

## The library refuses to run without a declared dialect
`req~ac-04~1`

The library refuses to run without a declared source dialect, with a message that says
why.

Ring: inner

Needs: impl, utest

## The false-positive rate under a wrong dialect has its own denominator
`req~ac-05~1`

The false-positive rate under a wrongly declared dialect is measured with its own
denominator and published. The 452-of-459 and 39 figures in the measurements reuse a
denominator from a different experiment and must be re-derived before being cited.

Ring: nightly

Needs: impl, utest

## The verdict holds across three size thresholds
`req~ac-06~1`

The verdict holds on fixtures crossing 1 MiB, 4 MiB and 64 MiB, with the test asserting
`os.path.getsize()` before running the differential. Measured: Hypothesis buffers at 8,192
bytes and its largest generated example was 32 bytes, so the inner ring never enters the
regime this library polices.

Ring: nightly

Needs: impl, utest

## Corpus A and B run without a workspace and without a JVM
`req~ac-07~1`

Corpus layers A and B run in CI with no workspace and no JVM in the declaration layer, in
under a minute.

Ring: inner

Needs: impl, utest

## The check runs inside Spark against local Delta
`req~ac-08a~1`

The check runs inside Spark against local open-source Delta and fails the task, with no
credential and no workspace. `databricks/resources/*.yml` is committed.

Ring: nightly

Needs: impl, utest

## One workspace execution, scheduled by a human
`req~ac-08b~1`

One execution in the workspace, scheduled by Jorge, outside the loop, with the run id as
evidence. Never inside the loop: the Databricks quota is per-account and would take down
the flagship lane.

Ring: external

Needs: impl, utest

## The comparison target is promote union quarantine
`req~ac-09~1`

The differential compares against `promote ∪ quarantine` for one `_batch_id`: a record
routed to quarantine is not reported as damage. Measured: comparing against the landed
bronze table gives 1% false positives with zero real damage, because bronze is the parse
minus what the quality gate rejected.

Ring: inner

Needs: impl, utest

## The package installs from PyPI
`req~ac-10~1`

`pip install ingestproof` works from PyPI, with `py.typed` and attestations.

Ring: external

Needs: impl, utest

## The adoption pull request lands in the production path
`req~ac-11~1`

The adoption pull request inserts the gate into the flagship's production path, between
`promote` and `reclaim_landing`, and that repository's CI stays green.

Ring: external

Needs: impl, utest

## The ledger records every turn and the README publishes the measured split
`req~ac-12~1`

The ledger records every turn with an `author` field, and the README publishes the
measured human/loop division plus at least one case of the gate stopping the agent.

Ring: inner

Needs: impl, utest

## The README opens with the free DuckDB baseline
`req~ac-13~1`

The README opens with the free DuckDB baseline, with the script committed and runnable.

Ring: inner

Needs: impl, utest

## The prior-art table names every neighbour
`req~ac-14~1`

The prior-art table names DQX, Lakebridge, DVT, Frictionless, Pollock, dlt and datacompy,
each with what it lets through.

Ring: inner

Needs: impl, utest

## Adding JSON Lines modifies no existing file
`req~ac-15~1`

Adding JSON Lines produces a `git show --stat` with zero modified files.

Ring: nightly

Needs: impl, utest

## A review finding is resolved only by a diff that touches it
`req~ac-16~1`

The loop opens the pull request, waits for the reviewer to conclude, and marks a finding
resolved only when that turn's diff touches the file and the line range the finding cites.
It does not merge.

Ring: inner

Needs: impl, utest

## An interrupted turn does not contaminate the next one
`req~ac-17~1`

An interrupted turn does not contaminate the next one: `reset --hard && clean -fdx`
removes an untracked file planted before the turn. Measured: `reset --hard` alone leaves
it, and an orphan `conftest.py` was observed turning a red acceptance suite green.

Ring: inner

Needs: impl, utest

## The audit report lands in a Unity Catalog table
`req~ac-18~1`

The report is written to a Unity Catalog table (`<catalog>.<schema>.<table>`), with owner
and grant declared in the bundle YAML.

Ring: nightly

Needs: impl, utest

## The VPS is rebuilt from committed code
`req~ac-19~1`

The VPS is rebuilt from scratch by committed code; `terraform plan` posts as a pull-request
comment and `apply` runs only on merge, from a protected environment.

Ring: external

Needs: impl, utest

## The release path is hardened after it is proven
`req~ac-20~1`

The Trusted Publisher environment is `pypi`, the GitHub environment of the same name
requires a reviewer, and there is one recorded run that stopped waiting for approval.
Deliberately after the first publish: the OIDC path has never been exercised here, and
stacking protection on an unproven step gives one error two causes.

Ring: external

Needs: impl, utest
