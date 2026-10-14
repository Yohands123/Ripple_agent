# Ripple: rules for every coding agent

Ripple is an interactive model of Apple's publicly known supply chain, built
only from public data. Read `docs/tasks.md` for your tasks and
`docs/contracts.md` for the data format both sides share.

## Ownership (strict)

| Folder | Owner | Others may |
|---|---|---|
| `pipeline/`, `ml/`, `data/` | Codex | read only |
| `web/` | Claude Code | read only |
| `contracts/`, `docs/`, `design/`, `AGENTS.md`, `CLAUDE.md` | the human | read only |

- Never edit files outside your folders.
- The one exception: in `docs/tasks.md`, update the **Status** of your own
  tasks only.
- If you need the contract to change, add an entry to
  `docs/contract-requests.md` (what, why, example) and keep working on
  something else. Do not change the shape of the data on your own.

## Working style

- Do one task at a time, in the order listed, respecting **Depends on**.
- Commit small and often. Prefix each commit with the task ID: `W4: sea route ticks`.
- A task is done only when its **Done when** line is true and checks pass.
- If you are stuck or a task is ambiguous, write the question under the task
  in `docs/tasks.md` and move to the next unblocked task.

## Data rules

- Public sources only. Every node and edge carries `sources` with a title and URL.
- Links are `known` (stated in a source) or `inferred` (deduced). Never present
  an inferred link as known.
- Never invent numbers. Values that are assumptions are labeled as such in the
  data (`"assumption": true`) and shown as ranges.
- Sample data is marked `"sampleData": true`, and the interface shows a
  "Sample data" tag whenever it is present.
- Each historical event uses the Apple Supplier List from its own year (no
  future data in a backtest).

## Framing

Ripple is a resilience case study from public data. It does not describe
Apple's internal operations or recommend what Apple should do. No Apple logo,
no photos of real people, and no characters or artwork from other companies
(for example, no game coins or pipes from existing games). All icons are original.

## Checks before merging

- Codex: `python -m pytest` passes and `python pipeline/validate.py` confirms
  every exported file matches `contracts/`.
- Claude Code: `npm run lint`, `npm run typecheck`, and `npm run build` pass
  in `web/`.
