# High 11: Solar gain seasons hardcoded for Northern Hemisphere

**File:** `solar/solar_gain.py:109-147`

**Problem:** `_get_season` uses calendar dates. Southern Hemisphere users (AU/BR/NZ/ZA) get inverted seasons — summer labeled WINTER, `seasonal_intensity` table destroys learning.

**Fix:**
1. Add `hemisphere: north|south|auto` config (auto via HA latitude).
2. Flip month→season mapping for south.
3. Better long-term: derive season from solar elevation via `astral`/`sun.sun` integration.

**Test:** Unit: latitude=-33 (Sydney), date=Dec 21; assert SUMMER.

**Risk:** Med.

**Depends on:** none.

**Blocks:** H12 (cloud adjustment uses season).
