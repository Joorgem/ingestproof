# ingestproof

> A bronze ingestion is a contract — and a proof that the parse did not lie.

Declare a table once and get its schema, its quality rules, its quarantine, its promotion
and its job wiring — plus a fidelity check that compares what landed against the bytes
that were sent.

**Status: P0.** The name is claimed, the harness is built, and the library is not written
yet. What follows is measured, not planned.

## Start with what you already have for free

Before this library is worth installing, here is the free baseline: DuckDB, reading the
three CSV incidents this project was built around, with a clean negative control.

`tools/duckdb_baseline.py`, runnable as `uv run python -m tools.duckdb_baseline`:

```
duckdb 1.5.5

multiline.csv: 2 rows accepted, 0 rejected

escape.csv: 1 rows accepted, 0 rejected

extra_field.csv: 2 rows accepted, 1 rejected
    line=4 col=3 TOO MANY COLUMNS: '3,4,EXTRA'

clean.csv: 3 rows accepted, 0 rejected
```

DuckDB catches one of the three: in `extra_field.csv`, one row is rejected as
`TOO MANY COLUMNS` at line 4. The other two it parses correctly — `multiline.csv` keeps
the newline inside the quoted field, and `escape.csv` returns `say "hi", bye` intact.
That is the measured gap, and it is not a defect in DuckDB: those two files are valid CSV,
and the damage in the real incident was done by the production reader, not by the file.
A correct parser has nothing to reject there and nothing to compare against, which is why
one parser cannot see this class of defect and a differential between two parsers can.

Two limits of that baseline:

- DuckDB's `reject_errors` populates **only for rows it rejects**. The row that reproduces
  the incident — `1,"say ""hi"", bye"` — it parses cleanly and emits no position for. It
  does report a position for what it *does* reject: the output above says `line=4 col=3`.
  So the limit is not that DuckDB lacks positions — it is that it has none for the rows it
  **accepted**, which is exactly where the damage in these incidents lives.
- Its non-UTF-8 path is single-threaded: **~15 MB/s in cp1252** against ~121 MB/s in UTF-8.
  The corpus that matters here is cp1252.

## Prior art, and what each one lets through

| tool | what it does | what it lets through |
|---|---|---|
| **Databricks Labs DQX** | quality rules plus `compare_datasets` on Databricks | compares two DataFrames — both already parsed, so a shared parse defect cancels on both sides |
| **Databricks Labs Lakebridge** | reconciles a relational source against Databricks | relational sources only; does not accept a file |
| **Google DVT** | file against table | reads with bare `pandas.read_csv(path)`, no dialect; row-hash unsupported for file connections |
| **datacompy** | DataFrame-to-DataFrame comparison with a difference report | both sides are already parsed, and it takes no position on how they were read |
| **Frictionless** | checksum, byte count, row count, field count of the file | proves the file is the expected file, not that the parse preserved it |
| **Great Expectations / dbt-expectations / Deequ** | table, and cross-table | the same shared-defect cancellation |
| **Soda** | reconciliation between two relations | reconciliation is not in the open-source package |
| **dlt / Pandera** | schema contracts at ingestion | contracts of type and shape, not of parse fidelity |
| **DuckDB** `strict_mode` + `store_rejects` | the rejections of DuckDB's own parse | describes DuckDB's parse, not the table that landed |
| **Pollock** (VLDB 2023) | a formal file-to-load metric | needs ground truth; it is a benchmark, not a gate |

The sentence that covers the whole cross-table family: they all compare two things that
have **already been parsed**, so a shared parse defect cancels on both sides — which is
exactly the incident where a row count closed perfectly around the damage.

Source-to-target reconciliation is a named category with roughly twelve implementations,
two of them from Databricks Labs. What is not packaged anywhere is a single declaration
that owns the schema, the rules, the quarantine, the promotion **and** a fidelity check
against the source bytes.

## What the research killed

Publishing the dead ends is the point of this section.

- **Byte-for-byte round-trip is unsound.** RFC 4180 makes quoting optional, so valid CSV
  false-positives. And the obvious correction creates a blind spot: re-segmentation damage
  round-trips byte-identical.
- **Scalar conservation is blind where it matters.** Of the 459 real damaged records from
  the `escape` incident, **456 preserve field count, row count, total bytes and payload
  digest**. Any conservation check walks straight past them.
- **Row-to-record alignment breaks before the check does.** One record with an embedded
  newline makes a 1,000-record file emit 1,001 rows, and a positional zip then reports
  about 500 divergences for one real defect. Resynchronisation is a requirement, not a
  refinement.
- **Comparing against the landed bronze table is wrong by construction.** Measured: 1%
  false positives with zero real damage, because bronze is the parse *minus* what the
  quality gate rejected. The correct target is `promote ∪ quarantine` for one batch.

Every number above is in [`docs/measurements.md`](docs/measurements.md), which is the only
citable source. Anything listed as fragile there is not cited anywhere until it is
re-derived.

## How this was built

Not written yet. AC-12 requires this section to publish the human/loop split measured from
the ledger, together with a case of the gate stopping the agent; `LOOP.md` carries the
ledger's current rendering.

## Licence

MIT.
