# Turning the allowlist hook off

The `PreToolUse` allowlist refuses writes **inside this repository** that fall outside the
set a turn may write: `src/**`, `tests/unit/**`, `tests/property/**`, `docs/**` and
`LOOP.md`. That set is wider than the frozen set, and anything outside this repository passes
untouched. It is installed **machine-wide**, in `~/.claude/settings.json`, because a hook the
agent could edit would be advice rather than a block (design section 7.3).

Machine-wide is its risk. If tool calls start failing in *any* project for a reason that
names ingestproof, use one of the two switches below.

**Know what the switch costs before you throw it.** CI re-checks the *frozen* paths, not
everything this hook refuses, so disarming does not fall back on CI for the rest. Measured
over the escapes this hook exists to close -- `conftest.py`, `pytest.ini`, `tox.ini`,
`setup.cfg`, `tests/integration/test_x.py`, `TASKS.md` -- CI's frozen-path gate catches
`TASKS.md` and nothing else. A root `conftest.py`, measured in this repository turning a red
acceptance suite green, is checked by this hook alone. Re-arm when the incident is over, and
read the diff of anything written while it was off.

## The soft switch — leaves the settings alone

```bash
D="${LOOP_HOME:-$HOME/.ingestproof-loop}" && mkdir -p "$D" && touch "$D/allowlist.off"
```

`_kill_switch()` reads `$LOOP_HOME` when it is set and falls back to `~/.ingestproof-loop`.
`LOOP_HOME` is unset on this machine today, so the two are the same directory — but with it
set elsewhere, a `touch ~/.ingestproof-loop/allowlist.off` leaves the hook armed. Use the
line above, which is right either way.

`decide()` checks for that file first and allows everything while it exists. Delete it to
re-arm. Prefer this switch: it is reversible in a keystroke and changes nothing global.

`tests/unit/test_allowlist_hook.py` pins `LOOP_HOME` per test, so the inner ring stays green
with the switch on — but anything else reading the real `$LOOP_HOME` sees a disarmed hook.

## The hard switch — restore the settings file

Written by task 14, immediately before the hook was appended:

```bash
cp ~/.claude/settings.json.bak-ingestproof-20260821-134612 ~/.claude/settings.json
```

That backup is byte-identical to the file as it stood with **one** `PreToolUse` entry, the
Orca one. Restoring it removes the allowlist entry and leaves Orca armed.

Reload timing is not reliable in either direction. Claude Code is documented as snapshotting
hooks at start-up, but task 14 appended this hook mid-session and it blocked a `Write` in
that same session, with no restart. Restart if you need a change to have applied, and
re-test if you need it not to have.

## What was installed

| | |
|---|---|
| Hook | `~/.claude/hooks/ingestproof-allowlist.py`, a byte-identical copy of `tools/hooks/ingestproof_allowlist.py` |
| Settings entry | appended to `hooks.PreToolUse`, `matcher: "Write\|Edit\|MultiEdit\|NotebookEdit"` |
| Command | `py -3.12 "C:/Users/jorge/.claude/hooks/ingestproof-allowlist.py"` |

`loop.run_turn.assert_hook_installed` compares the installed copy against the in-repo one
and raises when they differ. `prompt.md` makes it the first call of every turn, with the
invocation form. Nothing in the installed system calls it on its own, and nothing can: it is
a check the session running the turn makes, before it starts. The in-repo copy is what CI
tests; the installed copy is what actually refuses.
