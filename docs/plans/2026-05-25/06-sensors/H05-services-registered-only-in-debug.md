# High 05: Run-learning/PID-rec services registered only in debug

**File:** `services/__init__.py:413-414`

**Problem:** `SERVICE_RUN_LEARNING`/`SERVICE_PID_RECOMMENDATIONS` advertised in `services.yaml` but only registered when `debug=true`. Users get "service not found".

**Fix:**
1. Decide: always-register (preferred) or debug-only.
2. If always-register: remove debug gate.
3. If debug-only: remove from `services.yaml`, mark as internal in docs.

**Test:** Integration: run-without-debug, call service; assert handled or clear error.

**Risk:** Low.

**Depends on:** none.

**Blocks:** A05 (service response support).
