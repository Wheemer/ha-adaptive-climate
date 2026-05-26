# PID & Control Output Review

Scope: `pid_controller/__init__.py`, `managers/pid_gains_manager.py`, `managers/pid_tuning.py`, `managers/control_output.py`, `managers/setpoint_boost.py`, `managers/ke_manager.py`.

---

## Critical (must fix)

### 1. PID uses wall-clock `time()` inside `pid_controller/__init__.py`; CLAUDE.md mandates `time.monotonic()` for elapsed durations
- **pid_controller/__init__.py:5** — `from time import time` and uses it at:
  - `pid_controller/__init__.py:514` (`time() - self._last_input_time < self._sampling_period`),
  - `pid_controller/__init__.py:532` (`self._input_time = time()` as fallback when `input_time is None`),
  - `pid_controller/__init__.py:537` (sampling-period mode: `self._input_time = time()`).
- All three usages compute `dt` from these timestamps (`self._dt = self._input_time - self._last_input_time`, line 560), then convert to hours and multiply by `Ki/Kd`. A user changing the system clock, NTP step, or DST transition will inject a multi-hour `dt` straight into the integral, causing an enormous Ki windup or Kd spike. This is exactly the class of bug `time.monotonic()` exists to prevent and is called out as a project convention.
- **Fix:** use `time.monotonic()` for `_input_time` / sampling-period gate. The `MAX_REASONABLE_DT` clamp in `ControlOutputManager` covers the event-driven path (because it computes `effective_input_time = current_time` from `time.monotonic()`), but the sampling-period branch and the warning-fallback at line 532 do not.

### 2. `prepare_bumpless_transfer` is invoked on every calc that has transfer state, before `dt` and saturation checks are evaluated
- **pid_controller/__init__.py:597-598** — `if self.has_transfer_state: self.prepare_bumpless_transfer()` runs unconditionally on the first AUTO calc after OFF. Two issues:
  1. **Stale `self._error`:** `prepare_bumpless_transfer` reads `abs(self._error) > BUMPLESS_TRANSFER_THRESHOLD` (line 357), but `self._error` was already updated on line 554 of the *current* calc. So the bumpless skip-on-large-error check uses the current error — fine. However the *integral being computed* in the same calc will not include the bumpless integral because lines 605–668 then write to `self._integral` based on the just-set bumpless value. The accumulated integral term (Ki·err·dt) on the very first restart calc gets *added* to the bumpless integral, which means the transfer is not actually bumpless on dt-positive first calls. Better: compute output with the bumpless integral, skip the accumulation branch on that exact tick.
  2. **`_proportional` is zero on first calc** (line 590–593 guard `if self._last_input is not None`), so `required_integral = last_output - 0 - external + feedforward`. That is correct for the very first calc, but `_last_input` is cleared by `clear_samples()` only in the OFF→AUTO mode setter — which happens BEFORE the first calc. So `_last_input is None` on that first calc, P=0, bumpless math works. But if `set_transport_delay`/other paths cleared samples and the integral target ends up matching the previous output AND `dt` is short (>0 but <5s), the integral is set then immediately overwritten by the freeze branch (line 686-696) — actually no, freeze leaves integral alone — so this case works. Still worth documenting/asserting `_last_input is None` here, or moving the bumpless call into the `dt < MIN_DT_FOR_DERIVATIVE` path explicitly.
- **Fix:** after `prepare_bumpless_transfer()` succeeds, set a flag and skip the accumulate/clamp branch for that single tick. Otherwise the very first integral update layers on top of the bumpless value (small for typical 5s dt but conceptually wrong and easily becomes large with multi-minute first dt).

