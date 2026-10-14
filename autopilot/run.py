#!/usr/bin/env python3
"""Ripple autopilot: runs Codex and Claude Code unattended on the task queue.

For each task it: syncs the agent's worktree with main, runs the agent
headless, commits leftovers, checks the agent stayed in its folders, runs the
checks itself, asks the OTHER agent to review the diff, and merges into main
only if everything passes. Failed tasks retry with the failure attached, then
get marked blocked so the queue keeps moving.

Usage (from the main repo root, on branch main):
    python3 autopilot/run.py              run until done, out of budget, or STOP
    python3 autopilot/run.py --dry-run    show what would run next, then exit
    python3 autopilot/run.py --retry M3   reset a blocked task, then run
    touch autopilot/STOP                  stop after the current runs finish
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AP = ROOT / "autopilot"
LOGS = AP / "logs"
REVIEWS = AP / "reviews"
STATE_FILE = AP / "state.json"
REPORT_FILE = AP / "REPORT.md"
STOP_FILE = AP / "STOP"

# ---- Settings (override with environment variables) ----
def env_int(name, default):
    return int(os.environ.get(name, default))

MAX_HOURS = env_int("AUTOPILOT_MAX_HOURS", 72)          # stop starting new runs after this
MAX_RUNS = env_int("AUTOPILOT_MAX_RUNS", 60)            # total agent runs, reviews included
RETRIES = env_int("AUTOPILOT_RETRIES", 2)               # extra attempts per task after a failure
RUN_TIMEOUT_MIN = env_int("AUTOPILOT_RUN_TIMEOUT_MIN", 60)
CHECK_TIMEOUT_MIN = env_int("AUTOPILOT_CHECK_TIMEOUT_MIN", 30)
PHASES = os.environ.get("AUTOPILOT_PHASES", "mvp,phase2").split(",")
CROSS_REVIEW = os.environ.get("AUTOPILOT_CROSS_REVIEW", "1") == "1"
PUSH_MAIN = os.environ.get("AUTOPILOT_PUSH_MAIN", "0") == "1"   # push main after each merge
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")                   # optional phone alerts via ntfy.sh
SKIP_CHECKS = os.environ.get("AUTOPILOT_SKIP_CHECKS_FOR_TESTING", "0") == "1"
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
CLAUDE_MAX_TURNS = os.environ.get("CLAUDE_MAX_TURNS", "80")

WORKTREE = {"codex": ROOT.parent / "ripple-ml", "claude": ROOT.parent / "ripple-web"}
BRANCH = {"codex": "ml", "claude": "web"}
OTHER = {"codex": "claude", "claude": "codex"}
CHECK_SCRIPT = {"codex": "autopilot/checks/ml.sh", "claude": "autopilot/checks/web.sh"}

# Folders each agent may change. Anything else in its diff fails the task.
ALLOWED = {
    "codex": ["pipeline/", "ml/", "data/", "tests/", "requirements.txt", "web/public/data/real/"],
    "claude": ["web/"],
}
FORBIDDEN = {"codex": [], "claude": ["web/public/data/real/"]}

CLAUDE_TOOLS_WORK = ",".join([
    "Read", "Edit", "Write", "Glob", "Grep",
    "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(ls:*)", "Bash(cat:*)",
    "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)", "Bash(git status:*)", "Bash(git diff:*)",
    "Bash(git log:*)", "Bash(git add:*)", "Bash(git commit:*)",
])
CLAUDE_TOOLS_REVIEW = "Read,Glob,Grep,Bash(git diff:*),Bash(git log:*),Bash(git status:*)"

lock = threading.Lock()        # guards state, report, and merges into main
runs_used = 0
deadline = datetime.now() + timedelta(hours=MAX_HOURS)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def sh(cmd, cwd, timeout_min=None, stdin=None):
    """Run a command; return (exit code, combined output)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout_min * 60 if timeout_min else None,
                           stdin=stdin if stdin is not None else subprocess.DEVNULL,
                           shell=isinstance(cmd, str))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return 124, out + f"\n[timed out after {timeout_min} min]"


def notify(msg):
    print(f"[{now()}] {msg}", flush=True)
    if NTFY_TOPIC:
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode(), method="POST"), timeout=10)
        except Exception:
            pass


# ---- State ----
def load_tasks():
    return json.loads((AP / "tasks.json").read_text())["tasks"]


def load_state(tasks):
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    for t in tasks:
        state.setdefault(t["id"], {"status": "human" if t["owner"] == "human" else "pending",
                                   "attempts": 0, "note": "", "updated": ""})
        if state[t["id"]]["status"] in ("running", "review"):
            state[t["id"]].update(status="pending", note="interrupted; will rerun")
    return state


