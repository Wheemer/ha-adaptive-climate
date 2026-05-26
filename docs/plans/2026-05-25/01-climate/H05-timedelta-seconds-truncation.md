# High 05: `timedelta.seconds` truncates ≥1 day; AttributeError on programmatic init

**File:** `custom_components/adaptive_climate/climate.py:102,103,405`

**Problem:** `kwargs.get("sampling_period").seconds` AttributeErrors when called programmatically (tests, no schema defaults). `.seconds` truncates anything ≥1 day — `sensor_stall: "30:00:00"` silently becomes 6h.

**Fix:**
1. Replace all `.seconds` with `.total_seconds()` (returns float).
2. Add fallback: `(kwargs.get("sampling_period") or DEFAULT_SAMPLING_PERIOD).total_seconds()`.
3. Cast to int where int needed.
4. Audit codebase for other `.seconds` misuse.

**Test:** Unit: 30h timedelta → 108000 (not 21600). Programmatic AdaptiveThermostat(**{}) no AttributeError.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
