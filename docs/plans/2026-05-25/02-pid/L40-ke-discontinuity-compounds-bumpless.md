# Low 40: Ke discontinuity compounds with bumpless transfer

**File:** `pid_controller/__init__.py` (interaction)

**Problem:** OFF→AUTO with negative error → `_external = 0`; integral solved against 0. When error crosses positive, external jumps; integral basis wrong.

**Fix:**
1. Subsumed by H14 (remove Ke gate) — once external is continuous, bumpless math is consistent.
2. Add cross-reference test: bumpless + Ke step boundary.

**Test:** Unit: bumpless across setpoint crossing, assert output continuity.

**Risk:** Low.

**Depends on:** H14.

**Blocks:** none.
