---
name: coordinating-agents-in-herdr
description: Use when running inside Herdr (HERDR_ENV=1) and the user asks to delegate work to another agent in a pane (a Codex or Claude reviewing, testing or investigating in parallel, a helper that must report back, several helpers whose results must be combined), or asks for a new worktree in plain language ("create a worktree for this issue", "isolate this in a branch", "open a branch to test without touching main"), even without naming Herdr. Also use when, while coordinating in Herdr, work comes up (editing a file, running tests, build or lint) in another repository or another worktree than the current pane's, even a one-line change. Also use when the user asks to get oriented across panes and worktrees ("where am I", "what's open", "which pane is which"). Also use when, in a repository's main checkout, the user starts work that will edit code ("let's start PROJ-123", "fix X"), even without asking for a worktree.
---

# Coordinating agents in Herdr

## Overview

The helper delivers its result into the coordinator's input with `herdr agent prompt`. The coordinator does not poll: it keeps working and reads the report when it arrives, as if the user had typed it.

## Before anything

1. Confirm you are inside Herdr. If this fails, say so and stop:

   ```bash
   test "${HERDR_ENV:-}" = 1
   ```

2. Before your first `herdr` command, if Herdr's own skill is not already in your context, run `herdr --skill` and read its output. A plain question or lookup that needs no `herdr` command skips this. It is the authority on commands, IDs and safety rules; this skill only adds the coordination protocol on top of it. A request for a worktree counts as an explicit request to use Herdr.

## Answer here or delegate

- **Questions, lookups and reading** happen right where you are, including the main checkout. No worktree, no helper.
- **A small edit** is made in place, in the checkout you are in, with no worktree and no helper. Small means all three hold: one file, a few lines, and no change in behavior (a typo, a comment, documentation, the wording of a message). A change to a value or to logic is not small, even on one line, because a test, build or lint would have to check it. Make the edit, show the change in one line, and do not commit, push or switch branches unless asked. If a follow-up takes it past any of the three (a second file, a behavior change, something to run), stop and treat the whole thing as the next case: carry the in-place edit in the hand-off text so it is redone in the worktree, and tell the user it is still uncommitted in this checkout for them to keep or discard. While a helper is editing this checkout, do not edit under it: make the small edit after its report arrives, and say so.
- **Any other request that will edit code** (issue, feature, fix, refactor) follows the conventions below. So does a lookup conversation that turns into such an edit midway ("ok, add it then").

## Default conventions

These are defaults. The user's own instructions (CLAUDE.md, AGENTS.md, or what they say in this session) override any of them.

| Convention | Why |
|---|---|
| Code edits beyond a small edit (see "Answer here or delegate") happen in a worktree. The main checkout stays on the default branch. | No work in progress piles up in the main checkout and the editor/IDE stays attached to it; a typo does not pay for a worktree. |
| One coordinator per project, started in the worktree's root pane. | Each workspace maps to one checkout, so the sidebar shows which branch you are looking at. |
| The coordinator only works in its own workspace's checkout. Work in another repository or worktree is done by a helper there. | Keeps the workspace↔checkout mapping and prevents orphaned panes when a worktree is removed. |
| Worktree workspaces and helper panes are labeled with the project name first (see "Names and orientation"). | With several projects open, `PROJ-123` alone in the sidebar says nothing. |
| Claude helpers start with `--permission-mode auto` and `CLAUDE_CODE_AUTO_CONNECT_IDE=false`. | Without auto mode the helper blocks on every command; without the variable it takes the IDE connection away from the coordinator. |

**Announce a convention the first time it changes something.** The first time in a session that a convention does something the user did not ask for, say so in one line and say how to turn it off. For example: "Opening a worktree so main stays clean. Say 'work here' or set this in CLAUDE.md to turn it off." Put that line in the same message as any question the step needs (such as the project name). A convention the user's instructions already turned off is not announced.

**"Work here" lasts for the session.** If the user says to work in place ("work here", "just do it here", "no worktree"), edit in the current checkout for the rest of the session. This turns off only the worktree-for-edits convention; the others still apply unless the user turns them off too. It does not authorize committing, pushing, switching branches or pulling; do those only when the user asks.