def save(state, tasks):
    STATE_FILE.write_text(json.dumps(state, indent=2))
    write_report(state, tasks)


def set_status(state, tasks, tid, status, note=""):
    with lock:
        state[tid].update(status=status, note=note[:300], updated=now())
        save(state, tasks)


def write_report(state, tasks):
    order = {"blocked": 0, "running": 1, "review": 1, "pending": 2, "merged": 3, "human": 4}
    rows = sorted(tasks, key=lambda t: (order.get(state[t["id"]]["status"], 9), t["id"]))
    lines = [f"# Autopilot report", "", f"Updated {now()}. Runs used: {runs_used} of {MAX_RUNS}. "
             f"Stops starting new work at {deadline:%Y-%m-%d %H:%M}.", "",
             "| Task | Owner | Status | Attempts | Note |", "|---|---|---|---|---|"]
    by_id = {t["id"]: t for t in tasks}

    def stuck_on(tid, seen=None):
        seen = seen or set()
        for d in by_id[tid]["depends"]:
            if d in seen:
                continue
            seen.add(d)
            if state[d]["status"] in ("blocked", "human"):
                return d
            found = stuck_on(d, seen)
            if found:
                return found
        return None

    for t in rows:
        s = state[t["id"]]
        note = s["note"].replace("|", "/").replace("\n", " ")
        if s["status"] == "pending" and not note:
            d = stuck_on(t["id"])
            if d:
                note = f"waiting on {d} ({state[d]['status']})"
        lines.append(f"| {t['id']} {t['title']} | {t['owner']} | {s['status']} | {s['attempts']} | {note} |")
    lines += ["", "Logs are in autopilot/logs/, reviews in autopilot/reviews/.",
              "Blocked work is saved on branches named parked/<task>-<reason>.",
              "To retry a blocked task after fixing the cause: `python3 autopilot/run.py --retry <ID>`."]
    REPORT_FILE.write_text("\n".join(lines) + "\n")


# ---- Agent runs ----
def take_run():
    global runs_used
    with lock:
        if runs_used >= MAX_RUNS:
            return False
        runs_used += 1
        return True


def build_prompt(task, feedback):
    extra = ""
    if feedback:
        extra = ("\n\nYOUR PREVIOUS ATTEMPT FAILED. Fix this before anything else:\n"
                 + feedback[-6000:])
    return f"""You are running UNATTENDED as part of Ripple's autopilot. No human will answer questions.
Follow AGENTS.md{' and CLAUDE.md' if task['owner'] == 'claude' else ''} exactly.

Task {task['id']}: {task['title']}
Details: {task['details']}
Done when: {task['done_when']}

Rules for this run:
- Work on this task only. Stay inside your own folders (see AGENTS.md).
- Commit your work with messages starting with "{task['id']}:".
- Run your checks before finishing: bash {CHECK_SCRIPT[task['owner']]}
- Never merge, push, rebase, reset, or switch branches. Never edit contracts/, docs/, design/, or autopilot/.
- If something needs a human decision or a contract change, do not guess: describe it in your final message.
- End your final message with exactly one line:
  RESULT: DONE
  or
  RESULT: BLOCKED: <one-line reason>{extra}
"""


def run_agent(agent, prompt, tag, read_only=False, cwd=None):
    """Run one headless agent session. Returns (exit, final text)."""
    wt = cwd or WORKTREE[agent]
    log = LOGS / f"{tag}.log"
    if agent == "claude":
        cmd = [CLAUDE_BIN, "-p", prompt, "--max-turns", CLAUDE_MAX_TURNS,
               "--allowedTools", CLAUDE_TOOLS_REVIEW if read_only else CLAUDE_TOOLS_WORK]
        if not read_only:
            cmd += ["--permission-mode", "acceptEdits"]
        code, out = sh(cmd, wt, RUN_TIMEOUT_MIN)
        final = out
    else:
        last = LOGS / f"{tag}.last.txt"
        cmd = [CODEX_BIN, "exec", "-C", str(wt), "-o", str(last)]
        if read_only:
            cmd += ["-s", "read-only"]
        else:
            cmd += ["--full-auto", "-c", "sandbox_workspace_write.network_access=true",
                    "--add-dir", str(ROOT / ".git")]
        cmd.append(prompt)
        code, out = sh(cmd, wt, RUN_TIMEOUT_MIN)
        final = last.read_text() if last.exists() else out
    log.write_text(f"$ {' '.join(cmd[:3])} ...\n\n{out}\n\n--- final message ---\n{final}")
    return code, final


def parse_result(text):
    m = None
    for m in re.finditer(r"RESULT:\s*(DONE|BLOCKED)(?::\s*(.*))?", text):
        pass
    if not m:
        return "MISSING", "agent did not end with a RESULT line"
    return m.group(1), (m.group(2) or "").strip()


