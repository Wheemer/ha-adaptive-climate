# Adaptive Learning Review

Scope: `custom_components/adaptive_climate/adaptive/*.py` plus `managers/learning_gate.py`, `managers/learning_milestone.py`, `managers/comfort_degradation.py`.

Note: The task brief lists `open_window_detection.py` under adaptive, but no such file exists in the repo (only references in `state_attributes.py` and `status_manager.py`). Either the module was removed, never landed, or it lives elsewhere; review focuses on what is actually present.

## Critical (must fix)

- **adaptive/learning.py:1700** — File is **1701 lines**, more than 2x the 800-line maximum in `CLAUDE.md` ("Max file length: 800 lines - extract into modules when exceeded"). It already does extensive re-export of cycle_analysis / pid_rules / pwm_tuning etc., so the spine should be split: `AdaptiveLearner` core (~300 lines), the `_check_*` / averaging math (~200 lines), undershoot wiring (~100 lines), serialization wiring (~100 lines), and the long block of backward-compat property aliases (`_heating_convergence_confidence`, `_cycle_history`, …, lines 224–350) extracted into a mixin or removed entirely.

- **adaptive/validation.py:182-186** — `check_auto_apply_limits` does `entry.get("timestamp", now) > cutoff` where `cutoff` is a `datetime` and `entry["timestamp"]` is an ISO **string** (produced by `pid_gains_manager.py:168` as `dt_util.utcnow().isoformat()`). Comparing `str > datetime` raises `TypeError`. The bug is currently masked because `learning.py:617` and `learning.py:1359` pass `pid_history=[]`, but as soon as anyone wires the real history back in, every auto-apply attempt crashes. Fix: parse via `datetime.fromisoformat(entry["timestamp"])` with tz-awareness, and skip entries with missing/unparseable timestamps. Also restore real `pid_history` wiring — otherwise the `MAX_AUTO_APPLIES_PER_SEASON` (5/90d) gate is a no-op and only the lifetime gate (`MAX_AUTO_APPLIES_LIFETIME = 20`) protects against runaway tuning.

- **managers/pid_tuning.py:324, 328 (interacting with adaptive/confidence.py)** — Auto-apply count is incremented via `adaptive_learner._auto_apply_count += 1`, which through the alias at `learning.py:281-284` always writes to **`_heating_auto_apply_count`** regardless of HVAC mode. Result: every cooling auto-apply is mis-counted as a heating auto-apply. The "first vs subsequent" gate in `auto_apply.py:219` (`if auto_apply_count == 0:`) reads `confidence_tracker.get_auto_apply_count(mode)`, which then disagrees with what gets incremented. Cooling auto-apply will therefore re-enter the "first apply requires only tuned" path indefinitely, and heating's seasonal/lifetime budget is silently consumed by cooling activity. Fix: call `confidence_tracker.increment_auto_apply_count(mode)` (already implemented at `confidence.py:220`) from `pid_tuning.py` with the active mode.

- **adaptive/confidence.py:56-57, 122-124 + learner_serialization.py** — `_heating_cycle_count` / `_cooling_cycle_count` are incremented in `update_convergence_confidence` but **never serialized**. After an HA restart, `confidence_tracker.get_cycle_count(mode)` returns 0 even when `_heating_cycle_history` has 50 entries. `auto_apply.py:206-215` then computes `learning_status` against `MIN_CYCLES_FOR_LEARNING` using that zero, and `_compute_learning_status` returns `"collecting"` on every restart, blocking auto-apply until cycles re-accumulate in-session. Fix: persist `heating_cycle_count` and `cooling_cycle_count` in `learner_to_dict` and restore them, OR derive cycle count from `len(cycle_history)` in `ConfidenceTracker.get_cycle_count`.

- **adaptive/learner_serialization.py:216-223** — Version handling is excessively strict: any `format_version != 10` returns a fresh `_default_learner_state()`, **silently wiping all persisted learning** (cycle history, confidences, undershoot multiplier, contribution caps, heating-rate observations). The docstring on `AdaptiveLearner.restore_from_dict` even claims it "Supports v10 format only," but the code paths in `learning.py:1627-1656` go to lengths to mention "serialization module already handles v7->v8 migration", "v8->v9 migration", "v9->v10 migration" — none of which actually exist here. Either (a) implement real migrations from v5–v9 (the format-version constant has been bumped at least 5 times), or (b) when an older version is encountered, preserve the cycle history list and reset only the new fields, not the entire state. Today every release that bumps `CURRENT_VERSION` invalidates every user's learning data.

- **adaptive/learner_serialization.py:189** — `_default_learner_state()` writes `"format_version": "v10"` (string), but `learner_to_dict` writes `"format_version": 10` (int) and `restore_learner_from_dict` checks `if stored_version != 10` (int). The default-state value would itself fail version check if it ever round-tripped. Make the constant unambiguous (always int).

