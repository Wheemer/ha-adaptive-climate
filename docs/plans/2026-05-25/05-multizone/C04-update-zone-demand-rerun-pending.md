# Critical 04: `update_zone_demand` drops state changes during task body

**File:** `coordinator.py:347-375`

**Problem:** `_update_pending` single-flight guard captures changes before task starts, but state changes occurring **during** task body after `get_aggregate_demand()` are silently dropped. Symptom: rapid zone mode flips leave central heater stuck on/off until next 30s periodic update.

**Fix:**
1. Add `_rerun_pending: bool = False`.
2. When new demand arrives while `_update_pending` True, set `_rerun_pending=True`.
3. In `_update_with_guard` `finally`: if `_rerun_pending`, clear it and schedule another `update()`.
4. Add unit test simulating rapid flips during task.

**Test:** Unit: simulate 3 demand changes during in-flight task; assert final demand state reflects last change. Integration: rapid zone mode flip → heater state correct.

**Risk:** Med — concurrency change.

**Depends on:** none.

**Blocks:** H01.