# ---- Git and checks ----
def sync_with_main(agent):
    wt = WORKTREE[agent]
    code, out = sh(["git", "merge", "main", "--no-edit"], wt)
    if code != 0:
        sh(["git", "merge", "--abort"], wt)
        return False, "could not merge main into the worktree:\n" + out[-2000:]
    return True, ""


def commit_leftovers(agent, tid):
    wt = WORKTREE[agent]
    sh(["git", "add", "-A"], wt)
    code, _ = sh(["git", "diff", "--cached", "--quiet"], wt)
    if code != 0:
        sh(["git", "commit", "-m", f"{tid}: autopilot commit of uncommitted work"], wt)


def changed_files(agent):
    _, out = sh(["git", "diff", "--name-only", "main...HEAD"], WORKTREE[agent])
    return [f for f in out.splitlines() if f.strip()]


def ownership_problems(agent, files):
    bad = []
    for f in files:
        ok = any(f == a or f.startswith(a) for a in ALLOWED[agent])
        if not ok or any(f.startswith(x) for x in FORBIDDEN[agent]):
            bad.append(f)
    return bad


def park(agent, tid, label):
    """Save the branch's current work as parked/<tid>-<label>, then reset the branch to main."""
    wt = WORKTREE[agent]
    sh(["git", "branch", "-f", f"parked/{tid}-{label}", "HEAD"], wt)
    sh(["git", "reset", "--hard", "main"], wt)


def run_checks(agent):
    if SKIP_CHECKS:
        return True, "checks skipped (testing mode)"
    code, out = sh(["bash", CHECK_SCRIPT[agent]], WORKTREE[agent], CHECK_TIMEOUT_MIN)
    return code == 0, out[-6000:]


def cross_review(agent, task, attempt):
    reviewer = OTHER[agent]
    if not CROSS_REVIEW:
        return True, "review turned off"
    if not take_run():
        return None, "run budget used up before review"
    spec = ", docs/design-spec.md" if agent == "claude" else ""
    prompt = f"""You are reviewing another agent's work, unattended. Do NOT modify any files.
The working directory is the branch for task {task['id']}: {task['title']}.
Done when: {task['done_when']}
Run `git diff main...HEAD` to see the changes. Judge them against AGENTS.md, docs/contracts.md{spec}.
Report only problems that matter: bugs, contract violations, invented or unsourced data,
rule breaks, or an unmet "done when". Ignore style preferences.
End with exactly one line: VERDICT: APPROVE  or  VERDICT: CHANGES"""
    # The reviewer reads the author's worktree, read-only.
    _, text = run_agent(reviewer, prompt, f"{task['id']}-a{attempt}-review-by-{reviewer}",
                        read_only=True, cwd=WORKTREE[agent])
    (REVIEWS / f"{task['id']}-a{attempt}.md").write_text(text)
    verdicts = re.findall(r"VERDICT:\s*(APPROVE|CHANGES)", text)
    if verdicts and verdicts[-1] == "CHANGES":
        return False, "The other agent's review asked for changes:\n" + text[-5000:]
    return True, "approved" if verdicts else "reviewer gave no verdict; treated as approved"


def merge_to_main(agent, tid):
    with lock:
        code, out = sh(["git", "merge", "--no-ff", BRANCH[agent], "-m", f"autopilot: merge {tid}"], ROOT)
        if code != 0:
            sh(["git", "merge", "--abort"], ROOT)
            return False, "merge into main failed:\n" + out[-2000:]
        if PUSH_MAIN:
            sh(["git", "push", "origin", "main"], ROOT)
        return True, ""


# ---- Scheduling ----
def next_task(agent, tasks, state):
    with lock:
        for t in tasks:
            s = state[t["id"]]
            if t["owner"] != agent or s["status"] != "pending" or t.get("phase") not in PHASES:
                continue
            deps = [state[d]["status"] for d in t["depends"]]
            if all(d in ("merged", "human_done") for d in deps):
                return t
    return None


def can_progress(tid, by_id, state, seen=None):
    """A task can still finish if nothing it depends on (directly or not) is stuck."""
    seen = seen or set()
    if tid in seen:
        return False
    seen.add(tid)
    st = state[tid]["status"]
    if st in ("merged", "human_done"):
        return True
    if st in ("blocked", "human") or by_id[tid].get("phase") not in PHASES + ["setup"]:
        return False
    return all(can_progress(d, by_id, state, seen) for d in by_id[tid]["depends"])


def anything_left(agent, tasks, state):
    """True if this agent still has pending tasks that could become ready later."""
    by_id = {t["id"]: t for t in tasks}
    with lock:
        return any(t["owner"] == agent and state[t["id"]]["status"] == "pending"
                   and can_progress(t["id"], by_id, state) for t in tasks)


