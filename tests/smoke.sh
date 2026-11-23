#!/usr/bin/env bash
# Real end-to-end check of crew.py inside Herdr. Usage: bash tests/smoke.sh
# Starts one reviewer helper in a throwaway repository, sends a contract whose RETURN
# writes the report file, waits for it, ends the helper and closes the pane it opened.
set -euo pipefail
[ "${HERDR_ENV:-}" = 1 ] || { echo "SKIP: not inside Herdr (HERDR_ENV != 1)"; exit 0; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CREW="$ROOT/skills/coordinating-agents-in-herdr/scripts/crew.py"
PROJECT="crew-smoke-$$"
REPO="${CREW_SMOKE_REPO:-$HOME/.herdr-crew-smoke-repo}"
j() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(sys.argv[1], ""))' "$1"; }
step() { printf '\n== %s\n' "$*"; }

step "throwaway repository at $REPO"
if [ ! -d "$REPO/.git" ]; then
  mkdir -p "$REPO" && git -C "$REPO" init -q -b main
  printf 'def add(a, b):\n    return a + b\n' > "$REPO/calc.py"
  git -C "$REPO" add . && git -C "$REPO" -c user.name=smoke -c user.email=smoke@example.invalid commit -qm init
fi
rm -rf "$REPO/.claude" "$REPO"/shapes.py "$REPO"/temps.py "$REPO"/test_all.py
printf 'def add(a, b):\n    return a - b\n' > "$REPO/calc.py"
cd "$REPO"

step "map"
python3 "$CREW" map | j ok | grep -qx True

step "helper-start"
OUT="$(python3 "$CREW" helper-start --project "$PROJECT" --role reviewer --task "smoke test" --return file || true)"
NAME="$(echo "$OUT" | j name)"; PANE="$(echo "$OUT" | j pane_id)"
CONTRACT="$(echo "$OUT" | j contract_file)"; REPORT="$(echo "$OUT" | j report_file)"; TASK="$(echo "$OUT" | j task_id)"
[ -n "$NAME" ] || { echo "$OUT"; echo "FAIL: helper-start"; exit 1; }
cleanup() {
  python3 "$CREW" end --project "$PROJECT" --name "$NAME" >/dev/null 2>&1 || true
  herdr pane close "$PANE" >/dev/null 2>&1 || true
  rm -rf "$HOME/.herdr-crew/$PROJECT"; git -C "$REPO" checkout -q -- calc.py
}
trap cleanup EXIT
if [ "$(echo "$OUT" | j error)" = blocked_at_startup ]; then
  echo "Helper $NAME in pane $PANE waits at a dialog (folder trust?). Answer it in that pane."
  herdr agent wait "$NAME" --until idle --timeout 300000 >/dev/null
fi

step "send refuses an unfilled contract"
{ python3 "$CREW" send --project "$PROJECT" --name "$NAME" || true; } | j error | grep -qx contract_incomplete

step "fill and send"
python3 - "$CONTRACT" "$REPO" <<'PY'
import re, sys
p, repo = sys.argv[1], sys.argv[2]
s = open(p).read()
fills = ["read-only reviewer", f"repository {repo}, branch main, nobody else is editing",
         "review the uncommitted change in calc.py; report bugs only", "HEAD",
         "anything that deploys, migrates a database, publishes a package or image, or writes to a remote service",
         "one line per finding as file:line: problem"]
for f in fills:
    s = re.sub(r"<FILL[^>]*>", f, s, count=1)
open(p, "w").write(s)
PY
python3 "$CREW" send --project "$PROJECT" --name "$NAME" | j ok | grep -qx True

step "wait for the report ($TASK)"
for _ in $(seq 1 90); do
  [ -s "$REPORT" ] && break
  sleep 2
done
[ -s "$REPORT" ] || { echo "FAIL: no report file"; herdr agent read "$NAME" --source visible --lines 30; exit 1; }
head -20 "$REPORT"; grep -q "<from: $NAME task: $TASK>" "$REPORT"

step "read-only role was started without edit tools"
git -C "$REPO" diff --stat -- calc.py | grep -q calc.py   # the bug is still there: the helper did not fix it

step "end"
herdr agent wait "$NAME" --until idle --timeout 120000 >/dev/null 2>&1 || true
python3 "$CREW" end --project "$PROJECT" --name "$NAME" | j ended | grep -qx True

step "resume and follow-up keep the same task id"
SID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]["session_id"])' "$HOME/.herdr-crew/$PROJECT/$(echo "$HERDR_WORKSPACE_ID" | tr 'A-Z' 'a-z')/helpers.json" "$NAME")"
OUT="$(python3 "$CREW" helper-start --project "$PROJECT" --resume "$SID")"
[ "$(echo "$OUT" | j task_id)" = "$TASK" ] && [ "$(echo "$OUT" | j pane_id)" = "$PANE" ] || { echo "$OUT"; echo "FAIL: resume"; exit 1; }
herdr agent wait "$NAME" --until idle --timeout 120000 >/dev/null 2>&1 || true
rm -f "$REPORT"
python3 "$CREW" send --project "$PROJECT" --name "$NAME" --message "Follow-up: in one line, which operator should line 2 use? Include the word FOLLOWUP-$$ in the result." | j ok | grep -qx True
for _ in $(seq 1 90); do [ -s "$REPORT" ] && break; sleep 2; done
grep -q "<from: $NAME task: $TASK>" "$REPORT" && grep -q "FOLLOWUP-$$" "$REPORT" || { echo "FAIL: follow-up report"; cat "$REPORT" 2>/dev/null; exit 1; }
head -5 "$REPORT"
herdr agent wait "$NAME" --until idle --timeout 120000 >/dev/null 2>&1 || true
python3 "$CREW" end --project "$PROJECT" --name "$NAME" | j ended | grep -qx True

