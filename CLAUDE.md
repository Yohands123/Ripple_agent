@AGENTS.md

# Claude Code: your role

You build the interface in `web/`. You do not touch `pipeline/`, `ml/`, or `data/`.

- Load data only from `web/public/data/`. Until the pipeline delivers real
  files, copy `contracts/fixtures/` there.
- Match the concept art exactly. `docs/design-spec.md` gives every value;
  `design/reference/*.html` shows the target. When the spec and the reference
  disagree, the spec wins; note the difference in `docs/tasks.md`.
- After each visual task, take a screenshot and compare it side by side with
  the matching reference file before marking the task done.
- Respect `prefers-reduced-motion`: coins and ships stop animating and sit at
  fixed positions.
