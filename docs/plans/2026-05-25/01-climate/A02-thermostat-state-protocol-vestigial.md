# Architectural 02: ThermostatState Protocol is vestigial

**File:** `custom_components/adaptive_climate/protocols.py`, callers across `climate_init.py`, `climate_control.py`, `managers/*`

**Problem:** Protocol exists but callers bypass it via lambda closures and `_*` reach-through.

**Fix:**
1. Decision: commit to Protocol OR remove indirection.
2. If commit: ban `_*` cross-module access; route every manager method through typed Protocol facade.
3. If remove: delete protocols.py, pass `self` directly with concrete type.
4. Recommend commit; document in CLAUDE.md.

**Test:** Pyright strict; grep zero `manager._privatefield` from non-manager modules.

**Risk:** High — touches every manager.

**Depends on:** H02.

**Blocks:** A03, 02-pid/A-related, 04-learning/A-related.

**Unresolved:** Commit or remove? (per E in summary).
