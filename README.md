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
- `jq` (worktree removal) and `python3` or `uuidgen` (session ids).

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
| Labels like `myapp · PROJ-123 short title` and `myapp · reviewer-1: review diff`. | Sidebar stays readable with several projects. | Give your own format in CLAUDE.md. |
| Claude helpers start with `--permission-mode auto` and `CLAUDE_CODE_AUTO_CONNECT_IDE=false`. | Helpers don't block on every command or steal the IDE connection. The contract's LIMITS block is what contains them. | Say so in CLAUDE.md. |

## Model routing (optional)

By default every agent uses your default model and the skill never asks. To pick models per role, create `.claude/herdr-routing.json` in your project (or `~/.claude/herdr-routing.json` for all projects):

```json
{ "coordinator": "opus", "reviewer": "opus", "builder": "sonnet", "investigator": "haiku" }
```

The key is the agent's role: a helper named `reviewer-1` uses `reviewer`; the coordinator started in a new worktree uses `coordinator`. Values are model ids or aliases accepted by `claude --model`. See `examples/herdr-routing.json`.

## First run in a repository

Claude Code asks "Is this a project you created or one you trust?" the first time it starts in a folder. A helper started in a repository where you have never run Claude Code will wait at that dialog; the coordinator tells you which pane is waiting and never answers it for you. Answer it once in that pane and the helper carries on.

## Where state is kept

The helper table, saved contracts and received reports go to `~/.herdr-crew/<project>/`, never inside your checkout. To avoid a permission prompt on the first write, allow it in your Claude Code settings:

```json
{ "permissions": { "allow": ["Edit(~/.herdr-crew/**)"] } }
```

## License

MIT
