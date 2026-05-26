# Architectural 05: Services returning dicts need supports_response

**File:** `services/__init__.py` (registration of run_learning, pid_recommendations)

**Problem:** `async_handle_run_learning` / `async_handle_pid_recommendations` return rich dicts. Without `supports_response=SupportsResponse.OPTIONAL`, `return_response=True` callers get nothing.

**Fix:**
1. Pass `supports_response=SupportsResponse.OPTIONAL` to `async_register`.
2. Update `services.yaml` with response schema.
3. Or: stop returning data and document side-effect-only.

**Test:** Integration: call service with `return_response=True`; assert dict received.

**Risk:** Low.

**Depends on:** H05 (registration decisions).

**Blocks:** none.
