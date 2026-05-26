# High 07: Cold-soak margin formula ambiguous parens

**File:** `adaptive/preheat.py:236-238`

**Problem:** `(1.0 + delta / 10.0 * 0.3) * cold_soak_margin` = `(1 + delta * 0.03)` by precedence; reader may expect `(1 + delta * 0.3 / 10)`. Same value today; future tweak to "30%" surprises.

**Fix:**
1. Precompute slope as module constant: `COLD_SOAK_DELTA_SLOPE = 0.03  # 30%/10°C`.
2. Rewrite: `margin = (1.0 + delta * COLD_SOAK_DELTA_SLOPE) * cold_soak_margin`.

**Test:** None functional; visual diff + existing tests.

**Risk:** Low — zero behavior change.

**Depends on:** none.

**Blocks:** none.
