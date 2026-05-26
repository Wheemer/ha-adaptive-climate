# Medium 11: Manifold last_active parse failures silent

**File:** `adaptive/manifold_registry.py:175-180`

**Problem:** `parse_datetime` swallows ValueError/TypeError; loses last-active time silently. WARN logged but no aggregate count.

**Fix:**
1. Track count of skipped manifolds.
2. Log summary INFO at end of restore: "Dropped N manifold last-active timestamps due to parse failure".
3. Expose in diagnostics dict if available.

**Test:** Unit: 2 of 5 corrupt → summary log shows count 2.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
