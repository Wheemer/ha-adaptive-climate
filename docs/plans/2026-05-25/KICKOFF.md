# Wave 0 Kickoff — 2026-05-25

You've been asked to execute fixes from a full-codebase review. Everything you need is in `docs/plans/2026-05-25/` and `docs/reviews/full-review-2026-05-25/`.

## Read these first (in order)

1. **`00-decisions.md`** — 16 binding architectural/domain decisions (D1-D16). Treat as gospel unless the user explicitly overrules.
2. **`00-execution-graph.md`** — Wave structure, batches, parallel slots. You're working in **Wave 0** unless told otherwise.
3. **`/CLAUDE.md`** — Project conventions. **Critical rules:**
   - Time: `time.monotonic()` for elapsed; `dt_util.utcnow()` for wall-clock; **never** `time()` or `datetime.now()`.
   - No `assert` in production code — raise `ValueError`/`TypeError`.
   - `X | None`, not `Optional[X]`.
   - `@callback` only on synchronous functions.
   - Use `self._coordinator` cached property; never inline `hass.data.get(DOMAIN, {}).get("coordinator")`.
   - Max file length 800 lines (per D6: hard limit 1100, exceptions for the three giant files being split in Wave 3).
   - Engineers must NOT run tests directly — delegate to `test-runner` subagent via Task tool.
   - Engineers must NOT edit more than 5 files per task; split if needed.
   - Always invoke `committing` skill before any `git commit`.

## What is "Wave 0"?

Six parallel themes that can ship independently. Pick a theme, claim it, work through its batch.

| Slot | Theme | Owner role | Plan IDs (sample) |
|------|-------|-----------|-------------------|
| 1 | Time handling sweep | software-engineer | `02-pid/C01`, `05-multizone/C06`, `04-learning/C09,C10,A08,M10`, `02-pid/M25` |
| 2 | Input validation | software-engineer | `02-pid/H08,H09,H10,M22,A08`, `06-sensors/H14`, `05-multizone/H13` |
| 3 | Quick critical fixes | software-engineer | `05-multizone/C01,M09,C02`, `04-learning/C02,C04,C06`, `06-sensors/H11,H12`, `01-climate/C05` |
| 4 | Low cleanup sweep | software-engineer | All Low items with `Depends on: none` across all 6 subsystems |
| 5 | Cycle metrics correctness | hvac-expert | `03-heater/C04,C05,C02,M02,M03,H07,H08,H09` |
| 6 | Services & sensors batch | software-engineer | `06-sensors/C01,C02,H04,H07,H05,C06,M04,C07,H10,M05` |

Full details in `00-execution-graph.md`.

## Per-issue plan format

Each `<sev><num>-<slug>.md` file under a subsystem folder has:

- **File:** specific `path/to/file.py:LINE`
- **Problem:** 1-2 sentence statement
- **Fix:** numbered steps
- **Test:** what to verify (unit / integration / manual)
- **Risk:** Low/Med/High + reason
- **Depends on / Blocks:** within-subsystem and cross-subsystem
- **Unresolved:** any open implementation questions (most resolved by decisions doc)

Always check the plan's `Depends on` before starting — confirm prerequisites are merged.

## Workflow per slot

1. Pick a slot (or the user assigns one).
2. Read `<subsystem>/_index.md` to see batch ordering.
3. Read the per-issue plan files for your batch.
4. For each plan:
   a. Check `Depends on` is satisfied.
   b. Implement the fix (delegate to typescript-engineer/software-engineer/lua-engineer per CLAUDE.md routing).
   c. Add/update tests if the plan calls for it.
   d. Run tests via `test-runner` subagent.
   e. Verify per the plan's `Test:` line.
5. When the batch is complete:
   a. Use `code-review` agent if changes are major.
   b. Invoke `committing` skill, commit with Angular convention.
   c. Move to next batch or end.

## Don'ts

- **Don't run tests yourself** — always delegate to `test-runner`.
- **Don't edit more than 5 files in one task** — split into multiple tasks.
- **Don't skip plans because they "look small"** — many Low items are part of batches.
- **Don't make architectural decisions** — they're in `00-decisions.md`. If something seems wrong, ask the user; don't decide unilaterally.
- **Don't reopen decisions D1-D16** without user confirmation.
- **Don't touch Wave 2+ work** unless the user explicitly assigns it.

## When to stop and ask

- A plan's `Unresolved:` section blocks the fix.
- You discover a new issue the review missed.
- A dependency you need is in a different subsystem and hasn't been merged.
- The decisions doc seems to contradict what the plan says.

## Status reporting

Use `TaskCreate` / `TaskUpdate` / `TaskList` to track work. One task per plan ID. Mark `in_progress` when starting, `completed` only when fully done (tests passing, committed).

## Reference docs (read if you get stuck)

- `docs/reviews/full-review-2026-05-25/00-summary.md` — cross-cutting themes
- `docs/reviews/full-review-2026-05-25/0[1-6]-*.md` — full review per subsystem
- `docs/architecture/` — existing architecture docs
- `CLAUDE.md` — conventions (re-read if you forget)

Good luck.
