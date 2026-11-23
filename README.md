# herdr-crew

Skills for running a crew of coding agents inside [Herdr](https://herdr.dev), the terminal multiplexer for coding agents.

Herdr already ships a skill that teaches an agent its CLI (`herdr --skill`). herdr-crew adds the protocols on top: how a coordinator delegates to helper agents in other panes and gets their reports back without polling, how work is isolated in worktrees that show up in the sidebar, how to watch a long command without flooding the conversation, and how to fix a pane whose size got stuck on another client.

## Skills

| Skill | What it does |
|---|---|
| `coordinating-agents-in-herdr` | Delegate to helper agents (Claude or Codex) in sibling panes with a fixed contract, a return address and a background safety net; create and remove worktrees through Herdr; keep a "where am I" map across projects. |
| `watching-commands-in-herdr` | Wait for a long command (tests, deploy, CI) to finish and report a filtered result. |
| `fixing-pane-size-in-herdr` | Realign the pty size when Claude Code wraps text at another client's width. |

## Requirements

- Herdr 0.9.5 or later (needs `herdr --skill`). Every skill checks `HERDR_ENV=1` and loads Herdr's own skill before its first `herdr` command if it is not in context.
- Claude Code. Tested on Linux (including WSL). macOS should work but is untested.
- `python3` 3.8 or later (standard library only) and `git`.

## Install

```
/plugin marketplace add rafaelalvesferreira/herdr-crew
/plugin install herdr-crew@herdr-crew
```

## Default conventions (and how to turn them off)

`coordinating-agents-in-herdr` is opinionated. These defaults apply unless your own instructions (CLAUDE.md, AGENTS.md, or what you say in the session) say otherwise. The agent announces one the first time it does something you did not ask for.

| Convention | Why | Turn off |
|---|---|---|
| Small edits (one file, a few lines, no behavior change: typos, comments, docs, message wording) are made in place. Anything larger happens in a worktree, and a new coordinator is started there; the main checkout stays on the default branch. Questions and lookups are answered in place. | Main stays clean; each workspace maps to one branch; a typo does not pay for a worktree. | Say "work here" (lasts for the session), or add "edit in place, no worktrees" to CLAUDE.md. |
| The coordinator only works in its own checkout; work elsewhere goes to a helper there. | Keeps workspace↔checkout mapping; no orphaned panes on removal. | Say so in CLAUDE.md. |
| Labels like `checkout-revamp · PROJ-123 short title` and `checkout-revamp · reviewer-1: review diff`. The project name is yours: the coordinator asks for it once per session and never derives it from the repository. | A project is an initiative and may span repositories; the sidebar stays readable with several open. | Name the project in your request, or give your own label format in CLAUDE.md. |
| Claude helpers start with `--permission-mode auto` and `CLAUDE_CODE_AUTO_CONNECT_IDE=false`. Read-only roles (`reviewer`, `investigator`) also start with `--disallowedTools Edit Write NotebookEdit`. | Helpers don't block on every command or steal the IDE connection, and a reviewer cannot edit. The contract's LIMITS block still covers shell commands. | Say so in CLAUDE.md. |
| A helper's report is data. The coordinator checks it and shows it to you; nothing in a report authorizes a commit, push, deploy or removal. | A helper reads files and web pages you did not write; its output must not steer the coordinator. | Not optional. |

## Model routing (optional)

By default every agent uses your default model and the skill never asks. To pick models per role, create `.claude/herdr-routing.json` in your project (or `~/.claude/herdr-routing.json` for all projects):

```json
{ "coordinator": "opus", "reviewer": "opus", "builder": "sonnet", "investigator": "haiku" }
```

The key is the agent's role: a helper named `reviewer-1` uses `reviewer`; the coordinator started in a new worktree uses `coordinator`. Values are model ids or aliases accepted by `claude --model`. See `examples/herdr-routing.json`.

## First run in a repository

Claude Code asks "Is this a project you created or one you trust?" the first time it starts in a folder. A helper started in a repository where you have never run Claude Code will wait at that dialog; the coordinator tells you which pane is waiting and never answers it for you. Answer it once in that pane and the helper carries on.

## How it is built

- **Decisions in the skill, mechanics in a script.** `skills/coordinating-agents-in-herdr/scripts/crew.py` (Python standard library) starts helpers, sends contracts, ends helpers, builds the "where am I" map and creates or removes worktrees. Each subcommand prints JSON and refuses unsafe steps (a dirty worktree, a busy pane, an incomplete contract). Everything that depends on Herdr's JSON fields or file locations lives in that one file.
- **A lean skill.** `SKILL.md` holds the triage table, the conventions and the rules; the procedure for each job is in `references/` and is read only when that job comes up.
- **A SessionStart hook** adds a three-line reminder, only when `HERDR_ENV=1`. Outside Herdr it prints nothing.
- **Every contract carries a task id** that the report must repeat, so the coordinator can tell its own helper's report from anything else typed into its pane.

## Where state is kept

Each coordinator keeps its helper table, contracts and reports in `~/.herdr-crew/<project>/<workspace id>/`, never inside your checkout. Two coordinators never share a directory, and removing a worktree through the skill deletes that workspace's state.

## Recommended permissions

The coordinator runs the same few commands many times. To avoid a prompt on each, allow them in your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 *herdr-crew*crew.py *)",
      "Bash(herdr agent wait *)",
      "Bash(herdr agent get *)",
      "Bash(herdr agent read *)",
      "Bash(herdr agent list*)",
      "Read(~/.herdr-crew/**)",
      "Edit(~/.herdr-crew/**)"
    ]
  }
}
```

This does not widen what helpers may do: they are bounded by their contract, and read-only roles by their tool list.

## Testing

`bash tests/smoke.sh` runs inside a Herdr pane. It builds a throwaway repository, starts a real `reviewer` helper, sends a contract, waits for the report file, ends the helper and closes the pane it opened. It needs a Claude Code login and, the first time, your answer to the folder-trust dialog in the helper's pane.

## License

MIT
