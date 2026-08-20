# The turn

You are executing one turn of the ingestproof loop. Read `TASKS.md`, take the **first
unclosed** item, and do only that.

## Before anything

1. `git reset --hard && git clean -fdx -e .venv`. Not one or the other. `reset --hard`
   leaves untracked files, and an orphan `conftest.py` was measured turning a red
   acceptance suite green.
2. Read the item's criterion in `.spec/acceptance.md`. If the item does not name a
   criterion id, stop: the queue is malformed and that is a human's problem.

## What you may write

`src/**`, `tests/unit/**`, `tests/property/**`, `docs/**`, and `LOOP.md`.

Nothing else. `tests/acceptance/**`, `.spec/**`, `TASKS.md`, `prompt.md`, `CLAUDE.md`,
`pyproject.toml`, `uv.lock`, `.github/**`, `.gitattributes`, `tools/**` and `loop/**` are
frozen. A `PreToolUse` hook refuses the write, and CI fails any pull request whose diff
names one of them. There is no override. If a frozen file is genuinely wrong, say so in
`LOOP.md` and stop — that is a human's edit.

`tools/**` and `loop/**` are frozen because they are the gates. You do not get to edit
your own judge.

## The rules that are not obvious

- **Never edit the body or the name of a property test in the same commit that changes
  `src/**`.** The Hypothesis seed is a hash of the test's cleaned source, so renaming one
  re-draws its entire corpus: a green turns red with nothing in production having moved.
  Adding `@example(...)` is safe — `_clean_source` strips decorators.
- **A property failed?** The whole turn is: pin the counterexample as `@example(...)` in
  `tests/property/**`, fix the code, commit. Nothing else.
- **A new module-level constant in `src/**` needs a test that asserts its value.** mutmut 3
  only mutates inside functions, so a bare constant produces zero mutants and the mutation
  gate is silently inert on it.
- **`# pragma: no mutate`, `@pytest.mark.skip` and `xfail` each need a one-line
  justification**, and every use is counted into the ledger.
- **Invoke Java as `"$JAVA_HOME/bin/java"`.** Bare `java` is 11 on this machine; OFT is a
  Java 17 jar.
- **Never touch Databricks.** The quota is per-account and shared with a live lane.
- **Never claim this problem is unsolved.** Source-to-target reconciliation has about
  twelve implementations, two of them from Databricks Labs. Writing that no one else
  does this is banned in every artefact, and a repository-wide grep is run against that
  phrasing: it must find nothing.

## Finishing

You do not close a task. A task closes when its criterion id goes from uncovered to
covered in the traceability report **and** the frozen acceptance test citing that id goes
from red to green. Both are observed outside you.

Open the pull request, wait for the reviewer to conclude, and fix what it raises. A
finding counts as resolved only if this turn's diff touches the file and the line range it
cites; anything you close without a matching hunk goes in the pull-request body as
**dismissed, with the reason**. `pending` and "rate limited" block — do not proceed past
them. **Do not merge.**
