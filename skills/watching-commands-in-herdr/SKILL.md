---
name: watching-commands-in-herdr
description: Use when inside Herdr (HERDR_ENV=1) the user asks to keep an eye on a long command already running in their pane ("let me know when the build finishes", "watch my deploy", "tell me if CI passed"), or asks you to run a read-only command and report the result (test suite, lint, gh pr checks) without dumping its output into the conversation.
---

# Watching commands in Herdr

## Overview

Wait in the background for the current run to end, covering success and failure, then read only a filtered tail of the current run. The user's pane: observe only, never send keys. A read-only command you run yourself: your own shell with output redirected to a file, where the exit code decides.

## Before anything

1. `test "${HERDR_ENV:-}" = 1`. If it fails, say you are not inside Herdr and stop.
2. If Herdr's own skill is not already in your context, run `herdr --skill` and read its output (`pane read`, `wait-output`). A request to watch a command counts as an explicit request to use Herdr.

## Pick the path

| Situation | Path |
|---|---|
| You run the command yourself | **Own shell.** Run it in the background with output to a file: `<cmd> > <tmpdir>/<name>.log 2>&1; echo "exit=$?" >> <tmpdir>/<name>.log`. When it finishes, the exit code is the verdict; grep the log for counts and failures. `<tmpdir>` is your session's scratch or temp directory, absolute path. |
| The command already runs in the user's pane, and no end line from an earlier run is on screen | **`wait-output`.** `herdr pane wait-output <pane> --regex '<success>\|<failure>' --timeout <ms>` in the background. |
| The command already runs in the user's pane, and an earlier run's end line is still on screen | **Poll the current run.** `wait-output` would match the old line at once. Use the loop below. |
| The tool prints no end line on success (e.g. `go test ./...` across packages) | **Poll for the shell prompt.** Same loop, with the user's prompt (the last line of a recent read before the command started, e.g. `\$ $`) as the "end" signature. |

Decide which pane case applies by reading first: `herdr pane read <pane> --source recent-unwrapped --lines 60`, then find the last start marker and check whether any end signature appears after it.

## Polling the current run

Keep only text after the last start marker, so an earlier run never matches:

```bash
PANE=w1:p3; START='test session starts'; END='[0-9]+ (passed|failed)|=+ ERRORS =+|Interrupted'
for i in $(seq 1 120); do   # 120 x 5 s = 10 min
  herdr pane read "$PANE" --source recent-unwrapped --lines 200 \
    | awk -v s="$START" '$0 ~ s {buf=""} {buf=buf $0 "\n"} END {printf "%s", buf}' > /tmp/run.txt
  grep -Eq "$END" /tmp/run.txt && break
  sleep 5
done
grep -E "$END" /tmp/run.txt | tail -n 15
```

Run it in the background. Replace `/tmp/run.txt` with a path in your temp directory.

## Rules

- **The end signature covers success and failure.** Waiting only for success hangs until timeout when the command fails.
- **The final read decides, not the match.** The wait only says "it ended". Read the current run's tail (`grep -E '<signatures>' | tail -n 15`) and judge success from that, keeping only lines after the last start marker. For the cause of a failure, a second read with `grep -A6 '<failure signature>' | head -30`.
- **Timeout without a match is not success.** Read again and report "no result yet". Tools not in the table: 10 minutes for tests, 30 for deploys, unless the user says otherwise.
- **Report counts and names.** Passed/failed counts (summed when the tool prints several result lines, e.g. one per test binary), names of failing tests or targets. A green build is not a green test run.
- **Tell the user the wait is running** in the background and that they can ask you to stop it.
- **`(?m)` for line anchors.** In the Rust regex used by `wait-output`, `^` without `(?m)` matches only at the start of the whole text.

## Example signatures

Starting points; adapt to the tool at hand.

| Command | Start marker | Success | Failure |
|---|---|---|---|
| `pytest` | `test session starts` | final `=+ N passed` line with no `failed` | `failed`, `=+ ERRORS =+`, `Interrupted` |
| `cargo test` | `Compiling` or first `Running` | every `test result: ok.` and exit 0 | `test result: FAILED`; `error(\[E[0-9]+\])?:`; `could not compile` |
| `npm test` (jest) | `> jest` or the script name | `Tests:` line with no `failed` | `Tests:.*failed`; `npm ERR!` |
| `go test ./...` | none | shell prompt back, no `FAIL` | `^FAIL`, `--- FAIL`, `panic:` |
| `gh pr checks --watch` | n/a | exits 0 | exits non-zero; `fail` in the table |
| `terraform apply` | `Terraform will perform` | `Apply complete!` | line starting with `Error:` |
| `dbt run/build` | `Running with dbt` | `Done. PASS=… ERROR=0 SKIP=0` | `Completed with N error`; `ERROR>0` in `Done.`; `Encountered an error`; `Compilation Error`; `Runtime Error` |

Example `wait-output` regex for terraform: `(?m)Apply complete!|^Error:`.
