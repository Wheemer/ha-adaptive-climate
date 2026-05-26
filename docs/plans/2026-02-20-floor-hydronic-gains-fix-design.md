# Floor Hydronic Physics Init Gains Fix

**Date:** 2026-02-20
**Status:** Approved

## Problem

Floor hydronic zones with night setback persistently undershoot by 0.3–0.5°C. Root cause: physics init produces insufficient Ki and Ke for P-on-M systems where the integral is the sole steady-state mechanism.

**gf zone data** (tau≈2.0, outdoor≈2°C, target=20.5°C):
- Needs ~25% output, achieves ~15%
- E-term: Ke=0.22 × 18.5 = 4.1% (only 16% of needed)
- I-term: Ki=2.29 × 0.3 error × 11h daytime = 7.6%
- Night setback (13h) destroys integral nightly → rebuilds from 0 each morning
- Undershoot detector correctly boosted Ki to 2x — validated the deficit

## Changes

### 1. Increase floor_hydronic Ki reference profile (+60%)

File: `adaptive/physics.py`, `reference_profiles[FLOOR_HYDRONIC]`

| tau | Old Ki | New Ki |
|-----|--------|--------|
| 2.0 | 2.0    | 3.2    |
| 4.0 | 1.2    | 1.9    |
| 6.0 | 0.8    | 1.3    |
| 8.0 | 0.6    | 1.0    |

Rationale: P-on-M means integral carries entire steady-state load. Floor systems need faster accumulation because night setback/perturbations reset integral frequently.

### 2. Increase floor_hydronic Ke heating_type_factor (1.2 → 2.0)

File: `adaptive/physics.py`, `calculate_initial_ke()`, `heating_type_factors`

Rationale: Slow systems need the E-term (feedforward) to carry more of the outdoor-dependent steady-state load. Reduces integral burden from ~85% to ~65% of total output.

### 3. Add supply_temperature scaling to Ke calculation

File: `adaptive/physics.py`, `calculate_initial_ke()`

Lower supply temp = less thermal capacity per cycle = needs higher Ke. Uses same reference temps as PID power scaling (e.g., floor_hydronic ref=45°C). At supply=35°C: factor = 25/15 = 1.67.

### 4. Increase MAX_UNDERSHOOT_KI_MULTIPLIER (2.0 → 3.0)

File: `const.py`, line 941

Rationale: More headroom for zones that need even more Ki after the higher init. Safety net for extreme conditions (very cold, poor insulation, undersized system).

## Impact

- **New installations only** for changes 1 & 2 (physics init runs once at setup)
- **All installations** for change 3 (runtime cap)
- Existing zones keep learned gains — no disruption
- Undershoot detector still triggers from the higher baseline if needed

## Risk

- **Low** — Ki increase matches what undershoot detector converges to
- **Kp unchanged** — no oscillation risk
- **Ke increase is conservative** — 2.0x factor still produces moderate Ke values (0.30–0.66 depending on energy rating)
