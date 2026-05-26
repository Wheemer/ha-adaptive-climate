# Critical 05: heater_active_periods fabricated from median timestamp

**File:** `managers/cycle_metrics.py:433-441`

**Problem:** `heating_end = temperature_history[len//2][0]` uses median sample as fake heater-end. Real `_device_on_time` and `_device_off_time` already tracked from HEATING_STARTED/HEATING_ENDED events. Heuristic mislabels heating periods → pollutes disturbance detector.

**Fix:**
1. Replace fabrication with:
   ```
   heater_active_periods = []
   if self._device_on_time is not None:
       end = self._device_off_time or temperature_history[-1][0]
       heater_active_periods.append((self._device_on_time, end))
   ```
2. Remove the median-timestamp logic.

**Test:** Unit test record cycle with known on/off events — assert returned periods match exact event timestamps.

**Risk:** Low — uses existing tracked fields.

**Depends on:** none.

**Blocks:** none.