## Where the coordinator works

Vocabulary: users may say "space" or "workspace" for the sidebar item with id `wN`. Always write "workspace".

- Each workspace corresponds to one checkout, and all of its panes stay inside that checkout. The user switches workspaces in the sidebar to see the files of the branch being worked on; this mapping is what makes that possible.
- The coordinator works only in the workspace it was opened in (`$HERDR_WORKSPACE_ID`). It edits files and runs build, test, lint or install only inside that workspace's checkout, the one `git rev-parse --show-toplevel` returns in its pane. It does not move into another checkout to work there: no `cd` or `--cwd` into another checkout, no `git worktree add`. Work on another branch happens in that branch's workspace, done by a helper in its root pane.
- Consequence used at removal time: if this holds, the only panes inside a checkout are those of its worktree workspace, and `herdr worktree remove` closes them by itself. The cwd-prefix check across all workspaces (see `references/removing-worktrees.md`) still runs, to catch anyone who broke the rule.

Every worktree created with `herdr worktree create` gets its own workspace with a root pane already open in its checkout. "Open the worktree in a space" and "take me to the PROJ-123 space" ask for focus: `herdr workspace focus <id>`. For a new workspace created on "open ... for me": create it with `--no-focus`, start the helper if there is work, and only then focus it.

Any work in another checkout (another repository, or another worktree of this repository) happens in another workspace and belongs to a helper running in that worktree workspace's root pane:

1. No worktree for this task in that repository yet: create one with `herdr worktree create` (section "Worktree requested in plain language"; for another repository, add `--cwd <repo root>`, which only tells Herdr which repository to create the new workspace from and does not move any coordinator pane there). The helper never works in the other repository's main checkout, and `pane split --cwd <other repo>` is not a substitute for a worktree.
2. Start a helper in the worktree's root pane (`root_pane.pane_id` in the `worktree create` result, or `herdr pane list --workspace <id>`) and send the contract (Flow, from step 2; step 2 renames the root pane). A worktree for this task that already exists and has no agent: if the helper table has a previous helper for this task, resume it (Flow, step 9); otherwise Flow from step 2.
3. The helper does the work there and sends back the report. The coordinator handles the report and talks to the user.

The small-edit exception covers only the checkout you are in. In another checkout the size of the change does not enter the decision: a one-line change in another repository's `README` follows the same path. Context only the coordinator has goes into the CONTEXT block of the contract, with ready-to-paste text when there is any.

Outside its own checkout the coordinator only reads: `git diff`, `git log`, `gh pr view` and reading files, to write the contract and to check the helper's report. The only commands it runs against another checkout are the ones this skill names: `git -C <repo> fetch`, the checks before `worktree create`, and the removal steps in `references/removing-worktrees.md`.

## Starting in the main checkout

A session opened in the main checkout (`git rev-parse --git-dir` equals `git rev-parse --git-common-dir`) does not switch branches or `git pull` there: the main checkout stays on the default branch, and the IDE stays with the project coordinator, not with helpers. Questions, lookups, reading and small edits stay in the main checkout. Any other request that will edit code goes through the steps below, even if the user did not mention worktrees, unless the user turned the convention off ("work here", or their instructions).

