# High 12: Validation degradation triggers on noise when baseline=0

**File:** `adaptive/validation.py:107-111`

**Problem:** `baseline = self._validation_baseline_overshoot or 0.1`; falsy 0.0 → 0.1; `degradation_pct = avg_overshoot / 0.1` → any >0.03°C overshoot exceeds 0.30 threshold. Noise rolls back.

**Fix:**
1. Use absolute floor for degradation: `if baseline < 0.1: trigger only if avg_overshoot > baseline + 0.15` (absolute).
2. For non-trivial baseline: keep relative + add absolute floor: `recent > baseline + max(baseline * 0.5, 0.15)`.
3. Replace `or 0.1` with `if x is None else x` (paired with L17).

**Test:** Unit: baseline=0, recent=0.05 → no rollback; baseline=0.4, recent=0.6 → triggers; baseline=0.4, recent=0.5 → triggers (slow degrade fix).

**Risk:** Med — affects auto-rollback aggressiveness.

**Depends on:** none.

**Blocks:** M03.

**Unresolved:** Confirm absolute floor (0.15°C) acceptable across heating types.
