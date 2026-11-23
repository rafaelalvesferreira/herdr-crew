#!/usr/bin/env python3
"""herdr-crew mechanics: the deterministic parts of coordinating agents in Herdr.

Every subcommand prints one JSON object on stdout. "ok": false means stop and
read "error" and "hint". Standard library only.

  crew.py helper-start --project P --role R --task "few words" [--pane ID] [--resume SID] [--kind claude|codex]
  crew.py send --project P --name N [--message "follow-up text"]
  crew.py end --project P --name N
  crew.py map
  crew.py worktree-create --project P --branch B --label "ID short title" [--repo PATH] [--coordinator ID --handoff-file F]
  crew.py worktree-remove --path CHECKOUT [--execute]
  crew.py routing --role R
  crew.py state-dir --project P
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

MIN_HERDR = (0, 9, 5)
READ_ONLY_ROLES = {"reviewer", "investigator"}
READ_ONLY_DISALLOWED = ["Edit", "Write", "NotebookEdit"]
SESSION_FILE = Path.home() / ".config" / "herdr" / "session.json"
PLACEHOLDER = "<FILL"

CONTRACT_TEMPLATE = """ROLE: <FILL: one line, what the helper is>
CONTEXT: <FILL: repo, branch, checkout path, what another agent is editing at the same time>
TASK: <FILL: what to do, criteria, what to ignore>
{plan_block}COMPARISON_BASE: <FILL: ref to compare against, or n/a>
LIMITS: {limits_first}; do not run git commit/push/checkout/stash; do not run commands that write
  to shared environments (<FILL: the repo's commands, or: anything that deploys, migrates a database, publishes a package or image, or writes to a remote service>); if you need an approval, stop and say so in the RETURN.
FORMAT: <FILL: shape of the result, short>; end with the line END-{name}
{return_block}"""

LEAD_RULE = ("Start one subagent per part; each subagent edits only that part's files. You integrate, run CHECK "
             "and fix what it shows. Do not skip or merge a part without saying so. Report each part with its "
             "outcome, then the CHECK result.")
PLAN_BLOCK = """PLAN: {rule}
  part 1: <FILL: what | files: paths this part owns | interface: what it exposes or consumes | done when: check>
  part 2: <FILL: same shape>
  part 3: <FILL: same shape; add more part lines below when needed>
CHECK: <FILL: the command that shows the parts fit>
"""
MODEL_RE = re.compile(r"^[A-Za-z0-9._:\[\]-]+$")

RETURN_PROMPT = """RETURN: when done, run exactly:
  herdr agent prompt {ret} "<from: {name} task: {task_id}> <one-line status>
  <result, at most 40 lines>"
  Result longer than 40 lines: write it with a shell redirect to {report} and send only the path.
  If the command returns agent_blocked or an error, write that file and end with END-{name}.
"""

RETURN_FILE = """RETURN: when done, write the result with a shell redirect to {report}
  starting with the line <from: {name} task: {task_id}> <one-line status>
  and then print the line END-{name}. Do not run herdr agent prompt.
"""


def out(obj, code=0):
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    sys.exit(code)


def fail(error, hint="", **extra):
    out({"ok": False, "error": error, "hint": hint, **extra}, 1)


def sh(cmd, cwd=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    except OSError as e:
        return 127, "", str(e)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def herdr(*args):
    """Run a herdr command. Returns (ok, result_or_error_dict)."""
    code, so, se = sh(["herdr", *args])
    raw = so if so else se
    try:
        data = json.loads(raw)
    except ValueError:
        return code == 0, {"raw": raw}
    if not isinstance(data, dict):
        return False, {"raw": raw}
    if "error" in data:
        return False, data["error"]
    return code == 0, data.get("result", data)


def preflight():
    if os.environ.get("HERDR_ENV") != "1":
        fail("not_in_herdr", "HERDR_ENV is not 1. Say you are not inside Herdr and stop.")
    code, so, _ = sh(["herdr", "--version"])
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", so)
    if m and tuple(int(x) for x in m.groups()) < MIN_HERDR:
        return f"herdr {m.group(0)} is older than the tested {'.'.join(map(str, MIN_HERDR))}"
    return None


def slug(text):
    return re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-") or "project"


def state_dir(project):
    ws = os.environ.get("HERDR_WORKSPACE_ID", "no-workspace")
    d = Path.home() / ".herdr-crew" / slug(project) / slug(ws)
    (d / "contracts").mkdir(parents=True, exist_ok=True)
    (d / "reports").mkdir(parents=True, exist_ok=True)
    return d


def load_helpers(d):
    f = d / "helpers.json"
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text())
    except ValueError:
        fail("bad_state_file", f"{f} is not valid JSON. Tell the user; do not delete it.")
    return data if isinstance(data, dict) else {}


def save_helpers(d, helpers):
    tmp = d / "helpers.json.tmp"
    tmp.write_text(json.dumps(helpers, indent=2, ensure_ascii=False))
    tmp.replace(d / "helpers.json")


def checkout_root(cwd=None):
    code, so, _ = sh(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    return so if code == 0 else None


def main_checkout(cwd=None):
    code, so, _ = sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=cwd)
    return str(Path(so).parent) if code == 0 and so else None


def routing_model(role, fallback=True):
    """Model for a role (else the file's `default`) from the first routing file found, else None."""
    candidates = []
    top = checkout_root()
    if top:
        candidates.append(Path(top) / ".claude" / "herdr-routing.json")
    main = main_checkout()
    if main:
        candidates.append(Path(main) / ".claude" / "herdr-routing.json")
    candidates.append(Path.home() / ".claude" / "herdr-routing.json")
    for f in candidates:
        if f.exists():
            try:
                data = json.loads(f.read_text())
                if not isinstance(data, dict):
                    raise ValueError
                model = data.get(role) or (data.get("default") if fallback else None)
                if model is not None and not (isinstance(model, str) and MODEL_RE.match(model)):
                    fail("bad_routing_file", f"{f}: `{model}` is not a model id or alias. Tell the user.")
                return model, str(f)
            except ValueError:
                fail("bad_routing_file", f"{f} is not valid JSON. Tell the user; do not edit it.")
    return None, None


def return_address():
    pane = os.environ.get("HERDR_PANE_ID")
    if not pane:
        fail("no_return_address", "HERDR_PANE_ID is empty.")
    me = next((p for p in panes() if p["pane_id"] == pane), {})
    if not me.get("agent"):
        fail("return_pane_is_a_shell", "Herdr sees no agent in this pane, so a report prompted here would be "
             "typed into a shell. Run from the coordinator's own pane, or pass --return file.")
    return pane


def agents():
    ok, res = herdr("agent", "list")
    return res.get("agents", []) if ok else []


def panes(workspace=None):
    args = ["pane", "list"] + (["--workspace", workspace] if workspace else [])
    ok, res = herdr(*args)
    return res.get("panes", []) if ok else []


def pane_label(p):
    return p.get("label") or p.get("name") or ""


def shell_idle(pane_id):
    ok, res = herdr("pane", "process-info", "--pane", pane_id)
    info = res.get("process_info", {}) if ok else {}
    return bool(info) and info.get("foreground_process_group_id") == info.get("shell_pid"), info


def split_direction():
    """Split to the right only while the coordinator's own pane is wide enough for two."""
    me = os.environ.get("HERDR_PANE_ID", "")
    ok, res = herdr("pane", "layout", "--pane", me)
    stack = [res] if ok else []
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x.get("pane_id") == me and isinstance(x.get("rect"), dict):
                return "right" if x["rect"].get("width", 0) >= 160 else "down"
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    return "down"


def live_pane(name):
    """Pane of the live agent with this name, or None. Names are server-wide, so always compare panes."""
    return next((x.get("pane_id") for x in agents() if x.get("name") == name), None)


def read_screen(target, lines=30):
    code, so, _ = sh(["herdr", "agent", "read", target, "--source", "visible", "--lines", str(lines)])
    return "\n".join(l for l in so.splitlines() if l.strip())[-1500:]


# ---------------------------------------------------------------- helper-start
def cmd_helper_start(a):
    warn = preflight()
    if not a.resume and not (a.role and a.task):
        fail("missing_arguments", "--role and --task are required unless --resume is given.")
    role = slug(a.role or "x")
    d = state_dir(a.project)
    helpers = load_helpers(d)
    ws = os.environ.get("HERDR_WORKSPACE_ID")
    if not ws:
        fail("no_workspace", "HERDR_WORKSPACE_ID is empty.")

    live = {x.get("name") for x in agents()}
    if a.resume:
        prev = [n for n, h in helpers.items() if h.get("session_id") == a.resume]
        if not prev:
            fail("unknown_session", "That session id is not in this coordinator's helper table.")
        name = prev[0]
        role = name.rsplit("-", 1)[0]  # the role comes from the table, never from the flag
        if helpers[name].get("kind") != "claude":
            fail("not_resumable", "Only Claude helpers can be resumed. Start a new helper.")
        if name in live:
            if live_pane(name) == helpers[name].get("pane_id"):
                fail("already_running", f"{name} is live. Send the follow-up with `crew.py send --message`.")
            fail("name_taken", f"Another agent named {name} is live in pane {live_pane(name)} (not yours). "
                 "Start a new helper for the follow-up instead of resuming.")
    else:
        n = 1
        while f"{role}-{n}" in live or f"{role}-{n}" in helpers:
            n += 1
        name = f"{role}-{n}"

    # everything that can refuse is settled before any pane or agent is touched
    model, routing_file = routing_model(role)
    sub_model = routing_model("subagent", fallback=False)[0] if role == "lead" else None
    if a.resume:
        model, sub_model = helpers[name].get("model"), helpers[name].get("subagent_model")
    if role == "lead" and a.kind != "claude":
        fail("lead_needs_claude", "Only a Claude helper can be a lead.")
    task_id = helpers[name]["task_id"] if a.resume else "t-" + uuid.uuid4().hex[:6]
    ret = helpers[name]["return"] if a.resume else ("file" if a.return_mode == "file" else return_address())
    top = helpers[name].get("cwd") if a.resume else checkout_root()
    helper_label = re.compile(rf"^{re.escape(a.project)} · [a-z]+-\d+: ")

    label = f"{a.project} · {name}: {a.task}" if a.task else helpers.get(name, {}).get("label", f"{a.project} · {name}")
    reused = False
    if a.pane:
        pane_id = a.pane
    elif a.resume and helpers[name].get("pane_id") in {p["pane_id"] for p in panes()}:
        pane_id = helpers[name]["pane_id"]
    else:
        pane_id = None
        for p in panes(ws):  # reuse an ended helper pane of this project before splitting again
            if (not a.resume and helper_label.match(pane_label(p)) and not p.get("agent") and p["pane_id"] != os.environ.get("HERDR_PANE_ID")
                    and shell_idle(p["pane_id"])[0]):
                pane_id, reused = p["pane_id"], True
                break
        if not pane_id:
            if not top:
                fail("not_a_checkout", "The current directory is not inside a git checkout.")
            ok, res = herdr("pane", "split", "--current", "--direction", split_direction(), "--cwd", top,
                            "--env", "CLAUDE_CODE_AUTO_CONNECT_IDE=false", "--no-focus")
            if not ok:
                fail("split_failed", json.dumps(res))
            pane_id = res["pane"]["pane_id"]

    idle, info = shell_idle(pane_id)
    if not idle:
        fail("pane_busy", "The pane is not at a shell prompt. Do not start an agent over a running command.",
             pane_id=pane_id, process=info.get("foreground_processes"))
    if a.pane or reused:  # panes that did not come from our split lack the env var
        herdr("pane", "run", pane_id, "export CLAUDE_CODE_AUTO_CONNECT_IDE=false")
        time.sleep(0.5)
    if reused and top:  # a reused shell may have wandered; a split already starts at the checkout root
        herdr("pane", "run", pane_id, "cd " + json.dumps(top))
        time.sleep(0.5)
    if sub_model:  # the lead's subagents run on the routing file's `subagent` model
        herdr("pane", "run", pane_id, f"export CLAUDE_CODE_SUBAGENT_MODEL={sub_model}")
        time.sleep(0.5)
    elif a.pane or reused:  # a reused pane may carry a previous lead's setting
        herdr("pane", "run", pane_id, "unset CLAUDE_CODE_SUBAGENT_MODEL")
        time.sleep(0.5)
    if a.pane:  # a worktree root pane: the helper's directory is that pane's, not ours
        top = next((p.get("cwd") for p in panes() if p["pane_id"] == pane_id), top)
    herdr("pane", "rename", pane_id, label)

    session_id = a.resume or str(uuid.uuid4())
    args = []
    if a.kind == "claude":
        args = ["--permission-mode", "auto", "--resume" if a.resume else "--session-id", session_id]
        if model:
            args += ["--model", model]
        if role in READ_ONLY_ROLES:
            args += ["--disallowedTools", *READ_ONLY_DISALLOWED]
    start = ["agent", "start", name, "--kind", a.kind, "--pane", pane_id]
    ok, res = herdr(*(start + (["--"] + args if args else [])))

    contract = d / "contracts" / f"{name}.md"
    report = d / "reports" / f"{name}.md"
    if not a.resume:
        limits_first = ("do not edit files" if role in READ_ONLY_ROLES else
                        "<FILL: `do not edit files` for a run-only task, or `edit only inside` plus the worktree path>")
        block = (RETURN_FILE if ret == "file" else RETURN_PROMPT).format(
            name=name, ret=ret, task_id=task_id, report=report)
        contract.write_text(CONTRACT_TEMPLATE.format(
            name=name, limits_first=limits_first, return_block=block,
            plan_block=PLAN_BLOCK.format(rule=LEAD_RULE) if role == "lead" else ""))
    helpers[name] = {**helpers.get(name, {}), "pane_id": pane_id, "label": label, "kind": a.kind,
                     "session_id": session_id if a.kind == "claude" else "-", "model": model, "subagent_model": sub_model, "cwd": top,
                     "task_id": task_id, "return": ret, "received": False, "ended": False}
    save_helpers(d, helpers)

    base = {"name": name, "pane_id": pane_id, "label": label, "session_id": helpers[name]["session_id"],
            "model": model or "default", "subagent_model": (sub_model or "same as the lead") if role == "lead" else None,
            "routing_file": routing_file, "reused_pane": reused,
            "task_id": task_id, "return": ret, "contract_file": str(contract), "report_file": str(report),
            "state_dir": str(d), "warning": warn}
    if not ok:
        code = res.get("code") if isinstance(res, dict) else None
        if code == "agent_not_ready":
            out({"ok": False, "error": "blocked_at_startup", **base, "screen": read_screen(name),
                 "hint": "A dialog is open before the first prompt. Only the user answers it: tell them which "
                         "pane waits and why. Then run `herdr agent wait " + name + " --until idle --timeout "
                         "900000` in the background and `crew.py send` once it fires"
                         + (" (with --message for the follow-up)" if a.resume else "") + ". Send no keys."}, 1)
        fail("agent_start_failed", json.dumps(res), **base)
    nxt = (f"Send the follow-up with `crew.py send --project \"{a.project}\" --name {name} --message \"...\"`." if a.resume else
           f"Fill every <FILL...> in {contract}, then run `crew.py send --project \"{a.project}\" --name {name}`.")
    out({"ok": True, **base, "next": nxt})


# ------------------------------------------------------------------------ send
def cmd_send(a):
    preflight()
    d = state_dir(a.project)
    helpers = load_helpers(d)
    if a.name not in helpers:
        fail("unknown_helper", "No such helper in this coordinator's table.")
    f = d / "contracts" / f"{a.name}.md"
    text = f.read_text() if f.exists() else ""
    missing = [b for b in ("ROLE:", "CONTEXT:", "TASK:", "COMPARISON_BASE:", "LIMITS:", "FORMAT:", "RETURN:")
               if not re.search(rf"^{b}", text, re.M)]
    if missing or PLACEHOLDER in text:
        fail("contract_incomplete", f"Fix {f}: missing blocks {missing}; unfilled placeholders: "
             f"{text.count(PLACEHOLDER)}. All seven blocks are required.")
    h = helpers[a.name]
    if a.name.rsplit("-", 1)[0] == "lead":
        parts = len(re.findall(r"^\s*part \d+:\s*\S", text, re.M))
        check = re.search(r"^CHECK:\s*\S", text, re.M)
        if parts < 3 or not check or LEAD_RULE not in text:
            fail("plan_incomplete", f"A lead needs PLAN with at least 3 parts (found {parts}), a CHECK command "
                 "and the generated PLAN rule unchanged. Fewer than 3 independent parts: use a builder.")
    if a.message:  # follow-up: the message plus the contract's own RETURN block
        i = text.find("RETURN:")
        if i < 0:
            fail("contract_incomplete", f"{f} has no RETURN block to reuse.")
        text = a.message.strip() + "\n" + text[i:]
    needles = [f"END-{a.name}", f"<from: {a.name} task: {h['task_id']}>"]
    needles.append("Do not run herdr agent prompt" if h["return"] == "file" else f"herdr agent prompt {h['return']} ")
    for needle in needles:
        if needle not in text:
            fail("contract_altered", f"The contract must keep `{needle}` exactly as generated.")
    if live_pane(a.name) != h["pane_id"]:
        fail("helper_not_running", f"No live agent {a.name} in pane {h['pane_id']}. If it ended, resume it with "
             "`helper-start --resume <session_id>`.", session_id=h.get("session_id"))
    ok, st = herdr("agent", "get", a.name)
    status = (st.get("agent") or st).get("agent_status") if ok else None
    if status not in ("idle", "done"):
        fail("helper_not_ready", f"{a.name} is `{status}`. If blocked, read its screen and tell the user; "
             "do not send keys.", screen=read_screen(a.name) if status == "blocked" else None)
    ok, res = herdr("agent", "prompt", a.name, text)
    if not ok:
        fail("prompt_failed", json.dumps(res) + " Do not resend blindly: `herdr agent get` and `agent read` first.")
    time.sleep(3)
    ok, st = herdr("agent", "get", a.name)
    status = (st.get("agent") or st).get("agent_status") if ok else None
    out({"ok": True, "name": a.name, "status": status, "task_id": h["task_id"],
         "next": f"Run `herdr agent wait {a.name} --timeout 900000` as a background command, then go back to "
                 f"your work. The report arrives as a message starting with `<from: {a.name} task: {h['task_id']}>`."})


# ------------------------------------------------------------------------- end
def cmd_end(a):
    preflight()
    d = state_dir(a.project)
    helpers = load_helpers(d)
    if a.name not in helpers:
        fail("unknown_helper", "Only helpers this coordinator started are ended this way.")
    h = helpers[a.name]
    where = live_pane(a.name)
    if where and where != h["pane_id"]:
        where = None  # same name, someone else's agent: ours is already gone
    ok, st = herdr("agent", "get", a.name) if where else (False, {})
    if where and not ok:
        fail("status_unknown", json.dumps(st) + " Try again; nothing was changed.")
    if ok:
        status = (st.get("agent") or st).get("agent_status")
        if status == "blocked":
            fail("helper_blocked", "A dialog is open; the Enter of /exit could confirm it. Read the screen, "
                 "report the literal text to the user and wait.", screen=read_screen(a.name))
        if status == "working":
            fail("helper_working", "It is still working. Wait for the report or ask the user.")
        herdr("agent", "prompt", a.name, "/exit")
        for _ in range(10):
            time.sleep(1)
            if live_pane(a.name) != h["pane_id"]:
                break
        else:
            fail("exit_not_confirmed", f"{a.name} still shows in `herdr agent list`. Read its screen.")
    helpers[a.name].update({"received": True, "ended": True})
    save_helpers(d, helpers)
    out({"ok": True, "name": a.name, "ended": True, "pane_id": helpers[a.name]["pane_id"],
         "session_id": helpers[a.name]["session_id"],
         "note": "The pane stays as a shell with its label and is reused by the next helper."})


# ------------------------------------------------------------------------- map
def cmd_map(a):
    preflight()
    ok, res = herdr("workspace", "list")
    wss = res.get("workspaces", []) if ok else []
    all_panes = panes()
    by_ws = {}
    for p in all_panes:
        by_ws.setdefault(p["workspace_id"], []).append(p)
    names = {x["pane_id"]: x.get("name") for x in agents()}
    ended = {}
    root = Path.home() / ".herdr-crew"
    for f in root.glob("*/*/helpers.json") if root.exists() else []:
        try:
            for n, h in json.loads(f.read_text()).items():
                ended[h.get("pane_id")] = (n, h)
        except ValueError:
            pass

    def model_of(session_id, passed):
        """The model the agent last answered with, from its transcript; else what the script passed."""
        if session_id and re.fullmatch(r"[0-9a-f-]{36}", session_id):
            for f in (Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"):
                try:
                    with open(f, "rb") as fh:
                        fh.seek(max(0, f.stat().st_size - 200000))
                        lines = fh.read().splitlines()
                    for line in reversed(lines):  # only real answers: tool definitions also name models
                        if b'"type":"assistant"' in line:
                            m = re.search(rb'"model":"(claude-[^"]+)"', line)
                            if m:
                                return m.group(1).decode()
                except OSError:
                    pass
        return f"{passed} (requested)" if passed else ""

    def branch_of(path):
        code, so, _ = sh(["git", "-C", path, "branch", "--show-current"]) if path else (1, "", "")
        return so if code == 0 else ""

    me = os.environ.get("HERDR_PANE_ID")
    rows, here = [], None
    for w in wss:
        wt = w.get("worktree") or {}
        label = w.get("label", "")
        project = label.split(" · ")[0] if " · " in label else None
        path = wt.get("checkout_path", "")
        br = branch_of(path)
        for p in by_ws.get(w["workspace_id"], []):
            pl = pane_label(p)
            proj = project or (pl.split(" · ")[0] if " · " in pl else None)
            n, h = ended.get(p["pane_id"], (None, {}))
            if h.get("label") != pl:  # stale state for a pane id that now belongs to something else
                n, h = None, {}
            sess = (p.get("agent_session") or {}).get("value") or h.get("session_id") or ""
            row = {"project": proj or "no project", "repo": wt.get("repo_name", ""),
                   "workspace": f"{label} ({w['workspace_id']})", "branch": br,
                   "pane": f"{pl or '-'} ({p['pane_id']})", "agent": names.get(p["pane_id"]) or p.get("agent") or
                   (f"{n} (ended)" if n and h.get("ended") else "-"),
                   "status": p.get("agent_status", "-") if p.get("agent") else "shell",
                   "session_id": sess, "model": model_of(sess, h.get("model")) if (p.get("agent") or n) else "",
                   "here": p["pane_id"] == me}
            rows.append(row)
            if row["here"]:
                here = {"pane": p["pane_id"], "workspace": row["workspace"], "checkout": path or p.get("cwd"),
                        "branch": br}
    repo_project = {}
    for r in rows:  # a main-checkout workspace groups with the project of its worktrees
        if r["project"] != "no project" and r["repo"]:
            repo_project.setdefault(r["repo"], r["project"])
    for r in rows:
        if r["project"] == "no project" and r["repo"] in repo_project:
            r["project"] = repo_project[r["repo"]]
    rows.sort(key=lambda r: (r["project"] == "no project", r["project"], r["workspace"]))
    out({"ok": True, "you_are_here": here, "rows": rows})


# ------------------------------------------------------------- worktree-remove
def cmd_worktree_remove(a):
    preflight()
    path = str(Path(a.path).expanduser().resolve())
    if not Path(path).is_dir():
        fail("no_such_path", f"{path} does not exist.")
    repo = main_checkout(path)
    if not repo or repo == path:
        fail("not_a_linked_worktree", "That path is a main checkout or not a git checkout. Nothing removed.")
    ok, res = herdr("worktree", "list", "--cwd", repo)
    entry = next((w for w in res.get("worktrees", []) if w.get("path") == path), None) if ok else None
    if not entry:
        fail("worktree_not_listed", "`herdr worktree list` does not show that path.")
    ws = entry.get("open_workspace_id")
    if ws and ws == os.environ.get("HERDR_WORKSPACE_ID"):
        fail("own_pane_inside", "You are in that worktree's workspace; removing it ends you. Tell the user to "
             "/exit this session and ask from a session in the main checkout.")
    code, dirty, err = sh(["git", "-C", path, "status", "--porcelain"])
    if code != 0:
        fail("status_failed", f"git status failed in {path}: {err[:200]}. Nothing removed.")
    if dirty:
        fail("dirty_worktree", "Stop. List these files and ask the user: commit, stash, discard or force-remove. "
             "`--force` only when they explicitly say to force or discard.", files=dirty.splitlines())
    me = os.environ.get("HERDR_PANE_ID")
    inside, busy = [], []
    for p in panes():
        if (ws and p["workspace_id"] == ws) or any(
                c == path or c.startswith(path + "/") for c in (p.get("cwd") or "", p.get("foreground_cwd") or "")):
            item = {"pane_id": p["pane_id"], "workspace_id": p["workspace_id"], "agent": p.get("agent"),
                    "status": p.get("agent_status")}
            inside.append(item)
            if p["pane_id"] == me:
                fail("own_pane_inside", "Your own pane is inside that checkout; removing it ends you. Tell the "
                     "user to /exit this session and ask from a session in the main checkout.")
            if p.get("agent"):
                if p.get("agent_status") in ("working", "blocked"):
                    busy.append({**item, "why": "agent " + p["agent_status"]})
            else:
                idle, info = shell_idle(p["pane_id"])
                if not idle:
                    busy.append({**item, "why": "command running",
                                 "cmdline": [x.get("cmdline") or x.get("name") for x in info.get("foreground_processes", [])]})
    if busy:
        fail("panes_busy", "Stop and ask the user about these panes.", busy=busy)
    if not ws:
        fail("workspace_closed", f"The checkout is on disk but its workspace is closed. Reopen with `herdr worktree "
             f"open --cwd {repo} --path {path} --no-focus`, then run this again.")
    plan = {"checkout": path, "repo": repo, "workspace_id": ws, "branch": entry.get("branch"),
            "close_first": [p["pane_id"] for p in inside if p["workspace_id"] != ws],
            "closed_by_remove": [p["pane_id"] for p in inside if p["workspace_id"] == ws],
            "idle_agents_that_will_end": [p["pane_id"] for p in inside if p["agent"]]}
    if not a.execute:
        out({"ok": True, "checked": True, "executed": False, **plan,
             "next": "All clear. If idle_agents_that_will_end is not empty, name them to the user first. "
                     "Run again with --execute to remove."})
    for pid in plan["close_first"]:
        herdr("pane", "close", pid)
    ok, res = herdr("worktree", "remove", "--workspace", ws)
    if not ok:
        fail("remove_failed", json.dumps(res) + " Do not retry with --force or --trust-repository.", **plan)
    sh(["git", "-C", repo, "worktree", "prune"])
    code, so, _ = sh(["git", "-C", repo, "worktree", "list", "--porcelain"])
    time.sleep(10)
    orphans = SESSION_FILE.read_text().count("(deleted)") if SESSION_FILE.exists() else None
    removed_state = []
    for d in (Path.home() / ".herdr-crew").glob(f"*/{slug(ws)}"):  # state of the workspace that no longer exists
        shutil.rmtree(d, ignore_errors=True)
        removed_state.append(str(d))
    out({"ok": True, "executed": True, **plan, "state_removed": removed_state,
         "still_listed_by_git": f"worktree {path}" in so.splitlines(), "orphaned_panes": orphans,
         "hint": "orphaned_panes > 0: find them with `herdr pane list` ((deleted) in cwd) and close them."
         if orphans else None})


# ------------------------------------------------------------- worktree-create
def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r is not None:
                return r
    return None


def cmd_worktree_create(a):
    warn = preflight()
    if a.repo and not Path(a.repo).expanduser().is_dir():
        fail("no_such_path", f"{a.repo} does not exist.")
    if a.handoff_file and not Path(a.handoff_file).is_file():
        fail("no_handoff_file", f"{a.handoff_file} does not exist. Write the hand-off text first.")
    repo = main_checkout(str(Path(a.repo).expanduser())) if a.repo else main_checkout()
    if not repo:
        fail("not_a_checkout", "Run inside a git checkout or pass --repo <repository root>.")
    code, _, err = sh(["git", "-C", repo, "fetch", "origin"])
    code2, head, _ = sh(["git", "-C", repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
    if code2 == 0:
        base = head
        if code != 0:
            warn = f"git fetch failed ({err[:80]}); base `{head}` may be stale"
    else:
        _, cur, _ = sh(["git", "-C", repo, "branch", "--show-current"])
        base = cur or "HEAD"
        warn = f"no usable origin ({err[:80] or 'origin/HEAD not set'}); base is local `{base}`"
    _, exists, _ = sh(["git", "-C", repo, "branch", "--list", a.branch])
    ok, res = herdr("worktree", "list", "--cwd", repo)
    listed = [w for w in (res.get("worktrees", []) if ok else []) if w.get("branch") == a.branch]
    remote_exists = sh(["git", "-C", repo, "rev-parse", "--verify", "--quiet",
                        f"refs/remotes/origin/{a.branch}"])[0] == 0
    if exists or listed or remote_exists:
        fail("branch_exists", "Stop and report; do not overwrite. An existing worktree for this task is reused, "
             "not recreated.", branch=a.branch, worktree=listed[0] if listed else None)
    label = a.label if a.label.startswith(f"{a.project} · ") else f"{a.project} · {a.label}"
    ok, res = herdr("worktree", "create", "--cwd", repo, "--branch", a.branch, "--base", base,
                    "--label", label, "--no-focus")
    if not ok:
        fail("create_failed", json.dumps(res))
    root_pane = (find_key(res, "root_pane") or {}).get("pane_id")
    ws = find_key(res, "workspace_id") or find_key(res, "open_workspace_id")
    path = find_key(res, "checkout_path") or find_key(res, "path")
    base_out = {"repo": repo, "branch": a.branch, "base": base, "label": label, "workspace_id": ws,
                "root_pane": root_pane, "checkout": path, "warning": warn}
    if not a.coordinator:
        out({"ok": True, **base_out, "next": "Report path, branch, label and the setup the new checkout needs. "
             "Work to do there: `crew.py helper-start --pane " + str(root_pane) + "`."})
    name = "coord-" + slug(a.coordinator)
    session_id = str(uuid.uuid4())
    model, routing_file = routing_model("coordinator")
    herdr("pane", "rename", root_pane, f"{a.project} · coordinator")
    args = ["--session-id", session_id] + (["--model", model] if model else [])
    ok, res = herdr("agent", "start", name, "--kind", "claude", "--pane", root_pane, "--", *args)
    co = {**base_out, "coordinator": name, "session_id": session_id, "model": model or "default",
          "routing_file": routing_file}
    if not ok:
        if isinstance(res, dict) and res.get("code") == "agent_not_ready":
            out({"ok": False, "error": "blocked_at_startup", **co, "screen": read_screen(name),
                 "hint": "A dialog is open before the first prompt. Only the user answers it: tell them which "
                         f"pane waits and why. Then `herdr agent wait {name} --until idle --timeout 900000` in the "
                         f"background, and once it fires `herdr agent prompt {name} \"$(cat <handoff file>)\"`."}, 1)
        fail("agent_start_failed", json.dumps(res), **co)
    sent = False
    if a.handoff_file:
        ok, res = herdr("agent", "prompt", name, Path(a.handoff_file).read_text())
        if not ok:
            fail("handoff_failed", json.dumps(res) + " Do not resend blindly: `herdr agent get` first.", **co)
        sent = True
    out({"ok": True, **co, "handoff_sent": sent,
         "next": f"Report workspace, branch, checkout, setup and session id; `herdr workspace focus {ws}`; then stop."})


def cmd_routing(a):
    model, f = routing_model(slug(a.role))
    out({"ok": True, "role": a.role, "model": model, "routing_file": f,
         "flag": ["--model", model] if model else []})


def cmd_state_dir(a):
    out({"ok": True, "state_dir": str(state_dir(a.project))})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("helper-start")
    s.add_argument("--project", required=True)
    s.add_argument("--role", help="required unless --resume")
    s.add_argument("--task", help="required unless --resume")
    s.add_argument("--pane")
    s.add_argument("--resume")
    s.add_argument("--kind", default="claude", choices=["claude", "codex"])
    s.add_argument("--return", dest="return_mode", default="prompt", choices=["prompt", "file"],
                   help="file: the helper only writes the report file (no coordinator agent to prompt)")
    s.set_defaults(fn=cmd_helper_start)
    for name, fn in (("send", cmd_send), ("end", cmd_end)):
        s = sub.add_parser(name)
        s.add_argument("--project", required=True)
        s.add_argument("--name", required=True)
        if name == "send":
            s.add_argument("--message", help="follow-up text; sent with the contract's RETURN block")
        s.set_defaults(fn=fn)
    sub.add_parser("map").set_defaults(fn=cmd_map)
    s = sub.add_parser("worktree-remove")
    s.add_argument("--path", required=True)
    s.add_argument("--execute", action="store_true")
    s.set_defaults(fn=cmd_worktree_remove)
    s = sub.add_parser("worktree-create")
    s.add_argument("--project", required=True)
    s.add_argument("--branch", required=True)
    s.add_argument("--label", required=True)
    s.add_argument("--repo")
    s.add_argument("--coordinator", help="issue id or short name; starts coord-<id> in the root pane")
    s.add_argument("--handoff-file")
    s.set_defaults(fn=cmd_worktree_create)
    s = sub.add_parser("routing")
    s.add_argument("--role", required=True)
    s.set_defaults(fn=cmd_routing)
    s = sub.add_parser("state-dir")
    s.add_argument("--project", required=True)
    s.set_defaults(fn=cmd_state_dir)
    a = ap.parse_args()
    try:
        a.fn(a)
    except Exception as e:  # never a traceback: the caller reads JSON
        fail("internal_error", repr(e), where=type(e).__name__)


if __name__ == "__main__":
    main()
