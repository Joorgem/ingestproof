# Two rows that recorded a commit instead of a task

`$LOOP_HOME/iterations.jsonl` is append-only and hash-chained, so a wrong row is corrected
by appending, never by editing. Two rows are worth knowing about before anything is
published from them — AC-12 reads this file.

Both have the same shape and the same fix. Each recorded the size of its task's first
commit rather than of the task, and each now carries an appended correcting row that names
the seq it corrects and the cutoff its figure is cut at.

## How `diff_lines` was derived

Each task's range comes from the `review-<base>..<tip>.diff` filenames in the SDD directory,
then `git diff --numstat --no-renames base tip`, summing insertions and deletions. The
method is not assumed: recomputing it for the three oldest rows reproduces their recorded
numbers exactly, including commit 1, where whether `uv.lock` counts decides between 753 and
222 and the recorded figure is 753.

## P0-T4 — recorded 224, which is the task's feature commit

| range | ins+del |
|---|---|
| `ce9ef05..544d429` — `feat: the turn ledger`, the feature commit | **224** |
| `ce9ef05..5915c5b` | 231 |
| `ce9ef05..feb54ee` — the whole task | 236 |

Seq 15 corrects seq 3, carries the 12-line difference, and names `feb54ee` as the cutoff.

This section used to say the figure reproduced nowhere, and it listed only the last two
rows of that table. It tried two of the three cuts and stopped one short of the one the
next section already describes. The wrong claim is recorded here rather than deleted: a
document that quietly drops what it got wrong teaches nothing to the next reader of it.

## P0-T14 — recorded 374, which is the first of the task's commits

The row was written from `e991de0..13c2660`, the pre-gate commit alone, while the task went
on to produce more. Seq 14 carries the real figure — 514 at cutoff `5081750`, against 438
at `74d1fb7` and 451 at `1cf8002` — and names the commit it was cut at.

That cutoff is not a rounding choice. A row recording the size of the task that writes it
cannot include the commit that renders the row, so some cutoff is unavoidable; naming it is
the part that makes the number checkable.

## What a correcting row costs, which is nothing

A correcting row is still a row, and the renderer used to count rows -- so `LOOP.md` briefly
published fifteen turns for fourteen turns of work. That was fixed rather than written down:
a row naming the seq it corrects is not a turn, `loop.ledger.is_turn` is the single place
that says so, and both things that count turns use it -- the `LOOP.md` rendering and the
stall detector, which would otherwise have walked toward its own limit for bookkeeping.

`LOOP.md` reads `Turns: **14**` and `| human | 14 |`. The chain holds sixteen rows and the
tip is the sixteenth, because the tip anchors the file rather than the turns.

So correcting a figure is cheap. If a later row is found to be wrong, append another.

## The rule a consumer of `diff_lines` needs

`loop.ledger.is_turn` answers one question — *is this row a turn* — and it is the right
filter for exactly one thing.

- **Counting turns:** filter by `is_turn`. Fourteen turns over sixteen rows.
- **Summing `diff_lines`:** do **not** filter. The correcting rows carry the difference, so
  they have to be added in. A consumer that filters by `is_turn` before summing reports
  **374** for P0-T14 where the task is 514, and **224** for P0-T4 where it is 236.

The two rules pull opposite ways on the same predicate, which is why this is written down
rather than left to be inferred. AC-12 publishes from the `diff_lines` column, so the
difference here is the difference between a published number and a wrong one.
