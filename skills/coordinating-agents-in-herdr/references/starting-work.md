# Starting work: project name, worktrees, hand-off

Vocabulary: users may say "space" for the sidebar item with id `wN`. Always write "workspace". Each workspace corresponds to one checkout, and all of its panes stay inside it.

## Project name

The project is the user's initiative, and one project can span several repositories. It is not the repository name and you do not derive it.

- **The request names it:** use it.
- **Starting new work from a main checkout:** ask. One question, in the same message as the announce line, listing the `<project> · ` prefixes already open so the user can pick one or give a new short kebab-case name. An existing prefix does not apply just because it exists: this is new work.
- **Already coordinating (first helper or worktree of the session):** exactly one `<project> · ` prefix in your workspace's label or panes: reuse it and say which in one line. None, or more than one: ask once.

Run `python3 "$CREW" map` before asking: its `project` column lists the prefixes in use. Ask once per session; after that the name is settled.

Task name: the issue ID in the request; otherwise a short kebab-case name you take from the request (`fix-login-redirect`). State it in the same message so the user can correct it. Ask for an issue ID only when the repository's branch convention requires one.

## Session in a main checkout: hand off

A session whose `git rev-parse --git-dir` equals `git rev-parse --git-common-dir` is in a main checkout. It does not switch branches or `git pull` there. A request that will edit code, beyond a small edit, goes to a new coordinator in a worktree, unless the user said "work here".

1. Settle project and task name (above). This is usually the only question.
2. Pick the branch name (section "Branch name") and the label `<ID> <short title>` (see `orientation.md`, "Labels").
3. Write the hand-off text to a file in a temp directory outside every checkout. It says: you are the coordinator of project `<project>` in this worktree and must follow the `coordinating-agents-in-herdr` skill; the user's request in their words; the issue ID; what was already read or decided in this session; absolute paths of context files; any in-place small edit to redo. It is not a helper contract: no return address.
4. Create the worktree, start the coordinator and send the hand-off in one step:

   ```bash
   python3 "$CREW" worktree-create --project "<project>" --branch <branch> \
     --label "<ID> <short title>" --coordinator <id> --handoff-file <file>
   ```

   `--coordinator` takes the issue ID, or the task's short name when there is no issue. `--label` takes the issue ID and short title, or the task's short name; the script adds the `<project> · ` prefix.
   The script fetches `origin`, bases the branch on `origin/<default branch>`, refuses if the branch exists, labels the workspace and the root pane (`<project> · coordinator`), starts `coord-<id>` with the user's own permission mode and the IDE connection, applies the `coordinator` routing key if there is one, and sends the text.
   `blocked_at_startup`: a dialog is open (usually folder trust for the new checkout). Do step 5 now, adding which pane waits and why, so the user can answer it there. Arm the background wait from the hint; when it fires, send the hand-off with the command in the hint and confirm with `herdr agent get coord-<id>` that it went `working`. A wait that times out is armed again. Then step 6.
5. Report in a few lines: workspace (label and id), branch, checkout path, the setup the new checkout needs (section "Setup"), the coordinator's session id, and that the conversation continues in the new workspace. Run `herdr workspace focus <workspace_id>`. If the user says the IDE is not attached to the coordinator, tell them to run `/ide` in its pane.
6. Stop. This session does not continue the work and does not close its own pane.

## Worktree requested in plain language

"Create a worktree for PROJ-123", "isolate this in a branch": inside Herdr this is always `herdr worktree create`, through the script. Plain `git worktree add` leaves the worktree invisible in the sidebar.

```bash
python3 "$CREW" worktree-create --project "<project>" --branch <branch> --label "<ID> <short title>" [--repo <other repo root>]
```

- **From a main-checkout session with work to do:** that is the hand-off above (`--coordinator`), not a helper.
- **From a coordinator in its own worktree, work in another repository or branch:** create without `--coordinator`, then start a helper in the result's `root_pane` (`delegating.md`: `helper-start --pane <root_pane>`). Announce it in one line; the user turns this off in their own instructions, not with "work here". The helper never works in the other repository's main checkout, and a pane split pointing there is not a substitute for a worktree. Use the same `<project>`.
- **A worktree for this task already exists** (`branch_exists`): do not recreate. No agent in it: resume its previous helper if your table has one, otherwise start a helper in its root pane.
- **Only "create the worktree":** create, report and stop. No agent, no issue-tracker changes.

A worktree in another repository that had no open workspace also opens a workspace for that repository's main checkout. Report both, and say the main-checkout one stays open after the worktree is removed.

To take the user to a workspace ("open the PROJ-123 space"): `herdr workspace focus <id>`.

## Branch name

Follow the convention of the repository the worktree is created in: read its CLAUDE.md, AGENTS.md or CONTRIBUTING. With a type prefix, pick the type from the request's verb: refactor = `refactor`, fix = `fix`, new = `feat`, docs only = `docs`, deps or config = `chore`. No documented convention: `<type>/<ID>-<short-kebab-name>`, or `<type>/<short-kebab-name>` without an issue.

## Setup

A new worktree has only what is committed. Installed dependencies, virtual environments, local credentials and uncommitted local files (`.env`) do not come along. Read the setup the repository requires in its README or CLAUDE.md and tell the user what must be redone in the new checkout (`npm install`, `uv sync`, copying `.env`). The first Claude Code agent in a new checkout also asks the user to trust the folder.

## Inside the worktree

The coordinator edits and runs build, test and lint only inside its own checkout, the one `git rev-parse --show-toplevel` returns in its pane. Outside it, it only reads (`git diff`, `git log`, `gh pr view`, files) to write contracts and check reports. Context only the coordinator has goes into the contract's CONTEXT block, with ready-to-paste text.

The coordinator does not remove the worktree it is in. Asked to, it says so and tells the user to `/exit` it and ask from a session in the main checkout.
