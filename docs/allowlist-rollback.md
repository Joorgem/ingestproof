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
mkdir -p ~/.ingestproof-loop && touch ~/.ingestproof-loop/allowlist.off
```

`decide()` checks for that file first and allows everything while it exists. Delete it to
re-arm. Prefer this one: it is reversible in a keystroke and changes nothing global.

It has one consequence worth knowing. `tests/unit/test_allowlist_hook.py` pins `LOOP_HOME`
per test, so the inner ring stays green with the switch on — but anything else that reads
the real `$LOOP_HOME` sees a disarmed hook.

## The hard switch — restore the settings file

Written by task 14, immediately before the hook was appended:

```bash
cp ~/.claude/settings.json.bak-ingestproof-20260821-134612 ~/.claude/settings.json
```

That backup is byte-identical to the file as it stood with **one** `PreToolUse` entry, the
Orca one. Restoring it removes the allowlist entry and leaves Orca armed.

Restarting Claude Code is what reloads `settings.json`; a session already running keeps the
hooks it started with.

## What was installed

| | |
|---|---|
| Hook | `~/.claude/hooks/ingestproof-allowlist.py`, a byte-identical copy of `tools/hooks/ingestproof_allowlist.py` |
| Settings entry | appended to `hooks.PreToolUse`, `matcher: "Write\|Edit\|MultiEdit\|NotebookEdit"` |
| Command | `py -3.12 "C:/Users/jorge/.claude/hooks/ingestproof-allowlist.py"` |

`loop.run_turn.assert_hook_installed` compares the installed copy against the in-repo one
and refuses to start a turn when they differ. The in-repo copy is what CI tests; the
installed copy is what actually refuses.