1. Settle project and task name without stopping the user when you can. Project: the name in the request; otherwise, if no `<project> · ` prefix is in use for this repository, the repository's directory name. Task: the issue ID in the request; otherwise a short kebab-case name taken from the request (`fix-login-redirect`). State both in the announce line ("project `myapp`, task `fix-login-redirect`") so the user can correct them. Ask only in two cases: the repository's branch convention requires an issue ID and the request has none (ask for the ID), or prefixes are already in use for this repository: this starts new work, so an existing prefix does not apply just because it exists. List them in one question and reuse one only if the user says the task belongs to that project.
2. Create the worktree with steps 1 to 4 of "Worktree requested in plain language": `git fetch origin` and `--base origin/<default branch>`, no `pull` in the main checkout, label `<project> · <ID> <short title>`.
3. Start the project coordinator in the worktree's root pane. Rename the pane to `<project> · coordinator`, generate a session id and run `herdr agent start coord-<id> --kind claude --pane <root_pane> -- --session-id <uuid>`, with `<id>` = issue ID or short name, lowercase (`coord-proj-123`): agent names cannot repeat across projects. Add `--model <model>` only if the routing file has a `coordinator` key (section "Model routing"); otherwise the coordinator uses the user's default model. Do not ask which model. No `--permission-mode`: the mode is the user's. No `CLAUDE_CODE_AUTO_CONNECT_IDE=false`: this is the agent that should hold the IDE connection.
4. Hand over with `herdr agent prompt coord-<id> "<text>"`, without `--wait`. The text says it is the coordinator of project `<project>` in that worktree and must follow the `coordinating-agents-in-herdr` skill, and carries the user's request, the issue ID, what was already read or decided in this session, and the absolute paths of any context files. This is not a helper contract: no return address. Confirm with `herdr agent get coord-<id>` that it went `working`. If `agent start` in step 3 returned `agent_not_ready`, follow "Helper blocked at startup" first and send the hand-off only once the agent is `idle`.
5. Report to the user in a few lines: workspace (label and id), branch, checkout path, setup the new checkout needs (step 5 of "Worktree requested in plain language"), the coordinator's session id, and that the conversation continues in the new workspace. Focus the new workspace (`herdr workspace focus <id>`). If the user reports that the IDE is not attached to the coordinator, tell them to run `/ide` in its pane. Then stop: this session does not continue the work and does not close its own pane; ending it (`/exit`) is the user's call.

Inside the worktree the rest of this skill applies. A helper in the same project: split in the coordinator's workspace (Flow). A helper in another repository: an up-to-date worktree in that repository with the same `<project> · ` prefix (section "Where the coordinator works"). Removing the project's worktree is a request made from a main-checkout session after the coordinator's `/exit`: the coordinator does not remove the worktree it is in. Asked to, it says so and tells the user to `/exit` it and ask from a session in the main checkout.

## Return address

A coordinator the user opened by hand has no agent name; one started by hand-off is named `coord-<id>`. This picks whichever applies:

```bash
RETURN="$HERDR_PANE_ID"            # e.g. wP:pN
herdr agent get --current >/dev/null 2>&1 && RETURN="<returned name>"
```

Never derive the address from the sidebar or from examples.

## Names and orientation

With several projects open, `PROJ-123` in the sidebar says nothing. Every worktree workspace and every helper pane the coordinator creates carries the project name first.

**Project name.** On the session's first worktree or helper, look for a `<project> · ` prefix already in use: in the worktree workspaces of the same repository (`herdr worktree list --cwd <repo root>` gives `open_workspace_id`; the label comes from `herdr workspace list`) and in the helper panes of the current workspace (`herdr pane list --workspace "$HERDR_WORKSPACE_ID"`). Exactly one prefix: reuse it and say which in one line (except when starting new work in the main checkout, which asks). None: use the repository's directory name and say so in one line. More than one: ask the user which project, once per session.

**Labels.**

| What | Label | When |
|---|---|---|
| Main checkout workspace | repository name (what Herdr sets) | do not rename |
| Worktree workspace | `<project> · <ID> <short title>` | `--label` on `worktree create` |
| Worktree workspace without an issue | `<project> · <short branch name>` | same |
| Coordinator pane (worktree root pane, by hand-off) | `<project> · coordinator` | `herdr pane rename` before `agent start` |
| Helper pane | `<project> · <role>-<n>: <task in a few words>` | `herdr pane rename <pane_id> "<label>"` before `agent start` (Flow, step 2) |

The short title is the issue tracker's title cut to about four words. Read it with whatever issue tool the session has (`gh issue view`, an issue-tracker MCP tool). ID known but title unavailable: `<project> · <ID>`. No ID: the branch name without its type prefix. Do not block on it. The agent name stays `<role>-<n>`: that is what goes in `<from: …>` and `END-…`. A worktree workspace the coordinator created for this task whose label is off-format: `herdr workspace rename <id> "<label>"`. Do not rename a workspace from another project or one the user opened unless asked.

