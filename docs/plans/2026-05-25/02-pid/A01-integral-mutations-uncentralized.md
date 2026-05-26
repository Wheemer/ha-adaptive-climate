# Architectural 1: Integral mutations scattered across 8 files, skip clamp

**File:** Multiple (`climate.py:1118,1221,1550`, `climate_control.py:93,167`, `pid_tuning.py:130,210,306,395`, `state_restorer.py:132`, `setpoint_boost.py:150,162`, `pid_controller/__init__.py:689`)

**Problem:** PIDGainsManager centralized gain mutations; integral has same need but is mutated freely; most sites skip clamp.

**Fix:**
1. Extend `PIDGainsManager` to own `IntegralManager` responsibilities, or create separate `IntegralManager`.
2. Provide `set_integral(value, reason)`, `add_integral(delta, reason)`, `scale_integral(factor, reason)`, `decay_integral(factor, reason)` — all clamp + record reason.
3. Migrate all 8 call sites.
4. Optional: integral history (mirrors gain history).

**Test:** Audit: no direct `self._pid.integral =` outside manager. Pyright forbids via private attr.

**Risk:** High. Multi-file refactor; coordinate with C03, C05, H10.

**Depends on:** C03 (shared clamp method).

**Blocks:** none.

**Unresolved:** Separate manager or extend gains manager? History storage cost vs debugging value?
