# Common mistakes

| Mistake | Fix |
|---|---|
| `agent prompt --wait` to a helper | Blocks the coordinator. No `--wait`; the safety net is the background `agent wait`. |
| Waiting for the report only through the `done` state | State is inferred from the screen. The signal is the `<from: name>` message or the `END-name` marker in a read. |
| Re-sending the prompt after `timeout` or `agent_prompt_stalled` | May duplicate the task. `agent get` and `agent read` first. |
| Answering a helper's approval dialog | Only the user approves. `esc` declines; report the literal command. |
| Return address by name when the coordinator is not named | Use `$HERDR_PANE_ID`. |
| Claude helper started without `--permission-mode auto` | Blocks on every command and shows "needs you". Flow, step 2. |
| Helper started without `CLAUDE_CODE_AUTO_CONNECT_IDE=false` | Takes the IDE away from the coordinator ("switched to another Claude Code session"). `--env` on the split or `export` in the pane (Flow, steps 1 and 2). |
| Starting an issue in the main checkout with `git checkout -b` or by editing there ("the request didn't mention a worktree", "it's quick") | Moves the main checkout off the default branch and pins the IDE to it. Section "Starting in the main checkout" (unless the user said "work here"). |
| Helper left alive after its report | Shows `done` in the sidebar until the user looks. `/exit` (Flow, step 8). |
| Closing the worktree's root pane to end the helper | Takes the worktree workspace down. End the agent with `/exit`; the pane stays. |
| Resuming a helper with `agent start` without `--resume <session-id>` | Starts an empty conversation. Use the session id from the helper table. |
| Worktree or helper pane labeled only `PROJ-123` | Without project and title the user gets lost across projects. Format in "Names and orientation". |
| Long report inside `agent prompt` | Goes to a file in the temp directory; the prompt carries only the path. |
| Coordinator editing or running tests in another checkout ("it's one line", "I already have the context", "a helper is slower") | Worktree plus helper in its pane, always. The context goes in the contract. |
| The worktree already exists and has no agent, so the coordinator makes the change from there | Helper in the worktree's pane: Flow, step 9 if there was a previous helper for the task, otherwise step 2. |
| `git worktree add` directly inside Herdr | Worktree without a workspace, invisible in the sidebar. `herdr worktree create`. |
| Removing the worktree (or deleting the directory after `workspace close`) with panes inside | The pane's cwd becomes "(deleted)" and Herdr falls back to HOME on restore. Follow `removing-worktrees.md`. |
| Coordinator moves into another workspace's checkout (`cd`, `--cwd`, a split pointing there) | Breaks the workspace↔branch mapping and leaves an orphaned pane when the worktree is removed. The work belongs to a helper in that branch's workspace. |
| Applying a convention silently the first time | Announce it in one line with how to turn it off (section "Default conventions"). |
| Asking for a worktree again after the user said "work here" | "Work here" lasts for the session. |