- **adaptive/undershoot_detector.py:269, 274-276 vs CLAUDE.md** — `MAX_UNDERSHOOT_KI_MULTIPLIER = 3.0` in `const.py:943`, but `CLAUDE.md` (multiple places, e.g. "Cumulative multiplier capped at 2.0x to prevent runaway integral gain") and the documented behavior promise a **2.0x cap**. A 3.0x cap allows Ki to triple before the safety gate fires, which on `floor_hydronic` (whose initial Ki is already aggressive from `physics.py:362-369`) can drive the system into severe overshoot. Either lower the constant to 2.0 or update the documentation; the two cannot diverge silently.

- **adaptive/undershoot_detector.py:357-396 (`apply_adjustment`)** — `cumulative_ki_multiplier *= multiplier` is updated **before** any sanity check that the multiplier actually got clamped. If `get_adjustment` returned `min(multiplier, max_allowed)` where `max_allowed` went negative (e.g. `cumulative_ki_multiplier` somehow exceeded the cap from a bad restore), `cumulative *= negative` produces a negative cumulative tracker, which then makes `max_allowed = CAP / cumulative` negative on the next call and `min(positive, negative) = negative` — the gate breaks permanently. Defensively clamp: `multiplier = max(1.0, get_adjustment(...))` and `cumulative_ki_multiplier = min(MAX_UNDERSHOOT_KI_MULTIPLIER, cumulative_ki_multiplier * multiplier)`.

