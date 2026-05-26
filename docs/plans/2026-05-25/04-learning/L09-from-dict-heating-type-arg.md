# Low 09: `from_dict` silent fallback to radiator

**File:** `adaptive/heating_rate_learner.py:495-547`

**Problem:** `data.get("heating_type", "radiator")` — silently wrong if mismatches zone config.

**Fix:**
1. Take `heating_type` as explicit arg: `from_dict(cls, data, heating_type)`.
2. Caller passes zone's current type.
3. Drop persisted heating_type from payload (or warn on mismatch).

**Test:** Unit: persisted heating_type ≠ arg → uses arg; logs WARN.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
