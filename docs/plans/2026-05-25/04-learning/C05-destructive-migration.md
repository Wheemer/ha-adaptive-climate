# Critical 05: Unknown `format_version` wipes all learning data

**File:** `adaptive/learner_serialization.py:216-223`

**Problem:** `format_version != 10` → returns `_default_learner_state()` silently. Wipes cycle history, confidences, undershoot multiplier, contribution caps, heating-rate obs. Comments in `learning.py:1627-1656` reference nonexistent v7→v10 migrations.

**Fix:**
1. Implement preservation path: on unknown version, keep `cycle_history` lists + `convergence_confidence` values; reset only new/unknown fields. Log WARN with old version.
2. Add per-version migrators (v5→v6→…→v10) as small functions; chain them.
3. Each migrator: minimal field-by-field shape adapter, never wipe history.
4. Add `_migrate(data) -> dict` dispatch table keyed on stored version.
5. Remove misleading "v7->v8 migration" comments in `learning.py`.

**Test:** Unit: load each historical schema (v5–v9 fixtures) → cycle_history preserved, status sensible. Round-trip current v10.

**Risk:** Med — must have fixtures for old versions; risk of subtle key-shape mismatch.

**Depends on:** C06 (consistent format_version type first).

**Blocks:** A03 (migration story).

**Unresolved:** Are v5–v9 fixtures available, or do we synthesize from git history?
