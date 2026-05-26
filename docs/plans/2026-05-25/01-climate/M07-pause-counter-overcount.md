# Medium 07: pause counter +=N for N sensors opening together

**File:** `custom_components/adaptive_climate/climate.py:329-330,1922-1933`

**Problem:** Counter increments per sensor open transition, but pause is aggregated (any-open). N simultaneous opens = 1 pause but counter +=N.

**Fix:**
1. Rename to `contact_open_events` (truthful), OR
2. Track actual paused-state transitions (none-open → any-open and back).
3. Use `_is_any_contact_open` previous-state vs current-state diff in handler.

**Test:** Unit: 3 sensors open at once → counter +=1 (paused-transition mode).

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
