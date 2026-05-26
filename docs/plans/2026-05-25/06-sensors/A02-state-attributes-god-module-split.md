# Architectural 02: Split state_attributes.py god module

**File:** `managers/state_attributes.py` (813 lines)

**Problem:** Mixes pure builders (`build_cycle_count`, `build_learning_object`, `build_debug_object`) with impure orchestration (`_build_status_attribute`, `_add_*`).

**Fix:**
1. `state_attributes/builders.py` — pure functions.
2. `state_attributes/orchestration.py` — impure (calls into managers/thermostat).
3. `state_attributes/__init__.py` re-exports.
4. Add tests for pure builders (no mocks needed).

**Test:** Pyright + existing integration; new unit tests for builders.

**Risk:** Med. Import paths change.

**Depends on:** C05 (initial split).

**Blocks:** none.
