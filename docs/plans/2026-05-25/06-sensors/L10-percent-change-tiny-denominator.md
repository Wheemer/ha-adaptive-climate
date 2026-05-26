# Low 10: PID change% panics on tiny baseline

**File:** `services/__init__.py:125-127`

**Problem:** ki=0.001 → 0.002 = 100% change. Cosmetic panic.

**Fix:**
1. If baseline <0.01, label "small change" or show absolute delta.
2. Round to 0 decimals for >100% changes.

**Test:** Unit: small baseline; assert friendly label.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
