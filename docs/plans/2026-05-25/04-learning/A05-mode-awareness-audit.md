# Architectural 05: Mode-awareness audit across learners/trackers

**File:** undershoot_detector, heating_rate_learner, confidence_contribution

**Problem:** Mixed mode-aware / mode-less state; cooling/heating cross-contamination.

**Fix:**
1. Document per-manager: "supports mode X" or "shared".
2. For shared with risk: split into per-mode instances or add explicit assert at module boundary.
3. UndershootDetector: decide single-mode policy or add cooling variant.
4. HeatingRateLearner: rename CoolingRateLearner symmetry or restrict to heating.

**Test:** Unit: cooling activity doesn't pollute heating state.

**Risk:** Med.

**Depends on:** A01.

**Blocks:** none.

**Unresolved:** Cool undershoot detection desired? hvac-expert.
