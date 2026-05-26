# Architectural 02: HeaterController takes concrete AdaptiveThermostat, violates ThermostatState Protocol

**File:** `managers/heater_controller.py:285, 292, 899`

**Problem:** `getattr(self._thermostat, "_current_temp", 0.0)` — silent default, raw private access. CLAUDE.md mandates Protocol.

**Fix:**
1. Define narrow `TemperatureState` Protocol (or reuse existing).
2. Pass Protocol instance to HeaterController constructor.
3. Replace `getattr` with typed property reads.
4. Make missing temp `float | None` (no silent zero).

**Test:** Type check passes; unit tests confirm None handling.

**Risk:** Med — touches constructor signature, all call sites.

**Depends on:** H01.

**Blocks:** A04 (PWMController coupling — same pattern).