def should_stop():
    return STOP_FILE.exists() or datetime.now() > deadline or runs_used >= MAX_RUNS


def do_task(agent, task, tasks, state):
    tid = task["id"]
    feedback = ""
    for attempt in range(1, RETRIES + 2):
        if should_stop():
            set_status(state, tasks, tid, "pending", "stopped before finishing")
            return
        ok, msg = sync_with_main(agent)
        if not ok:
            set_status(state, tasks, tid, "blocked", msg)
            notify(f"Ripple {tid} blocked: merge conflict with main")
            return
        if not take_run():
            set_status(state, tasks, tid, "pending", "run budget used up")
            return
        with lock:
            state[tid]["attempts"] += 1
        set_status(state, tasks, tid, "running", f"attempt {attempt}")
        _, text = run_agent(agent, build_prompt(task, feedback), f"{tid}-a{attempt}-{agent}")
        commit_leftovers(agent, tid)
        result, reason = parse_result(text)

        if result == "BLOCKED":
            park(agent, tid, "blocked")
            set_status(state, tasks, tid, "blocked", f"agent: {reason}")
            notify(f"Ripple {tid} blocked: {reason}")
            return

        files = changed_files(agent)
        if not files:
            feedback = "No changes were committed for this task."
            continue
        bad = ownership_problems(agent, files)
        if bad:
            park(agent, tid, f"a{attempt}-outside-folders")   # discard the whole attempt, keep a copy
            feedback = "You changed files outside your folders, so the attempt was discarded: " + ", ".join(bad[:20])
            continue
        ok, out = run_checks(agent)
        if not ok:
            feedback = "Checks failed:\n" + out
            continue
        set_status(state, tasks, tid, "review", f"attempt {attempt}: in review")
        ok, out = cross_review(agent, task, attempt)
        if ok is None:
            set_status(state, tasks, tid, "pending", out)
            return
        if not ok:
            feedback = out
            continue
        ok, out = merge_to_main(agent, tid)
        if not ok:
            park(agent, tid, "merge-failed")
            set_status(state, tasks, tid, "blocked", out)
            notify(f"Ripple {tid} blocked: could not merge")
            return
        set_status(state, tasks, tid, "merged", f"merged on attempt {attempt}")
        notify(f"Ripple {tid} merged ({task['title']})")
        return
    park(agent, tid, "failed")
    set_status(state, tasks, tid, "blocked", "failed after retries: " + feedback[:250])
    notify(f"Ripple {tid} blocked after {RETRIES + 1} attempts")


def worker(agent, tasks, state):
    while not should_stop():
        task = next_task(agent, tasks, state)
        if task:
            do_task(agent, task, tasks, state)
            continue
        if not anything_left(agent, tasks, state):
            return
        time.sleep(60)   # waiting on the other agent's work


def preflight_ok():
    code, branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], ROOT)
    if branch.strip() != "main":
        print("Run this from the main repo checkout on branch main.")
        return False
    code, dirty = sh(["git", "status", "--porcelain", "--untracked-files=no"], ROOT)
    if dirty.strip():
        print("The main checkout has uncommitted changes. Commit or stash them first.")
        return False
    for a, wt in WORKTREE.items():
        if not wt.exists():
            print(f"Missing worktree {wt}. Run scripts/setup-worktrees.sh first.")
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--retry", nargs="*", default=[])
    args = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    REVIEWS.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()
    state = load_state(tasks)
    for tid in args.retry:
        if tid in state:
            state[tid].update(status="pending", note="reset by --retry", attempts=0)
    # S0 (the human setup task) counts as done once both worktrees exist.
    if all(wt.exists() for wt in WORKTREE.values()):
        state["S0"].update(status="human_done", note="worktrees exist")
    save(state, tasks)
    if args.dry_run:
        for a in ("codex", "claude"):
            t = next_task(a, tasks, state)
            print(f"{a}: next task = {t['id'] + ' ' + t['title'] if t else 'none ready'}")
        print(f"Report: {REPORT_FILE}")
        return
    if not preflight_ok():
        sys.exit(1)
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    notify(f"Ripple autopilot started. Phases: {', '.join(PHASES)}. Budget: {MAX_RUNS} runs, {MAX_HOURS} h.")
    threads = [threading.Thread(target=worker, args=(a, tasks, state), daemon=True) for a in ("codex", "claude")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    merged = sum(1 for s in state.values() if s["status"] == "merged")
    blocked = [k for k, s in state.items() if s["status"] == "blocked"]
    save(state, tasks)
    notify(f"Ripple autopilot finished: {merged} merged, {len(blocked)} blocked"
           + (f" ({', '.join(blocked)})" if blocked else "") + ". See autopilot/REPORT.md.")


if __name__ == "__main__":
    main()