step "lead: three parts, subagents on the routing file's model"
mkdir -p "$REPO/.claude" && printf '{"default": "sonnet", "subagent": "haiku"}\n' > "$REPO/.claude/herdr-routing.json"
OUT="$(python3 "$CREW" helper-start --project "$PROJECT" --role lead --task "three modules" --return file)"
LEAD="$(echo "$OUT" | j name)"; LCONTRACT="$(echo "$OUT" | j contract_file)"; LREPORT="$(echo "$OUT" | j report_file)"
[ "$(echo "$OUT" | j model)" = sonnet ] && [ "$(echo "$OUT" | j subagent_model)" = haiku ] || { echo "$OUT"; echo "FAIL: lead models"; exit 1; }
NAME="$LEAD"   # cleanup now ends the lead
{ python3 "$CREW" send --project "$PROJECT" --name "$LEAD" || true; } | j error | grep -qx contract_incomplete
python3 - "$LCONTRACT" "$REPO" <<'PY'
import re, sys
p, repo = sys.argv[1], sys.argv[2]
s = open(p).read()
fills = ["lead that splits the work among subagents", f"repository {repo}, branch main, nobody else is editing",
         "add three small pure-Python modules and one test file, as planned; calc.py stays untouched",
         "create shapes.py | files: shapes.py | interface: area(w: float, h: float) -> float returns w*h | done when: importable",
         "create temps.py | files: temps.py | interface: c_to_f(c: float) -> float returns c*9/5+32 | done when: importable",
         "create test_all.py | files: test_all.py | interface: imports area from shapes and c_to_f from temps; asserts area(2,3)==6 and c_to_f(100)==212; prints OK | done when: file exists",
         "python3 test_all.py", "HEAD", f"edit only inside {repo}",
         "anything that deploys, migrates a database, publishes a package or image, or writes to a remote service",
         "one line per part with its outcome, then the CHECK output"]
for f in fills:
    s = re.sub(r"<FILL[^>]*>", lambda m: f, s, count=1)
open(p, "w").write(s)
PY
! grep -q "<FILL" "$LCONTRACT" || { cat "$LCONTRACT"; echo "FAIL: lead contract fill"; exit 1; }
python3 "$CREW" send --project "$PROJECT" --name "$LEAD" | j ok | grep -qx True
for _ in $(seq 1 240); do [ -s "$LREPORT" ] && break; sleep 2; done
[ -s "$LREPORT" ] || { echo "FAIL: no lead report"; herdr agent read "$LEAD" --source visible --lines 30; exit 1; }
head -12 "$LREPORT"
( cd "$REPO" && python3 test_all.py )
LSID="$(echo "$OUT" | j session_id)"
echo "models in the lead's session files:"; grep -rhoE '"model":"claude-[a-z0-9-]+"' "$HOME"/.claude/projects/*/"$LSID"* 2>/dev/null | sort | uniq -c || true
herdr agent wait "$LEAD" --until idle --timeout 120000 >/dev/null 2>&1 || true
python3 "$CREW" end --project "$PROJECT" --name "$LEAD" | j ended | grep -qx True
rm -rf "$REPO/.claude" "$REPO"/shapes.py "$REPO"/temps.py "$REPO"/test_all.py "$REPO"/__pycache__

step "worktree create, refuse dirty, remove"
git -C "$REPO" checkout -q -- calc.py
WS_BEFORE="$(herdr workspace list | python3 -c 'import json,sys; print(" ".join(w["workspace_id"] for w in json.load(sys.stdin)["result"]["workspaces"]))')"
BR="chore/smoke-$$"
OUT="$(python3 "$CREW" worktree-create --project "$PROJECT" --branch "$BR" --label "smoke $$")"
WT="$(echo "$OUT" | j checkout)"; WTWS="$(echo "$OUT" | j workspace_id)"
[ -d "$WT" ] && [ -n "$WTWS" ] || { echo "$OUT"; echo "FAIL: worktree-create"; exit 1; }
{ python3 "$CREW" worktree-create --project "$PROJECT" --branch "$BR" --label x || true; } | j error | grep -qx branch_exists
touch "$WT/untracked.txt"
{ python3 "$CREW" worktree-remove --path "$WT" --execute || true; } | j error | grep -qx dirty_worktree
rm "$WT/untracked.txt"
python3 "$CREW" worktree-remove --path "$WT" | j executed | grep -qx False
OUT="$(python3 "$CREW" worktree-remove --path "$WT" --execute)"
[ ! -d "$WT" ] && [ "$(echo "$OUT" | j orphaned_panes)" = 0 ] || { echo "$OUT"; echo "FAIL: worktree-remove"; exit 1; }
git -C "$REPO" branch -q -D "$BR"
for w in $(herdr workspace list | python3 -c 'import json,sys; print(" ".join(w["workspace_id"] for w in json.load(sys.stdin)["result"]["workspaces"]))'); do
  case " $WS_BEFORE " in *" $w "*) ;; *) herdr workspace close "$w" >/dev/null 2>&1 || true ;; esac   # the main-checkout workspace Herdr opened
done

echo; echo "PASS"
