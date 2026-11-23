# Names and orientation

## "Where am I"

```bash
python3 "$CREW" map
```

Read-only. Start the answer with one line from `you_are_here`: pane, workspace, checkout path, branch. Then show `rows` as a table grouped by `project`, with columns workspace, branch, pane, agent, status, model, session id, and mark the row with `"here": true`. A main-checkout workspace is already grouped with the project of its worktrees; the rest is under "no project". Nothing is renamed or closed while answering.

## Labels

Every worktree workspace and helper pane carries the project name first. The script writes these; the format matters when you fix one by hand.

| What | Label |
|---|---|
| Main checkout workspace | repository name (what Herdr sets); do not rename |
| Worktree workspace | `<project> · <ID> <short title>` |
| Worktree workspace without an issue | `<project> · <branch name without its type prefix>` |
| Coordinator pane (worktree root pane) | `<project> · coordinator` |
| Helper pane | `<project> · <role>-<n>: <task in a few words>` |

The short title is the issue's title cut to about four words, read with whatever issue tool the session has (`gh issue view`, an issue-tracker MCP tool). ID known but title unavailable: `<project> · <ID>`. Do not block on it.

The agent name stays `<role>-<n>` and is unique across the whole Herdr server. The pane label shows in the sidebar instead of the generic agent name and survives the agent's exit. A workspace you created whose label is off-format: `herdr workspace rename <id> "<label>"`. Do not rename a workspace from another project or one the user opened unless asked.