The sidebar groups a worktree workspace right under its repository's workspace; the prefix tells which project it belongs to, it does not sort. The pane label shows in the sidebar's agent list instead of the generic agent name and survives `/exit`.

**"Where am I".** For an orientation request ("where am I", "what's open", "which pane is which"), build a table from `herdr workspace list`, `herdr pane list` and `herdr agent list`, plus the coordinator's helper table (section "Several helpers"). `herdr pane list` without `--workspace` covers every workspace. The helper table is read only if `~/.herdr-crew/<project>/helpers.md` exists. Start the answer with one line saying where the user is now: pane, workspace, checkout path and branch. Columns: project, workspace (label and id), branch, pane (label and id), agent, status, session id; mark the current pane. Group by project; a main-checkout workspace groups with the project of its worktrees, and anything else without a prefix goes under "no project". Read-only: nothing is renamed or closed while building the map.

## Flow

1. `herdr pane split --current --direction right --cwd "$(git rev-parse --show-toplevel)" --env CLAUDE_CODE_AUTO_CONNECT_IDE=false --no-focus`. The checkout root, not `$PWD`: the helper does not inherit a subdirectory. Read the id from `.result.pane.pane_id`.
2. Rename the pane (`herdr pane rename <id> "<label>"`, format from "Names and orientation"; this also applies to a worktree root pane). Generate a session id (`python3 -c 'import uuid;print(uuid.uuid4())'` or `uuidgen`) and start the helper:
   `herdr agent start <role>-<n> --kind claude --pane <id> -- --permission-mode auto --session-id <uuid>`.
   Add `--model <model>` after `--session-id <uuid>` when the routing file has a key for `<role>` (section "Model routing").
   `agent start` returned `agent_not_ready`: section "Helper blocked at startup".
   A pane that did not come from the split in step 1 (worktree root pane, reopened pane): before `agent start`, `herdr pane run <id> "export CLAUDE_CODE_AUTO_CONNECT_IDE=false"`. `worktree create` does not accept `--env`.
   Why no IDE: an IDE extension serves one Claude Code session at a time, and the last one to connect wins. With `autoConnectIde` on, every Claude started in a folder open in the IDE connects by itself, and the helper takes the IDE away from the coordinator (notice "Visual Studio Code switched to another Claude Code session"): the coordinator loses selection, in-editor diff and diagnostics until the user runs `/ide`. With the variable set, the helper starts with `/ide` → None and the IDE stays with the coordinator. Several coordinators: the last one started holds it; the user switches with `/ide`.
   Name = role plus numeric suffix. Roles: `reviewer` and `investigator` (read-only), `tester` (runs or writes tests), `builder` (edits code). Agent names are unique across the whole Herdr server, not per project: take the lowest `<n>` that `herdr agent list` does not show for that role. Record name, pane and session id in the helper table (section "Several helpers").
   Why auto mode: without it Claude starts in default mode, which asks for approval before every command, and the helper sits `blocked` ("needs you" in the sidebar) on every `git diff` and on the return `herdr agent prompt` itself. Auto mode does not replace LIMITS: in testing it let through even a POST to an external service. The contract is what contains the helper.
   Codex (`--kind codex`) only when the user asks, and without those flags: with `-a never` its sandbox denies the return `herdr agent prompt`, and startup dialogs (update, hook review) leave it `blocked`. A Codex helper will ask the user for approval in its pane, gets session id `-` in the table and cannot be resumed with step 9: if needed again, start a new one.
3. Save the contract text to `<state>/contracts/<name>.md` (section "Several helpers" defines `<state>`; never inside the checkout). Then send it from the file, which avoids quoting problems: `herdr agent prompt <name> "$(cat <state>/contracts/<name>.md)"`, **without `--wait`**. Confirm with `herdr agent get <name>` that it went `working`.
4. Arm the safety net in the background (a background shell command):
   `herdr agent wait <name> --timeout 900000`. It fires on `done`, `idle` or `blocked`.
