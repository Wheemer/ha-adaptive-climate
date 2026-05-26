# Critical 05: f-string `.4f` on default `'N/A'` raises ValueError

**File:** `custom_components/adaptive_climate/climate.py:1332-1338`

**Problem:** `f"Kp: {old_values.get('kp', 'N/A'):.4f}"` — `.4f` rejects strings. If `old_values` missing kp/ki/kd, persistent-notification call raises after gains already mutated. User sees no notification; no clean log.

**Fix:**
1. Default to `0.0` not `'N/A'` in `.get()` calls.
2. Or guard: `f"Kp: {old_values['kp']:.4f}" if old_values.get('kp') is not None else "Kp: N/A"`.
3. Wrap notification block in try/except logging at ERROR with old/new values.

**Test:** Unit: call notification builder with empty `old_values` dict → no ValueError, message contains `N/A` or `0.0000`.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
