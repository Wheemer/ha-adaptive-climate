# Medium 22: `_is_environmentally_disrupted` swallows wrong exceptions

**File:** `managers/learning_gate.py:120-140`

**Problem:** Broad `except (TypeError, AttributeError)` misses `KeyError` from stale entity_id; setback suppression fails open.

**Fix:**
1. Narrow except per call site; or use `except Exception as e:` with WARN log + safe default.
2. Keep behavior fail-safe (treat as disrupted) when uncertain.

**Test:** Unit: stub `is_any_contact_open` raises KeyError → fn returns True + WARN logged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