5. Go back to your own work.
6. A message starting with `<from: name>` arrived: that is the report. Save it to `<state>/reports/<name>.md` (copy the file when the helper sent a path), handle it, give each item a disposition, continue.
7. The safety net fired without a report: `herdr agent get`. If `blocked`, read the screen, report the literal text to the user and wait; do not send keys. If `done` or `idle`, `herdr agent read <name> --source recent-unwrapped --lines 200`. If still `working` (the wait timed out), arm the safety net again.
8. Report handled: `herdr agent get <name>`. If `blocked`, send nothing (the Enter of `/exit` could confirm the open dialog); follow step 7. If `idle` or `done`, end it with `herdr agent prompt <name> "/exit"` and confirm in `herdr agent list` that the name is gone; mark it "ended" in the table. An agent left alive after finishing shows `done` in the sidebar until the user opens that pane, and there is no way to mark it seen without stealing their focus. `/exit` ends only the agent: the pane stays, goes back to a shell and keeps its label. This applies to helpers the coordinator started; an agent the user opened, only when asked.
9. Need the helper again (a follow-up, a question about what it read): in the same pane, `herdr agent start <name> --kind claude --pane <id> -- --permission-mode auto --resume <session-id>` (plus the same `--model` as before, from the helper table). The whole conversation comes back. A follow-up is not a new contract: send the question followed by the RETURN block with the current return address, then safety net and `/exit` as in steps 4 to 8. The user can do the same by hand with `claude --resume <session-id>` in the pane. Pane closed in the meantime: for a split pane, steps 1 and 2 with the same label and `--resume` instead of `--session-id`; in a worktree whose workspace is gone, reopen it with `herdr worktree open --cwd <repo> --path <checkout path> --no-focus` and use the root pane. Resume fails, or the session id is not in the helper table: first check whether the task already ran (`herdr agent get` and `herdr agent read` on the pane, and the report file `<tmpdir>/<name>.md`). If the result is there, use it. If not, tell the user in one line that the helper's conversation could not be resumed, then start a new helper with the same name (steps 2 to 4, new session id). For the original task, send the saved contract with the RETURN address and temp path refreshed. For a follow-up question, do not repeat the task: send a short contract whose CONTEXT points to `<state>/contracts/<name>.md` and `<state>/reports/<name>.md` and whose TASK is the question.
10. Do not close a pane unless the user asks. A request to remove a worktree authorizes closing the panes and agents inside its checkout (see `references/removing-worktrees.md`), and only those.

## Helper blocked at startup

`herdr agent start` returning `agent_not_ready` means the agent is waiting at a dialog before its first prompt. The name stays valid. Read the screen: `herdr agent read <name> --source visible --lines 30`.

- **"Is this a project you created or one you trust?"** Claude Code asks this the first time it runs in a folder, typically a repository where it has never been started. Only the user answers it. Tell them in one line which pane is waiting and why ("`reviewer-1` in pane w2:p3 is waiting for you to trust `~/code/shared-lib`"), keep working, and send the contract once the agent is `idle`: arm `herdr agent wait <name> --until idle --timeout 900000` in the background to be told when. Do not send keys to it.
- **Any other dialog** (update notice, login, hook review): same rule. Report the literal text and wait for the user.

Never retry `agent start` on the same pane while the dialog is open, and never move the helper to a different folder to avoid the question.

## Helper contract

The first prompt to a helper has these seven blocks, in this order. None is optional. (Later prompts to the same helper are a follow-up question plus the RETURN block, or `/exit`.)

```
ROLE: <one line: what the helper is, e.g. read-only reviewer>
CONTEXT: <repo, branch, what another agent is editing at the same time>
TASK: <what to do, criteria, what to ignore>
COMPARISON_BASE: <ref the helper compares against, e.g. origin/main; n/a when the task compares nothing>
LIMITS: do not edit files; do not run git commit/push/checkout/stash; do not run commands that write
  to shared environments (<list the repo's>); if you need an approval, stop and say so in the RETURN.
FORMAT: <shape of the result, short; end with the line END-<name>>
RETURN: when done, run exactly:
  herdr agent prompt <RETURN> "<from: <name>> <one-line status>
  <result, at most 40 lines>"
  Result longer than 40 lines: write it to <tmpdir>/<name>.md and send only the path.
  If the command returns agent_blocked or an error, write the file and end with END-<name>.
```

