# Removing a worktree safely

Remove only when the user asks, and in this order. A pane left inside a removed checkout becomes an orphan: Herdr saves its cwd with "(deleted)" and, on restore, falls back to HOME. Tools that open a project from the pane's cwd then treat the whole home directory as the project (an IDE refuses to mount it, a language extension scans all of it).

0. Read the checkout path and the workspace id from JSON, not from the conversation: `herdr worktree list --cwd <repo root>` gives `path` and `open_workspace_id` for each worktree. Then, before closing any pane: `git -C <checkout path> status --porcelain`. Non-empty output: stop, list the files and ask the user (commit, stash, discard, or force-remove). `herdr worktree remove --force` only when the user explicitly says to force or to discard those changes; a plain "yes, remove it" is not that.

1. List the panes of ALL workspaces whose cwd is the checkout path or starts with it (a subdirectory counts). `herdr pane list` without `--workspace` returns every pane, with `cwd` and `foreground_cwd`:

   ```bash
   CHECKOUT=<checkout path>
   herdr pane list | jq -r --arg c "$CHECKOUT" '.result.panes[]
     | select(any(.cwd // "", .foreground_cwd // ""; . == $c or startswith($c + "/")))
     | [.pane_id, (.agent // "-"), .agent_status, .cwd] | @tsv'
   ```

2. For each listed pane with an agent: `herdr agent get <pane_id>`. If `working`, stop and ask the user. For a listed pane without an agent: `herdr pane process-info --pane <pane_id>`. If `foreground_process_group_id` differs from `shell_pid`, a command is running (server, test, build): stop, report the `cmdline` and ask. If they are equal, it is an idle shell. Your own pane (`$HERDR_PANE_ID`) in the list: stop and report; closing it ends the coordinator.

3. Close only the listed panes that are in ANOTHER workspace: `herdr pane close <pane_id>`. The panes of the worktree's own workspace stay open: closing the last pane takes the workspace down, and step 4 then fails with `workspace_not_found`.

4. `herdr worktree remove --workspace <id>`. It closes the panes of the worktree workspace and deletes the checkout. Do not use `--trust-repository` as a retry.

5. `git -C <repo> worktree prune` and `git -C <repo> worktree list`: the checkout no longer appears.

6. Wait 10 seconds and run `grep -c '(deleted)' ~/.config/herdr/session.json` (default session file path; it may differ on your system): expect 0. Herdr rewrites the file about 5 seconds after each change, so an immediate count still shows the previous state. More than 0: the orphan shows in `herdr pane list` with "(deleted)" in its `cwd`; close it through Herdr (`herdr pane close <pane_id>`).

`workspace close` closes only Herdr's state and keeps the checkout on disk. Closing the workspace and then deleting the directory (by hand or with `git worktree remove`) produces the same orphan: panes of other workspaces that were inside the checkout stay open.

## Failure modes

| Result | What to do |
|---|---|
| `workspace_not_found` because the worktree workspace was closed first | The checkout is still on disk. Reopen with `herdr worktree open --cwd <repo> --path <checkout path> --no-focus` and remove using the new id. |
| `dirty_worktree_requires_force` | Modified or untracked files in the checkout. List them with `git status --porcelain` and ask the user; do not retry with `--force`. |
| Pane already orphaned (cwd with "(deleted)" in `session.json`) | Close it through Herdr: `herdr pane close <pane_id>`. Never edit `session.json` while the server runs; it rewrites the file. |