- **adaptive/undershoot_detector.py:398-434 (`_in_cooldown`)** — Mixes `time.monotonic()` (within-session) with wall-clock `dt_util.utcnow()` for cross-restart. The monotonic timer cannot be persisted, so on restart `self.last_adjustment_time` is `None` and the only protection is the history-based check — but `learning.py:check_undershoot_adjustment` is the only caller passing `pid_history`, and `should_adjust_ki` is also called from `_perform_historic_scan` (line 1690) **without** any history. During the historic scan path the cooldown is effectively disabled, so a restart with adverse history can immediately apply a Ki boost that the user already received hours ago. Persist `last_adjustment_time` as ISO datetime in the serialized state (the field already exists in `learner_to_dict:90` as a raw monotonic float, which is meaningless across restart — that's a separate bug).

- **adaptive/learner_serialization.py:90** — `"last_adjustment_time": undershoot_detector.last_adjustment_time` writes a `time.monotonic()` float into persistent storage. On restart this float is meaningless (monotonic clock origin changes per boot) but `learning.py:restore_from_dict` does not even read it back; it only restores `cumulative_ki_multiplier`. So we serialize garbage and discard it. Either drop the field or store wall-clock UTC datetime and restore it.

- **adaptive/learning.py:1208 + confidence_contribution.py** — Poor cycle path subtracts `CONFIDENCE_INCREASE_PER_GOOD_CYCLE * 0.5` directly from `current_confidence` but does **not** rebate the `_heating_maintenance_contribution` cap used by `apply_maintenance_gain`. After many up/down cycles, confidence drifts back toward 0 while the contribution counter is permanently at the cap, so future maintenance cycles only ever get `MAINTENANCE_DIMINISHING_RATE * gain` and the system can never re-converge through maintenance. Fix: when confidence decreases, decrement the matching contribution tracker proportionally, or recompute contributions from confidence delta.

## High

- **adaptive/humidity_detector.py:102-112** — Forced resume from `paused` clears `_peak_humidity` and `_pause_start` but does **not** clear `_stabilization_start`. If a previous fast-spike → drop → re-spike sequence set `_stabilization_start`, the next stabilizing entry can think it's already past delay. Explicitly set `self._stabilization_start = None` here.

- **adaptive/humidity_detector.py:167-168, 183-184** — On trigger, `self._pause_start = self._last_timestamp`. If `_check_triggers` is invoked during construction (it isn't today, but flow-wise) or before `record_humidity` was called for this reading, `_last_timestamp` is the *previous* reading's ts (or `None`), so `_pause_start` is set to the wrong instant. Pass `ts` into `_check_triggers` and use it directly; the same applies in `_update_state` where `ts` is already in scope but discarded.

- **adaptive/humidity_detector.py:130-131** — On exit to `stabilizing`, `_humidity_history.clear()` then appends only the current reading. The next call needs 2 readings before rate-of-change can fire again (`if len(self._humidity_history) >= 2`), meaning a brand-new spike during stabilizing has to wait for two `record_humidity` calls in the new window. If sensor updates are slow (HA only pushes on change), that window can be minutes. Either keep one historical reading or trigger on absolute single-sample rate.

- **adaptive/humidity_detector.py:62, 78-85** — `_humidity_history` is an unbounded `deque` (no `maxlen`). Eviction is by time only. If `record_humidity` is invoked at high frequency (e.g. a per-second pseudo-sensor) for several minutes, the buffer grows without bound until eviction catches up; even then, every append O(N) scans the front. Use `deque(maxlen=N)` with a sensible cap and rely on time pruning for staleness.

- **adaptive/preheat.py:373-374** — `bin_key = tuple(obs_data["bin_key"])`. JSON deserializes 2-element lists into 2-element lists; `tuple(["delta_0_2","cold"])` becomes a 2-tuple, fine. But if storage corruption produces a 3-element list, the tuple is silently 3-wide and `learner._observations[bin_key]` creates a new wrong-keyed bin that is never read by `get_learned_rate`. Validate shape explicitly: `if len(obs_data["bin_key"]) != 2: continue`.

- **adaptive/preheat.py:374-386, 358** — `from_dict` does not guard against `KeyError` if any of `start_temp`/`end_temp`/`outdoor_temp`/`duration_minutes`/`rate`/`timestamp` is missing. A single malformed observation in storage aborts the entire restore and the call site has no try/except (checked: `learning.py:1646-1655` doesn't catch). Add a per-observation try/except that logs and skips bad entries.

- **adaptive/preheat.py:236-238** — Cold-soak margin formula `margin = (1.0 + delta / 10.0 * 0.3) * cold_soak_margin` has a subtle order-of-operations: this is `(1 + delta * 0.03) * cold_soak_margin`, not `(1 + delta * 0.3 / 10) * cold_soak_margin` (same result by accident). Add parentheses or precompute the slope; otherwise a future tweak to "30%" will surprise.

- **adaptive/heating_rate_learner.py:368-371** — `should_boost_ki()` references `self._last_session_avg_duty` but the attribute is only set inside `end_session` (line 254) **and only if `session.cycle_duties` is truthy**. If the first session ends without ever recording a duty (e.g. override interrupt → discarded session takes the early-return path at line 257, never assigning), `should_boost_ki` accesses an undefined attribute and raises `AttributeError`. Initialize `self._last_session_avg_duty: float | None = None` in `__init__`.

- **adaptive/heating_rate_learner.py:331-332** — `is_stalled()` returns true after `STALL_CYCLES` (3) consecutive cycles with no progress, but `last_progress_cycle` starts at 0, and `cycles_in_session` increments on every cycle including the first. So a fresh session with 3 slow but progressing cycles can show `cycles_since_progress = 3 - 0 = 3` if the rise threshold `0.1°C` is never crossed in the first 3 samples. Initialize `last_progress_cycle = cycles_in_session` at session start once a temp is observed.

- **adaptive/learning.py:1196 vs 1208** — Reward path uses `weighted_gain` (×0.1 base × weight × cap routing) but penalty path uses a flat `CONFIDENCE_INCREASE_PER_GOOD_CYCLE * 0.5 = 0.05` independent of cycle weight. So a high-difficulty recovery cycle that goes badly is penalized 0.05 while a clean maintenance cycle (capped) gains <0.05 — the penalty is *bigger* than the reward in that regime, biasing the system toward downward drift. Mirror the weighting on penalties (with the same caps) or document why penalties are intentionally non-weighted.

- **adaptive/learning.py:1100-1107, 1151-1163** — `is_stable = current_confidence >= (tier1_base * 0.8)` is duplicated in two scopes with the comment "Floor scaling approximation" — but the real floor scaling factor is in `HEATING_TYPE_CONFIDENCE_SCALE` (`const.py:557`). The hard-coded 0.8 is correct for `floor_hydronic` and wrong for everything else (radiator=0.9, convector=1.0, forced_air=1.1). Inject the real scaled tier-1 from `confidence.py` instead of approximating.

- **adaptive/validation.py:107-111** — `degradation_pct = (avg_overshoot - baseline) / max(baseline, 0.1)`. If baseline is `0.0` (clean prior run), denominator is 0.1, and `degradation_pct = avg_overshoot / 0.1 = 10 * avg_overshoot`. With `VALIDATION_DEGRADATION_THRESHOLD = 0.30`, any post-apply average overshoot > 0.03°C triggers rollback. Real-world sensor noise of ±0.1°C trivially exceeds this. Use additive guard (`if baseline < 0.1: pass if avg_overshoot < some_absolute`) or a relative-plus-absolute test.

- **adaptive/validation.py:294-296** — Outdoor temp history kept as the last 30 raw readings ("roughly 15 hours at 30-min intervals"). But there is no time-based pruning, only count-based; HA sensors that report only on change can produce 30 readings within minutes during weather transitions, making `old_avg` and `new_avg` both near-identical and seasonal-shift detection silently dormant. Add a max age (e.g. 24h) or store `(ts, temp)` tuples.

- **adaptive/undershoot_detector.py:269** — `cumulative_ki_multiplier >= MAX_UNDERSHOOT_KI_MULTIPLIER` blocks adjustment, but the boost itself is then computed in `get_adjustment` by `max_allowed = CAP / cumulative`. If `cumulative == CAP` exactly, `max_allowed = 1.0` and `min(multiplier, 1.0) = 1.0` is applied, making the cap a no-op increment that still resets `_consecutive_failures = 0` and records `last_adjustment_time`. Caller (`learning.py:1446-1447`) logs "increasing Ki from X to X (0.0% increase)" and decreases convergence confidence for nothing. Guard: if computed multiplier is ≤1.0 (or within ε of 1.0), return `None` from `check_undershoot_adjustment` instead of applying a no-op.

- **adaptive/undershoot_detector.py:298-308** — Real-time mode returns true if `_time_below_target >= time_threshold OR _thermal_debt >= debt_threshold`, but `_time_below_target` is never decayed unless temp rises *above setpoint* (`reset_realtime`). A system spending 100% of its time within tolerance (`0 <= error <= cold_tolerance`) but rarely above setpoint accumulates time indefinitely. After several days, every cycle on cold mornings re-triggers the boost from a stale counter. Either decay `_time_below_target` continuously or reset it when within tolerance for some time.

- **adaptive/learning.py:1429-1436** — Backward-compat reads both `"undershoot_ki_boost"` and `"chronic_approach_ki_boost"` from pid_history, but the codebase only ever writes `UNDERSHOOT_BOOST` per `pid_gains_manager.py` (and `CLAUDE.md`'s PID Change Reasons table lists `UNDERSHOOT_BOOST` only). If `PIDChangeReason` enum doesn't serialize to either of those exact strings, both reads return `None` and the cross-restart cooldown is silently disabled. Verify the enum's string value and use it directly (e.g. `PIDChangeReason.UNDERSHOOT_BOOST.value`) rather than hard-coded strings that drift from the enum.

- **adaptive/confidence.py:107-183 vs learning.py:1081-1224** — `ConfidenceTracker.update_convergence_confidence` is fully implemented (with its own rise-time/recovery logic) but `AdaptiveLearner.update_convergence_confidence` (lines 1081-1224) re-implements all of that with weighted learning and never calls the tracker's version. So `confidence.py`'s implementation is dead code reachable only through tests; any change to its logic has zero runtime effect. Either delete the dead implementation or have `AdaptiveLearner.update_convergence_confidence` delegate.

## Medium

- **adaptive/learning.py:641** — `recent_cycles = cycle_history[-min_cycles * 2 :]` then filters disturbed and slices `[-min_cycles:]`. If `min_cycles = 4`, this looks at the last 8 cycles. When `MIN_CYCLES_FOR_LEARNING` rises (e.g. subsequent learning multiplier = 2.0 → 8), this looks at 16 cycles — but `MAX_CYCLE_HISTORY` is capped, so we may consume the entire history with no buffer for outlier rejection. Make the window size explicit (e.g. `max(min_cycles * 2, 8)`).

- **adaptive/learning.py:752-757** — `avg_inter_cycle_drift` and `avg_settling_mae` use plain `sum/len` while overshoot, undershoot, settling_time, oscillations, rise_time use `robust_average` (MAD outlier rejection). Same window, same data quality concerns — apply `robust_average` consistently for all metrics that feed convergence checks.

- **adaptive/learning.py:683-700** — When `overshoot_values` is empty, `avg_overshoot = 0.0`. When all cycles have `controllable_overshoot = None` and `overshoot = None`, the system silently behaves as if perfectly tuned. Distinguish "no data" (skip adjustment, return None) from "zero overshoot" (apply rules).

- **adaptive/validation.py:266** — `recent_overshoot > baseline_overshoot * 1.5 and recent_overshoot > 0.3` — baseline=0.05 → threshold=0.075; recent=0.31 triggers. baseline=0.4 → threshold=0.6; recent=0.5 (worse than baseline) does not trigger. The dual condition makes degradation detection insensitive to slow degradation in already-poor systems. Use additive: `recent > baseline + max(baseline * 0.5, 0.15)`.

- **adaptive/undershoot_detector.py:478-525 (`check_rate_based_undershoot`)** — Method exists but is never called from `learning.py`. Either wire it into `check_undershoot_adjustment` (currently only realtime + cycle modes are checked) or remove it. The class docstring at lines 12-16 advertises three modes; only two are integrated.

- **adaptive/confidence_contribution.py:115-143 (`apply_maintenance_gain`)** — The "crosses cap" branch (lines 127-143) is fine, but on subsequent calls when contribution already > cap, `room = cap - current_contribution` is negative, the `if gain <= room` branch evaluates (positive <= negative → False), and code falls through to the "Crosses cap" branch, where `under_cap_gain = room` (negative). The contribution then receives `negative + diminished_overflow`, which can decrement the contribution counter — direct contradiction to the "diminishing returns" intent (the path on line 116-123 was supposed to handle this case). Add `elif current_contribution >= cap: return early` clearly or restructure the conditional.

- **adaptive/confidence_contribution.py:145-162 (`apply_heating_rate_gain`)** — Hard cap with `if room <= 0: return 0.0` is fine, but no diminishing-returns rebate is offered. After cap is reached, every subsequent rise-time-measured cycle returns 0 and the rest of the system gets no feedback that heating-rate observations are still arriving. Consider returning a small diminishing share for consistency with maintenance gain logic, or document why heating-rate has a hard wall.

- **adaptive/auto_apply.py:113-127** — Status branches return `"stable"` from two paths (lines 125, 127) with subtly different meaning: one is "confidence ≥ tier_2 but not enough recovery cycles for tier 2" and the other is "tier_1 met, tier_2 not met". Indistinguishable from outside, but the first is "degraded tuned" and the second is "honest stable". Add a separate status (e.g. `"tuned_pending"`) or persist the gating reason.

- **adaptive/auto_apply.py:140 return type** — `tuple[bool, int | None, int | None, int | None]` is unwieldy. A small dataclass `AutoApplyGateResult(passed, min_interval_hours, min_adjustment_cycles, min_cycles)` would be clearer and make `None` semantics explicit (currently `None` means "blocked", which the caller has to know by convention).

- **adaptive/learning.py:103-113** — `datetime.fromisoformat` without try/except: a corrupt or differently-formatted timestamp string (e.g. from a hand-edited storage file or older HA version) raises `ValueError` that is not caught anywhere on the call chain. Wrap in try/except and return None on parse failure.

- **adaptive/learner_serialization.py:262-265** — Same issue: bare `datetime.fromisoformat(last_adj_time)` with no error handling. A corrupt store entry crashes the entire restore.

- **adaptive/preheat.py:381** — `datetime.fromisoformat(obs_data["timestamp"])` — no error handling. Combine with the per-observation try/except suggested above.

- **adaptive/manifold_registry.py:175-180** — `parse_datetime` swallows ValueError/TypeError but not other exceptions, and silently drops a manifold's last-active time on parse failure. Could be worth logging at WARN level (currently is WARN, good) and surfacing how many manifolds were lost for diagnostics.

- **adaptive/persistence.py:71** — `if data["version"] < 1 or data["version"] > STORAGE_VERSION:` accepts any version 1-5 but the loader doesn't actually migrate v1-v4 — it just stores `self._data = data` (line 122). If older clients persist v1 schemas, `get_zone_data` returns whatever shape was stored and downstream code may crash. Either explicitly migrate or reject anything not exactly v5.

- **adaptive/robust_stats.py:148-150** — When `len(values) < min_valid_count`, returns median without outlier detection — fine, but caller `learning.py:684-735` unpacks `(avg, outliers)` and logs outlier count: 0. Document that the empty outlier list does not mean "no outliers detected" but "outlier detection skipped". Today a single rogue value in a 3-cycle window propagates straight into `avg_overshoot` etc.

- **adaptive/robust_stats.py:105-107** — `if mad == 0: return ([], [0.0] * len(values))` — fine when all values identical. But MAD can also be 0 when 51%+ values are identical even if outliers exist (e.g. nine zeros and one 100 → MAD=0). Use MAD with tie-breaking via the IQR alternative, or fall back to stdev-based detection when MAD is 0 but values vary.

- **adaptive/undershoot_detector.py:191-195** — Counter resets on `cycle.rise_time is not None` even if `cycle.undershoot >= threshold`. A cycle that *barely* reaches setpoint then immediately falls back resets the chronic-approach counter despite obviously underperforming. Only reset on a "clean" cycle (rise_time set AND undershoot < threshold).

- **adaptive/undershoot_detector.py:140** — `self._thermal_debt = min(self._thermal_debt, 10.0)` is a hard cap on `°C·hours`. But `_thermal_debt` is read against per-heating-type `debt_threshold` (`UNDERSHOOT_THRESHOLDS[t]["debt_threshold"]`) which for floor_hydronic is 150 °C·min = 2.5 °C·h. So the cap 10.0 is fine relative to thresholds but is type-agnostic — leaks abstraction. Make the cap `2 * SEVERE_UNDERSHOOT_MULTIPLIER * debt_threshold` so it scales with the system.

- **adaptive/humidity_detector.py:115-117** — `if self._peak_humidity is None or current_humidity > self._peak_humidity:` — peak only ratchets upward while paused. If the spike happens during a short rapid evaluation cycle and never reaches a single new high, peak is the first reading. Combined with the `exit_humidity_drop` exit requirement, this can shorten pauses. Initialize peak to `max(history)` on entering paused.

- **adaptive/heating_rate_learner.py:268-282** — `rate = temp_rise / duration_hours if duration_hours > 0 else 0.0` then immediately rejects `rate < MIN_OBSERVATION_RATE` (0.02). The zero from the safety branch is logged as "rejected" but `temp_rise` might be perfectly valid — duration just happened to be 0 due to a clock anomaly. Treat duration==0 as "skip", not as "stalled rate 0".

- **adaptive/heating_rate_learner.py:160-161** — `if len(...) > MAX:` then `self._bins[bin_key] = self._bins[bin_key][-MAX:]` recreates the list every overflow. Use `deque(maxlen=MAX)` per bin to avoid O(N) copies. Same in `preheat.py:160-162`.

- **adaptive/cycle_weight.py:99-100** — `delta_multiplier = 1.0 + (starting_delta - threshold) * DELTA_MULTIPLIER_SCALE; min(..., DELTA_MULTIPLIER_CAP)`. If `starting_delta < threshold` somehow but `is_recovery_cycle` already returned True (race on `is_stable` changing between calls), multiplier can be < 1.0 — meaning a "recovery" cycle gets *less* weight than maintenance. Clamp `delta_multiplier = max(1.0, min(delta_multiplier, CAP))` for safety.

- **adaptive/learning.py:1182-1187, 1166-1168** — Recovery cycle is added to `_contribution_tracker.add_recovery_cycle(mode)` based on `is_stable` computed from `current_confidence`. But the confidence here is the *pre-update* value. A cycle that pushes confidence from "below tier 1" to "above tier 1" is judged as collecting at the moment of classification, even though next cycle uses the new value. Borderline cycles flicker between recovery and maintenance categorization. Use a hysteresis band (e.g. `is_stable = confidence > tier1 * 0.85` for promotion and `< tier1 * 0.75` for demotion).

- **managers/learning_gate.py:120-140** — `_is_environmentally_disrupted` uses broad `except (TypeError, AttributeError)` swallowing exceptions. If `contact_sensor_handler.is_any_contact_open` ever raises (e.g. `KeyError` from a stale entity_id), the suppression silently fails open and the setback delta isn't suppressed. Be specific or log the exception.

- **managers/learning_gate.py:105-106** — `cycle_count = adaptive_learner.get_cycle_count()` (defaults to HEAT). For cooling-only zones this always returns the heat history length, which may be 0 forever; the cooling setback never gets gated by cooling cycles. Pass the active mode through.

- **managers/learning_milestone.py:64** — Skipping notifications when "new_status == 'idle' or prev == 'idle'" means a transition optimized→idle (e.g. user opens a contact) sends no recovery notification, and back idle→optimized sends none either. User may miss that their HVAC tuning state was bumped. Consider firing a low-priority notification.

- **managers/comfort_degradation.py:43-55** — `check_degradation` doesn't track a cooldown. The same low score can fire repeatedly until enough good samples raise the average. If callers don't dedupe, the user gets a notification storm. Add a `last_alert_at` with a minimum interval.

- **managers/comfort_degradation.py:30** — `deque(maxlen=max_samples)` (288 = 24h @ 5min). On slow days with infrequent updates (HA sensor-on-change), the deque can hold > 24h of data and `rolling_average` is then a multi-day mean. Add a per-sample timestamp and time-window pruning.

## Low / nice-to-have

- **adaptive/learning.py:224-350** — Backward-compat property aliases (`_cycle_history`, `_heating_convergence_confidence`, `_cooling_convergence_confidence`, `_auto_apply_count`, …) are advertised as "for testing". They expose `_confidence._cooling_convergence_confidence` via `_heating_convergence_confidence.setter` etc. Easy to mis-set in tests and end up with a confused fixture. If tests really need this, move to a `testing/__init__.py` helper rather than polluting production code. Otherwise prefer to refactor tests to use the public API.

- **adaptive/learning.py:352** — `def add_cycle_metrics(self, metrics: CycleMetrics, mode: HVACMode = None)` — `HVACMode = None` as default uses the import-time symbol from a TYPE_CHECKING-guarded block, which works only because of `from __future__ import annotations`. Use `mode: "HVACMode | None" = None` consistently with PEP 604 + string forward-ref or move `HVACMode` to runtime imports.

- **adaptive/learning.py:898-923** — `clear_history` does inline `from ..const import HeatingType as HeatingTypeEnum` and inline `from .confidence_contribution import ConfidenceContributionTracker` and `from .heating_rate_learner import HeatingRateLearner`. Hoist to module level (the imports already exist at top of file).

- **adaptive/learning.py:917, 921-923** — `ConfidenceContributionTracker` and `HeatingRateLearner` recreation requires an instance with the original heating_type — easy to forget. Both classes should have a `reset()` method instead of forcing the caller to throw away and recreate.

- **adaptive/learning.py:925-935** — `get_previous_pid` always returns None (deprecated). Either delete or mark with `@deprecated` decorator. Keeping zombie methods around invites confusion.

- **adaptive/learning.py:1141-1144** — Comment says "Recovery cycle that failed to reach target" — but `is_recovery and metrics.rise_time is None` is the *only* time we reach this elif. Move the check earlier in the chain (after the `is_good_cycle` test) and add a unit test for the misclassification path.

- **adaptive/learning.py:1163** — TODO comments (`# TODO: Add effective_duty to metrics`, `# TODO: Add night setback tracking`) in a "production" file. Either complete or move to issue tracker; TODOs in code rot.

- **adaptive/heating_rate_learner.py:124-146 + add_observation** — Inline `from homeassistant.util import dt as dt_util` inside `add_observation`. Hoist to module level. Same in `start_session`, `end_session`.

- **adaptive/heating_rate_learner.py:495-547** — `from_dict` uses `data.get("heating_type", "radiator")` — silently falls back to radiator if the persisted heating_type doesn't match the zone's current config. Better to take heating_type as an argument like `ConfidenceContributionTracker.from_dict(data, heating_type)`.

- **adaptive/disturbance_detector.py:21-23** — Uses `self._logger = _LOGGER` instead of just `_LOGGER` everywhere. The wrapper adds nothing.

- **adaptive/disturbance_detector.py:131-176 (`_detect_wind_loss`)** — Magic numbers `5.0 m/s`, `2.0°C`, `0.5°C`, `1.0°C/h`. Extract to module-level constants with provenance comments.

- **adaptive/disturbance_detector.py:106-119** — `solar_increase > 100` — unit ambiguous (W/m² or lux). Code comment says "(>100 W/m² or >1000 lux)" but the threshold is the same; if the sensor reports lux, the threshold is way too low. Either normalize the input or branch on units.

- **adaptive/preheat.py:69 ("Counter for optimization: expire old observations every 10 calls")** — Adds non-determinism. After 9 adds with no expiration, the 10th triggers a full scan that can be slow when many bins accumulated. Use a time-since-last-prune instead (e.g. prune if last prune was > 1 day ago).

- **adaptive/preheat.py:170-184** — `_expire_old_observations` mutates a list while iterating its key snapshot — safe pattern but could be replaced with `{k: [obs for obs in v if obs.timestamp >= cutoff] for k, v in self._observations.items()}` for clarity, then drop empty bins.

- **adaptive/preheat.py:285-290** — `statistics.median(rates)` on every call; uses Python sort O(N log N). For up to 20 obs per bin this is fine; for high-update systems the heating-rate-learner does the same. If profiling shows hotspot, switch to `statistics.quantiles` cache.

- **adaptive/humidity_detector.py:204** — `should_pause` returns True in both "paused" and "stabilizing". Document that stabilizing also pauses heating (today only the docstring on line 197 mentions both); callers may assume "stabilizing" means "ramping back up".

- **adaptive/humidity_detector.py:205-220 (`get_time_until_resume`)** — Uses `self._last_timestamp` for elapsed calc but never updates it during stabilizing if no new humidity reading arrives. Time freezes between updates, so the returned "remaining seconds" can hold an inaccurate value indefinitely. Use `dt_util.utcnow()` as fallback for "time elapsed since the recorded stabilization start", not the last sensor sample.

- **adaptive/validation.py:107** — `baseline = self._validation_baseline_overshoot or 0.1` — `0.0` is falsy. A clean baseline of exactly 0 silently becomes 0.1. Use `baseline = self._validation_baseline_overshoot if self._validation_baseline_overshoot is not None else 0.1`.

- **adaptive/validation.py:362-388** — Drift calc divides by `_physics_baseline_kp` directly without checking `> 0`. The `ki`/`kd` paths guard, but `kp` doesn't. If a zero baseline ever gets set, division by zero crashes. The constructor at `validation.py:46-48` initializes to `None`, and the `if self._physics_baseline_kp is None` guard at line 362 covers None but not 0.

- **adaptive/cycle_weight.py:113** — `challenge = base_weight * delta_multiplier * outcome_factor` — outcome factor for UNDERSHOOT is 0.5 (per `const.py`), so a high-difficulty cycle with undershoot still contributes weight ≈ 0.5 to confidence increases when classified as good. But `update_convergence_confidence` already checked `is_good_cycle` (which fails on undershoot above threshold), so this branch can never run with UNDERSHOOT outcome — dead arithmetic. Either prune unreachable code or document.

- **adaptive/auto_apply.py:33-49 (`get_auto_apply_thresholds`)** — Default fallback is `HeatingType.CONVECTOR`. Doc says "or None for default" — but for a `floor_hydronic` zone with a typo'd heating_type, returning convector thresholds is wrong (much shorter cooldowns). Raise on unknown heating_type or at minimum log a WARN.

- **adaptive/floor_physics.py:93** — `isinstance(thickness_mm, (int, float))` is fine but tuple form is older style; `int | float` would be modern but isinstance does not accept PEP 604 unions for runtime checks in older Python. Leave as-is.

- **adaptive/floor_physics.py:97** — `min_thickness, max_thickness = FLOOR_THICKNESS_LIMITS[layer_type]` after the `if layer_type not in ["top_floor", "screed"]: continue` guard above. Good, but a missing key in `FLOOR_THICKNESS_LIMITS` for a valid layer_type raises KeyError. Use `.get(layer_type, (0, 1000))` or add a const-side test.

- **adaptive/persistence.py:39, 211** — `self._data = {"version": 5, "zones": {}}` — version constant `STORAGE_VERSION` exists; use it instead of the magic int 5 for consistency.

- **adaptive/persistence.py:194-213** — `schedule_zone_save` passes `lambda: self._data` as data factory. The lambda captures `self` by reference, so if `self._data` is replaced (e.g. async_load called again before the delayed save fires), the *new* data is saved. Probably correct behavior, but worth a comment.

- **managers/learning_gate.py:155-159, 162-166, 169-175** — Three nearly-identical try/except blocks. Extract a helper `_safe_check(callable, default=False)`.

- **managers/comfort_degradation.py:67-70** — Pluralization "{n} contact sensor pause{'s' if n != 1 else ''}" is correct but ugly. Use a tiny helper or f-string with `:plural` extension via a small util.

## Architectural observations

1. **AdaptiveLearner is god-class.** 1701 lines, 30+ methods, owns confidence tracker + validation + undershoot detector + contribution tracker + heating-rate learner + rule state tracker, plus 20+ backward-compat aliases. The codebase has the right idea (managers as `*Manager` per CLAUDE.md) but the orchestrator itself hasn't been broken up. Consider extracting a `LearningCoordinator` that just composes the various managers and exposes a small public API.

2. **Dead code paths.** `confidence.py:update_convergence_confidence`, `undershoot_detector.check_rate_based_undershoot`, `learning.py:get_previous_pid` (always returns None), `cycle_weight` UNDERSHOOT branch all appear to be unreachable or unwired. Establishing a test that exercises each public method end-to-end would catch this.

3. **Migration story is broken.** `learner_serialization.py` reads format_version `!= 10 → wipe`; comments throughout `learning.py` claim migrations exist ("v7->v8 migration", "v8->v9 migration", "v9->v10 migration") but the code performs none. Either implement real per-version migrations with tests for each prior version, or freeze the schema and bump the storage_version with explicit user-facing breaking-change documentation.

4. **Cross-restart state is inconsistent.** `_heating_cycle_count`/`_cooling_cycle_count` (in ConfidenceTracker) not persisted; `_consecutive_failures` in undershoot detector restored from v10; `_stall_counter` in HeatingRateLearner persisted; `_last_adjustment_time` on AdaptiveLearner persisted; `last_adjustment_time` on UndershootDetector serialized but never restored. The picture of "what survives a restart" is fragmented. Audit and make it uniform.

5. **Mode-awareness is partial.** Cycle history, confidence, auto-apply count all have heat/cool variants — but undershoot detector is heating-only (`learning.py:1418-1422` early-returns for cool mode), heating-rate learner has no mode separation, and the contribution tracker's `_heating_rate_contribution` is mode-less. Mixed cooling-heating zones will share the same learner state across modes, which can cross-contaminate.

6. **Cumulative caps not coordinated.** Three separate caps exist:
   - `MAX_UNDERSHOOT_KI_MULTIPLIER` (in undershoot detector, cumulative)
   - `MAX_CUMULATIVE_DRIFT_PCT` (in validation, vs physics baseline)
   - `MAINTENANCE_CONFIDENCE_CAP` (in contribution tracker)
   Each enforced independently, but the user-facing question is "did learning go too far?" — one consolidated `LearningHealthMonitor` could aggregate and produce a single health score.

7. **Magic numbers proliferate.** `0.8` (floor scaling approximation, `learning.py:1104, 1155, 1181`), `0.5` (penalty multiplier, `learning.py:1208, 1473`), `0.4` (`tier1_base`, `learning.py:1103, 1154, 1180`) — all should be derived from `HEATING_TYPE_CONFIDENCE_SCALE`/`CONFIDENCE_TIER_*` constants or imported from them, not duplicated.

8. **Time handling.** Mix of `time.monotonic()` (undershoot cooldown), `dt_util.utcnow()` (most places), `datetime.fromisoformat` (deserialize) all correct individually, but the cross-restart bridging between monotonic and wall-clock is a recurring source of bugs (see Critical/High for the `last_adjustment_time` serialization mismatch). Pick one wall-clock source for anything that crosses persistence boundaries.

9. **Pyright/lint enforcement.** CLAUDE.md mandates `pyright strict on source`. Some `HVACMode = None` defaults (e.g. `learning.py:352`) use a TYPE_CHECKING-only symbol at runtime via `__future__ annotations`. Pyright strict will complain or silently accept depending on settings — verify the configuration covers these.

10. **CLAUDE.md doc drift.** Documented behaviors that diverge from code: (a) "Ki boost capped at 2.0x cumulative" vs `MAX_UNDERSHOOT_KI_MULTIPLIER = 3.0`. (b) "Open-window detection uses Danfoss Ally algorithm" but the `OpenWindowDetector` module doesn't exist in this tree. (c) "Persistence v10 format; backward compat matters" vs serialization wiping unknown versions. Audit CLAUDE.md against the code and either bring code into line or update the doc.
