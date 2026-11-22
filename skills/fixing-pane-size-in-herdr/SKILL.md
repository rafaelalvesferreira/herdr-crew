---
name: fixing-pane-size-in-herdr
description: Use when inside Herdr (HERDR_ENV=1) the user complains that Claude Code text wraps wrong, comes out too wide, or tears mid-word in the current pane (typical when opening from a phone or another terminal a pane created on a laptop), or asks to fix the pane or terminal size.
---

# Fixing pane size in Herdr

## Overview

A Herdr pane's pty can keep the size of another client (created on a laptop at 200 columns, opened later on a phone at 60). Claude Code wraps text at the old size and the terminal tears the lines. This aligns the pty with the current pane.

Arguments: none uses the size Herdr reports for the pane. `<cols> <rows>` forces those values (use it when Herdr reports another client's size).

## Steps

1. Confirm you are inside Herdr. If this fails, say so and stop:

   ```bash
   test "${HERDR_ENV:-}" = 1
   ```

2. Find the pane's real size and the session's tty. The tty is the one of the `claude` process that is the parent of your tool's shell, never the shell's own `stty size` (it has no tty):

   ```bash
   herdr pane layout --pane "$HERDR_PANE_ID" | grep -o '"area":{[^}]*}'
   F=-F; [ "$(uname)" = Darwin ] && F=-f      # GNU stty uses -F, macOS uses -f
   tty=$(ps -o tty= -p $PPID | tr -d ' '); echo "$tty"; stty $F /dev/$tty size
   ```

   `area.width` is columns and `area.height` is rows. If `ps` does not return a `pts/N` (or `ttysNNN` on macOS), walk up the tree with `ps -o ppid= -p` until the `claude` process. Shell variables may not survive between tool calls: repeat the `F=` and `tty=` lines in the commands of steps 4 and 5 if needed.

3. If `stty size` (rows cols) already matches the layout and the user passed no arguments, say it is already aligned and stop.

4. Try the native path first, which makes Herdr resend the size:

   ```bash
   herdr pane zoom --current --on && herdr pane zoom --current --off
   stty $F /dev/$tty size
   ```

5. If it still differs, force the pty. This triggers SIGWINCH and Claude Code redraws:

   ```bash
   stty $F /dev/$tty cols <cols> rows <rows> && stty $F /dev/$tty size
   ```

6. Answer in one line: previous size, final size and which path worked. Warn that history already rendered stays torn and only new text comes out right. If the size snaps back to the old one, another client (the laptop) is still attached and holding the size; disconnecting it fixes it for good.

## Don't

- Touch another pane's pty unless the user asks and names the pane.
- Restart the Claude session or close panes.