### 3. `setpoint_boost.py` mutates `self._pid.integral` without going through clamp logic — can violate `out_max - E - F` invariant
- **managers/setpoint_boost.py:150** (`self._pid.integral += boost`) and **:162** (`self._pid.integral *= decay`).
- The PID controller carefully clamps the integral to `[out_min - E - F, out_max - E - F]` inside `calc()` (line 665-668), but that clamp only runs after a successful `dt >= MIN_DT_FOR_DERIVATIVE` branch. Between the `_apply_boost` callback firing and the next sensor calc, `self._pid.integral` is unconstrained. If the next calc lands in the freeze branch (`0 < dt < 5s`) or first-call branch (`dt = 0`), the clamp is **never** applied and the unconstrained integral flows straight into `output = P + I + D + E - F`. Final output clamp at line 723 catches it for total output bounds, but learning/persistence sees an inflated integral that does not represent the actual contribution. A 15.0% boost on top of an integral already at `out_max - E - F` becomes recorded windup the back-calculation can never recover from quickly.
- **Fix:** route boost/decay through `PIDController` methods that re-clamp (e.g., a `boost_integral(amount)` that performs the clamp), or always run the clamp at the top of `calc()` regardless of dt. The existing `scale_integral` and `decay_integral` have the same issue.

### 4. `PIDGainsManager.restore_from_state` re-syncs old gains to PID controller and records a duplicate RESTORE entry, but only for HEAT
- **managers/pid_gains_manager.py:212-242** — On restore, only the heating mode is processed (`mode_key = "heating"`; `if self._pid_history["heating"]`). Cooling restoration is silently skipped even when cooling history was persisted in `get_state_for_persistence` (line 405-411). After a HA restart in cooling mode, the controller will run with the previously initialized cooling gains (not the restored ones) until a manual reapply.
- **Fix:** restore both modes; if `get_hvac_mode` is HVACMode.COOL, sync cooling to PID controller; otherwise just store cooling gains. Also: the restore unconditionally calls `set_gains(..., RESTORE)` even when gains match the just-restored last history entry — the `_gains_match_last_entry` dedup *does* fire (line 154), so no duplicate snapshot is recorded. Good there. But the bug is the COOL mode being dropped.

### 5. State-restore re-applies integral *after* `gains_manager.restore_from_state` synced gains and re-clamped nothing
- **managers/state_restorer.py:132** — `thermostat._pid_controller.integral = thermostat._i` writes the raw restored integral via the setter (which only type-checks float). If the persisted integral was saved when `out_max` / `Ke` / `feedforward` differed (configuration change between sessions), it can violate the bound on first calc. The PID's first calc has `dt == 0`, so the integral clamp at line 665 is **skipped** — see issue #3. The first valve setting could be `P + restored_I + 0 + E - F`, which is then clamped at `output` level (line 723), but the integral remains at its pre-restore (possibly oversized) value indefinitely until a `dt >= 5s` calc runs.
- **Fix:** in `_restore_pid_values` or on first calc, clamp restored integral to `[out_min - E - F, out_max - E - F]` immediately.

---

## High (should fix)

### 6. `_accumulate_integral` boundary-crossing math uses wrong `time_normal` when interval starts during dead time and ends after
- **pid_controller/__init__.py:475-480** — `time_in_dead = transport_delay_seconds - (elapsed_seconds - self._dt)` and `time_normal = self._dt - time_in_dead`. If `elapsed_seconds - self._dt < transport_delay_seconds <= elapsed_seconds`, that is correct: `(elapsed - dt)` is the start of the interval, `(transport_delay - (elapsed - dt))` is the portion before crossover, rest is after. OK on inspection.
- But `time_in_dead` could be negative if numerical jitter makes `elapsed_seconds - self._dt > transport_delay_seconds` while still falling into this elif (it cannot if conditions are strictly checked, but the comparisons mix monotonic-elapsed and sensor-derived `_dt`). Recommend `time_in_dead = max(0.0, ...)` and `time_normal = max(0.0, ...)` for safety. Currently a single bad sample can briefly subtract integral.

