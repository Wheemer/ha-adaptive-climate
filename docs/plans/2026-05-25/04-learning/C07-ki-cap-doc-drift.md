# Critical 07: `MAX_UNDERSHOOT_KI_MULTIPLIER = 3.0` vs CLAUDE.md "2.0x cap"

**File:** `adaptive/undershoot_detector.py:269, 274-276` + `const.py:943` + `CLAUDE.md`

**Problem:** Code allows 3.0x cumulative Ki; docs promise 2.0x. floor_hydronic init Ki already aggressive → 3.0x risks severe overshoot.

**Fix:**
1. Decide: lower `MAX_UNDERSHOOT_KI_MULTIPLIER` to 2.0 (matches docs and safer).
2. Update tests asserting 3.0 to 2.0.
3. Confirm CLAUDE.md "Undershoot Detection" section reads 2.0x (already correct per quote).

**Test:** Unit: apply boosts until cap → caps at 2.0x. Integration: floor_hydronic stress test no runaway overshoot.

**Risk:** Low — tightening safety bound.

**Depends on:** none.

**Blocks:** C08 (defensive clamp uses same cap).

**Unresolved:** Confirm with hvac-expert that 2.0x is sufficient for chronic-undershoot recovery on floor_hydronic.
