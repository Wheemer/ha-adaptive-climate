# Medium 04: Currency silently changes on cost-entity UoM flap

**File:** `sensors/energy.py:519-530`

**Problem:** UoM parsed every update. `unknown`→different UoM on HA restart triggers HA to invalidate MONETARY historical stats.

**Fix:**
1. Set currency once at init; ignore later changes unless explicit reconfig.
2. Persist chosen currency in extra_state_attributes.
3. Log if entity reports different currency.

**Test:** Unit: simulate UoM change mid-session; assert currency stable.

**Risk:** Low.

**Depends on:** C06.

**Blocks:** none.