The LIMITS block above is for a read-only helper (reviewer, investigator). For a helper that does work in its worktree, change only the first clause, `do not edit files`, to `edit only inside <worktree path>`; the rest stays, and commit, push and PR remain off-limits without a direct order from the user in the helper's pane.

A command that writes to a shared environment is any command whose effect leaves the checkout: database, cloud, external service, deploy. Replace `<list the repo's>` with that repository's concrete commands, for example: `do not run migrations against a shared database; do not run terraform apply; do not deploy`. When the repository documents none, write this fallback instead: `anything that deploys, migrates a database, publishes a package or image, or writes to a remote service`.

COMPARISON_BASE is what "the diff" means for this task. Use the base the user or the repository's instructions name; otherwise `origin/<default branch>`, with the default branch read from `git symbolic-ref --short refs/remotes/origin/HEAD`. Say in TASK whether uncommitted changes are included.

LIMITS are spelled out because the helper does not inherit the coordinator's memory or instructions: what the coordinator knows from memory, from an instructions file (CLAUDE.md) or from the conversation does not reach the helper, and a helper of another kind (a Codex coordinated by a Claude, for example) does not even read the coordinator's instruction files. Replace `<RETURN>` with the address and `<name>` with the exact lowercase name passed to `agent start` before sending: the `<from: reviewer-1>` tag and the `END-reviewer-1` marker use the agent's exact spelling. `<tmpdir>` is the coordinator's session scratch or temp directory: write its absolute path in the contract, not the placeholder.

## Model routing

Optional. Without a routing file, never pass `--model`: every agent uses the user's default model. Do not ask the user which model to use.

Look for `.claude/herdr-routing.json` in the current checkout, then in the repository's main checkout (the parent of `git rev-parse --git-common-dir`; an untracked file does not exist in a new worktree), then `~/.claude/herdr-routing.json`. The first one found wins. It maps a role to a model id or alias:

```json
{ "coordinator": "opus", "reviewer": "opus", "builder": "sonnet", "investigator": "haiku" }
```

The key is the agent name without its numeric suffix: `reviewer-1` looks up `reviewer`, the hand-off coordinator looks up `coordinator`. Key present: pass `--model <value>` to that agent's `herdr agent start`, after the `--` and after `--session-id <uuid>`. Key absent: no `--model`. The file only reads; never create or edit it unless the user asks.

## Worktree requested in plain language

"Create a worktree for PROJ-123", "isolate this in a branch", "open a branch to test without touching main": inside Herdr this is `herdr worktree create`, never a bare `git worktree add`. Herdr creates the checkout, opens a workspace grouped with the current one and shows it in the sidebar. Plain git leaves the worktree invisible.

1. `git fetch origin`. The base is `origin/<default branch>`, not the local branch.
2. Branch name per the convention of the repository the worktree is created in: read its CLAUDE.md, AGENTS.md or CONTRIBUTING. A convention with a type prefix (`<type>/<short-name>`, with or without an issue ID): pick the type from the request's verb, refactor = `refactor`, fix = `fix`, new = `feat`, docs only = `docs`, deps or config = `chore`. If the convention requires an issue ID and the request has none, ask for the ID, nothing else. If it does not require one, do not ask. No documented convention: `<type>/<short-kebab-name>`.
3. Check that the branch and checkout do not exist yet: `git branch --list '<branch>'` and `herdr worktree list`. If they exist, stop and report; do not overwrite.
4. Create without stealing focus:

   ```bash
   herdr worktree create --workspace "$HERDR_WORKSPACE_ID" \
     --branch <branch> --base origin/<default branch> --label "<label>" --no-focus
   ```

   `<label>` is the sidebar name, formatted as in "Names and orientation": `<project> · <ID> <short title>`, or `<project> · <short branch name>` without an issue.

   Worktree in another repository: replace `--workspace "$HERDR_WORKSPACE_ID"` with `--cwd <other repo root>`, run `git fetch` with `git -C <other repo root>`, and the step 3 checks become `git -C <other repo root> branch --list '<branch>'` and `herdr worktree list --cwd <other repo root>`.

   Without `--path`, the checkout goes to `<worktrees.directory>/<repo>/<branch-slug>`, default `~/.herdr/worktrees`. Read the path and the new workspace id from the JSON result.