### 7. Bumpless transfer skip on large error / setpoint change *discards* the last_output instead of integrating it later
- **pid_controller/__init__.py:354 and :360** — when conditions fail, `self._last_output_before_off = None` is set, meaning the next calc has nothing to transfer from. That is by design (large error = re-tune from scratch), but the integral is also untouched, so a stale large integral from before the OFF period persists and is now incorrect (the system was OFF for an arbitrary time during which thermal state diverged). Combined with no `clear_samples()` on the integral, the first calc after a long OFF can apply 100% output from stale integral.
- **Fix:** when bumpless is skipped, also reset the integral (or scale by an OFF-duration-dependent decay).

### 8. `set_pid_param` silently ignores non-numeric values rather than raising
- **pid_controller/__init__.py:382-391** — `if kp is not None and isinstance(kp, (int, float)): self._Kp = kp` — passing a string or NaN silently no-ops. This subverts the gains manager guarantee that "all gain changes go through history" because a caller that passes a typo'd value gets neither an error nor a sync. Worse, `math.isnan(kp)` is allowed in (float NaN passes `isinstance(float)`), and NaN propagation into `_proportional = -self._Kp * self._input_diff` poisons the entire controller.
- **Fix:** raise `TypeError`/`ValueError` for non-numeric and NaN/Inf; do the validation in `set_pid_param`.

### 9. `PIDGainsManager.set_gains` does not validate gains for NaN/Inf/negative
- **managers/pid_gains_manager.py:113-155** — `kp/ki/kd/ke` are passed straight into `replace()` and into `set_pid_param`. Negative Kp/Ki would invert the controller (heating cools), NaN poisons calculations. A misbehaving learning rule (e.g., div-by-zero in `calculate_pid_adjustment`) could store NaN to history and disk.
- **Fix:** validate `>= 0` and `math.isfinite()` before assignment; raise `ValueError` on failure.

