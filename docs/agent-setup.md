# Ripple: two-agent setup with autopilot

Codex builds the data and ML pipeline in Python. Claude Code builds the
interface in TypeScript. They meet only at the JSON files in
`docs/contracts.md`. The autopilot runs both unattended while you're away.

| Owner | Folders |
|---|---|
| Codex | `pipeline/`, `ml/`, `data/`, `tests/`, `requirements.txt`, and `web/public/data/real/` via the export script |
| Claude Code | `web/` (except `web/public/data/real/`) |
| You | `contracts/`, `docs/`, `design/`, `autopilot/`, `AGENTS.md`, `CLAUDE.md`, `.gitignore` |

Different folders and languages mean the agents never edit the same files.
The interface builds on sample data in `contracts/fixtures/` from day one and
switches to real data automatically when `web/public/data/real/` appears.

## How the autopilot works

`autopilot/run.py` runs one worker per agent, in parallel. For each task, in
dependency order, it:

1. **Syncs** the agent's worktree with the latest `main`.
2. **Runs the agent headless** on that one task (`claude -p` or `codex exec`),
   with the task's details, "done when" line, and the rules.
3. **Commits** anything the agent left uncommitted.
4. **Checks ownership.** If the agent changed files outside its folders, the
   attempt is discarded (kept on a `parked/` branch) and retried.
5. **Runs the checks itself** (`autopilot/checks/`), rather than trusting the
   agent's word: tests and contract validation for Codex; lint, typecheck,
   and build for Claude Code.
6. **Cross-review.** The other agent reads the diff, read-only, and approves
   or asks for changes.
7. **Merges** into `main` only if everything passed. The other agent picks up
   the new `main` before its next task.

A failed step sends the failure back to the agent for another attempt (2
retries by default). After that, the task is marked **blocked**, its work is
parked on `parked/<task>-failed`, and the queue moves on. Tasks that depend on
a blocked task wait; everything else continues. The autopilot stops when the
queue is done, the time or run budget is used up, or you create `autopilot/STOP`.

What it never does: edit the contract, push (unless you turn that on), merge
anything that failed a check, or do your tasks (the 30-link hand check and
final review).

## Before you leave

1. **Install and log in to both tools.** Follow the current official instructions:
   Claude Code at https://docs.claude.com/en/docs/claude-code/overview and the
   Codex CLI at https://github.com/openai/codex. Run each once interactively to log in.
2. **Create the repo with this kit and set up the worktrees:**
   ```bash
   mkdir ripple && cd ripple && git init
   # copy this kit's files in
   git add . && git commit -m "S0: contracts, design spec, agent rules, autopilot"
   bash scripts/setup-worktrees.sh
   ```
3. **Set environment variables** (add them to your shell profile so they survive a restart):
   ```bash
   export SEC_USER_AGENT="Your Name your@email.com"   # required by SEC
   export NTFY_TOPIC="ripple-<something-random>"       # optional phone alerts
   ```
   For phone alerts, install the free ntfy app and subscribe to that topic.
   Anyone who knows the topic name can read it, so make it hard to guess.
4. **Run the preflight.** Every line should say OK:
   ```bash
   bash autopilot/preflight.sh
   ```
5. **Start it so it survives closing the terminal and the computer won't sleep:**
   ```bash
   # macOS
   mkdir -p autopilot/logs
   nohup caffeinate -is python3 autopilot/run.py > autopilot/logs/run.out 2>&1 &
   # Linux
   nohup systemd-inhibit python3 autopilot/run.py > autopilot/logs/run.out 2>&1 &
   ```
   Keep the computer plugged in. On Windows, run everything inside WSL and set
   the power plan to never sleep.

## Settings

All optional, as environment variables set before starting:

| Variable | Default | Meaning |
|---|---|---|
| `AUTOPILOT_MAX_HOURS` | 72 | Stop starting new work after this many hours |
| `AUTOPILOT_MAX_RUNS` | 60 | Total agent runs, including reviews; this is your cost cap |
| `AUTOPILOT_RETRIES` | 2 | Extra attempts per task after a failure |
| `AUTOPILOT_RUN_TIMEOUT_MIN` | 60 | Longest a single agent run may take |
| `AUTOPILOT_PHASES` | `mvp,phase2` | Which phases to run |
| `AUTOPILOT_CROSS_REVIEW` | 1 | Set to 0 to skip reviews (cheaper, riskier) |
| `AUTOPILOT_PUSH_MAIN` | 0 | Set to 1 to push `main` after each merge (for auto-deploys) |
| `CLAUDE_MAX_TURNS` | 80 | Turn limit per Claude Code run |

Agent runs use your Claude and OpenAI plans or API credit. `AUTOPILOT_MAX_RUNS`
is the main cap on cost; check your usage limits before leaving.

## While you're away

- `autopilot/REPORT.md` shows every task's status, refreshed after each step.
- Phone alerts (if set) arrive on every merge, every block, and at the end.
- To stop safely: `touch autopilot/STOP`. Runs in progress finish first.

## When you're back

1. Read `autopilot/REPORT.md`.
2. For each blocked task, read its note and its last log in `autopilot/logs/`.
   Failed work is on `parked/<task>-...` branches. Fix the cause, then:
   ```bash
   python3 autopilot/run.py --retry M3
   ```
3. Look through the agents' final messages in `autopilot/logs/` for contract
   change requests and questions; decide them in `docs/contract-requests.md`.
4. Do your tasks: hand-check `data/review/hand_check.csv` (I1) and review
   `main` and the site (I2).
5. Restarting is safe: the autopilot remembers what's done and resumes.

## Safety

The agents run with permission to edit files and run commands without asking.
Claude Code's commands are limited to a list in `run.py`; Codex runs in its
workspace sandbox with network on (needed for downloads). For extra safety,
run the whole thing on a spare machine, a virtual machine, or a cloud server
instead of your main laptop, and keep no unrelated secrets in its environment.

## Following the concept art exactly

`design/reference/` holds both concept-art scenes as HTML files; open them in
a browser to see the target. `docs/design-spec.md` lists every exact value.
Claude Code screenshots its work against these files after each visual task.