5. Report path, branch and the workspace's sidebar name. A worktree in another repository that had no open workspace yet: Herdr also opens a workspace for that repository's main checkout (it shows in `herdr workspace list`, not in the `worktree create` result). Report both and warn that the main-checkout one stays open after the worktree is removed; the helper goes in the result's `root_pane`, never in that other workspace's pane.
   Per-checkout setup: the new worktree has only what is committed. Installed dependencies, virtual environments, local credentials and files with uncommitted local changes (`.env`, files marked skip-worktree) do not come along. Read the setup the repository requires in its README or CLAUDE.md and tell the user what has to be redone inside the new checkout before running anything there, for example `npm install` or `uv sync`, copying `.env`, or refreshing a local credentials file.
6. There is work to do in the worktree (the request includes implementing, adjusting, investigating or testing): start a helper in its pane and send the contract. `herdr pane list --workspace <new id>` gives the pane; follow the Flow from step 2, which also renames the root pane. The coordinator does not edit or run commands there (section "Where the coordinator works"). This step is for a coordinator already working in its own worktree. From a main-checkout session, the agent started in the new worktree is the project coordinator, by hand-off, not a helper (section "Starting in the main checkout"). A request only to create the worktree: create, report and stop; do not start an agent or touch the issue tracker.
7. Remove only when asked. **Before removing, read `references/removing-worktrees.md` and follow its order.** In short: read path and workspace id from `herdr worktree list`; stop if `git status --porcelain` is not empty; find panes in every workspace whose cwd is inside the checkout and stop if any is busy or is your own; close only those in other workspaces; then `herdr worktree remove --workspace <id>`. A pane left inside a removed checkout becomes an orphan: Herdr saves its cwd with "(deleted)" and, on restore, falls back to HOME.

## Several helpers

Start them all at once, each with its own name and contract and the same return address. Keep the helper table in a file, not only in your reasoning: `<state>/helpers.md`, one line per helper with name, pane (id and label), session id, model, received, ended. `<state>` is `~/.herdr-crew/<project>/`, outside every checkout so it never shows in `git status` and survives a reboot; the contracts and received reports live beside it in `<state>/contracts/` and `<state>/reports/`. Update the table on every change. The coordinator's conversation may be compacted, and this file is where the session id for resuming and the helper part of the "where am I" map come from. Live state (which panes and agents exist, and their status) always comes from `herdr pane list` and `herdr agent list`, never from this file. A step that depends on two reports starts only when both have arrived. Only one agent edits a working tree at a time, and the coordinator counts: while a `builder` or `tester` helper is editing your checkout, you only read there; while you are editing, helpers in your checkout are read-only.

## On receiving the report

List every item with a disposition: valid, already fixed, discarded and why. The user wants the full list, not a summary. Cross-check against the current code, because the working tree changed while the helper was reading.

## Red flags

Full table with fixes in `references/common-mistakes.md`. The ones that do silent damage:

- `agent prompt --wait` to a helper: blocks the coordinator.
- Re-sending a prompt after `timeout` or `agent_prompt_stalled`: may duplicate the task. `agent get` and `agent read` first.
- Answering a helper's approval dialog: only the user approves.
- Closing a worktree's root pane to end a helper: takes the worktree workspace down. End the agent with `/exit`.
- The coordinator editing or running tests in another checkout ("it's one line", "I already have the context"): worktree plus helper, always. The small-edit exception is for your own checkout only.
- Writing contracts, tables or any state file inside a checkout: it dirties `git status` and blocks worktree removal. State goes in `~/.herdr-crew/<project>/`.
- Asking the user which model to use: routing file or the user's default, no question.
- Answering a folder-trust or any other startup dialog for a helper: only the user does.
- Removing a worktree with panes inside it: orphaned "(deleted)" cwd. Follow `references/removing-worktrees.md`.
- `git worktree add` inside Herdr: worktree with no workspace, invisible in the sidebar.
