# Low 05: _coordinator lookup not cached on first hit

**File:** `sensors/energy.py:300-301`, `sensors/performance.py:71-76`

**Problem:** `hass.data.get().get()` chain every access.

**Fix:**
1. Cache `self.__coordinator` once after first successful read.
2. Invalidate on reload (already covered by entity recreation).

**Test:** Unit: assert N accesses → 1 lookup.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
