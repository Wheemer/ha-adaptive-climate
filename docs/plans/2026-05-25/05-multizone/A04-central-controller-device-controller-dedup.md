# Arch 04: Collapse heater/cooler duplication via `_DeviceController`

**File:** `central_controller.py`

**Problem:** 5 pairs of near-identical functions; ~40% reduction possible; copy-paste drift exists.

**Fix:**
1. Define `_DeviceController(name: str, switches: list[str], ...)` helper class.
2. Encapsulate startup task, turnoff task, lock, demand state per device.
3. `CentralController` composes two instances (heater, cooler).
4. Eliminate `_update_heater`/`_update_cooler` duplication.

**Test:** Full test suite passes. Add tests for both devices via parameterization.

**Risk:** High — major refactor of concurrency-sensitive code.

**Depends on:** C07, H08, H14.

**Blocks:** none.
