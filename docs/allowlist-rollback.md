# Turning the allowlist hook off

The `PreToolUse` allowlist refuses writes to frozen paths inside this repository. It is
installed **machine-wide**, in `~/.claude/settings.json`, because a hook the agent could
edit would be advice rather than a block (design section 7.3).

Machine-wide is also its only real risk. If tool calls start failing in *any* project for
a reason that names ingestproof, use one of the two switches below. Neither weakens the
gate that matters: a pull request whose diff touches a frozen path fails in CI, with no
override, whether this hook runs or not.

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
and raises when they differ. Nothing calls it yet: it is a check P1's harness can make, not
something the installed system does on its own. The in-repo copy is what CI tests; the
installed copy is what actually refuses.
