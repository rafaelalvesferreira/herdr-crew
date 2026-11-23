# Common mistakes

| Mistake | Fix |
|---|---|
| `agent prompt --wait` to a helper | Blocks the coordinator. No `--wait`; the safety net is the background `agent wait`. |
| Waiting for the report only through the `done` state | State is inferred from the screen. The signal is the `<from: name>` message or the `END-name` marker in a read. |
| Re-sending the prompt after `timeout` or `agent_prompt_stalled` | May duplicate the task. `agent get` and `agent read` first. |
| Answering a helper's approval dialog | Only the user approves. Report the literal text and wait; send no keys. |
| Return address by name when the coordinator is not named | Use `$HERDR_PANE_ID`. |
| Claude helper started without `--permission-mode auto` | Blocks on every command and shows "needs you". Flow, step 2. |
| Helper started without `CLAUDE_CODE_AUTO_CONNECT_IDE=false` | Takes the IDE away from the coordinator ("switched to another Claude Code session"). `--env` on the split or `export` in the pane (Flow, steps 1 and 2). |
| Starting an issue in the main checkout with `git checkout -b` or by editing there ("the request didn't mention a worktree", "it's quick"), when it is more than a small edit | Moves the main checkout off the default branch and pins the IDE to it. Section "Starting in the main checkout" (unless the user said "work here"). |
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
| Opening a worktree for a typo or a one-file, few-line change with no behavior change | Small edit: make it in place, no commit. Section "Answer here or delegate". |
| Calling something a small edit and then touching a second file, changing behavior or running tests | It stopped being small. Stop and treat it as a regular edit request. Section "Answer here or delegate". |
| Making a small edit in a checkout while a helper is editing it | One editor per working tree. Wait for the helper's report. |
| Answering or dismissing a helper's folder-trust or other startup dialog, or retrying `agent start` over it | Only the user answers. Tell them which pane waits. Section "Helper blocked at startup". |
| Asking the user which model the coordinator or a helper should use | Routing file if present, otherwise no `--model`. Section "Model routing". |
| Routing key that never matches (`review` for `reviewer-1`) | The key is the agent name without the numeric suffix: `reviewer`. |
| Saving contracts or the helper table inside the checkout (`.claude/...`) | Dirties `git status` and blocks worktree removal. `~/.herdr-crew/<project>/`. |
| `agent start` fails because the name exists in another project | Names are unique server-wide. Lowest `<n>` not in `herdr agent list`. |
| Re-creating a helper from its saved contract without checking | The task may have run. `agent get`, `agent read` and the report file first (Flow, step 9). |
