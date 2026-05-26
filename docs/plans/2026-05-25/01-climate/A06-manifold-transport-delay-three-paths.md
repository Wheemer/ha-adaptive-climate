# Architectural 06: manifold transport delay wired through 3 separate paths

**File:** `climate.py:1859,1862`, `climate_control.py:344`

**Problem:** Three call sites push delta with separate unit assumptions and coordinator lookups (PID controller, cycle tracker, heater controller).

**Fix:**
1. Coordinator pushes delta to single subscriber via existing CycleEventDispatcher event (e.g. `TransportDelayChangedEvent`).
2. Each consumer subscribes; no polling.
3. Define unit explicitly in event payload (`seconds: int`).

**Test:** Unit: manifold update emits 1 event → all 3 consumers updated atomically.

**Risk:** Med.

**Depends on:** C02, C03, H07.

**Blocks:** none.

**Cross-ref:** 05-multizone (CycleEventDispatcher / coordinator).
