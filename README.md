# Ripple: two-agent setup (Claude Code + Codex)

This kit lets Claude Code and Codex build Ripple at the same time without
stepping on each other. Drop these files into the root of your repo.

## The division in one sentence

**Codex builds the data and ML pipeline in Python. Claude Code builds the
interface in TypeScript. They meet only at the JSON files described in
`docs/contracts.md`.**

Why this split works:

- **No shared files.** Different folders, different languages, different
  toolchains. Merge conflicts become nearly impossible.
- **Nobody waits.** The interface builds against sample data in
  `contracts/fixtures/` from day one. When the pipeline produces real data in
  the same shape, you swap it in.
- **Each task suits its tool's working style.** Pipeline work is long-running
  batch jobs (downloads, parsing, training) that can run in the background.
  Interface work needs constant visual checking against the concept art. You
  can swap the roles if one tool works better for you; the boundary is what
  matters, not who sits on which side.

| Owner | Folders | Language |
|---|---|---|
| Codex | `pipeline/`, `ml/`, `data/` | Python |
| Claude Code | `web/` | TypeScript (Next.js) |
| You | `contracts/`, `docs/`, `design/`, `AGENTS.md`, `CLAUDE.md` | Markdown, JSON |

You own the contract. Agents never edit it; they request changes in
`docs/contract-requests.md` and you decide.

## Setup

1. **Install both tools.** Follow the current official instructions:
   - Claude Code: https://docs.claude.com/en/docs/claude-code/overview
   - Codex CLI: https://github.com/openai/codex
2. **Create the repo and commit this kit first**, so both agents start from
   the same contract:
   ```bash
   mkdir ripple && cd ripple && git init
   # copy this kit's files in
   git add . && git commit -m "S0: contracts, design spec, agent rules"
   ```
3. **Give each agent its own working copy** with git worktrees, so they never
   edit the same checkout:
   ```bash
   bash scripts/setup-worktrees.sh
   ```
   This creates `../ripple-ml` (branch `ml`) and `../ripple-web` (branch `web`).
4. **Start each agent in its own terminal:**
   ```bash
   cd ../ripple-ml  && codex     # then: "Read AGENTS.md and docs/tasks.md. Start task M1."
   cd ../ripple-web && claude    # then: "Read CLAUDE.md and docs/tasks.md. Start task W1."
   ```

Codex reads `AGENTS.md` automatically. Claude Code reads `CLAUDE.md`, which
imports `AGENTS.md`, so both agents follow the same rules.

## Daily loop

1. Each agent works through its own tasks in `docs/tasks.md`, committing small
   changes prefixed with the task ID (`M3: extract part types`).
2. At the end of each session, merge each branch into `main` once its checks
   pass:
   ```bash
   git checkout main
   git merge ml && git merge web
   ```
3. Cross-review: paste the other agent's diff into each tool and ask it to
   review against `AGENTS.md` and the contract. Each catches different mistakes.
4. Check `docs/contract-requests.md`. If a change is approved, edit
   `contracts/` yourself, commit to `main`, and have both agents pull.

## Following the concept art exactly

`design/reference/` holds the two concept-art scenes as HTML files. Open them
in a browser to see the target. `docs/design-spec.md` lists every exact color,
size, font, and line style taken from them. Task W8 is a screenshot comparison
against these files.
