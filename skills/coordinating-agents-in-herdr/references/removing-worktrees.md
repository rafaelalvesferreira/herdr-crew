# Removing a worktree safely

Remove only when the user asks. A pane left inside a removed checkout becomes an orphan: Herdr saves its cwd with "(deleted)" and falls back to HOME on restore, and tools that open a project from the pane's cwd then treat the whole home directory as the project.

```bash
python3 "$CREW" worktree-remove --path <checkout path>             # checks only
python3 "$CREW" worktree-remove --path <checkout path> --execute   # checks again, then removes
```

Take the checkout path from `python3 "$CREW" map` or `herdr worktree list --cwd <repo root>`, not from the conversation. The first call changes nothing and prints the plan. Run the second only when the first returned `"ok": true`. If the plan lists `idle_agents_that_will_end`, name them to the user before the second call: removal ends them.

| `error` | What to do |
|---|---|
| `dirty_worktree` | Stop. Show the `files` and ask the user: commit, stash, discard or force-remove. `herdr worktree remove --force` only when they explicitly say to force or discard; a plain "yes, remove it" is not that. |
| `panes_busy` | An agent is working or blocked, or a command is running, in the worktree's workspace or inside the checkout. Show the list and ask. |
| `status_failed` | `git status` could not run there. Report it; nothing was removed. |
| `own_pane_inside` | You are inside that checkout. Tell the user to `/exit` this session and ask from a session in the main checkout. |
| `workspace_closed` | The checkout is on disk but its workspace is closed. Run the `herdr worktree open` command from the hint, then start again. |
| `not_a_linked_worktree` | That is a main checkout. Never removed. |
| `remove_failed` | Report it. Do not retry with `--force` or `--trust-repository`. |

On success the script closed the panes that other workspaces had inside the checkout, removed the worktree and its workspace, pruned git, deleted the coordinator state of that workspace under `~/.herdr-crew/`, and counted orphans. `orphaned_panes` above 0: find them with `herdr pane list` ("(deleted)" in `cwd`) and close each with `herdr pane close <pane_id>`. Never edit Herdr's `session.json` while the server runs.

Do not replace this with `herdr workspace close` plus deleting the directory: that leaves the same orphans.
