# Architectural 06: Consolidate cumulative caps into `LearningHealthMonitor`

**File:** new module + undershoot_detector, validation, contribution_tracker

**Problem:** Three separate caps; user sees no aggregate "is learning too aggressive?" signal.

**Fix:**
1. Create `LearningHealthMonitor` aggregating: undershoot Ki multiplier, validation drift, maintenance contribution.
2. Produce single 0-100 health score + status.
3. Expose via `learning.health` attribute.
4. Threshold alerts when score drops.

**Test:** Unit: synthetic high-multiplier + drift → low score.

**Risk:** Med — new module, integration scope.

**Depends on:** A01.

**Blocks:** none.

**Unresolved:** UI surface for health score?
