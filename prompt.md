# The turn

You are executing one turn of the ingestproof loop. Read `TASKS.md`, take the **first
unclosed** item, and do only that.

## Before anything

1. `git reset --hard && git clean -fdx -e .venv`. Not one or the other. `reset --hard`
   leaves untracked files, and an orphan `conftest.py` was measured turning a red
   acceptance suite green.
2. Read the item's criterion in `.spec/acceptance.md`. If the item does not name a
   criterion id, stop: the queue is malformed and that is a human's problem.

## The turn contract — you are the harness

**Nothing runs a turn but you.** There is no driver in `loop/**` and there is not going to
be one: a runner written before anyone had run a turn would be unexercised code, frozen the
day it was written, which is the defect this repository already carries once. The
mechanisms are libraries; the session is what calls them. Every command below was run from
the repository root and printed what it says it prints.

| step | call |
|---|---|
| before the turn | `assert_hook_installed` |
| clean slate | `clean_slate`, or the two git commands above |
| the work | your edits, inside the writable set |
| the inner ring | `uv run pytest` |
| the verdict | `classify` |
| the record | `loop.ledger.append` |
| the view | `python -m loop.render_loop_md` |
| the brake | `stall_report` |
| the pull request | `tools.review_resolution.partition` and `dismissal_section` |

**Refuse to start if the gate is not armed.**

```bash
uv run python -c "from pathlib import Path; from loop.run_turn import assert_hook_installed; assert_hook_installed(Path('.'))"
```

Silence means the installed hook exists and is byte-identical to `tools/hooks/`. It does
not check that `~/.claude/settings.json` still arms it, and it cannot: a turn that could
read its own gate's configuration is a turn that could learn to edit it.

**The clean slate**, if you would rather call it than type it:

```bash
uv run python -c "from pathlib import Path; from loop.run_turn import clean_slate; clean_slate(Path('.'))"
```

**The verdict.** `classify` is a pure function and it is the only thing that decides the
outcome. Do not name an outcome by hand; feed it what happened.

```bash
uv run python -c "from loop.run_turn import classify; print(classify(tests_passed=False, timed_out=False, changed_paths=['src/ingestproof/__init__.py'], test_was_green_before=True))"
```

`changed_paths` is `git diff --name-only` over the turn's own commits. `RED` and `TIMEOUT`
both mean undo.

**The record.** One row per turn, appended PROGRAMMATICALLY. The ledger lives outside the
work tree and the agent's editor never touches it — that is not a style rule, it is what
makes the row survive the `git reset --hard` that ends a RED turn.

```bash
uv run python -c "
from loop.ledger import append
append({'ts': '2026-08-24T12:00:00Z', 'task': 'P1-1', 'criterion': 'req~ac-01~1',
        'outcome': 'RED', 'diff_lines': 0, 'cost_usd': 0.0, 'pragmas': 0, 'author': 'loop'})
"
```

All eight keys are required and `append` refuses the row without them. `diff_lines` is
`git diff --numstat --no-renames <base>..<tip>` with insertions and deletions summed, and
the cutoff you used belongs in the row's `note`. `pragmas` counts every
`# pragma: no mutate`, `@pytest.mark.skip` and `xfail` the turn added.

Add `closed_criterion` **only when both signals in `TASKS.md`'s closing rule were observed**
— the id gone from `oft-report.txt`, and the frozen acceptance test green. Not when you
believe the item is done. The stall detector reads that field, and a field written from
belief turns the brake into a formality.

**The view.** `LOOP.md` is generated; re-render it after every append.

```bash
uv run python -m loop.render_loop_md
```

**The brake.** Five consecutive loop turns closing nothing stops the loop.

```bash
uv run python -c "from loop.ledger import read_all; from loop.run_turn import stall_report; print(stall_report(read_all()))"
```

`None` means keep going. Anything else is the text to write and stop on, and the decision
after it is a human's.

**The pull-request body.** A finding counts as resolved only if this turn's diff touches
the file and the line range it cites, and `partition` is what decides that — not you.

```bash
git diff --no-renames -U0 origin/main...HEAD > turn.diff
uv run python -c "
from pathlib import Path
from tools.review_resolution import Finding, dismissal_section, partition
findings = [Finding('src/ingestproof/contracts.py', 12, 14, 'what the reviewer said')]
resolved, dismissed = partition(findings, Path('turn.diff').read_text(encoding='utf-8'))
Path('dismissed.md').write_text(dismissal_section(dismissed), encoding='utf-8')
"
```

`-U0` and rename detection LEFT ON are both load-bearing and they pull opposite ways from
`tools/freeze_check.py`; the reasons are in `touched_lines`' docstring, and getting either
wrong resolves findings nothing fixed. Write the section to a file rather than pasting it
from this console: the dismissal bullet uses an em dash, and the Windows console default is
cp1252.

If a step here has no callable form, say so in `LOOP.md` and stop. Do not write one.

## What you may write

`src/**`, `tests/unit/**`, `tests/property/**`, `docs/**`, and `LOOP.md`.

Nothing else. `tests/acceptance/**`, `tests/conftest.py`, `.spec/**`, `TASKS.md`,
`prompt.md`, `CLAUDE.md`, `pyproject.toml`, `uv.lock`, `.github/**`, `.gitattributes`,
`.gitignore`, `LICENSE`, `README.md`, `tools/**` and `loop/**` are frozen. A `PreToolUse`
hook refuses the write, and CI fails any pull request whose diff names one of them.
There is no override. If a frozen file is genuinely wrong, say so in `LOOP.md` and stop
— that is a human's edit.

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
  twelve implementations, two of them from Databricks Labs. Writing that no one else does
  this is banned in every artefact. **No gate checks it** — no CI step, no test and no tool
  greps for the phrasing, so this ban holds because people hold it. The banned wording
  appears in exactly two places today, `docs/design.md` sections 3.1 and 3.5, and both are
  the document RECORDING the ban: leave them alone. A grep that finds it anywhere else is a
  defect.

## Finishing

You do not close a task. A task closes when its criterion id goes from uncovered to
covered in the traceability report **and** the frozen acceptance test citing that id goes
from red to green. Both are observed outside you.

Open the pull request, wait for the reviewer to conclude, and fix what it raises. A
finding counts as resolved only if this turn's diff touches the file and the line range it
cites; anything you close without a matching hunk goes in the pull-request body as
**dismissed, with the reason**. `pending` and "rate limited" block — do not proceed past
them. **Do not merge.**
