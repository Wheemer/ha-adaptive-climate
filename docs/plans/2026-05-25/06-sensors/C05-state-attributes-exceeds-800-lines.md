# Critical 05: state_attributes.py exceeds 800-line limit

**File:** `managers/state_attributes.py` (813 lines)

**Problem:** Violates CLAUDE.md hard limit. `_build_status_attribute` (~205 lines) has no shared state with other builders.

**Fix:**
1. Extract `_build_status_attribute` and helpers to `managers/status_attribute_builder.py`.
2. Re-export from `state_attributes.py` for back-compat if needed.
3. Verify pyright + tests pass.

**Test:** Pyright strict on both modules. Existing state-attribute tests unchanged.

**Risk:** Med. Large refactor; import cycles possible.

**Depends on:** C03, C04 (avoid rework).

**Blocks:** A02 (god-module split).
