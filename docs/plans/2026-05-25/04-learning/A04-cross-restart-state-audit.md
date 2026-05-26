# Architectural 04: Cross-restart state matrix audit

**File:** all adaptive/managers state holders

**Problem:** Inconsistent persist/restore: cycle_count not persisted, last_adjustment_time monotonic-float written then ignored, stall_counter persisted, etc.

**Fix:**
1. Build matrix doc: per-field {what, when set, persisted?, unit, restored?, default on miss}.
2. Decide per-field policy.
3. Refactor to match.
4. Add round-trip test per state holder.

**Test:** Unit per holder: save → load → identical state.

**Risk:** Med — touches many modules.

**Depends on:** A01.

**Blocks:** none.
