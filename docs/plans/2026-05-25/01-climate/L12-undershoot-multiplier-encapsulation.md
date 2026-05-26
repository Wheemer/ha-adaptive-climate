# Low 12: orchestration layer mutates `undershoot_detector.cumulative_ki_multiplier`

**File:** `custom_components/adaptive_climate/climate.py:1567`

**Problem:** Direct mutation of manager-owned counter.

**Fix:**
1. Add `UndershootDetector.apply_ki_boost(multiplier)` method.
2. Replace direct `*= suggested_boost` with method call.

**Test:** Unit: method respects existing cap (2.0× per CLAUDE.md).

**Risk:** Low.

**Depends on:** H02.

**Blocks:** none.
