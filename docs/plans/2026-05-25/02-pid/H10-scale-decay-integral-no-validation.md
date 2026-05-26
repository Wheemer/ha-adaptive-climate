# High 10: `scale_integral`/`decay_integral` lack validation, no re-clamp

**File:** `pid_controller/__init__.py:318-333`

**Problem:** `decay_integral(factor)` accepts negative (flips sign) / >1 (amplifies). `scale_integral` no validation; caller `climate.py:1550` can pass `old_ki/new_ki` with new_ki=0. No clamp after mutation (same root as C03).

**Fix:**
1. `decay_integral`: clamp `factor = max(0.0, min(1.0, factor))`, raise on NaN.
2. `scale_integral`: require `factor > 0` and finite, raise `ValueError`.
3. After mutation, call shared `clamp_integral()` (from C03).
4. Guard `climate.py:1550` caller: `if new_ki > 0`.

**Test:** Unit: decay_integral(-0.5) raises or clamps to 0; scale_integral(0) raises.

**Risk:** Low.

**Depends on:** C03.

**Blocks:** none.
