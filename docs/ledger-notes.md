# Two rows in the ledger that do not reproduce

`$LOOP_HOME/iterations.jsonl` is append-only and hash-chained, so a wrong row is corrected
by appending, never by editing. Two rows are worth knowing about before anything is
published from them — AC-12 reads this file.

## How `diff_lines` was derived

Each task's range comes from the `review-<base>..<tip>.diff` filenames in the SDD directory,
then `git diff --numstat --no-renames base tip`, summing insertions and deletions. The
method is not assumed: recomputing it for the three oldest rows reproduces their recorded
numbers exactly, including commit 1, where whether `uv.lock` counts decides between 753 and
222 and the recorded figure is 753.

## P0-T4 — recorded 224, and nothing reproduces it

`ce9ef05..feb54ee` measures 236; `ce9ef05..5915c5b`, the same range cut at the review rather
than the fix round, measures 231. Neither is 224. Since T1, T2 and T3 reproduce exactly,
this is not a fault in the method.

It predates task 14 and it is seven to twelve lines. It is recorded here because it means
one of the rows is not derivable from the repository, which is worth knowing before the
column is published rather than after.

## P0-T14 — recorded 374, which is the first of the task's commits

The row was written from `e991de0..13c2660`, the pre-gate commit alone, while the task went
on to produce more. An appended correcting entry carries the real figure and names the
commit it was cut at.

That cutoff is not a rounding choice. A row recording the size of the task that writes it
cannot include the commit that renders the row, so some cutoff is unavoidable; naming it is
the part that makes the number checkable.

## What a correcting row costs, which is nothing

A correcting row is still a row, and the renderer used to count rows -- so `LOOP.md` briefly
published fifteen turns for fourteen turns of work. That was fixed rather than written down:
a row naming the seq it corrects is not a turn, `loop.ledger.is_turn` is the single place
that says so, and both things that count turns use it -- the `LOOP.md` rendering and the
stall detector, which would otherwise have walked toward its own limit for bookkeeping.

`LOOP.md` reads `Turns: **14**` and `| human | 14 |`. The chain still holds fifteen rows and
the tip is still the fifteenth, because the tip anchors the file rather than the turns.

So correcting a figure is cheap. If a later row is found to be wrong, append another.
