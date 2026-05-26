# Architectural 4: `restore_from_state` HEAT-only — silent gap for cooling

**File:** `managers/pid_gains_manager.py:212-242`

**Problem:** Subsumed by C04. Architectural note: per-mode restoration must be uniformly applied across all managers (Ke, undershoot, confidence — see cross-cutting theme C).

**Fix:**
1. C04 fixes this specific bug.
2. Add restoration audit task: matrix of "what's persisted, per-mode aware?" across managers.

**Test:** Covered by C04.

**Risk:** Med (audit scope).

**Depends on:** C04.

**Blocks:** none. Coordinate with `04-learning` mode-awareness items.
