# Low 11: Magic numbers in `_detect_wind_loss`

**File:** `adaptive/disturbance_detector.py:131-176`

**Problem:** `5.0 m/s`, `2.0°C`, `0.5°C`, `1.0°C/h` — bare.

**Fix:**
1. Extract module-level constants with provenance comments (`WIND_LOSS_SPEED_THRESHOLD_MS = 5.0  # Beaufort 3+`).
2. Group under `# Disturbance detection thresholds` block.

**Test:** None functional.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