### 10. `PIDController.scale_integral`/`decay_integral` lack input validation and don't re-clamp
- **pid_controller/__init__.py:318-333** — `decay_integral(factor)` accepts any float, including negative (would flip integral sign) and >1 (would amplify, contradicting docstring "0-1"). `scale_integral` has no docstring guard at all and is used by climate.py:1550 with `scale_factor = old_ki / new_ki` — if `new_ki` somehow becomes 0, this raises `ZeroDivisionError` in the caller (caller guards `if old_ki > 0` but not `if new_ki > 0`). And after scaling the integral, no clamp is re-applied (same root cause as #3).
- **Fix:** validate `0 <= factor <= 1` in `decay_integral`, `factor > 0` in `scale_integral`, and clamp afterwards.

### 11. `ControlOutputManager.actual_dt` is silently clamped to 0 on negative or huge jumps, but the PID still computes
- **managers/control_output.py:148-159** — When the clock jumps, `actual_dt = 0` is passed as `effective_previous_time = current_time - 0 = current_time`, meaning the PID sees `dt = 0` and takes the first-call branch. Good — integral is preserved, derivative reset. But the warning is rate-limited per entity, and on a sleep/resume there is no learning-side rollback or "discard this cycle" signaling. CycleMetricsRecorder may continue accumulating stats across the gap.
- **Fix:** broadcast a `clock_jump` event so cycle tracker can invalidate the in-flight cycle.

### 12. `set_pid_param(ke=...)` is called by `PIDGainsManager._sync_gains_to_controller` even when `ke` was not in the partial update — but `_Ke` always exists, so it overwrites with the (preserved) value
- **managers/pid_gains_manager.py:88** — `set_pid_param(kp=gains.kp, ki=gains.ki, kd=gains.kd, ke=gains.ke)` is fine for full sync. But `restore_from_history` (line 357-364) passes `ke=entry.get("ke")` which is `None` for legacy entries pre-Ke, so `replace()` substitutes `current_gains.ke`. OK. The migration default at line 284 also fills `ke=0.0`. The risk is `restore_from_history` from a legacy snapshot with no `ke` field at all — it would zero Ke silently (the migration on `_restore_history` adds `ke: 0.0`, so this is mostly defensive). Still worth a debug log when ke transitions from a positive value to 0.0 due to legacy entry.

### 13. `setpoint_boost.py` uses `homeassistant.helpers.event.async_call_later` callback that is NOT cleared when the manager is destroyed via reload
- **managers/setpoint_boost.py:105 / :172-177** — `cancel()` exists and is called from `climate.py:631`. Good. However, `_apply_boost` does `self._pid.integral += boost` without checking that `self._pid` still references a live PID — on integration reload, the new PID controller is a different object, but the callback is bound to the old one. If `cancel()` is missed (exception path), the callback would mutate a stale object. Low actual-impact (orphan PID would be garbage-collected once written), but easy to harden.
- **Fix:** in `_apply_boost`, guard against `self._enabled` and add a `_destroyed` flag set by `cancel()`.

### 14. Ke external term short-circuits when `error < 0`, creating a discontinuity at the setpoint
- **pid_controller/__init__.py:582-585** — `if self._error >= 0: external = Ke·dext + ... else: external = 0`. As temp crosses setpoint from below to above, the external term drops from `Ke·(setpoint - ext_temp)` to 0 instantaneously. This adds a step to `output = P + I + D + E - F` exactly at the moment the system needs the smoothest possible roll-off. If `Ke·dext` is small (post-v0.7.0 reduction, <1%), the step is negligible — but with wind compensation it can be 2-5%. The justification "room has enough thermal energy" is true on average, but the step itself is an avoidable bump.
- **Fix:** scale `external` smoothly with error sign, e.g., multiply by `max(0, min(1, error / cold_tolerance + 1))` or just apply unconditionally and let the integral compensate (it already does via the saturated-low check).

### 15. `_accumulate_integral` may skip dead-time start capture if `_input_time` is None at `set_transport_delay`
- **pid_controller/__init__.py:303-307** — On `set_transport_delay` with no prior input, `_dead_time_start = -1.0` sentinel. Then `_accumulate_integral` line 462 sets `_dead_time_start = self._input_time` on first calc — but only when the *current* `_input_time` has been computed. That happens at line 532/535/537 before `_accumulate_integral` runs, so fine. **However**, if `_input_time` itself is `None` (impossible in current flow because we always set it before `_accumulate_integral`, but defensively …), assignment of `_dead_time_start = None` would silently disable dead time forever. Add an assert or fall-through to `base * dt_hours`.

### 16. `decay_integral` accepts negative `factor` and inverts integral sign silently
- **pid_controller/__init__.py:318-325** — Per-minute decay multiplier is computed in `climate_control.py:92` as `0.9 ** (elapsed / 60)`, which is always positive — so caller is safe. But `decay_integral(-0.5)` would flip integral sign and the controller would drive in the wrong direction. Defensive `factor = max(0.0, min(1.0, factor))` is appropriate.

---

## Medium (worth fixing)

### 17. `clear_samples` does not reset `_dext`, `_proportional`, `_derivative`, `_external`, `_feedforward`, `_input_diff`
- **pid_controller/__init__.py:393-400** — On OFF→AUTO transition (which triggers `clear_samples`), the residual `_external` and `_feedforward` from the last calc remain. They are recomputed on next calc, so this is mostly cosmetic. But `_proportional` is *not* recomputed on the first calc after OFF (`_last_input is None`, line 590 short-circuits), so the proportional term keeps its stale value momentarily until logged. Minor.

### 18. Two duplicated initializations in `PID.__init__`
- **pid_controller/__init__.py:110-128** — `self._proportional = 0.0` (line 110) then `self._proportional = 0` (line 127). Same for `_derivative` (lines 112 and 128). Harmless, but type-inconsistent (`float` vs `int`).

### 19. `_input_time` and `_last_input_time` are typed as `None` initially but used in arithmetic without narrowing
- **pid_controller/__init__.py:118, 119, 469** — Pyright strict (per CLAUDE.md) should flag `elapsed_seconds = self._input_time - self._dead_time_start` because either could be None. The code is correct at runtime due to control flow, but adding type annotations + `assert is not None` (or raising `ValueError`) would document the invariant. Per CLAUDE.md, never use `assert` in production — so raise instead.

### 20. `PIDGainsManager._migrate_history_entry` defaults `kp=0.0, ki=0.0, kd=0.0` for missing fields
- **managers/pid_gains_manager.py:279-296** — Migrating a malformed entry with missing kp produces a zero-gain entry. If `restore_from_history(idx)` then targets that entry, the user gets a dead PID. Either reject the entry or fall back to current gains. At minimum, log a warning.

### 21. `set_gains` deduplicates on rounded 2-decimal compare, but Ki is typically 0.001-0.05
- **managers/pid_gains_manager.py:102-111** — `r2(0.005) == r2(0.0049) == 0.00`. Two distinct Ki values get treated as identical and the snapshot is skipped. The PID controller still got the new Ki via `set_pid_param`, but history lies (says "still 0.0049"). For an integral coefficient this is a significant precision loss.
- **Fix:** use mode-aware tolerance, e.g., `round(ki, 5)`.

### 22. `PIDTuningManager.async_set_pid` accepts negative gains and infinities
- **managers/pid_tuning.py:62-83** — No validation on `float(kp)` etc. Forwarded straight to `_gains_manager.set_gains` which also doesn't validate (see #9). A service call `adaptive_climate.set_pid kp=-5` flips the controller direction. The CLAUDE.md project rule prohibits `assert`; explicit `ValueError` raising is correct here.

### 23. `KeManager` keeps both protocol-based and callback-based code paths, doubling surface area
- **managers/ke_manager.py:43-122** — The "backward compatibility" callbacks should be removed; all call sites have a `KeManagerState` protocol available (the protocol exists in `protocols.py:148`). Maintaining both paths means every getter has an `if self._state is not None: ... else ...` branch (lines 151-197), and dead-code testing is impossible. Per CLAUDE.md: "Managers receive a `ThermostatState` Protocol, not raw callbacks or thermostat references." Violates that rule.

### 24. `KeManager.async_apply_adaptive_ke` calls `ke_learner.apply_ke_adjustment(recommendation)` *before* `_gains_manager.set_gains`
- **managers/ke_manager.py:348-355** — If `set_gains` raises (e.g., NaN validation in the future), `ke_learner._current_ke` was already mutated. Reordering: persist intent via gains_manager first, then update the learner's `current_ke` only on success.

### 25. `KeManager.is_at_steady_state` uses `time.monotonic()` and persists `_steady_state_start` via `restore_state`
- **managers/ke_manager.py:233-241 and :365-377** — `_steady_state_start` is a monotonic timestamp; persisting it across HA restarts is *meaningless* because the monotonic clock resets to a new epoch every process. After restore, `current_time - self._steady_state_start` is essentially random (negative on a quick restart, very large on a long-gone restore). This breaks the steady-state-duration check entirely after every restart.
- **Fix:** either don't restore this timestamp (start fresh after every restart, which is correct because thermal state is unknown), or use `dt_util.utcnow()` and convert.

### 26. `ControlOutputManager._record_heat_output_for_thermal_groups` compares HVAC mode as raw string
- **managers/control_output.py:450** — `if self._thermostat_state._hvac_mode != "heat"` compares the `HVACMode` enum to a string literal. Same at `_calculate_coupling_compensation` line 472. Works because `HVACMode("heat") == "heat"`, but it should use `HVACMode.HEAT` / `HVACMode.COOL` for type safety. CLAUDE.md: "never raw strings" for `HeatingType`; same principle should apply.

### 27. `ControlOutputManager._dt_discrepancy_last_warned` is a module-global mutable dict
- **managers/control_output.py:26** — Per-entity warning state lives in a module global, never cleaned up on entity removal. Memory leak per integration reload (small per entry, but unbounded across reloads/test runs). Move to instance state.

### 28. `pid_tuning.py` uses `getattr(self._state, "_ke_controller", None)` and `_preheat_learner` directly
- **managers/pid_tuning.py:437, 463, 469** — The Protocol does not declare these. Either add them to the Protocol or inject them as constructor parameters. Currently breaks the "managers receive a Protocol" rule and bypasses type checking.

### 29. `pid_tuning.py:471` mutates private state of the preheat learner
- **managers/pid_tuning.py:471-472** — `preheat_learner._observations.clear()` and `preheat_learner._add_observation_counter = 0` reach into another module's internals. Should be a `clear_observations()` method on the learner.

### 30. `prepare_bumpless_transfer` skip-criteria check `abs(self._error) > BUMPLESS_TRANSFER_THRESHOLD` happens *after* setting `self._set_point = set_point`
- **pid_controller/__init__.py:538-539 vs :350** — When user changes setpoint and resumes from OFF in the same calc, `_last_set_point` was set to the previously-stored `_set_point` (which is also the new one if no calc ran between mode flip and resume). The setpoint-delta check then sees 0 and proceeds, even when the *actual* setpoint changed. Minor edge case but means the bumpless transfer fires when it should be skipped.

### 31. `_apply_boost` integral cap `max(abs(self._pid.integral) * 0.5, 15.0)` does not respect `out_max - E - F` headroom
- **managers/setpoint_boost.py:147** — Cap is a function of current integral, not remaining output headroom. If integral is already 50 and `out_max - E - F` is 60, a 15% boost overshoots the clamp. See #3.

---

## Low / nits

### 32. Type-hint inconsistencies and missing annotations
- `pid_controller/__init__.py:42` — `error: float` class annotation, but `__init__` declares `self._error = 0` (int). Many params lack types (`def __init__(self, kp, ki, ...)`).
- `managers/ke_manager.py:50-61` — `callable | None` should be `Callable[..., Any] | None`. `callable` is the builtin function, not a type.
- `managers/pid_tuning.py:42` — `gains_manager: Any` — should be `PIDGainsManager` (already imported as TYPE_CHECKING). Remove `Any`.

### 33. Docstring inaccuracies
- **pid_controller/__init__.py:50** — `ke_wind=0.02` listed as default, but docstring just says "Wind speed compensation coefficient (per m/s)" without mentioning typical magnitude.
- **pid_controller/__init__.py:88-90** — `integral_exp_decay_tau` says "Time constant (hours)" but the code passes `dt_hours / self._integral_exp_decay_tau` to `math.exp(-…)` — consistent. Good.
- **setpoint_boost.py:124** — Says `_now` is "Current datetime" but `async_call_later` actually passes a `datetime` representing the scheduled time, not "now". Minor.

### 34. `clear_samples` does not reset `_derivative_filtered` only — actually it does (line 400). Good.

### 35. `MIN_DT_FOR_DERIVATIVE = 5.0` hard-coded
- **pid_controller/__init__.py:30** — A 5s lower bound is reasonable for typical sensors, but very fast forced-air systems with 1s update sensors will frequently fall into the freeze branch, effectively disabling derivative. Consider scaling by heating type.

### 36. `_LOGGER.warning` for clock-jumped dt — fine — but no metric/state exposed
- **managers/control_output.py:153** — Power users investigating poor performance after suspend/resume have no attribute to inspect. Consider adding `clock_jumps_detected` counter to debug attributes.

### 37. `PIDGainsManager.restore_from_history` raises `ValueError` for empty history with misleading message
- **managers/pid_gains_manager.py:347-348** — `f"Invalid history index {index} (history is empty)"` includes `index` which may be valid (e.g., 0). Reword: `"Cannot restore: PID history is empty"`.

### 38. `pid_tuning.py:324` directly accesses `adaptive_learner._auto_apply_count`
- Private attribute mutation across module boundary. Should be `set_auto_apply_count(count + 1)` or `increment_auto_apply_count()`.

### 39. `pid_tuning.py:170-236` `async_apply_adaptive_pid` does not include `metrics` in its `set_gains` call
- **managers/pid_tuning.py:213-218** — Unlike `async_auto_apply_adaptive_pid` (line 314-318), the manual apply records no metrics, making post-hoc analysis harder.

### 40. Outdoor compensation discontinuity (#14) compounds with bumpless transfer
- When OFF→AUTO transition lands with negative error, `_external = 0`, bumpless solves `required_integral = last_output - 0 - 0 + F`. When error transitions positive, `_external` jumps and integral now has wrong basis. Low impact because bumpless mostly fires near setpoint.

### 41. `_was_clamped` is sticky-until-reset_clamp_state but `reset_clamp_state` is documented as "call at cycle start"
- **pid_controller/__init__.py:276-283** — Search shows `reset_clamp_state` is defined but I do not find a call site in the codebase (grep would confirm). If no caller resets it, `was_clamped` becomes a permanently-true flag once tripped.

---

## Architectural observations

1. **Dual responsibility for integral mutations.** `PIDGainsManager` was created to centralize *gain* mutations with history, but the integral has analogous needs (it is the PID's state) and is mutated freely from at least 8 different files (climate.py:1118, 1221, 1550, climate_control.py:93, 167, pid_tuning.py:130, 210, 306, 395, state_restorer.py:132, setpoint_boost.py:150, 162, __init__.py:689, ke_manager.py unchanged). Most of these mutations skip the clamp and could violate the I-headroom invariant (#3, #5). Consider an `IntegralManager` or extending `PIDGainsManager` to own integral writes too.

2. **Two parallel APIs for KeManager.** Protocol-based and callback-based code paths coexist (#23). Pick one and delete the other; it's not just code smell — it's actively making the file harder to type-check and reason about. CLAUDE.md explicitly mandates Protocol.

3. **Sampling-period mode vs event-driven mode bifurcation in PID.calc().** Two completely different code paths for `_input_time` (line 519-537). The wall-clock path (#1) is the legacy mode; event-driven mode is what `ControlOutputManager` actually uses. If sampling-period mode is dead code, delete it. If it must stay, switch it to monotonic.

4. **`PIDGainsManager.restore_from_state` only restores HEAT.** This is a quiet correctness gap for COOL mode (#4) that will silently drop saved cooling gains on every restart for users with cooling.

5. **Outdoor compensation (`Ke·dext`) is only applied when `error >= 0`.** This is an "implicit feedforward gate" baked into the controller, but neither the docstring (line 68 mentions Ke without explaining the gate) nor the architecture docs mention it. Either remove the gate (#14) or make it configurable.

6. **PID controller imports try/except for constants (`INTEGRAL_DECAY_THRESHOLDS`, `HEATING_TYPE_CHARACTERISTICS`).** Fallback values inside the controller will diverge from `const.py` if the latter is updated. Either remove the fallback (controller is HA-only anyway) or DRY it via a shared `defaults.py`.

7. **`ControlOutputManager` reaches into protocol internals with leading-underscore attributes** (`_previous_temp_time`, `_current_temp`, `_ext_temp`, etc.). The Protocol exposes them, but the Protocol itself is partially "public" (`current_temperature`) and partially "private" (`_current_temp`). Picking one convention would make future refactors easier.

8. **No test harness shown for PID NaN/Inf injection.** Given how many entry points (`set_pid_param`, `set_gains`, `integral` setter, `decay_integral`, `scale_integral`, `set_feedforward`) accept floats without validation, a unit test pinning "NaN cannot enter PID state via any public method" would catch a whole class of future bugs.
