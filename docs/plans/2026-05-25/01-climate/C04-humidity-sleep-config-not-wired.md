# Critical 04: humidity_exit_threshold/drop, max_pause_duration, sleep_temp not wired

**File:** `climate_setup.py:100-103,312-316`, `climate.py:143,265-294`

**Problem:** Schema accepts `humidity_exit_threshold`, `humidity_exit_drop`, `humidity_max_pause_duration`, `sleep_temp`; `parameters` dict in `async_setup_platform` never copies them. Entity falls back to defaults silently. `sleep_temp` consumed at climate.py:143 but absent from schema/domain config.

**Fix:**
1. Add missing 3 humidity keys to `parameters` build in `climate_setup.py:237-324`.
2. Add `sleep_temp` to platform schema (mirror other preset temps).
3. Verify CLAUDE.md humidity section matches wired keys.
4. Update tests to assert overrides propagate.

**Test:** Integration: configure all 4 keys → assert HumidityDetector + entity use them, not defaults.

**Risk:** Low — additive wiring.

**Depends on:** none.

**Blocks:** A08 (typed config dataclass).
